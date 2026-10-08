"""Snapshot read and verify, copied from erp_schema_graph.snapshot at commit e6ca536 (build and publish omitted).

Snapshot identity is content-addressed: the snapshot id is derived from the identity block, whose
content_sha256 is the hash of nodes.jsonl + edges.jsonl. The CSV tables rebuild those files byte for byte,
so a snapshot shipped with only its CSV tables still verifies.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import contract as c
from .diagnostics import DiagnosticCollector
from .tables import TABLES, TableError, read_tables


def canonical_hash(payload: Any) -> str:
    """Copied from erp_schema_graph.pipeline_store: default separators, unlike dumps()."""
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def jsonl(records: list[dict[str, Any]]) -> bytes:
    return "".join(dumps(r) + "\n" for r in records).encode("utf-8")


def pretty(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()



def snapshots_dir(store: Path) -> Path:
    return Path(store) / "snapshots"


def read_manifest(snapshot_dir: Path) -> dict[str, Any]:
    return json.loads((Path(snapshot_dir) / "manifest.json").read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]


def load_records(snapshot_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Nodes and edges from the JSONL files, or rebuilt from the CSV tables when the JSONL is not shipped."""
    d = Path(snapshot_dir)
    if (d / "nodes.jsonl").is_file() and (d / "edges.jsonl").is_file():
        return read_jsonl(d / "nodes.jsonl"), read_jsonl(d / "edges.jsonl")
    return read_tables({name: (d / name).read_bytes() for name in TABLES})


def verify(snapshot_dir: Path) -> list[str]:
    """Re-check file hashes, content identity and the contract. Empty list = valid.

    The JSONL files may be absent when the CSV tables are present: their
    manifest hashes are then checked against the JSONL rebuilt from the CSVs."""
    d = Path(snapshot_dir)
    problems = []
    try:
        manifest = read_manifest(d)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest unreadable: {exc}"]
    files = manifest["files"]
    csv_only = all(name in files for name in TABLES) and not (d / "nodes.jsonl").is_file() \
        and not (d / "edges.jsonl").is_file()
    for name, digest in files.items():
        path = d / name
        if csv_only and name in ("nodes.jsonl", "edges.jsonl"):
            continue
        if not path.is_file() or sha256(path.read_bytes()) != digest:
            problems.append(f"{name}: hash mismatch or missing")
    if problems:
        return problems
    if all(name in files for name in TABLES):
        try:
            rn, re_ = read_tables({name: (d / name).read_bytes() for name in TABLES})
        except (TableError, ValueError) as exc:
            return [f"CSV tables unreadable: {exc}"]
        if sha256(jsonl(rn)) != files["nodes.jsonl"] or sha256(jsonl(re_)) != files["edges.jsonl"]:
            problems.append("CSV tables do not rebuild nodes.jsonl and edges.jsonl")
    if csv_only:
        nodes_b, edges_b = jsonl(rn), jsonl(re_)
    else:
        nodes_b, edges_b = (d / "nodes.jsonl").read_bytes(), (d / "edges.jsonl").read_bytes()
    identity = manifest["identity"]
    if sha256(nodes_b + b"\0" + edges_b) != identity["content_sha256"]:
        problems.append("content_sha256 mismatch")
    expected_id = f"{identity['erp']}-{identity['erp_version']}-{canonical_hash(identity)[:20]}"
    if expected_id != manifest["snapshot_id"] or d.name != manifest["snapshot_id"]:
        problems.append(f"snapshot id mismatch: expected {expected_id}")
    diag = DiagnosticCollector()
    nodes, edges = read_jsonl_bytes(nodes_b), read_jsonl_bytes(edges_b)
    vn, ve = c.validate(nodes, edges, identity["erp"], diag)
    if len(vn) != len(nodes) or len(ve) != len(edges):
        problems.append(f"contract violations: {diag.counts()}")
    return problems

