"""Catalogue loader.

  python -m catalog_loader seed-erp-config --database-url URL seed/erp_configs/odoo.json
  python -m catalog_loader load-baseline --database-url URL --store ARTIFACTS --snapshot GRAPH_SNAPSHOT_ID
      [--source csv|jsonl]   (default csv: the snapshot's relational CSV tables; the JSONL files are not needed)

  python -m catalog_loader stage SNAPSHOT_DIR [--out staged]
  python -m catalog_loader sync [--database-url URL] [--source-dir DIR]
      (reads catalog_snapshots.lock; downloads from CATALOG_S3_* object storage unless --source-dir is given)

Order per environment: migrate the database (alembic upgrade head), then sync, which seeds each ERP
configuration and loads each locked baseline that is not yet loaded. Every command is idempotent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from catalog_loader import load, sync


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="catalog_loader", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    seed = sub.add_parser("seed-erp-config", help="create and activate an ERP configuration version")
    seed.add_argument("--database-url", required=True)
    seed.add_argument("file", help="ERP configuration JSON")
    base = sub.add_parser("load-baseline", help="load a global graph snapshot as a shared baseline")
    base.add_argument("--database-url", required=True)
    base.add_argument("--store", required=True, help="erp-schema-graph artifacts directory (contains snapshots/)")
    base.add_argument("--snapshot", required=True, help="graph snapshot id, e.g. odoo-18.0-3c92dbec93d9b412af1c")
    base.add_argument("--source", choices=["csv", "jsonl"], default="csv",
                      help="read the snapshot's CSV tables (default) or its JSONL files")
    stg = sub.add_parser("stage", help="gzip a built snapshot for upload and add it to catalog_snapshots.lock")
    stg.add_argument("snapshot_dir", help="built snapshot directory, e.g. artifacts/snapshots/<id>")
    stg.add_argument("--out", default="staged", help="output directory to upload (default: staged)")
    syn = sub.add_parser("sync", help="seed ERP configurations and load every locked baseline not yet loaded")
    syn.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    syn.add_argument("--source-dir", type=Path, help="read staged files from this directory instead of object storage")
    a = p.parse_args(argv)

    if a.command == "stage":
        try:
            print(json.dumps(sync.stage(Path(a.snapshot_dir), Path(a.out)), indent=2))  # noqa: T201
        except load.LoaderError as exc:
            print(f"error: {exc}", file=sys.stderr)  # noqa: T201
            return 1
        return 0
    if not a.database_url:
        p.error("--database-url or DATABASE_URL is required")
    engine = create_engine(a.database_url.replace("+asyncpg", "+psycopg"))
    with Session(engine) as session:
        try:
            if a.command == "seed-erp-config":
                print(load.seed_erp_config(session, load.read_config_file(a.file)))  # noqa: T201
            elif a.command == "sync":
                print("\n".join(sync.sync(session, source_dir=a.source_dir)))  # noqa: T201
            else:
                print(json.dumps(load.load_baseline(session, Path(a.store), a.snapshot, a.source), indent=2))  # noqa: T201
        except load.LoaderError as exc:
            print(f"error: {exc}", file=sys.stderr)  # noqa: T201
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
