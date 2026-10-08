"""Database side of the loader: seed ERP configurations and load baseline graph snapshots.

Synchronous SQLAlchemy over psycopg, using the coa_db_models table classes. Every
command is idempotent: re-running it with the same input changes nothing.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from coa_db_models import (
    CatalogErpConfig,
    CatalogFieldGroup,
    CatalogScopeRoute,
    CatalogSnapshot,
    OutboxEvent,
    SchemaField,
    SchemaModel,
)
from coa_db_models.pipeline.models import _VALID_SCOPES
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from catalog_loader import projection

SUBJECT_PUBLISHED = "catalog.event.snapshot_published"
ERP_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SCOPES = set(re.findall(r"'([a-z_]+)'", _VALID_SCOPES))
ROLES = {"primary", "child", "reference"}
SETTINGS = ("authority_interface", "discovery_interface", "custom_prefixes", "discovery_type_families", "products")
GROUP_KEYS = ("group_key", "modules", "names", "relations")
ROUTE_KEYS = ("scope", "model", "role", "route_key", "subtype_routing", "filters", "child_paths",
              "exclude_field_groups", "optional_field_groups", "account_specific", "identifier_fields")
_BATCH = 1000


class LoaderError(Exception):
    pass


# --------------------------------------------------------------------------- ERP configuration
def _normalise(doc: dict) -> dict:
    """Comparable content of a configuration: settings, groups and routes (notes excluded)."""
    groups = sorted(
        ({k: g.get(k) or ([] if k != "group_key" else None) for k in GROUP_KEYS} for g in doc["field_groups"]),
        key=lambda g: g["group_key"],
    )
    routes = []
    for r in doc["scope_routes"]:
        row = {k: r.get(k) for k in ROUTE_KEYS}
        row["route_key"] = str(row["route_key"] or "default")
        row["account_specific"] = bool(row["account_specific"])
        for k in ("filters", "child_paths", "exclude_field_groups", "optional_field_groups", "identifier_fields"):
            row[k] = row[k] or []
        row["subtype_routing"] = row["subtype_routing"] or {}
        routes.append(row)
    routes.sort(key=lambda r: (r["scope"], r["model"], r["route_key"]))
    settings = {k: doc.get(k) for k in SETTINGS}
    settings["custom_prefixes"] = settings["custom_prefixes"] or {}
    settings["discovery_type_families"] = settings["discovery_type_families"] or {}
    settings["products"] = settings["products"] or {}
    return {"settings": settings, "field_groups": groups, "scope_routes": routes}


def validate_config(doc: dict) -> list[str]:
    problems = []
    erp = doc.get("erp")
    if not isinstance(erp, str) or not ERP_ID_RE.fullmatch(erp):
        problems.append(f"erp {erp!r} must match {ERP_ID_RE.pattern}")
    if not doc.get("authority_interface"):
        problems.append("authority_interface is required")
    products = doc.get("products") or {}
    if not isinstance(products, dict) or not all(
        isinstance(k, str) and k and isinstance(v, str) and v for k, v in products.items()
    ):
        problems.append("products must map ERP product ids to baseline editions, e.g. {\"odoo\": \"community\"}")
    keys = [g.get("group_key") for g in doc.get("field_groups") or []]
    if len(keys) != len(set(keys)) or not all(keys):
        problems.append("field group keys must be present and unique")
    seen = set()
    for r in doc.get("scope_routes") or []:
        name = f"{r.get('scope')}/{r.get('model')}"
        if r.get("scope") not in SCOPES:
            problems.append(f"{name}: scope not in {sorted(SCOPES)}")
        if r.get("role") not in ROLES:
            problems.append(f"{name}: role {r.get('role')!r} not in {sorted(ROLES)}")
        unknown = set(r.get("exclude_field_groups") or []) | set(r.get("optional_field_groups") or [])
        if unknown - set(keys):
            problems.append(f"{name}: unknown field groups {sorted(unknown - set(keys))}")
        idf = r.get("identifier_fields") or []
        if not isinstance(idf, list) or not all(isinstance(f, str) and f for f in idf) or len(idf) != len(set(idf)):
            problems.append(f"{name}: identifier_fields must be a list of distinct field names")
        ident = (r.get("scope"), r.get("model"), str(r.get("route_key") or "default"))
        if ident in seen:
            problems.append(f"{name}: duplicate route {ident[2]!r}")
        seen.add(ident)
    return problems


def _active_content(session: Session, cfg: CatalogErpConfig) -> dict:
    groups = session.execute(select(CatalogFieldGroup).where(CatalogFieldGroup.config_id == cfg.id)).scalars()
    routes = session.execute(select(CatalogScopeRoute).where(CatalogScopeRoute.config_id == cfg.id)).scalars()
    return _normalise({
        **{k: getattr(cfg, k) for k in SETTINGS},
        "field_groups": [{k: getattr(g, k) for k in GROUP_KEYS} for g in groups],
        "scope_routes": [{k: getattr(r, k) for k in ROUTE_KEYS} for r in routes],
    })


def active_config(session: Session, erp: str) -> CatalogErpConfig | None:
    return session.execute(
        select(CatalogErpConfig).where(CatalogErpConfig.erp == erp, CatalogErpConfig.status == "active")
    ).scalar_one_or_none()


def seed_erp_config(session: Session, doc: dict) -> str:
    """Create and activate a new configuration version, retiring the active one. One transaction."""
    problems = validate_config(doc)
    if problems:
        raise LoaderError("invalid ERP configuration: " + "; ".join(problems))
    erp, wanted = doc["erp"], _normalise(doc)
    current = active_config(session, erp)
    if current is not None and _active_content(session, current) == wanted:
        return f"{erp}: active version {current.version} already has this content; nothing changed"
    version = (session.execute(
        select(func.max(CatalogErpConfig.version)).where(CatalogErpConfig.erp == erp)
    ).scalar() or 0) + 1
    cfg = CatalogErpConfig(erp=erp, version=version, notes=doc.get("notes"), **wanted["settings"])
    session.add(cfg)
    session.flush()
    session.add_all(CatalogFieldGroup(config_id=cfg.id, **g) for g in wanted["field_groups"])
    by_ident = {(r["scope"], r["model"], str(r.get("route_key") or "default")): r for r in doc["scope_routes"]}
    session.add_all(
        CatalogScopeRoute(config_id=cfg.id, notes=by_ident[(r["scope"], r["model"], r["route_key"])].get("notes"), **r)
        for r in wanted["scope_routes"]
    )
    session.flush()
    if current is not None:
        session.execute(update(CatalogErpConfig).where(CatalogErpConfig.id == current.id).values(status="retired"))
    session.execute(
        update(CatalogErpConfig).where(CatalogErpConfig.id == cfg.id)
        .values(status="active", activated_at=datetime.now(UTC))
    )
    session.commit()
    retired = f", retired version {current.version}" if current is not None else ""
    return (f"{erp}: activated version {version} ({len(wanted['field_groups'])} field groups, "
            f"{len(wanted['scope_routes'])} scope routes){retired}")


# --------------------------------------------------------------------------- baseline load
def compare_hashes(old: dict[str, str], new: dict[str, str]) -> dict[str, Any]:
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    changed = sorted(k for k in old.keys() & new.keys() if old[k] != new[k])
    return {
        "counts": {"added": len(added), "removed": len(removed), "changed": len(changed),
                   "unchanged": len(old.keys() & new.keys()) - len(changed)},
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def _hashes(session: Session, snapshot_id: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for table in (SchemaModel, SchemaField):
        out.update(dict(session.execute(
            select(table.logical_id, table.content_sha256).where(table.snapshot_id == snapshot_id)
        ).all()))
    return out


def _fail(session: Session, snapshot_id: Any, message: str, problems: list[str] | None = None) -> None:
    session.rollback()
    session.execute(delete(SchemaField).where(SchemaField.snapshot_id == snapshot_id))
    session.execute(delete(SchemaModel).where(SchemaModel.snapshot_id == snapshot_id))
    session.execute(update(CatalogSnapshot).where(CatalogSnapshot.id == snapshot_id).values(
        status="failed", error_detail=message[:4000], diagnostics={"problems": (problems or [])[:500]}
    ))
    session.commit()


def baseline_identity(graph_snapshot_id: str) -> str:
    return projection.canonical_hash({
        "kind": "baseline",
        "catalog_contract": projection.CATALOG_CONTRACT_VERSION,
        "graph_snapshot_id": graph_snapshot_id,
    })


def baseline_loaded(session: Session, graph_snapshot_id: str) -> bool:
    """True when this graph snapshot is already a validated or published baseline (a load would write nothing)."""
    status = session.execute(
        select(CatalogSnapshot.status).where(CatalogSnapshot.identity_sha256 == baseline_identity(graph_snapshot_id))
    ).scalars().all()
    return any(s in ("validated", "published") for s in status)


def load_baseline(session: Session, store: Path, graph_snapshot_id: str, source: str = "csv") -> dict[str, Any]:
    """Load one global graph snapshot as a shared (org_id NULL) published baseline."""
    started = time.monotonic()
    try:
        manifest = projection.read_manifest(store, graph_snapshot_id)
    except projection.CatalogValidationError as exc:
        raise LoaderError(str(exc)) from exc
    if manifest.get("account_scope"):
        raise LoaderError(
            f"graph {graph_snapshot_id} is account-scoped ({manifest['account_scope']!r}); only global graphs are "
            "loaded as shared baselines. Customer-specific content arrives through account overlays."
        )
    if not projection.contract_supported(manifest.get("graph_contract_version")):
        raise LoaderError(f"graph contract {manifest.get('graph_contract_version')} is not supported")
    erp = manifest.get("erp")
    cfg = active_config(session, str(erp))
    if cfg is None:
        raise LoaderError(f"ERP {erp!r} has no active catalogue configuration; run seed-erp-config first")
    prefixes = dict(cfg.custom_prefixes or {})

    identity = baseline_identity(graph_snapshot_id)
    row = session.execute(
        select(CatalogSnapshot).where(CatalogSnapshot.identity_sha256 == identity, CatalogSnapshot.status != "failed")
    ).scalar_one_or_none()
    if row is not None and row.status in ("validated", "published"):
        return {"snapshot_id": str(row.id), "status": row.status, "created": False, "counts": row.counts}
    version, edition = manifest["erp_version"], manifest.get("erp_edition")
    if row is None:
        row = CatalogSnapshot(
            org_id=None,
            kind="baseline",
            scope_level="global",
            erp=erp,
            erp_version=version,
            erp_edition=edition,
            catalog_contract_version=projection.CATALOG_CONTRACT_VERSION,
            projection_version=projection.PROJECTION_VERSION,
            graph_contract_version=manifest["graph_contract_version"],
            graph_snapshot_id=graph_snapshot_id,
            lineage_key=f"baseline:{erp}:{version}:{edition}:global",
            identity_sha256=identity,
            manifest={
                "graph_identity": manifest.get("identity"),
                "graph_package": manifest.get("package"),
                "graph_parent_snapshot_id": manifest.get("parent_snapshot_id"),
                "graph_timestamps": manifest.get("timestamps"),
                "erp_config": {"id": str(cfg.id), "version": cfg.version},
            },
        )
        session.add(row)
        session.commit()  # staging row: an interrupted load resumes from here
    snapshot_id, lineage_key, base_manifest = row.id, row.lineage_key, dict(row.manifest)

    try:
        baseline = projection.load_baseline(store, graph_snapshot_id, None, prefixes, source)
    except projection.CatalogValidationError as exc:
        _fail(session, snapshot_id, f"validation failed: {exc}", exc.problems)
        raise LoaderError(f"validation failed; snapshot {snapshot_id} marked failed: {exc}") from exc

    # Content, validation, publication and the outbox event commit together.
    session.execute(delete(SchemaField).where(SchemaField.snapshot_id == snapshot_id))
    session.execute(delete(SchemaModel).where(SchemaModel.snapshot_id == snapshot_id))
    for table, rows in ((SchemaModel, baseline.models), (SchemaField, baseline.fields)):
        for i in range(0, len(rows), _BATCH):
            session.execute(insert(table), [{**r, "snapshot_id": snapshot_id} for r in rows[i : i + _BATCH]])
    session.execute(update(CatalogSnapshot).where(CatalogSnapshot.id == snapshot_id).values(
        status="validated",
        validated_at=datetime.now(UTC),
        content_sha256=baseline.content_sha256,
        completeness={"graph": baseline.completeness, "warnings": baseline.warnings},
        diagnostics={"graph_build": baseline.graph_diagnostics},
        counts=baseline.counts,
        manifest={
            **base_manifest,
            "graph_package_consumer": projection.graph_package_provenance(baseline.manifest),
            "graph_pipeline": baseline.manifest.get("pipeline"),
            "graph_source": source,  # csv: loaded from the snapshot's relational CSV tables
        },
    ))
    previous = session.execute(
        select(CatalogSnapshot)
        .where(CatalogSnapshot.org_id.is_(None), CatalogSnapshot.lineage_key == lineage_key,
               CatalogSnapshot.status == "published")
        .order_by(CatalogSnapshot.published_at.desc()).limit(1)
    ).scalar_one_or_none()
    report = None
    if previous is not None:
        report = compare_hashes(_hashes(session, previous.id), _hashes(session, snapshot_id))
        report["previous_snapshot_id"] = str(previous.id)
    session.execute(update(CatalogSnapshot).where(CatalogSnapshot.id == snapshot_id).values(
        status="published", published_at=datetime.now(UTC),
        previous_snapshot_id=previous.id if previous else None, change_report=report,
    ))
    session.execute(
        pg_insert(OutboxEvent).values(
            subject=SUBJECT_PUBLISHED,
            aggregate_type="catalog_snapshot",
            aggregate_id=snapshot_id,
            dedup_key=f"{SUBJECT_PUBLISHED}:{snapshot_id}",
            payload={
                "snapshot_id": str(snapshot_id),
                "org_id": None,
                "erp": erp,
                "kind": "baseline",
                "content_sha256": baseline.content_sha256,
                "previous_snapshot_id": str(previous.id) if previous else None,
                "changed_logical_ids": (report["added"] + report["changed"]) if report else None,
            },
        ).on_conflict_do_nothing(index_elements=["dedup_key"])
    )
    session.commit()
    return {
        "snapshot_id": str(snapshot_id),
        "status": "published",
        "created": True,
        "counts": baseline.counts,
        "previous_snapshot_id": str(previous.id) if previous else None,
        "change_counts": report["counts"] if report else None,
        "warnings": baseline.warnings,
        "seconds": round(time.monotonic() - started, 1),
    }


def read_config_file(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
