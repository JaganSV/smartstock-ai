"""The metrics must see the engineered seed-42 scenarios (in-memory seed, no database).

No risk classes are asserted here (P2-02). These checks only prove that the raw metrics reflect
the data engineered in BOB-P1-02.
"""

import time
from typing import Any

import pandas as pd
import pytest

from app.analytics.metrics import compute_metrics
from app.analytics.params import AnalyticsParams


def pick(metrics: pd.DataFrame, sku: str, warehouse: str) -> Any:
    match = metrics[(metrics["sku"] == sku) & (metrics["warehouse_code"] == warehouse)]
    assert len(match) == 1, (sku, warehouse)
    return match.iloc[0]


def skus(first: int, last: int) -> list[str]:
    return [f"SKU-{n:03d}" for n in range(first, last + 1)]


def test_seed_yields_150_rows_one_per_product_warehouse(
    seed_metrics: pd.DataFrame, seed_inputs: pd.DataFrame
) -> None:
    assert len(seed_inputs) == len(seed_metrics) == 150
    assert not seed_metrics.duplicated(["product_id", "warehouse_id"]).any()
    assert seed_metrics["sku"].nunique() == 50
    assert seed_metrics["warehouse_code"].nunique() == 3


def test_every_input_row_has_a_full_90_day_window(seed_inputs: pd.DataFrame) -> None:
    assert (seed_inputs["units_by_day"].map(len) == 90).all()


@pytest.mark.parametrize("sku", skus(1, 3))
def test_stockout_skus_have_non_positive_available_and_positive_demand(
    seed_metrics: pd.DataFrame, sku: str
) -> None:
    row = pick(seed_metrics, sku, "WH-MUM")
    assert row["available"] <= 0
    assert row["ads_30"] > 0
    assert row["days_of_cover"] == 0.0
    assert row["projected_stockout_day"] == 0


@pytest.mark.parametrize("sku", skus(4, 8))
def test_critical_skus_project_a_stockout_within_lead_time(
    seed_metrics: pd.DataFrame, sku: str
) -> None:
    row = pick(seed_metrics, sku, "WH-MUM")
    assert pd.notna(row["projected_stockout_day"])
    assert 0 <= row["projected_stockout_day"] <= row["lead_time_days"]
    assert row["available"] > 0


@pytest.mark.parametrize("sku", skus(24, 26))
def test_covered_by_incoming_skus_have_incoming_in_lead_time(
    seed_metrics: pd.DataFrame, sku: str
) -> None:
    row = pick(seed_metrics, sku, "WH-MUM")
    assert row["incoming_in_lt"] > 0
    assert row["inventory_position"] == row["available"] + row["incoming_in_lt"]
    assert row["days_of_cover"] < row["lead_time_days"]


@pytest.mark.parametrize("sku", skus(21, 23))
def test_dead_stock_skus_have_no_demand_and_nan_days_of_cover(
    seed_metrics: pd.DataFrame, sku: str
) -> None:
    row = pick(seed_metrics, sku, "WH-BLR")
    assert row["ads_30"] == 0
    assert pd.isna(row["days_of_cover"])
    assert pd.isna(row["projected_stockout_day"])
    assert row["available"] > 0
    assert row["reorder_qty"] == 0


def test_policy_overrides_reach_the_metrics(seed_metrics: pd.DataFrame) -> None:
    assert pick(seed_metrics, "SKU-031", "WH-MUM")["safety_stock"] == 25
    assert pick(seed_metrics, "SKU-032", "WH-BLR")["safety_stock"] == 0
    assert pick(seed_metrics, "SKU-033", "WH-DEL")["lead_time_days"] == 3


def test_overrides_are_the_only_deviations_from_the_computed_values(
    seed_metrics: pd.DataFrame, seed_inputs: pd.DataFrame
) -> None:
    overridden = (
        seed_inputs["safety_stock_override"].notna()
        | seed_inputs["lead_time_override_days"].notna()
    )
    assert int(overridden.sum()) == 3
    plain = seed_metrics[~overridden.to_numpy()]
    assert (
        plain["lead_time_days"] == seed_inputs.loc[~overridden, "supplier_lead_time_days"]
    ).all()


def test_committed_masking_skus_have_large_committed_and_low_available(
    seed_metrics: pd.DataFrame, seed_inputs: pd.DataFrame
) -> None:
    for sku in skus(27, 29):
        row = pick(seed_metrics, sku, "WH-DEL")
        source = seed_inputs[
            (seed_inputs["sku"] == sku) & (seed_inputs["warehouse_code"] == "WH-DEL")
        ]
        assert int(source["committed"].iloc[0]) > row["available"] > 0


def test_high_demand_skus_show_a_positive_trend(seed_metrics: pd.DataFrame) -> None:
    for sku in skus(9, 12):
        assert pick(seed_metrics, sku, "WH-BLR")["demand_trend"] >= 0.5 - 1e-9


def test_integer_columns_are_integer_typed_on_the_seed(seed_metrics: pd.DataFrame) -> None:
    for column in (
        "available",
        "incoming_in_lt",
        "lead_time_days",
        "safety_stock",
        "reorder_point",
        "inventory_position",
        "reorder_qty",
    ):
        assert str(seed_metrics[column].dtype) == "int64", column


def test_reorder_quantities_respect_pack_and_moq_on_the_seed(
    seed_metrics: pd.DataFrame, seed_inputs: pd.DataFrame
) -> None:
    qty = seed_metrics["reorder_qty"]
    assert (qty % seed_inputs["case_pack"] == 0).all()
    assert ((qty == 0) | (qty >= seed_inputs["supplier_moq"])).all()


def test_compute_metrics_on_the_seed_takes_under_one_second(
    seed_inputs: pd.DataFrame, seed_params: AnalyticsParams
) -> None:
    started = time.perf_counter()
    compute_metrics(seed_inputs, seed_params)
    assert time.perf_counter() - started < 1.0


def test_compute_metrics_is_deterministic_on_the_seed(
    seed_inputs: pd.DataFrame, seed_params: AnalyticsParams, seed_metrics: pd.DataFrame
) -> None:
    pd.testing.assert_frame_equal(compute_metrics(seed_inputs, seed_params), seed_metrics)
