"""Lossless relational CSV views of a snapshot.

Every table has a fixed header and a fixed type per column, defined here and
identical for every ERP and version. ERP-specific detail (Odoo and NetSuite
properties, binding properties, model attributes, edge pipeline properties)
is stored as rows in properties.csv, never as extra columns. Lists of records
become child tables keyed by the parent id.

Cell encoding (also written to tables.json for non-Python readers):
    null          \\N  (the PostgreSQL COPY null marker)
    text          the string as is; "" is an empty string, not null
    integer       decimal digits
    boolean       true / false
    json          compact JSON (lists, objects, and mixed-type values)
properties.csv carries a value_type per row (null, string, integer, number,
boolean, json) because its values have no single column type.

A key that is missing from a record (as opposed to present with null) is
listed by path in the row's absent_keys cell, and its cells hold \\N.

read_tables() is the exact inverse of build_tables(): it rebuilds the nodes
and edges, and the snapshot's content hash is checked against them, so the
CSVs alone are enough to reproduce and verify a snapshot.

Every key of every record must map to a column or a child table. An unmapped
key, a null parent object, a value of the wrong type or a text value equal
to \\N raises TableError, so a contract change cannot lose data silently.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from .contract import OPERATIONS

NULL = "\\N"
Path = tuple[str, ...]
TYPES = ("text", "integer", "boolean", "json")


class TableError(ValueError):
    pass


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    path: Path


@dataclass(frozen=True)
class Table:
    columns: tuple[Column, ...]
    children: frozenset[Path] = field(default_factory=frozenset)
    tracks_absent: bool = True

    @property
    def header(self) -> list[str]:
        return [c.name for c in self.columns] + (["absent_keys"] if self.tracks_absent else [])

    @property
    def data_columns(self) -> list[Column]:
        """Columns read from the record itself (not parent ids or kinds added by the writer)."""
        return [c for c in self.columns if not c.path[0].startswith("_")]


def _table(*specs: str, children: Iterable[Path] = (), tracks_absent: bool = True) -> Table:
    """Each spec is "name", "name:type" or "name:type=dotted.path"; type defaults to text."""
    cols = []
    for s in specs:
        head, _, path = s.partition("=")
        name, _, typ = head.partition(":")
        assert (typ or "text") in TYPES, s
        cols.append(Column(name, typ or "text", tuple((path or name).split("."))))
    return Table(tuple(cols), frozenset(children), tracks_absent)


TABLES: dict[str, Table] = {
    "models.csv": _table(
        "id", "erp", "model", "label", "model_kind", "table", "origin_module", "field_count:integer",
        "analysis_depth", "evidence_status", "pipeline_resolution_status",
        "pipeline_model_id:text=pipeline_ids.model_id", "constraints_availability:text=constraints.availability",
        children=[("attributes",), ("delegation",), ("inheritance",), ("contributing_modules",),
                  ("constraints", "items"), ("semantics",), ("canonical_mappings",), ("bindings",)]),
    "fields.csv": _table(
        "id", "erp", "kind", "model", "owner", "path", "qualified_path", "label", "help",
        "data_type_family:text=data_type.family", "data_type_native:text=data_type.native",
        "data_type_runtime_class:text=data_type.runtime_class", "relation", "relation_phrase",
        "relation_source", "readonly:boolean", "required:boolean", "stored:boolean",
        "computed:boolean=computed.compute", "computed_inverse:boolean=computed.inverse",
        # str (related path) or bool, so JSON keeps the type
        "computed_related:json=computed.related",
        "origin_module:text=origin.module", "origin_class:text=origin.class", "origin_file:text=origin.file",
        "origin_line:integer=origin.line", "origin_last_modified_by:text=origin.last_modified_by",
        "origin_contributors:json=origin.contributors", "evidence_status", "pipeline_resolution_status",
        "pipeline_field_id:text=pipeline_ids.field_id",
        children=[("properties",), ("origin", "modifications"), ("pipeline_differences",), ("bindings",)]),
    "edges.csv": _table(
        "id", "erp", "edge_type", "from_node", "to_node", "to_model", "cardinality", "native_edge_type",
        "interface", "evidence_status", "evidence:json", "pipeline_resolution_status",
        "pipeline_edge_id:text=pipeline_ids.edge_id",
        children=[("pipeline_properties",), ("properties",), ("semantics",)]),
    "bindings.csv": _table(
        "id", "node_id:text=_node_id", "interface", "native_name", "binding_basis", "evidence_status",
        "authorization_evaluated:boolean",
        *(f"{op}_{part}:{'json' if part == 'conditions' else 'text'}=capabilities.{op}.{part}"
          for op in OPERATIONS for part in ("state", "basis", "conditions")),
        children=[("properties",)]),
    # One row per ERP-specific value. scope: property | attribute | pipeline_property | binding_property.
    "properties.csv": _table("owner_id", "scope", "key", "value", "value_type", "source", tracks_absent=False),
    # Node semantics, canonical mappings, relationship semantics and pipeline
    # differences; annotation_kind says which. Keys a kind lacks are in absent_keys.
    "annotations.csv": _table(
        "target_id:text=_target_id", "annotation_kind:text=_kind", "annotation_id", "mapping_id",
        "relationship_id", "annotation_type", "value", "business_label", "inverse_label", "concept_id",
        "mapping_relation", "relationship_kind", "vocabulary_version", "rule_id", "confidence_band",
        "evidence_status", "review_status", "source_method", "provenance", "published:boolean", "rationale",
        "limitations:json", "evidence_refs:json", "reviewer_decisions:json"),
    # link_type: inherits | delegates (via_field set) | contributing_module. Row order is list order.
    "model_links.csv": _table("model_id", "link_type", "target", "via_field", tracks_absent=False),
    "constraints.csv": _table("constraint_id", "model_id:text=_model_id", "name", "type", "table", "fields:json",
                              "evidence_status", "provenance"),
    "field_origin.csv": _table("field_id:text=_field_id", "sequence:integer", "module", "action",
                               "attributes:json"),
}


# ---------------------------------------------------------------- cells

def _json(v: Any) -> str:
    return json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _encode(v: Any, typ: str, where: str) -> str:
    if v is None:
        return NULL
    ok = {"text": isinstance(v, str),
          "integer": isinstance(v, int) and not isinstance(v, bool),
          "boolean": isinstance(v, bool),
          "json": True}[typ]
    if not ok:
        raise TableError(f"{where}: {type(v).__name__} value {v!r} in a {typ} column")
    if typ == "text":
        if v == NULL:
            raise TableError(f"{where}: text value equals the null marker {NULL}")
        return v
    if typ == "boolean":
        return "true" if v else "false"
    return str(v) if typ == "integer" else _json(v)


def _decode(s: str, typ: str) -> Any:
    if s == NULL:
        return None
    if typ == "text":
        return s
    if typ == "integer":
        return int(s)
    if typ == "boolean":
        return s == "true"
    if typ == "number":
        return float(s)
    return json.loads(s)


def _value_type(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    return "string" if isinstance(v, str) else "json"


def _encode_any(v: Any, where: str) -> tuple[str, str]:
    vt = _value_type(v)
    if vt == "number":
        return repr(v), vt
    return _encode(v, {"string": "text", "null": "text"}.get(vt, vt), where), vt


def _decode_any(s: str, vt: str) -> Any:
    return _decode(s, {"string": "text", "null": "text"}.get(vt, vt))


# ---------------------------------------------------------------- write

def _get(rec: Any, path: Path) -> Any:
    for k in path:
        if not isinstance(rec, dict):
            return None
        rec = rec.get(k)
    return rec


def _check(rec: dict[str, Any], covered: set[Path], where: str, prefix: Path = ()) -> None:
    """Fail on any key path not read by a column or handed to a child table."""
    for k, v in rec.items():
        p = prefix + (k,)
        if p in covered:
            continue
        if isinstance(v, dict) and any(c[:len(p)] == p for c in covered):
            _check(v, covered, where, p)
        else:
            raise TableError(f"{where}: key {'.'.join(p)!r} is not mapped to any CSV column or table")


def _absent(rec: dict[str, Any], table: Table, where: str) -> list[str]:
    """Shortest missing path for each column and child; null parents and null child containers fail."""
    out: list[str] = []
    for path, is_child in [(c.path, False) for c in table.data_columns] + [(p, True) for p in table.children]:
        cur: Any = rec
        for i, k in enumerate(path):
            if not isinstance(cur, dict):
                raise TableError(f"{where}: {'.'.join(path[:i])!r} is {cur!r}, expected an object")
            if k not in cur:
                key = ".".join(path[:i + 1])
                if key not in out:
                    out.append(key)
                break
            cur = cur[k]
        else:
            if is_child and cur is None:
                raise TableError(f"{where}: {'.'.join(path)!r} is null, expected a list or object")
    return out


def _row(rec: dict[str, Any], table: Table, where: str) -> list[str]:
    _check(rec, {c.path for c in table.columns} | set(table.children), where)
    cells = [_encode(_get(rec, c.path), c.type, f"{where} {c.name}") for c in table.columns]
    if table.tracks_absent:
        absent = _absent(rec, table, where)
        cells.append(_json(absent) if absent else NULL)
    return cells


def _props(owner: str, scope: str, d: dict[str, Any], attributes: bool = False) -> Iterable[list[str]]:
    for k, v in sorted(d.items()):
        source = None
        if attributes:
            if not isinstance(v, dict) or set(v) != {"source", "value"}:
                raise TableError(f"{owner}: attribute {k!r} is not {{source, value}}")
            source, v = v["source"], v["value"]
        value, vt = _encode_any(v, f"{owner} {scope}.{k}")
        yield [owner, scope, k, value, vt, _encode(source, "text", f"{owner} {k} source")]


def _link(model: str, link_type: str, target: Any, via: Any = None) -> list[str]:
    where = f"{model} {link_type}"
    return [model, link_type, _encode(target, "text", where), _encode(via, "text", where)]


def build_tables(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, list[list[str]]]:
    t: dict[str, list[list[str]]] = {name: [] for name in TABLES}

    def add(name: str, rec: dict[str, Any], where: str) -> None:
        t[name].append(_row(rec, TABLES[name], where))

    def annotate(target: str, kind: str, items: list[dict[str, Any]]) -> None:
        for a in items:
            add("annotations.csv", {**a, "_target_id": target, "_kind": kind}, f"{target} {kind}")

    for n in nodes:
        nid = n["id"]
        if n["kind"] == "model":
            add("models.csv", {k: v for k, v in n.items() if k != "kind"}, nid)
            t["properties.csv"].extend(_props(nid, "attribute", n.get("attributes") or {}, attributes=True))
            t["model_links.csv"].extend(_link(nid, "inherits", m) for m in n.get("inheritance") or [])
            t["model_links.csv"].extend(_link(nid, "delegates", m, f)
                                        for m, f in sorted((n.get("delegation") or {}).items()))
            t["model_links.csv"].extend(_link(nid, "contributing_module", m)
                                        for m in n.get("contributing_modules") or [])
            for item in (n.get("constraints") or {}).get("items") or []:
                add("constraints.csv", {**item, "_model_id": nid}, nid)
            annotate(nid, "semantic", n.get("semantics") or [])
            annotate(nid, "canonical_mapping", n.get("canonical_mappings") or [])
        else:
            add("fields.csv", n, nid)
            t["properties.csv"].extend(_props(nid, "property", n.get("properties") or {}))
            for m in (n.get("origin") or {}).get("modifications") or []:
                add("field_origin.csv", {**m, "_field_id": nid}, nid)
            annotate(nid, "pipeline_difference", [{"value": d} for d in n.get("pipeline_differences") or []])
        for b in n["bindings"]:
            add("bindings.csv", {**b, "_node_id": nid}, b["id"])
            t["properties.csv"].extend(_props(b["id"], "binding_property", b.get("properties") or {}))

    for e in edges:
        eid = e["id"]
        add("edges.csv", e, eid)
        t["properties.csv"].extend(_props(eid, "pipeline_property", e.get("pipeline_properties") or {}))
        t["properties.csv"].extend(_props(eid, "property", e.get("properties") or {}))
        annotate(eid, "relationship_semantic", e.get("semantics") or [])
    return t


def schema() -> dict[str, Any]:
    return {"null": NULL, "encoding": "utf-8 with BOM, RFC 4180 quoting, CRLF",
            "properties_value_types": ["null", "string", "integer", "number", "boolean", "json"],
            "tables": {name: {"columns": [{"name": c.name, "type": c.type} for c in tb.columns]
                              + ([{"name": "absent_keys", "type": "json"}] if tb.tracks_absent else [])}
                       for name, tb in TABLES.items()}}


def csv_files(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, bytes]:
    out = {}
    for name, rows in build_tables(nodes, edges).items():
        buf = io.StringIO(newline="")
        w = csv.writer(buf, lineterminator="\r\n")
        w.writerow(TABLES[name].header)
        w.writerows(rows)
        # utf-8-sig: BOM so Excel reads non-ASCII text correctly
        out[name] = buf.getvalue().encode("utf-8-sig")
    out["tables.json"] = (json.dumps(schema(), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return out


# ---------------------------------------------------------------- read

def _record(row: list[str], table: Table) -> tuple[dict[str, Any], dict[str, Any], set[str]]:
    """(record from data columns, writer-added values by path name, absent paths)."""
    cells = dict(zip(table.header, row))
    absent = set(_decode(cells["absent_keys"], "json") or []) if table.tracks_absent else set()
    rec: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    for c in table.columns:
        value = _decode(cells[c.name], c.type)
        if c.path[0].startswith("_"):
            extra[c.path[0]] = value
        else:
            _place(rec, c.path, absent, lambda v=value: v)
    return rec, extra, absent


def _place(rec: dict[str, Any], path: Path, absent: set[str], make: Any) -> None:
    """Set rec[path] = make() unless the path or a parent is absent; parents are created."""
    cur = rec
    for i, k in enumerate(path):
        if ".".join(path[:i + 1]) in absent:
            return
        if i < len(path) - 1:
            cur = cur.setdefault(k, {})
        else:
            cur[k] = make()


def read_tables(files: dict[str, bytes]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Inverse of build_tables: rebuild (nodes, edges), sorted by id as published."""
    rows = {name: list(csv.reader(io.StringIO(files[name].decode("utf-8-sig"), newline="")))
            for name in TABLES}
    for name, r in rows.items():
        if not r or r[0] != TABLES[name].header:
            raise TableError(f"{name}: header does not match this package's table definition")

    props: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
    for owner, scope, key, value, vt, source in rows["properties.csv"][1:]:
        v = _decode_any(value, vt)
        props[(owner, scope)][key] = {"source": _decode(source, "text"), "value": v} if scope == "attribute" else v
    links: dict[tuple[str, str], list[tuple[Any, Any]]] = defaultdict(list)
    for model, link_type, target, via in rows["model_links.csv"][1:]:
        links[(model, link_type)].append((_decode(target, "text"), _decode(via, "text")))

    def children(name: str, key: str) -> dict[Any, list[dict[str, Any]]]:
        out: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for r in rows[name][1:]:
            rec, extra, _ = _record(r, TABLES[name])
            out[tuple(extra[k] for k in key.split(","))].append(rec)
        return out

    annotations = children("annotations.csv", "_target_id,_kind")
    constraints = children("constraints.csv", "_model_id")
    origins = children("field_origin.csv", "_field_id")
    bindings: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for r in rows["bindings.csv"][1:]:
        rec, extra, absent = _record(r, TABLES["bindings.csv"])
        _place(rec, ("properties",), absent, lambda: props.pop((rec["id"], "binding_property"), {}))
        bindings[(extra["_node_id"],)].append(rec)

    nodes = []
    for r in rows["models.csv"][1:]:
        n, _, absent = _record(r, TABLES["models.csv"])
        nid = n["id"]
        n["kind"] = "model"
        fill = {
            ("attributes",): lambda: props.pop((nid, "attribute"), {}),
            ("delegation",): lambda: dict(links[(nid, "delegates")]),
            ("inheritance",): lambda: [m for m, _ in links[(nid, "inherits")]],
            ("contributing_modules",): lambda: [m for m, _ in links[(nid, "contributing_module")]],
            ("constraints", "items"): lambda: constraints.get((nid,), []),
            ("semantics",): lambda: annotations.get((nid, "semantic"), []),
            ("canonical_mappings",): lambda: annotations.get((nid, "canonical_mapping"), []),
            ("bindings",): lambda: bindings.get((nid,), []),
        }
        for path, make in fill.items():
            _place(n, path, absent, make)
        nodes.append(n)
    for r in rows["fields.csv"][1:]:
        n, _, absent = _record(r, TABLES["fields.csv"])
        nid = n["id"]
        fill = {
            ("properties",): lambda: props.pop((nid, "property"), {}),
            ("origin", "modifications"): lambda: origins.get((nid,), []),
            ("pipeline_differences",): lambda: [a["value"] for a in annotations.get((nid, "pipeline_difference"), [])],
            ("bindings",): lambda: bindings.get((nid,), []),
        }
        for path, make in fill.items():
            _place(n, path, absent, make)
        nodes.append(n)

    edges = []
    for r in rows["edges.csv"][1:]:
        e, _, absent = _record(r, TABLES["edges.csv"])
        eid = e["id"]
        fill = {
            ("pipeline_properties",): lambda: props.pop((eid, "pipeline_property"), {}),
            ("properties",): lambda: props.pop((eid, "property"), {}),
            ("semantics",): lambda: annotations.get((eid, "relationship_semantic"), []),
        }
        for path, make in fill.items():
            _place(e, path, absent, make)
        edges.append(e)
    return sorted(nodes, key=lambda n: n["id"]), sorted(edges, key=lambda e: e["id"])
