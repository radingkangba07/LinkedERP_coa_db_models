"""Pure projection logic (moved from the backend catalogue module)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from catalog_loader import projection
import graph_fixtures as gf


def _baseline(
    tmp_path: Path, erp: str = "odoo", prefixes: dict | None = None, source: str = "csv"
) -> projection.Baseline:
    nodes, edges = gf.odoo_graph() if erp == "odoo" else gf.netsuite_graph()
    sid = gf.publish_graph(tmp_path, erp, nodes, edges)
    return projection.load_baseline(tmp_path, sid, None, prefixes, source)


def _writable(path: Path) -> Path:
    os.chmod(path, 0o644)
    return path


def test_projection_keeps_full_definitions_and_every_edge(tmp_path: Path) -> None:
    nodes, edges = gf.odoo_graph()
    b = _baseline(tmp_path)
    assert b.counts == {"models": 3, "fields": 6, "edges": len(edges)}
    rows = {r["logical_id"]: r for r in b.models + b.fields}
    for n in nodes:
        assert projection.canonical_hash(
            {**rows[n["id"]]["definition"], "bindings": rows[n["id"]]["bindings"]}
        ) == projection.canonical_hash(n)
    assert rows["odoo:field:res.partner:legacy_code"]["readonly"] is None  # unknown stays NULL
    assert rows["odoo:field:res.partner:legacy_code"]["conditional_requirements"] is None
    assert rows["odoo:field:res.partner:country_id"]["cardinality"] == "many_to_one"


def test_projection_is_deterministic(tmp_path: Path) -> None:
    assert _baseline(tmp_path).content_sha256 == _baseline(tmp_path).content_sha256


def test_custom_prefixes_come_from_the_erp_configuration(tmp_path: Path) -> None:
    rows = {r["logical_id"]: r for r in _baseline(tmp_path, prefixes={"field": ["leg"]}).fields}
    assert rows["odoo:field:res.partner:legacy_code"]["is_custom"] is True
    assert rows["odoo:field:res.partner:vat"]["is_custom"] is False
    assert not any(r["is_custom"] for r in _baseline(tmp_path).fields)  # no prefixes, nothing custom


def test_tampered_snapshot_is_rejected(tmp_path: Path) -> None:
    nodes, edges = gf.odoo_graph()
    sid = gf.publish_graph(tmp_path, "odoo", nodes, edges)
    d = tmp_path / "snapshots" / sid
    f = _writable(d / "fields.csv")
    f.write_text(f.read_text(encoding="utf-8-sig").replace(",vat,", ",vatx,", 1), encoding="utf-8-sig")
    with pytest.raises(projection.CatalogValidationError, match="fields.csv: hash mismatch"):
        projection.load_baseline(tmp_path, sid, None)
    j = _writable(d / "nodes.jsonl")
    j.write_text(j.read_text().replace('"vat"', '"vatx"', 1))
    with pytest.raises(projection.CatalogValidationError, match="verification failed"):
        projection.load_baseline(tmp_path, sid, None, source="jsonl")


def test_csv_tables_load_the_same_rows_as_the_jsonl_files_and_do_not_need_them(tmp_path: Path) -> None:
    from_jsonl = _baseline(tmp_path, source="jsonl")
    from_csv = _baseline(tmp_path)
    assert from_csv.content_sha256 == from_jsonl.content_sha256 and from_csv.models == from_jsonl.models
    assert from_csv.fields == from_jsonl.fields and from_csv.warnings == []
    sid = next((tmp_path / "snapshots").iterdir()).name
    for name in ("nodes.jsonl", "edges.jsonl"):  # e.g. a copy from GitHub, where the JSONL files are not kept
        _writable(tmp_path / "snapshots" / sid / name).unlink()
    csv_only = projection.load_baseline(tmp_path, sid, None)
    assert csv_only.content_sha256 == from_jsonl.content_sha256 and csv_only.warnings == []
    assert csv_only.counts == from_jsonl.counts


def test_snapshot_without_csv_tables_is_refused_in_csv_mode(tmp_path: Path) -> None:
    nodes, edges = gf.odoo_graph()
    sid = gf.publish_graph(tmp_path, "odoo", nodes, edges)
    m = _writable(tmp_path / "snapshots" / sid / "manifest.json")
    manifest = json.loads(m.read_text())
    manifest["files"].pop("models.csv")
    m.write_text(json.dumps(manifest))
    with pytest.raises(projection.CatalogValidationError, match="has no CSV tables"):
        projection.load_baseline(tmp_path, sid, None)


def test_unknown_contract_major_is_rejected(tmp_path: Path) -> None:
    nodes, edges = gf.odoo_graph()
    sid = gf.publish_graph(tmp_path, "odoo", nodes, edges, contract_version="9.0.0")
    with pytest.raises(projection.CatalogValidationError, match="unsupported"):
        projection.load_baseline(tmp_path, sid, None)


def test_capability_without_basis_is_rejected(tmp_path: Path) -> None:
    nodes, edges = gf.odoo_graph()
    nodes[3]["bindings"][0]["capabilities"]["update"]["basis"] = ""
    sid = gf.publish_graph(tmp_path, "odoo", nodes, edges)
    with pytest.raises(projection.CatalogValidationError):
        projection.load_baseline(tmp_path, sid, None)


def test_path_traversal_snapshot_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(projection.CatalogValidationError, match="invalid graph snapshot id"):
        projection.snapshot_dir(tmp_path, "../../etc")
