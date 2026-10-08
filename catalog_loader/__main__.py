"""Catalogue loader.

  python -m catalog_loader seed-erp-config --database-url URL seed/erp_configs/odoo.json
  python -m catalog_loader load-baseline --database-url URL --store ARTIFACTS --snapshot GRAPH_SNAPSHOT_ID
      [--source csv|jsonl]   (default csv: the snapshot's relational CSV tables; the JSONL files are not needed)

Order per environment: migrate the database (coa-db-models), seed each ERP configuration,
then load each baseline. Both commands are idempotent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from catalog_loader import load


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
    a = p.parse_args(argv)

    engine = create_engine(a.database_url.replace("+asyncpg", "+psycopg"))
    with Session(engine) as session:
        try:
            if a.command == "seed-erp-config":
                print(load.seed_erp_config(session, load.read_config_file(a.file)))  # noqa: T201
            else:
                print(json.dumps(load.load_baseline(session, Path(a.store), a.snapshot, a.source), indent=2))  # noqa: T201
        except load.LoaderError as exc:
            print(f"error: {exc}", file=sys.stderr)  # noqa: T201
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
