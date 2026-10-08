"""Stage graph snapshots for object storage, and sync them from object storage into the database.

catalog_snapshots.lock (repository root) pins every file of every snapshot by object key and sha256:

    {"prefix": "catalog-snapshots",
     "snapshots": {"<graph snapshot id>": {"<file>": {"key": "...", "sha256": "...", "bytes": 123}}}}

Files are stored as built, uncompressed: the CSV tables, nodes.jsonl / edges.jsonl and the JSON metadata.

stage   verifies one built snapshot directory, copies its files to <out>/<prefix>/<id>/ for upload and writes
        its lock entry.
sync    for each locked snapshot that is not yet a published baseline: download, check sha256, then seed the
        ERP configurations and load the baseline. Already loaded snapshots are not downloaded.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from catalog_loader import load
from catalog_loader.graph import snapshot as gs

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "catalog_snapshots.lock"
SEED_DIR = ROOT / "seed" / "erp_configs"
PREFIX = "catalog-snapshots"
ENV = ("S3_ENDPOINT", "S3_ACCESS_KEY", "S3_SECRET_KEY", "S3_BUCKET")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_lock(path: Path = LOCK) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"prefix": PREFIX, "snapshots": {}}


def write_lock(lock: dict[str, Any], path: Path = LOCK) -> None:
    path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- stage
def stage(snapshot_dir: Path, out: Path, lock_path: Path = LOCK) -> dict[str, Any]:
    """Copy <snapshot dir>/* to <out>/<prefix>/<snapshot id>/ and write the snapshot's lock entry."""
    src = Path(snapshot_dir)
    sid = gs.read_manifest(src)["snapshot_id"]
    problems = gs.verify(src)
    if problems:
        raise load.LoaderError(f"{sid} does not verify: {'; '.join(problems)}")
    lock = read_lock(lock_path)
    prefix = lock.get("prefix", PREFIX)
    dest = Path(out) / prefix / sid
    dest.mkdir(parents=True, exist_ok=True)
    entry = {}
    for name in sorted(p.name for p in src.iterdir() if p.is_file()):
        data = (src / name).read_bytes()
        shutil.copyfile(src / name, dest / name)
        entry[name] = {"key": f"{prefix}/{sid}/{name}", "sha256": _sha256(data), "bytes": len(data)}
    lock.setdefault("snapshots", {})[sid] = entry
    lock["prefix"] = prefix
    write_lock(lock, lock_path)
    return {"snapshot_id": sid, "files": len(entry), "bytes": sum(f["bytes"] for f in entry.values())}


# --------------------------------------------------------------------------- sync
def _s3_fetch():
    missing = [k for k in ENV if not os.environ.get(k)]
    if missing:
        raise load.LoaderError(f"missing environment variables: {', '.join(missing)}")
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=os.environ.get("S3_REGION") or "auto",
        # R2 rejects the CRC checksums newer botocore sends by default.
        config=Config(signature_version="s3v4", request_checksum_calculation="when_required",
                      response_checksum_validation="when_required"),
    )
    bucket = os.environ["S3_BUCKET"]
    return lambda key: client.get_object(Bucket=bucket, Key=key)["Body"].read()


def _dir_fetch(root: Path):
    return lambda key: (Path(root) / key).read_bytes()


def download(sid: str, entry: dict[str, Any], fetch, store: Path) -> Path:
    """Fetch, check sha256 against the lock, write into <store>/snapshots/<sid>/."""
    d = gs.snapshots_dir(store) / sid
    d.mkdir(parents=True, exist_ok=True)
    for name, f in sorted(entry.items()):
        data = fetch(f["key"])
        if _sha256(data) != f["sha256"]:
            raise load.LoaderError(f"{f['key']}: sha256 does not match catalog_snapshots.lock")
        (d / name).write_bytes(data)
    return d


def sync(session: Session, *, lock_path: Path = LOCK, source_dir: Path | None = None,
         seed_dir: Path = SEED_DIR) -> list[str]:
    """Seed every ERP configuration, then load every locked snapshot that is not yet loaded."""
    report = [load.seed_erp_config(session, load.read_config_file(str(p))) for p in sorted(seed_dir.glob("*.json"))]
    snapshots = read_lock(lock_path).get("snapshots", {})
    pending = [sid for sid in sorted(snapshots) if not load.baseline_loaded(session, sid)]
    report += [f"{sid}: already loaded" for sid in sorted(set(snapshots) - set(pending))]
    if not pending:
        return report
    fetch = _dir_fetch(source_dir) if source_dir else _s3_fetch()
    with tempfile.TemporaryDirectory() as store:
        for sid in pending:
            download(sid, snapshots[sid], fetch, Path(store))
            result = load.load_baseline(session, Path(store), sid)
            report.append(f"{sid}: {result['status']} ({result['counts']})")
    return report
