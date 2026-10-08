"""Validate a published erp-schema-graph snapshot and project it into catalogue rows.

Pure functions: no database access. The loader calls load_baseline() and
persists the returned rows. Every graph node becomes exactly one row; the
complete node (minus bindings, which get their own column) is kept in
`definition`, and every edge is kept on its from_node's row in `relations`,
so the full graph can be reconstructed from the catalogue (checked by
_check_survival before anything is written).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from catalog_loader import graph
from catalog_loader.graph import CONTRACT_VERSION as GRAPH_CONTRACT_VERSION
from catalog_loader.graph import contract as gc
from catalog_loader.graph import snapshot as gs
from catalog_loader.graph import tables as gt
from catalog_loader.graph.diagnostics import DiagnosticCollector

#: Version of the catalogue row format (schema_models / schema_fields projection).
CATALOG_CONTRACT_VERSION = "1.0.0"
#: Version of this projection code (graph node/edge -> catalogue row rules).
PROJECTION_VERSION = "1.0.0"

SNAPSHOT_ID_RE = re.compile(r"^[a-z][a-z0-9_]*-[A-Za-z0-9._]+-[0-9a-f]{20}$")
TYPE_FAMILIES = {"text", "boolean", "number", "datetime", "enum", "reference", "binary", "complex", "unknown"}


class CatalogValidationError(Exception):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems[:20]))
        self.problems = problems


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def row_hash(definition: dict, bindings: list, relations: list, conflicts: list) -> str:
    # Provenance is excluded: identical facts from a newer discovery keep the same hash,
    # so embedding indexes rebuild only when relevant metadata changes.
    return canonical_hash({"d": definition, "b": bindings, "r": relations, "c": conflicts})


def snapshot_content_hash(models: list[dict], fields: list[dict]) -> str:
    return canonical_hash(sorted((r["logical_id"], r["content_sha256"]) for r in models + fields))


def is_custom(prefixes: dict, model: str, path: str | None = None) -> bool:
    # Prefixes come from the active catalog_erp_configs row: {"model": ["x_"], "field": ["x_"]}.
    return model.startswith(tuple(prefixes.get("model") or [])) or bool(
        path and path.startswith(tuple(prefixes.get("field") or []))
    )


def snapshot_dir(store: Path, graph_snapshot_id: str) -> Path:
    if not SNAPSHOT_ID_RE.fullmatch(graph_snapshot_id):
        raise CatalogValidationError([f"invalid graph snapshot id {graph_snapshot_id!r}"])
    root = Path(gs.snapshots_dir(Path(store))).resolve()
    d = (root / graph_snapshot_id).resolve()
    if d.parent != root or not (d / "manifest.json").is_file():
        raise CatalogValidationError([f"graph snapshot {graph_snapshot_id} not found in store"])
    return d


def read_manifest(store: Path, graph_snapshot_id: str) -> dict[str, Any]:
    return dict(gs.read_manifest(snapshot_dir(store, graph_snapshot_id)))


def contract_supported(version: str | None) -> bool:
    return str(version or "").split(".")[0] == str(GRAPH_CONTRACT_VERSION).split(".")[0]


@dataclass
class Baseline:
    manifest: dict[str, Any]
    completeness: dict[str, Any]
    graph_diagnostics: dict[str, Any]
    models: list[dict[str, Any]]
    fields: list[dict[str, Any]]
    content_sha256: str
    counts: dict[str, int]
    warnings: list[str] = field(default_factory=list)


def _definition(node: dict) -> dict[str, Any]:
    # Keys starting with "_" carry catalogue-side facts (overlay provenance, conflicts), not graph content.
    return {k: v for k, v in node.items() if k != "bindings" and not k.startswith("_")}


def model_row(node: dict, relations: list, prefixes: dict) -> dict[str, Any]:
    definition = _definition(node)
    return {
        "logical_id": node["id"],
        "native_model": node["model"],
        "label": node.get("label"),
        "model_kind": node.get("model_kind"),
        "constraints": node.get("constraints") or {"availability": "missing", "items": []},
        "evidence_status": node["evidence_status"],
        "is_custom": node.get("_is_custom", is_custom(prefixes, node["model"])),
        "definition": definition,
        "bindings": node["bindings"],
        "relations": relations,
        "provenance": node.get("_provenance", {}),
        "conflicts": node.get("_conflicts", []),
        "content_sha256": row_hash(definition, node["bindings"], relations, node.get("_conflicts", [])),
    }


def field_row(node: dict, relations: list, erp: str, prefixes: dict) -> dict[str, Any]:
    definition = _definition(node)
    dt = node.get("data_type") or {}
    conflicts = node.get("_conflicts", [])
    props = node.get("properties") or {}
    ref_edges = [e for e in relations if e["edge_type"] in ("REFERENCES", "COLLECTION_OF") and e.get("cardinality")]
    return {
        "logical_id": node["id"],
        "model_logical_id": gc.model_id(erp, node["model"]),
        "pipeline_ids": node.get("pipeline_ids") or {},
        "cardinality": ref_edges[0]["cardinality"] if ref_edges else None,
        "conditional_requirements": props.get("conditional_requirements"),
        "enum_values": props.get("selection"),
        "kind": node["kind"],
        "owner_logical_id": node["owner"],
        "native_path": node["path"],
        "qualified_path": node["qualified_path"],
        "label": node.get("label"),
        "native_type": dt.get("native"),
        "type_family": dt.get("family") or "unknown",
        "required": gc.tristate(node.get("required")),
        "readonly": gc.tristate(node.get("readonly")),
        "stored": gc.tristate(node.get("stored")),
        "relation": node.get("relation"),
        "evidence_status": node["evidence_status"],
        "is_custom": node.get("_is_custom", is_custom(prefixes, node["model"], node["path"])),
        "definition": definition,
        "bindings": node["bindings"],
        "relations": relations,
        "provenance": node.get("_provenance", {}),
        "conflicts": conflicts,
        "content_sha256": row_hash(definition, node["bindings"], relations, conflicts),
    }


def project(erp: str, nodes: list[dict], edges: list[dict], prefixes: dict) -> tuple[list[dict], list[dict]]:
    outgoing: dict[str, list[dict]] = {}
    for e in edges:
        outgoing.setdefault(e["from_node"], []).append(e)
    models: list[dict] = []
    fields: list[dict] = []
    for n in nodes:
        rel = sorted(outgoing.get(n["id"], []), key=lambda e: e["id"])
        (models if n["kind"] == "model" else fields).append(
            model_row(n, rel, prefixes) if n["kind"] == "model" else field_row(n, rel, erp, prefixes)
        )
    return models, fields


def validate_graph(
    manifest: dict, completeness: dict, nodes: list[dict], edges: list[dict], expected_account_scope: str | None
) -> tuple[list[str], list[str]]:
    """Returns (problems, warnings). Any problem rejects the import."""
    problems: list[str] = []
    warnings: list[str] = []
    erp = manifest.get("erp")

    # Contract version and identity/reference rules (graph package validator, zero drops allowed).
    if not contract_supported(manifest.get("graph_contract_version")):
        problems.append(
            f"graph contract {manifest.get('graph_contract_version')} unsupported (reads {GRAPH_CONTRACT_VERSION})"
        )
        return problems, warnings
    diag = DiagnosticCollector()
    vn, ve = gc.validate(nodes, edges, str(erp), diag)
    if len(vn) != len(nodes) or len(ve) != len(edges) or diag.has_fatal():
        problems.append(f"contract violations in snapshot content: {diag.counts()}")

    # Provenance.
    identity = manifest.get("identity") or {}
    if not identity.get("input_artifact_sha256"):
        problems.append("manifest has no input artifact hashes")
    for art in (manifest.get("pipeline") or {}).get("artifacts", []):
        if art.get("state") == "present" and not art.get("sha256"):
            problems.append(f"artifact {art.get('artifact')} present without sha256")
        if art.get("state") in ("missing", "incomplete"):
            warnings.append(f"pipeline artifact {art.get('artifact')} is {art.get('state')}; dependent facts unknown")
    if not (manifest.get("package") or {}).get("package_source_sha256"):
        problems.append("manifest has no package source hash")

    # Completeness report.
    if completeness.get("snapshot_id") != manifest.get("snapshot_id"):
        problems.append("completeness.json belongs to another snapshot")
    for key in ("artifacts", "capability_states", "field_metadata_coverage"):
        if key not in completeness:
            problems.append(f"completeness.json missing {key}")

    # Account scope: a pipeline extracted from a customer account stays account-scoped.
    if manifest.get("account_scope") != identity.get("account_scope"):
        problems.append("manifest account_scope differs from identity")
    if manifest.get("account_scope") != expected_account_scope:
        problems.append(
            f"account scope mismatch: snapshot {manifest.get('account_scope')!r}, import {expected_account_scope!r}"
        )

    # Native and normalised types; explicit tri-state keys; explicit capability states.
    for n in nodes:
        if n["kind"] == "field":
            dt = n.get("data_type")
            if not isinstance(dt, dict) or "native" not in dt or dt.get("family") not in TYPE_FAMILIES:
                problems.append(f"{n['id']}: data_type missing native/family")
            for key in ("required", "readonly", "stored"):
                if key not in n:
                    problems.append(f"{n['id']}: tri-state {key} not stated")
        for b in n["bindings"]:
            for op in gc.OPERATIONS:
                cap = (b.get("capabilities") or {}).get(op) or {}
                if cap.get("state") not in gc.CAPABILITY_STATES or not cap.get("basis"):
                    problems.append(f"{b.get('id')}: {op} capability not explicit")
        if len(problems) > 200:
            break
    return problems, warnings


def _check_survival(nodes: list[dict], edges: list[dict], models: list[dict], fields: list[dict]) -> list[str]:
    """Every node and edge must be reconstructible from the rows."""
    problems = []
    by_id = {r["logical_id"]: r for r in models + fields}
    if len(by_id) != len(nodes):
        problems.append(f"row count {len(by_id)} != node count {len(nodes)}")
    for n in nodes:
        r = by_id.get(n["id"])
        if r is None or canonical_hash({**r["definition"], "bindings": r["bindings"]}) != canonical_hash(n):
            problems.append(f"{n['id']}: definition did not survive projection")
        elif n["kind"] == "field" and (r["required"], r["readonly"], r["stored"]) != (
            n.get("required"),
            n.get("readonly"),
            n.get("stored"),
        ):
            problems.append(f"{n['id']}: tri-state columns differ from definition")
    edge_ids = sorted(e["id"] for r in by_id.values() for e in r["relations"])
    if edge_ids != sorted(e["id"] for e in edges):
        problems.append("edges did not survive projection")
    return problems


def load_baseline(
    store: Path,
    graph_snapshot_id: str,
    expected_account_scope: str | None,
    prefixes: dict | None = None,
    source: str = "csv",
) -> Baseline:
    """source "csv": read the snapshot's relational CSV tables (the JSONL files are not needed);
    "jsonl": read nodes.jsonl / edges.jsonl.

    graph.snapshot.verify (copied from erp_schema_graph) checks every file hash, that the CSV tables rebuild nodes.jsonl and
    edges.jsonl byte for byte, the snapshot identity and the contract; it works without the JSONL files."""
    if source not in ("csv", "jsonl"):
        raise CatalogValidationError([f"unknown graph source {source!r}; use csv or jsonl"])
    d = snapshot_dir(store, graph_snapshot_id)
    manifest = gs.read_manifest(d)
    if source == "csv" and not all(name in manifest["files"] for name in gt.TABLES):
        raise CatalogValidationError(
            ["graph snapshot has no CSV tables (built before they existed); rebuild it or use --source jsonl"]
        )
    problems = gs.verify(d)
    if problems:
        raise CatalogValidationError([f"graph snapshot verification failed: {p}" for p in problems])
    if source == "csv":
        nodes, edges = gt.read_tables({name: (d / name).read_bytes() for name in gt.TABLES})
    else:
        nodes, edges = gs.read_jsonl(d / "nodes.jsonl"), gs.read_jsonl(d / "edges.jsonl")
    completeness = json.loads((d / "completeness.json").read_text(encoding="utf-8"))
    graph_diagnostics = json.loads((d / "diagnostics.json").read_text(encoding="utf-8"))

    problems, warnings = validate_graph(manifest, completeness, nodes, edges, expected_account_scope)
    if problems:
        raise CatalogValidationError(problems)
    models, fields = project(manifest["erp"], nodes, edges, prefixes or {})
    problems = _check_survival(nodes, edges, models, fields)
    if problems:
        raise CatalogValidationError(problems)
    return Baseline(
        manifest=manifest,
        completeness=completeness,
        graph_diagnostics={
            "counts": graph_diagnostics.get("counts"),
            "diagnostics": graph_diagnostics.get("diagnostics"),
        },
        models=models,
        fields=fields,
        content_sha256=snapshot_content_hash(models, fields),
        counts={"models": len(models), "fields": len(fields), "edges": len(edges)},
        warnings=warnings,
    )


def graph_package_provenance(manifest: dict) -> dict[str, Any]:
    return {
        "consumer_package_version": graph.__version__,
        "consumer_contract_version": GRAPH_CONTRACT_VERSION,
        "producer": manifest.get("package"),
    }
