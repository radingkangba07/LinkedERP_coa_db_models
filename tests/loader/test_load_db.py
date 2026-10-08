"""Loader against a scratch PostgreSQL database (catalog_loader_test), schema from coa_db_models."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import coa_db_models  # noqa: F401  (registers every table)
import pytest
from coa_db_models import CatalogErpConfig, CatalogScopeRoute, CatalogSnapshot, OutboxEvent, SchemaField
from coa_db_models.base import Base
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from catalog_loader import load
import graph_fixtures as gf

SERVER = "postgresql+psycopg://coa_user:coa_pass@localhost:5432"
SEED = Path(__file__).resolve().parents[2] / "seed" / "erp_configs"


@pytest.fixture(scope="module")
def engine():
    try:
        with create_engine(f"{SERVER}/catalog_demo", isolation_level="AUTOCOMMIT").connect() as c:
            c.execute(text("DROP DATABASE IF EXISTS catalog_loader_test WITH (FORCE)"))
            c.execute(text("CREATE DATABASE catalog_loader_test"))
    except OperationalError:
        pytest.skip("local PostgreSQL not available")
    eng = create_engine(f"{SERVER}/catalog_loader_test")
    with eng.begin() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def _odoo_config() -> dict:
    return json.loads((SEED / "odoo.json").read_text())


def test_seed_is_idempotent_and_a_change_makes_a_new_active_version(engine) -> None:
    doc = _odoo_config()
    with Session(engine) as s:
        assert "activated version 1" in load.seed_erp_config(s, doc)
        assert "nothing changed" in load.seed_erp_config(s, doc)
        changed = copy.deepcopy(doc)
        changed["scope_routes"][0]["notes"] = "notes do not count as content"
        assert "nothing changed" in load.seed_erp_config(s, changed)
        changed["field_groups"][0]["names"].append("website_extra_*")
        assert "activated version 2" in load.seed_erp_config(s, changed)
        rows = s.execute(select(CatalogErpConfig.version, CatalogErpConfig.status)
                         .where(CatalogErpConfig.erp == "odoo").order_by(CatalogErpConfig.version)).all()
        assert rows == [(1, "retired"), (2, "active")]
        active = load.active_config(s, "odoo")
        assert s.execute(select(func.count()).select_from(CatalogScopeRoute)
                         .where(CatalogScopeRoute.config_id == active.id)).scalar() == len(doc["scope_routes"])
        # Restore the original content as version 3 for the remaining tests.
        assert "activated version 3" in load.seed_erp_config(s, doc)


def test_invalid_configuration_is_rejected(engine) -> None:
    doc = _odoo_config()
    doc["scope_routes"][0]["optional_field_groups"] = ["no_such_group"]
    doc["scope_routes"][1]["role"] = "owner"
    with Session(engine) as s, pytest.raises(load.LoaderError, match="unknown field groups.*role 'owner'"):
        load.seed_erp_config(s, doc)


def test_baseline_without_active_configuration_is_rejected(engine, tmp_path: Path) -> None:
    nodes, edges = gf.netsuite_graph()
    sid = gf.publish_graph(tmp_path, "netsuite", nodes, edges)
    with Session(engine) as s, pytest.raises(load.LoaderError, match="no active catalogue configuration"):
        load.load_baseline(s, tmp_path, sid)


def test_account_scoped_graph_is_rejected(engine, tmp_path: Path) -> None:
    nodes, edges = gf.odoo_graph()
    sid = gf.publish_graph(tmp_path, "odoo", nodes, edges, account_scope="acme-prod")
    with Session(engine) as s, pytest.raises(load.LoaderError, match="account-scoped"):
        load.load_baseline(s, tmp_path, sid)


def test_baseline_is_shared_published_immutable_idempotent_and_reports_changes(engine, tmp_path: Path) -> None:
    nodes, edges = gf.odoo_graph()
    sid = gf.publish_graph(tmp_path, "odoo", nodes, edges)
    with Session(engine) as s:
        first = load.load_baseline(s, tmp_path, sid)
        assert first["created"] and first["status"] == "published" and first["counts"]["fields"] == 6
        again = load.load_baseline(s, tmp_path, sid)
        assert again == {"snapshot_id": first["snapshot_id"], "status": "published", "created": False,
                         "counts": first["counts"]}
        snap = s.get(CatalogSnapshot, first["snapshot_id"])
        assert snap.org_id is None and snap.kind == "baseline" and snap.previous_snapshot_id is None
        assert s.execute(select(func.count()).select_from(OutboxEvent)
                         .where(OutboxEvent.aggregate_id == snap.id)).scalar() == 1
    with pytest.raises(DBAPIError, match="immutable"), engine.begin() as c:
        c.execute(update(SchemaField).where(SchemaField.snapshot_id == snap.id).values(label="changed"))

    nodes2, edges2 = gf.odoo_graph(extra_label=" (v2)")  # same ERP version: next snapshot of the same lineage
    sid2 = gf.publish_graph(tmp_path, "odoo", nodes2, edges2)
    with Session(engine) as s:
        second = load.load_baseline(s, tmp_path, sid2)
        assert second["previous_snapshot_id"] == first["snapshot_id"]
        assert second["change_counts"] == {"added": 0, "removed": 0, "changed": 1, "unchanged": 8}
        report = s.get(CatalogSnapshot, second["snapshot_id"]).change_report
        assert report["changed"] == ["odoo:field:res.partner:name"]


def test_invalid_graph_marks_the_snapshot_failed_without_rows(engine, tmp_path: Path) -> None:
    nodes, edges = gf.odoo_graph()
    nodes[3]["bindings"][0]["capabilities"]["update"]["basis"] = ""
    sid = gf.publish_graph(tmp_path, "odoo", nodes, edges)
    with Session(engine) as s:
        with pytest.raises(load.LoaderError, match="marked failed"):
            load.load_baseline(s, tmp_path, sid)
        snap = s.execute(select(CatalogSnapshot).where(CatalogSnapshot.graph_snapshot_id == sid)).scalar_one()
        assert snap.status == "failed" and snap.diagnostics["problems"]
        assert s.execute(select(func.count()).select_from(SchemaField)
                         .where(SchemaField.snapshot_id == snap.id)).scalar() == 0
