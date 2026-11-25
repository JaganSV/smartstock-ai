"""API contract control (BOB-P3-02b, AC-3.6): the app's OpenAPI document must equal the committed
baseline ``docs/api/openapi-v1.json``. A deliberate change is exported with ``make openapi`` and
recorded in the API change log of docs/STATUS.md.
"""

import json
from pathlib import Path

from fastapi import FastAPI

from app.cli import openapi_json

BASELINE = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi-v1.json"
CHANGED = (
    "API contract changed: review the diff, then run `make openapi` and record the change in "
    "docs/STATUS.md (API change log)"
)


def test_openapi_document_equals_the_committed_baseline(app: FastAPI) -> None:
    assert BASELINE.is_file(), f"missing {BASELINE}; run `make openapi`"
    committed = BASELINE.read_text(encoding="utf-8")
    generated = openapi_json(app.openapi())
    assert generated == committed, CHANGED


def test_baseline_is_deterministic_json_with_a_trailing_newline() -> None:
    text = BASELINE.read_text(encoding="utf-8")
    assert text.endswith("}\n") and not text.endswith("\n\n")
    assert openapi_json(json.loads(text)) == text  # sorted keys, 2-space indent


def test_no_response_schema_has_a_params_json_or_contact_email_property() -> None:
    schemas = json.loads(BASELINE.read_text(encoding="utf-8"))["components"]["schemas"]
    properties = {name for schema in schemas.values() for name in schema.get("properties", {})}
    assert {"params_json", "contact_email"}.isdisjoint(properties)
    assert "risk_distribution" in properties  # sanity: the walk sees real properties


def test_the_cli_export_writes_exactly_the_baseline(tmp_path: Path) -> None:
    from app.cli import main

    out = tmp_path / "api" / "openapi.json"
    assert main(["openapi", "--out", str(out)]) == 0
    assert out.read_bytes() == BASELINE.read_text(encoding="utf-8").encode("utf-8")
