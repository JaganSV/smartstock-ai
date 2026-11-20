"""Risk classification (BP 7.4): one row per rule, every boundary, precedence, worked example."""

from typing import Any

import pandas as pd

from app.analytics.metrics import compute_metrics
from app.analytics.params import AnalyticsParams
from app.analytics.risk import RISK_RULES, classify_risk
from app.models.enums import RiskClass
from tests.unit.analytics.helpers import (
    T0,
    alternating,
    input_row,
    make_inputs,
    risk_frame,
    units,
)

PARAMS = AnalyticsParams(t0=T0)


def classify(**row: Any) -> tuple[str, str]:
    out = classify_risk(risk_frame(row), PARAMS)
    return str(out["risk_class"][0]), str(out["risk_reason_code"][0])


def test_default_row_is_low() -> None:
    assert classify() == ("LOW", "R6_HEALTHY")


def test_rule_table_order_and_codes() -> None:
    assert [(r.order, r.risk_class.value, r.code) for r in RISK_RULES] == [
        (1, "STOCKOUT", "R1_NO_AVAILABLE_STOCK"),
        (2, "CRITICAL", "R2_STOCKOUT_BEFORE_REPLENISHMENT"),
        (3, "HIGH", "R3_BELOW_REORDER_POINT"),
        (4, "MEDIUM", "R4_COVER_BELOW_LEAD_PLUS_REVIEW"),
        (5, "OVERSTOCK", "R5_EXCESS_COVER"),
        (6, "LOW", "R6_HEALTHY"),
    ]


# --- R1 ---


def test_r1_available_zero_with_demand_is_stockout() -> None:
    assert classify(available=0, inventory_position=0, days_of_cover=0.0)[0] == "STOCKOUT"


def test_r1_negative_available_is_stockout() -> None:
    assert classify(available=-5, inventory_position=-5, days_of_cover=0.0) == (
        "STOCKOUT",
        "R1_NO_AVAILABLE_STOCK",
    )


def test_r1_available_one_is_not_stockout() -> None:
    assert classify(available=1, days_of_cover=0.2)[0] != "STOCKOUT"


def test_r1_needs_demand() -> None:
    out = classify(available=0, ads_30=0.0, days_of_cover=None, inventory_position=60)
    assert out[0] != "STOCKOUT"


# --- R2 ---


def test_r2_stockout_day_present_is_critical() -> None:
    assert classify(projected_stockout_day=7) == ("CRITICAL", "R2_STOCKOUT_BEFORE_REPLENISHMENT")


def test_r2_needs_demand() -> None:
    assert classify(projected_stockout_day=3, ads_30=0.0, days_of_cover=None)[0] != "CRITICAL"


def _pipeline_class(available: int) -> str:
    """Constant 10 units/day (sigma 0 => SS 0, ROP 70), L = 7, R = 14, on_hand = available."""
    frame = make_inputs(
        input_row(
            on_hand=available,
            units_by_day=units(10, earlier=10),
            supplier_lead_time_days=7,
        )
    )
    metrics = compute_metrics(frame, PARAMS).assign(review_period_days=14, on_hand=available)
    return str(classify_risk(metrics, PARAMS)["risk_class"][0])


def test_r2_stockout_exactly_on_day_l_is_critical() -> None:
    # 70 - 10 k <= 0 first at k = 7 = L
    assert _pipeline_class(70) == "CRITICAL"


def test_r2_stockout_on_day_l_plus_one_is_not_critical() -> None:
    # 71 - 10 k <= 0 first at k = 8 = L + 1; IP 71 > ROP 70; DoC 7.1 < 21 -> MEDIUM
    assert _pipeline_class(71) == "MEDIUM"


# --- R3 ---


def test_r3_ip_equal_to_rop_is_high() -> None:
    assert classify(inventory_position=50, reorder_point=50) == ("HIGH", "R3_BELOW_REORDER_POINT")


def test_r3_ip_one_above_rop_is_not_high() -> None:
    assert classify(inventory_position=51, reorder_point=50)[0] != "HIGH"


def test_r3_applies_even_without_demand() -> None:
    # ADS30 = 0 => ROP = SS; IP <= SS is HIGH
    out = classify(ads_30=0.0, days_of_cover=None, inventory_position=5, reorder_point=10)
    assert out[0] == "HIGH"


# --- R4 ---


def test_r4_cover_equal_to_lead_plus_review_is_not_medium() -> None:
    assert classify(days_of_cover=21.0)[0] == "LOW"  # L + R = 7 + 14


def test_r4_cover_just_below_lead_plus_review_is_medium() -> None:
    assert classify(days_of_cover=20.999) == ("MEDIUM", "R4_COVER_BELOW_LEAD_PLUS_REVIEW")


def test_r4_uses_the_rows_own_review_period() -> None:
    assert classify(days_of_cover=25.0, review_period_days=14)[0] == "LOW"
    assert classify(days_of_cover=25.0, review_period_days=21)[0] == "MEDIUM"  # L + R = 28


def test_r4_null_cover_is_not_medium() -> None:
    assert classify(days_of_cover=None, ads_30=0.0, on_hand=0)[0] != "MEDIUM"


