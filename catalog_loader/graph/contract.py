"""Graph contract 1.0.0: identities, enumerations and the validator.

The validator is the enforcement point every adapter's output must pass
before a snapshot is published. Invalid records are diagnosed and dropped,
never silently accepted (same policy as Phase 6 contract_validator.py).
See docs/CONTRACT.md for the full specification.
"""

from __future__ import annotations

from typing import Any

from .diagnostics import DiagnosticCollector

ERP_SYSTEMS = {"odoo", "netsuite"}

NODE_KINDS = {"model", "field", "sublist", "search_join"}
FIELD_KINDS = NODE_KINDS - {"model"}

EDGE_TYPES = {
    "HAS_FIELD",        # owner (model or sublist) -> field/sublist/search_join  (from_node -> to_node)
    "REFERENCES",       # field -> model (many2one, many2many)
    "COLLECTION_OF",    # one2many field or sublist -> child model (parent/child)
    "INVERSE_OF",       # collection field -> the many2one field on the child model
    "SEARCH_JOIN",      # search_join node -> model (search interface only)
    "INHERITS_FROM",    # model -> model (Odoo _inherit prototype inheritance)
    "DELEGATES_TO",     # model -> model (Odoo _inherits delegation)
    "RELATED_FIELD",    # field -> field it is related to (first hop of related path)
    "FIELD_INHERITED_FROM",  # field -> same-named field of an INHERITS_FROM parent
}
CARDINALITIES = {"many_to_one", "one_to_many", "many_to_many", "one_to_one", None}

#: Evidence status of a fact or annotation.
VERIFIED = "verified"        # structural fact confirmed by a pipeline source
INFERRED = "inferred"        # deterministic rule output (e.g. help-text, name match), not reviewed
CONFLICTING = "conflicting"  # sources disagree (pipeline resolution_status mismatch)
REVIEWED = "reviewed"        # annotation with review_status approved
PROPOSED = "proposed"        # annotation not yet approved (needs_review / proposed)
REJECTED = "rejected"
UNKNOWN = "unknown"          # evidence missing or unresolved
EVIDENCE_STATUSES = {VERIFIED, INFERRED, CONFLICTING, REVIEWED, PROPOSED, REJECTED, UNKNOWN}

ALLOWED, DENIED = "allowed", "denied"
CAPABILITY_STATES = {ALLOWED, DENIED, UNKNOWN}
OPERATIONS = ("read", "create", "update")

#: Reused from Phase 6 cross_erp_linker._REVIEW_STRENGTH semantics: any
#: status not listed is the weakest, never assumed approved.
_REVIEW_TO_EVIDENCE = {
    "approved": REVIEWED,
    "needs_review": PROPOSED,
    "proposed": PROPOSED,
    "rejected": REJECTED,
}
_EVIDENCE_STRENGTH = {REVIEWED: 3, VERIFIED: 3, INFERRED: 1, PROPOSED: 1,
                      CONFLICTING: 0, REJECTED: 0, UNKNOWN: 0}


def review_to_evidence(review_status: Any) -> str:
    return _REVIEW_TO_EVIDENCE.get(review_status, UNKNOWN)


def weaker(a: str, b: str) -> str:
    return a if _EVIDENCE_STRENGTH.get(a, 0) <= _EVIDENCE_STRENGTH.get(b, 0) else b


# --- identities -------------------------------------------------------------
# Logical identity is stable across ERP versions and snapshots: it never
# contains a release, run id or hash. Snapshot-scoped identity is the pair
# (snapshot_id, logical_id), rendered by scoped_id().

def model_id(erp: str, model: str) -> str:
    return f"{erp}:model:{model}"


def field_id(erp: str, model: str, path: str, kind: str = "field") -> str:
    return f"{erp}:{kind}:{model}:{path}"


def binding_id(owner_id: str, interface: str) -> str:
    return f"{owner_id}@{interface}"


