"""Structured diagnostics.

Extracted from odoo_pipeline/phase_6/src/phase6_graph/diagnostics.py
(code, severity, identity, message, details). The pipeline's `source` key
is renamed `raised_by` here: in this package `source`/`target` mean migration
direction only (graph contract 2.0.0). Copied, not imported, so this package has no dependency
on another local checkout. See docs/PHASE6_EXTRACTION.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

INFO, WARNING, ERROR, FATAL = "info", "warning", "error", "fatal"


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    message: str
    raised_by: str
    identity: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "identity": self.identity,
            "message": self.message,
            "raised_by": self.raised_by,
            "details": self.details,
        }


class DiagnosticCollector:
    def __init__(self) -> None:
        self._items: list[Diagnostic] = []

    def add(self, code: str, severity: str, message: str, *, raised_by: str,
            identity: str | None = None, details: dict[str, Any] | None = None) -> None:
        self._items.append(Diagnostic(code, severity, message, raised_by, identity, details or {}))

    def info(self, code: str, message: str, **kw: Any) -> None:
        self.add(code, INFO, message, **kw)

    def warning(self, code: str, message: str, **kw: Any) -> None:
        self.add(code, WARNING, message, **kw)

    def error(self, code: str, message: str, **kw: Any) -> None:
        self.add(code, ERROR, message, **kw)

    def fatal(self, code: str, message: str, **kw: Any) -> None:
        self.add(code, FATAL, message, **kw)

    def has_fatal(self) -> bool:
        return any(d.severity == FATAL for d in self._items)

    def has_error(self) -> bool:
        return any(d.severity in (ERROR, FATAL) for d in self._items)

    def counts(self) -> dict[str, int]:
        out = {s: 0 for s in (INFO, WARNING, ERROR, FATAL)}
        for d in self._items:
            out[d.severity] += 1
        return out

    def sorted_dicts(self) -> list[dict[str, Any]]:
        items = sorted(self._items, key=lambda d: (d.raised_by, d.identity or "", d.code, d.message))
        return [d.to_dict() for d in items]
