"""stage -> object storage layout -> download, without a database or network (a local directory stands in for R2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import graph_fixtures as gf
from catalog_loader import load, sync
from catalog_loader.graph import snapshot as gs


def _staged(tmp_path: Path) -> tuple[str, Path, Path]:
    nodes, edges = gf.odoo_graph()
    sid = gf.publish_graph(tmp_path / "built", "odoo", nodes, edges)
    lock = tmp_path / "catalog_snapshots.lock"
    sync.stage(gs.snapshots_dir(tmp_path / "built") / sid, tmp_path / "staged", lock)
    return sid, tmp_path / "staged", lock


def test_stage_ships_no_jsonl_and_is_reproducible(tmp_path: Path) -> None:
    sid, staged, lock = _staged(tmp_path)
    entry = json.loads(lock.read_text())["snapshots"][sid]
    assert "nodes.jsonl.gz" not in entry and "edges.jsonl.gz" not in entry
    assert {"fields.csv.gz", "tables.json.gz", "manifest.json.gz"} <= set(entry)
    assert all(f["key"] == f"catalog-snapshots/{sid}/{name}" for name, f in entry.items())
    again = tmp_path / "again.lock"
    sync.stage(gs.snapshots_dir(tmp_path / "built") / sid, tmp_path / "staged2", again)
    assert json.loads(again.read_text())["snapshots"][sid] == entry


def test_download_verifies_and_rejects_a_changed_file(tmp_path: Path) -> None:
    sid, staged, lock = _staged(tmp_path)
    entry = json.loads(lock.read_text())["snapshots"][sid]
    d = sync.download(sid, entry, sync._dir_fetch(staged), tmp_path / "store")
    assert gs.verify(d) == []
    (staged / entry["fields.csv.gz"]["key"]).write_bytes(b"tampered")
    with pytest.raises(load.LoaderError, match="sha256"):
        sync.download(sid, entry, sync._dir_fetch(staged), tmp_path / "store2")
