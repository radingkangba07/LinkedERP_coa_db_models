"""ERP configuration validation (no database)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from catalog_loader import load

SEED = Path(__file__).resolve().parents[2] / "seed" / "erp_configs"


def _seed(name: str) -> dict:
    return json.loads((SEED / f"{name}.json").read_text())


def test_seed_configs_are_valid_and_name_their_products() -> None:
    assert load.validate_config(_seed("odoo")) == []
    assert load.validate_config(_seed("netsuite")) == []
    assert _seed("odoo")["products"] == {"odoo": "community"}
    assert _seed("netsuite")["products"] == {"oracle_netsuite": "standard"}


def test_products_and_identifier_fields_are_part_of_the_content() -> None:
    doc = _seed("odoo")
    changed = copy.deepcopy(doc)
    changed["products"]["odoo_enterprise"] = "enterprise"
    assert load._normalise(changed) != load._normalise(doc)
    changed = copy.deepcopy(doc)
    changed["scope_routes"][0]["identifier_fields"] = ["name"]
    assert load._normalise(changed) != load._normalise(doc)


def test_malformed_products_and_identifier_fields_are_rejected() -> None:
    doc = _seed("odoo")
    doc["products"] = {"odoo": ""}
    doc["scope_routes"][0]["identifier_fields"] = ["barcode", "barcode"]
    problems = load.validate_config(doc)
    assert any("products" in p for p in problems)
    assert any("identifier_fields" in p for p in problems)
