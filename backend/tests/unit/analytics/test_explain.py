"""Explanation payloads (FR-B6): complete, JSON-safe and exactly consistent with the metrics."""

import json
from typing import Any

import numpy as np
import pandas as pd
import pytest

from app.analytics.explain import EXPLAINED_METRICS, explain_row, json_safe
from app.analytics.params import AnalyticsParams
from app.analytics.snapshot import to_snapshot_rows
from tests.unit.analytics.helpers import T0

PARAMS = AnalyticsParams(t0=T0)
SPOT_CHECKS = [
    ("SKU-001", "WH-MUM"),
    ("SKU-004", "WH-MUM"),
    ("SKU-024", "WH-MUM"),
    ("SKU-027", "WH-DEL"),
    ("SKU-031", "WH-MUM"),
]


def pick(frame: pd.DataFrame, sku: str, warehouse: str) -> pd.Series:
    rows = frame[(frame["sku"] == sku) & (frame["warehouse_code"] == warehouse)]
    assert len(rows) == 1
    return rows.iloc[0]


def by_metric(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {m["metric"]: m for m in payload["metrics"]}


@pytest.mark.parametrize(("sku", "warehouse"), SPOT_CHECKS)
def test_every_metric_is_present_with_the_required_keys(
    seed_frame: pd.DataFrame, sku: str, warehouse: str
) -> None:
    payload = explain_row(pick(seed_frame, sku, warehouse), PARAMS)
    assert [m["metric"] for m in payload["metrics"]] == list(EXPLAINED_METRICS)
    for entry in payload["metrics"]:
        assert {"metric", "formula", "inputs", "result", "source"} <= set(entry)
        assert entry["formula"]
        assert entry["source"].startswith("BP 7.")
    assert payload["sku"] == sku
    assert payload["warehouse_code"] == warehouse
    assert payload["t0"] == "2026-09-30"


@pytest.mark.parametrize(("sku", "warehouse"), SPOT_CHECKS)
def test_payload_is_json_serialisable(seed_frame: pd.DataFrame, sku: str, warehouse: str) -> None:
    payload = explain_row(pick(seed_frame, sku, warehouse), PARAMS)
    text = json.dumps(payload, allow_nan=False)  # NaN would raise
    assert json.loads(text) == payload


@pytest.mark.parametrize(("sku", "warehouse"), SPOT_CHECKS)
def test_results_equal_the_stored_snapshot_values(
    seed_frame: pd.DataFrame, sku: str, warehouse: str
) -> None:
    """AC-2.7: the payload is consistent with the (DB-scale) snapshot row, to the digit."""
    row = pick(seed_frame, sku, warehouse)
    stored = to_snapshot_rows(seed_frame.loc[[row.name]])[0]
    metrics = by_metric(explain_row(row, PARAMS))
    for name in EXPLAINED_METRICS:
        # inventory_position is not a product_metrics column: compare with the frame value
        expected = stored[name] if name in stored else json_safe(row[name])
        got = metrics[name]["result"]
        if expected is None:
            assert got is None, name
        elif isinstance(expected, str):
            assert got == expected, name
        else:
            assert got == float(expected), name  # Decimal(4 dp) -> float is exact for these values


def test_explained_inputs_match_the_row_values(seed_frame: pd.DataFrame) -> None:
    row = pick(seed_frame, "SKU-004", "WH-MUM")
    metrics = by_metric(explain_row(row, PARAMS))
    assert metrics["available"]["inputs"] == {
        "on_hand": int(row["on_hand"]),
        "committed": int(row["committed"]),
    }
    assert metrics["reorder_point"]["inputs"] == {
        "ads_30": round(float(row["ads_30"]), 4),
        "lead_time_days": 14,
        "safety_stock": 47,
    }
    assert metrics["reorder_point"]["result"] == 349
    assert metrics["safety_stock"]["inputs"]["z"] == PARAMS.z_for(row["service_level"])
    assert metrics["reorder_qty"]["result"] == 432
    assert metrics["reorder_qty"]["inputs"]["q_raw"] == (
        np.ceil(round(float(row["ads_30"]) * 28, 9)) + 47 - 223
    )


def test_override_row_has_no_z_and_shows_the_override(seed_frame: pd.DataFrame) -> None:
    row = pick(seed_frame, "SKU-031", "WH-MUM")
    entry = by_metric(explain_row(row, PARAMS))["safety_stock"]
    assert entry["inputs"]["safety_stock_override"] == 25
    assert entry["inputs"]["z"] is None
    assert entry["result"] == 25


def test_null_cover_is_json_null(seed_frame: pd.DataFrame) -> None:
    row = pick(seed_frame, "SKU-021", "WH-BLR")  # dead stock: ADS30 = 0
    entry = by_metric(explain_row(row, PARAMS))["days_of_cover"]
    assert entry["result"] is None


def test_risk_trace_lists_rules_up_to_the_firing_rule(seed_frame: pd.DataFrame) -> None:
    expected_depth = {
        ("SKU-001", "WH-MUM"): (1, "R1_NO_AVAILABLE_STOCK"),
        ("SKU-004", "WH-MUM"): (2, "R2_STOCKOUT_BEFORE_REPLENISHMENT"),
        ("SKU-009", "WH-BLR"): (3, "R3_BELOW_REORDER_POINT"),
        ("SKU-024", "WH-MUM"): (4, "R4_COVER_BELOW_LEAD_PLUS_REVIEW"),
        ("SKU-013", "WH-DEL"): (5, "R5_EXCESS_COVER"),
        ("SKU-030", "WH-MUM"): (6, "R6_HEALTHY"),
    }
    for (sku, warehouse), (depth, code) in expected_depth.items():
        risk = by_metric(explain_row(pick(seed_frame, sku, warehouse), PARAMS))["risk_class"]
        checked = risk["rules_checked"]
        assert [r["order"] for r in checked] == list(range(1, depth + 1)), sku
        assert [r["matched"] for r in checked] == [False] * (depth - 1) + [True], sku
        assert risk["reason_code"] == code
        assert risk["fired_rule"] == checked[-1]
        assert risk["result"] == pick(seed_frame, sku, warehouse)["risk_class"]


def test_risk_trace_matches_classify_risk_for_all_seed_rows(seed_frame: pd.DataFrame) -> None:
    for _, row in seed_frame.iterrows():
        risk = by_metric(explain_row(row, PARAMS))["risk_class"]
        assert risk["result"] == row["risk_class"]
        assert risk["reason_code"] == row["risk_reason_code"]


def test_every_seed_row_explains_and_serialises(seed_frame: pd.DataFrame) -> None:
    for _, row in seed_frame.iterrows():
        json.dumps(explain_row(row, PARAMS), allow_nan=False)


# --- json_safe ---


def test_json_safe_conversions() -> None:
    from datetime import date
    from decimal import Decimal

    assert json_safe(Decimal("12000.5")) == "12000.50"
    assert json_safe(np.nan) is None
    assert json_safe(pd.NA) is None
    assert json_safe(None) is None
    assert json_safe(np.int64(7)) == 7
    assert isinstance(json_safe(np.int64(7)), int)
    assert json_safe(np.float64(1.5)) == 1.5
    assert json_safe(np.bool_(True)) is True
    assert json_safe(date(2026, 9, 30)) == "2026-09-30"
    assert json_safe("text") == "text"