def edge_id(edge_type: str, from_node: str, to_node: str | None) -> str:
    return f"{edge_type}|{from_node}|{to_node if to_node is not None else '?'}"


def native_model_of(node_id: str | None) -> str | None:
    """Native model name inside a model or field logical id (model names never contain ':')."""
    return node_id.split(":", 3)[2] if node_id else None


def scoped_id(snapshot_id: str, logical_id: str) -> str:
    return f"{snapshot_id}/{logical_id}"


# --- value helpers -------------------------------------------------------------

def tristate(value: Any) -> bool | None:
    """Only a real bool is a known value; None, "True", "" etc. are unknown."""
    return value if isinstance(value, bool) else None


def capability(state: str, basis: str, conditions: list[str] | None = None) -> dict[str, Any]:
    return {"state": state, "basis": basis, "conditions": conditions or []}


# --- validator -----------------------------------------------------------------

_NODE_REQUIRED = ("id", "kind", "erp", "model", "evidence_status", "pipeline_ids", "bindings")
_FIELD_REQUIRED = _NODE_REQUIRED + ("path", "qualified_path", "owner")
_EDGE_REQUIRED = ("id", "edge_type", "erp", "from_node", "to_node", "to_model", "cardinality",
                  "evidence_status", "pipeline_properties", "properties")
SOURCE = "contract_validator"


def _check_bindings(node: dict[str, Any], diag: DiagnosticCollector) -> bool:
    seen = set()
    for b in node["bindings"]:
        if b.get("id") != binding_id(node["id"], b.get("interface", "")):
            diag.error("MALFORMED_BINDING_ID", f"{node['id']}: binding id {b.get('id')!r}",
                       raised_by=SOURCE, identity=node["id"])
            return False
        if b["id"] in seen:
            diag.error("DUPLICATE_BINDING", f"{b['id']}: duplicate", raised_by=SOURCE, identity=b["id"])
            return False
        seen.add(b["id"])
        if b.get("evidence_status") not in EVIDENCE_STATUSES:
            diag.error("INVALID_EVIDENCE_STATUS", f"{b['id']}: {b.get('evidence_status')!r}",
                       raised_by=SOURCE, identity=b["id"])
            return False
        caps = b.get("capabilities", {})
        for op in OPERATIONS:
            cap = caps.get(op)
            if not cap or cap.get("state") not in CAPABILITY_STATES or not cap.get("basis"):
                diag.error("INVALID_CAPABILITY", f"{b['id']}: {op} capability {cap!r}",
                           raised_by=SOURCE, identity=b["id"])
                return False
    return True