# --- R5 ---


def test_r5_cover_of_exactly_120_is_not_overstock() -> None:
    assert classify(days_of_cover=120.0)[0] == "LOW"


def test_r5_cover_just_above_120_is_overstock() -> None:
    assert classify(days_of_cover=120.0001) == ("OVERSTOCK", "R5_EXCESS_COVER")


def test_r5_no_demand_with_stock_is_overstock() -> None:
    # ADS30 = 0 => ROP = SS = 0, so IP 40 is above it and rules 1-4 do not fire
    out = classify(
        ads_30=0.0, days_of_cover=None, on_hand=40, inventory_position=40, reorder_point=0
    )
    assert out == ("OVERSTOCK", "R5_EXCESS_COVER")


def test_r5_no_demand_and_no_stock_falls_through_to_low() -> None:
    """ADS30 = 0, on_hand = 0, and a position above the reorder point (incoming stock): LOW."""
    out = classify(
        ads_30=0.0,
        days_of_cover=None,
        on_hand=0,
        available=0,
        inventory_position=30,
        reorder_point=0,
    )
    assert out == ("LOW", "R6_HEALTHY")


def test_empty_idle_row_is_high_by_rule_3_and_has_zero_reorder_quantity() -> None:
    """Architect decision B1 (BOB-P3-01): on_hand = 0, ADS30 = 0, SS = 0 gives IP = ROP = 0, so
    BP 7.4 rule 3 (IP <= ROP) fires and the row is HIGH (R3). HIGH is correct. Its reorder
    quantity is 0 (Q_raw = 0), so P8 creates no recommendation for it (only where Q > 0)."""
    out = classify(
        ads_30=0.0,
        days_of_cover=None,
        on_hand=0,
        available=0,
        inventory_position=0,
        reorder_point=0,
    )
    assert out == ("HIGH", "R3_BELOW_REORDER_POINT")


def test_empty_idle_row_metrics_give_zero_reorder_quantity() -> None:
    inputs = make_inputs(input_row(on_hand=0, committed=0, units_by_day=units(0, 0)))
    metrics = compute_metrics(inputs, PARAMS)
    assert metrics["reorder_point"][0] == 0
    assert metrics["inventory_position"][0] == 0
    assert metrics["reorder_qty"][0] == 0


# --- precedence ---


def test_rule_2_beats_rule_3() -> None:
    out = classify(projected_stockout_day=4, inventory_position=10, reorder_point=50)
    assert out == ("CRITICAL", "R2_STOCKOUT_BEFORE_REPLENISHMENT")


def test_rule_1_beats_rules_2_and_3() -> None:
    out = classify(available=-1, projected_stockout_day=0, inventory_position=-1, reorder_point=9)
    assert out[0] == "STOCKOUT"


def test_rule_3_beats_rule_4() -> None:
    assert classify(inventory_position=10, reorder_point=50, days_of_cover=5.0)[0] == "HIGH"


def test_rule_4_beats_rule_5_when_both_could_apply() -> None:
    # a null cover cannot be MEDIUM, so this checks only the order of the numpy.select branches
    assert classify(days_of_cover=5.0, ads_30=5.0)[0] == "MEDIUM"


# --- BP 7.6 worked example ---


def test_worked_example_is_high_via_rule_3() -> None:
    inputs = make_inputs(
        input_row(
            on_hand=120,
            committed=20,
            units_by_day=units(alternating(6, 14), earlier=10),
            supplier_lead_time_days=9,
            service_level=0.95,
            supplier_moq=50,
            case_pack=12,
        )
    )
    metrics = compute_metrics(inputs, PARAMS).assign(review_period_days=14, on_hand=120)
    out = classify_risk(metrics, PARAMS)
    assert out["inventory_position"][0] == 100
    assert out["reorder_point"][0] == 110
    assert out["risk_class"][0] == "HIGH"
    assert out["risk_reason_code"][0] == "R3_BELOW_REORDER_POINT"


# --- shape ---


def test_vectorised_over_many_rows_and_input_is_not_mutated() -> None:
    frame = risk_frame(
        {"available": 0, "inventory_position": 0},
        {"projected_stockout_day": 2},
        {"inventory_position": 1},
        {"days_of_cover": 10.0},
        {"days_of_cover": 500.0},
        {},
    )
    before = frame.columns.tolist()
    out = classify_risk(frame, PARAMS)
    assert out["risk_class"].tolist() == [
        "STOCKOUT",
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "OVERSTOCK",
        "LOW",
    ]
    assert frame.columns.tolist() == before
    assert set(out["risk_class"]) == {c.value for c in RiskClass}


def test_returns_plain_strings() -> None:
    out = classify_risk(risk_frame({}), PARAMS)
    assert isinstance(out["risk_class"][0], str)
    assert isinstance(out["risk_reason_code"][0], str)
    assert isinstance(out, pd.DataFrame)


def test_empty_frame_gives_empty_columns() -> None:
    out = classify_risk(risk_frame({}).iloc[0:0], PARAMS)
    assert len(out) == 0
    assert {"risk_class", "risk_reason_code"} <= set(out.columns)
