"""Small, contract-valid graph snapshots and discovery evidence for tests.

These are TEST FIXTURES (copied from the backend catalogue tests). They are not live account verification.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from catalog_loader.graph import CONTRACT_VERSION
from catalog_loader.graph import contract as gc
from catalog_loader.graph import snapshot as gs
from catalog_loader.graph import tables as gt
from catalog_loader.graph.snapshot import canonical_hash


def cap(state: str, basis: str) -> dict:
    return {"state": state, "basis": basis, "conditions": []}


def binding(
    owner: str,
    iface: str,
    name: str,
    *,
    evidence: str = "verified",
    read: str = "allowed",
    create: str = "unknown",
    update: str = "unknown",
) -> dict:
    return {
        "id": gc.binding_id(owner, iface),
        "interface": iface,
        "native_name": name,
        "evidence_status": evidence,
        "binding_basis": "fixture",
        "authorization_evaluated": False,
        "capabilities": {
            "read": cap(read, "fixture"),
            "create": cap(create, "fixture"),
            "update": cap(update, "fixture"),
        },
        "properties": {},
    }


def model(erp: str, name: str, ifaces: list[str]) -> dict:
    mid = gc.model_id(erp, name)
    return {
        "id": mid,
        "kind": "model",
        "erp": erp,
        "model": name,
        "label": name,
        "model_kind": "model",
        "table": name.replace(".", "_"),
        "origin_module": "fixture",
        "contributing_modules": ["fixture"],
        "inheritance": [],
        "delegation": {},
        "field_count": 0,
        "attributes": {},
        "analysis_depth": "template",
        "evidence_status": "verified",
        "pipeline_ids": {"model_id": f"{erp}:fixture:{name}"},
        "pipeline_resolution_status": "confirmed",
        "constraints": {"availability": "explicit_empty", "items": []},
        "semantics": [],
        "canonical_mappings": [],
        "bindings": [binding(mid, i, name) for i in ifaces],
    }


def field(
    erp: str,
    mdl: str,
    path: str,
    native: str,
    family: str,
    *,
    readonly: bool | None,
    required: bool | None,
    bindings: list[dict] | None = None,
    relation: str | None = None,
    label: str | None = None,
) -> dict:
    fid = gc.field_id(erp, mdl, path)
    return {
        "id": fid,
        "kind": "field",
        "erp": erp,
        "model": mdl,
        "path": path,
        "qualified_path": f"{mdl}.{path}",
        "owner": gc.model_id(erp, mdl),
        "label": label or path,
        "help": None,
        "data_type": {"native": native, "family": family, "runtime_class": None},
        "relation": relation,
        "required": required,
        "readonly": readonly,
        "stored": None,
        "properties": {"selection": None},
        "origin": {"module": "fixture"},
        "pipeline_ids": {"field_id": fid},
        "pipeline_resolution_status": "confirmed",
        "pipeline_differences": [],
        "evidence_status": "verified",
        "bindings": bindings or [],
    }


def edge(erp: str, edge_type: str, frm: str, to: str | None, cardinality: str | None = None) -> dict:
    return {
        "id": gc.edge_id(edge_type, frm, to),
        "edge_type": edge_type,
        "native_edge_type": edge_type,
        "erp": erp,
        "from_node": frm,
        "to_node": to,
        "to_model": gc.native_model_of(to) if to else None,
        "cardinality": cardinality,
        "interface": None,
        "evidence_status": "verified" if to else "unknown",
        "evidence": [],
        "pipeline_ids": {},
        "pipeline_resolution_status": "confirmed",
        "pipeline_properties": {},
        "properties": {},
        "semantics": [],
    }


def odoo_graph(extra_label: str = "") -> tuple[list[dict], list[dict]]:
    """res.partner + product.template, orm and postgresql bindings."""
    e = "odoo"
    w = {"create": "allowed", "update": "allowed"}
    nodes = [
        model(e, "res.partner", ["orm"]),
        model(e, "product.template", ["orm"]),
        model(e, "res.country", ["orm"]),
        field(
            e,
            "res.partner",
            "name",
            "char",
            "text",
            readonly=False,
            required=True,
            label="Name" + extra_label,
            bindings=[binding("odoo:field:res.partner:name", "orm", "name", **w)],
        ),
        field(
            e,
            "res.partner",
            "vat",
            "char",
            "text",
            readonly=False,
            required=False,
            bindings=[binding("odoo:field:res.partner:vat", "orm", "vat", **w)],
        ),
        field(
            e,
            "res.partner",
            "display_name",
            "char",
            "text",
            readonly=True,
            required=False,
            bindings=[
                binding("odoo:field:res.partner:display_name", "orm", "display_name", create="denied", update="denied")
            ],
        ),
        field(
            e,
            "res.partner",
            "legacy_code",
            "char",
            "text",
            readonly=None,
            required=None,
            bindings=[binding("odoo:field:res.partner:legacy_code", "orm", "legacy_code")],
        ),
        field(
            e,
            "res.partner",
            "country_id",
            "many2one",
            "reference",
            readonly=False,
            required=False,
            relation="res.country",
            bindings=[binding("odoo:field:res.partner:country_id", "orm", "country_id", **w)],
        ),
        field(
            e,
            "product.template",
            "name",
            "char",
            "text",
            readonly=False,
            required=True,
            bindings=[binding("odoo:field:product.template:name", "orm", "name", **w)],
        ),
    ]
    edges = [edge(e, "HAS_FIELD", n["owner"], n["id"]) for n in nodes if n["kind"] == "field"]
    edges.append(edge(e, "REFERENCES", "odoo:field:res.partner:country_id", "odoo:model:res.country", "many_to_one"))
    return nodes, edges


def netsuite_graph() -> tuple[list[dict], list[dict]]:
    e = "netsuite"
    nodes = [model(e, "customer", ["suitescript_record"]), model(e, "subsidiary", ["suitescript_record"])]
    for path, native, fam, ro, req in (
        ("entityid", "text", "text", None, True),
        ("vatregnumber", "text", "text", None, False),
        ("subsidiary", "select", "reference", None, True),
    ):
        fid = gc.field_id(e, "customer", path)
        nodes.append(
            field(
                e,
                "customer",
                path,
                native,
                fam,
                readonly=ro,
                required=req,
                relation="subsidiary" if path == "subsidiary" else None,
                bindings=[
                    binding(fid, "suitescript_record", path),
                    binding(fid, "suitetalk_soap", path, evidence="inferred"),
                ],
            )
        )
    edges = [edge(e, "HAS_FIELD", n["owner"], n["id"]) for n in nodes if n["kind"] == "field"]
    edges.append(
        edge(e, "REFERENCES", "netsuite:field:customer:subsidiary", "netsuite:model:subsidiary", "many_to_one")
    )
    return nodes, edges


def publish_graph(
    store: Path,
    erp: str,
    nodes: list[dict],
    edges: list[dict],
    *,
    account_scope: str | None = None,
    contract_version: str = CONTRACT_VERSION,
    erp_version: str = "1.0",
) -> str:
    """Write a verifiable snapshot directory the way erp_schema_graph.snapshot.build does, CSV tables included."""
    nodes = sorted(copy.deepcopy(nodes), key=lambda n: n["id"])
    edges = sorted(copy.deepcopy(edges), key=lambda x: x["id"])
    nodes_b, edges_b = gs.jsonl(nodes), gs.jsonl(edges)
    identity = {
        "graph_contract_version": contract_version,
        "erp": erp,
        "erp_version": erp_version,
        "erp_edition": "fixture",
        "account_scope": account_scope,
        "content_sha256": gs.sha256(nodes_b + b"\0" + edges_b),
        "input_artifact_sha256": {"p4_effective_fields": canonical_hash(nodes)},
    }
    sid = f"{erp}-{erp_version}-{canonical_hash(identity)[:20]}"
    completeness = {"snapshot_id": sid, "artifacts": [], "capability_states": {}, "field_metadata_coverage": {}}
    files = {
        "nodes.jsonl": nodes_b,
        "edges.jsonl": edges_b,
        "diagnostics.json": gs.pretty({"snapshot_id": sid, "counts": {}, "diagnostics": []}),
        "completeness.json": gs.pretty(completeness),
        **gt.csv_files(nodes, edges),
    }
    manifest = {
        "snapshot_id": sid,
        "identity": identity,
        "graph_contract_version": contract_version,
        "package": {"name": "erp-schema-graph", "package_source_sha256": "fixture"},
        "erp": erp,
        "erp_version": erp_version,
        "erp_edition": "fixture",
        "account_scope": account_scope,
        "parent_snapshot_id": None,
        "pipeline": {"artifacts": [{"artifact": "p4_effective_fields", "state": "present", "sha256": "x"}]},
        "timestamps": {"created_at": "2026-09-25T00:00:00Z"},
        "counts": {"nodes": len(nodes), "edges": len(edges)},
        "files": {k: gs.sha256(v) for k, v in files.items()},
    }
    files["manifest.json"] = gs.pretty(manifest)
    d = gs.snapshots_dir(store) / sid
    d.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (d / name).write_bytes(data)
    return sid


def odoo_discovery(
    *, state: str = "complete", fields: dict | None = None, access: dict | None = None, extra_models: dict | None = None
) -> dict[str, Any]:
    """FIXTURE evidence shaped like OdooAdapter.discover_metadata output."""
    allowed = {
        "read": cap("allowed", "fixture"),
        "create": cap("allowed", "fixture"),
        "update": cap("allowed", "fixture"),
    }
    default_fields = {
        "name": {
            "interface_path": "name",
            "native_type": "char",
            "label": "Name",
            "required": True,
            "readonly": False,
            "capabilities": allowed,
        },
        "vat": {
            "interface_path": "vat",
            "native_type": "char",
            "label": "Tax ID",
            "required": True,
            "readonly": False,
            "capabilities": allowed,
        },
        "x_studio_segment": {
            "interface_path": "x_studio_segment",
            "native_type": "selection",
            "label": "Segment",
            "required": False,
            "readonly": False,
            "custom": True,
            "selection": [["a", "A"], ["b", "B"]],
            "capabilities": allowed,
        },
    }
    models = {
        "res.partner": {
            "state": state,
            "record_type": "res.partner",
            "label": "Contact",
            "access": access or allowed,
            "fields": default_fields if fields is None else fields,
        }
    }
    models.update(extra_models or {})
    return {
        "account_scope": "acme-prod",
        "erp_version": "18.0",
        "interface": "orm",
        "principal": {"uid": 2, "login": "fixture@example.com", "groups": ["Contact Creation"]},
        "models": models,
    }