def validate(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], erp: str,
             diag: DiagnosticCollector) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if erp not in ERP_SYSTEMS:
        diag.fatal("UNKNOWN_ERP_SYSTEM", f"erp {erp!r} not in {sorted(ERP_SYSTEMS)}", raised_by=SOURCE)
        return [], []

    valid_nodes: dict[str, dict[str, Any]] = {}
    for node in nodes:
        nid = node.get("id", "<missing>")
        required = _NODE_REQUIRED if node.get("kind") == "model" else _FIELD_REQUIRED
        missing = [k for k in required if k not in node]
        if node.get("kind") not in NODE_KINDS or missing:
            diag.error("MALFORMED_NODE", f"{nid}: kind {node.get('kind')!r}, missing {missing}",
                       raised_by=SOURCE, identity=nid)
            continue
        if node["erp"] != erp:
            diag.error("INCONSISTENT_ERP_SYSTEM", f"{nid}: erp {node['erp']!r} != {erp!r}",
                       raised_by=SOURCE, identity=nid)
            continue
        expected = (model_id(erp, node["model"]) if node["kind"] == "model"
                    else field_id(erp, node["model"], node["path"], node["kind"]))
        if nid != expected:
            diag.error("MALFORMED_NODE_ID", f"{nid}: expected {expected!r}", raised_by=SOURCE, identity=nid)
            continue
        if node["evidence_status"] not in EVIDENCE_STATUSES:
            diag.error("INVALID_EVIDENCE_STATUS", f"{nid}: {node['evidence_status']!r}",
                       raised_by=SOURCE, identity=nid)
            continue
        if nid in valid_nodes:
            diag.error("DUPLICATE_NODE_ID", f"{nid}: duplicate", raised_by=SOURCE, identity=nid)
            continue
        if not _check_bindings(node, diag):
            continue
        valid_nodes[nid] = node

    # Fields whose owner is not a valid node are dangling too. Repeat until
    # stable: dropping a sublist also orphans its child fields.
    changed = True
    while changed:
        changed = False
        for nid in [n for n, node in valid_nodes.items() if node["kind"] != "model"]:
            owner = valid_nodes[nid]["owner"]
            if owner not in valid_nodes:
                diag.error("DANGLING_FIELD_OWNER", f"{nid}: owner {owner!r} is not a node",
                           raised_by=SOURCE, identity=nid)
                del valid_nodes[nid]
                changed = True

    valid_edges: dict[str, dict[str, Any]] = {}
    for edge in edges:
        eid = edge.get("id", "<missing>")
        missing = [k for k in _EDGE_REQUIRED if k not in edge]
        if missing or edge.get("edge_type") not in EDGE_TYPES:
            diag.error("MALFORMED_EDGE", f"{eid}: type {edge.get('edge_type')!r}, missing {missing}",
                       raised_by=SOURCE, identity=eid)
            continue
        if edge["erp"] != erp:
            diag.error("INCONSISTENT_ERP_SYSTEM", f"{eid}: erp {edge['erp']!r}", raised_by=SOURCE, identity=eid)
            continue
        if eid != edge_id(edge["edge_type"], edge["from_node"], edge["to_node"]) \
                or edge["to_model"] != native_model_of(edge["to_node"]):
            diag.error("MALFORMED_EDGE_ID", f"{eid}", raised_by=SOURCE, identity=eid)
            continue
        if edge["cardinality"] not in CARDINALITIES or edge["evidence_status"] not in EVIDENCE_STATUSES:
            diag.error("INVALID_EDGE_VALUE", f"{eid}: cardinality/evidence_status",
                       raised_by=SOURCE, identity=eid)
            continue
        if edge["from_node"] not in valid_nodes:
            diag.error("DANGLING_EDGE_ENDPOINT", f"{eid}: from_node {edge['from_node']!r} is not a node",
                       raised_by=SOURCE, identity=eid, details={"edge": edge})
            continue
        if edge["to_node"] is None:
            # An unresolved reference is allowed only when stated as unknown.
            if edge["evidence_status"] != UNKNOWN:
                diag.error("UNSTATED_UNRESOLVED_TO_NODE", f"{eid}: null to_node must be unknown",
                           raised_by=SOURCE, identity=eid)
                continue
        elif edge["to_node"] not in valid_nodes:
            diag.error("DANGLING_EDGE_ENDPOINT", f"{eid}: to_node {edge['to_node']!r} is not a node",
                       raised_by=SOURCE, identity=eid, details={"edge": edge})
            continue
        if eid in valid_edges:
            diag.error("DUPLICATE_EDGE_ID", f"{eid}: duplicate", raised_by=SOURCE, identity=eid)
            continue
        valid_edges[eid] = edge

    owned = {e["to_node"] for e in valid_edges.values() if e["edge_type"] == "HAS_FIELD"}
    for nid, node in valid_nodes.items():
        if node["kind"] != "model" and nid not in owned:
            # Adapter bug, not a data gap: block publication.
            diag.fatal("FIELD_WITHOUT_OWNER_EDGE", f"{nid}: no HAS_FIELD edge", raised_by=SOURCE, identity=nid)

    return (sorted(valid_nodes.values(), key=lambda n: n["id"]),
            sorted(valid_edges.values(), key=lambda e: e["id"]))
