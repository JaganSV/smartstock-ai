"""Snapshot rows: DB scales, ROUND_HALF_UP via Decimal, null mapping, integer types."""

from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
import pytest

from app.analytics.numeric import round_decimal
from app.analytics.snapshot import to_snapshot_rows

PRODUCT_METRIC_COLUMNS = {
    "product_id",
    "warehouse_id",
    "on_hand",
    "committed",
    "available",
    "incoming_in_lt",
    "ads_30",
    "ads_90",
    "demand_std_30",
    "lead_time_days",
    "safety_stock",
    "reorder_point",
    "days_of_cover",
    "reorder_qty",
    "risk_class",
    "risk_reason_code",
    "is_slow_moving",
    "is_dead_stock",
    "demand_trend_pct",
    "inventory_value",
}


def one(**over: Any) -> pd.DataFrame:
    base: dict[str, Any] = {
        "product_id": 1,
        "warehouse_id": 2,
        "on_hand": 120,
        "committed": 20,
        "available": 100,
        "incoming_in_lt": 0,
        "ads_30": 21.766666666666666,
        "ads_90": 20.977777777777778,
        "demand_std_30": 4.506907,
        "lead_time_days": 9,
        "safety_stock": 20,
        "reorder_point": 110,
        "days_of_cover": 4.594180704441042,
        "reorder_qty": 156,
        "risk_class": "HIGH",
        "risk_reason_code": "R3_BELOW_REORDER_POINT",
        "is_slow_moving": False,
        "is_dead_stock": False,
        "demand_trend": 0.25,
        "inventory_value": Decimal("12000.00"),
        # extra columns are ignored
        "sku": "SKU-001",
        "inventory_position": 100,
        "projected_stockout_day": pd.NA,
        "is_high_demand": True,
    }
    return pd.DataFrame([{**base, **over}])


def test_columns_are_exactly_the_product_metrics_columns() -> None:
    assert set(to_snapshot_rows(one())[0]) == PRODUCT_METRIC_COLUMNS


def test_four_dp_rounding_example_from_the_spec() -> None:
    row = to_snapshot_rows(one())[0]
    assert row["ads_30"] == Decimal("21.7667")  # 21.766666... -> 21.7667
    assert row["ads_90"] == Decimal("20.9778")
    assert row["demand_std_30"] == Decimal("4.5069")
    assert row["days_of_cover"] == Decimal("4.5942")
    for name in ("ads_30", "ads_90", "demand_std_30", "days_of_cover", "demand_trend_pct"):
        assert isinstance(row[name], Decimal)
        assert row[name].as_tuple().exponent == -4


def test_round_half_up_not_bankers_rounding() -> None:
    assert round_decimal(0.00005, 4) == Decimal("0.0001")
    assert round_decimal(0.00015, 4) == Decimal("0.0002")  # banker's would give 0.0002 / 0.0001
    assert round_decimal(2.5, 0) == Decimal("3")
    assert round_decimal(Decimal("1.00005"), 4) == Decimal("1.0001")
    assert round_decimal(-0.00005, 4) == Decimal("-0.0001")


def test_float_goes_through_its_shortest_repr_not_its_binary_expansion() -> None:
    # 1.00005 is stored as 1.0000500000000000611...; repr-based rounding gives 1.0001 either way,
    # but 2.675 (binary 2.67499999...) must round half-up on the decimal text: 2.68.
    assert round_decimal(2.675, 2) == Decimal("2.68")


def test_demand_trend_is_stored_as_a_ratio() -> None:
    row = to_snapshot_rows(one(demand_trend=0.25))[0]
    assert row["demand_trend_pct"] == Decimal("0.2500")  # +25% is 0.25, not 25


def test_nan_and_na_become_none() -> None:
    row = to_snapshot_rows(one(days_of_cover=np.nan, demand_trend=np.nan))[0]
    assert row["days_of_cover"] is None
    assert row["demand_trend_pct"] is None
    row = to_snapshot_rows(one(days_of_cover=None, demand_trend=None))[0]
    assert row["days_of_cover"] is None
    assert row["demand_trend_pct"] is None


def test_zero_is_not_null() -> None:
    row = to_snapshot_rows(one(days_of_cover=0.0, demand_trend=0.0))[0]
    assert row["days_of_cover"] == Decimal("0.0000")
    assert row["demand_trend_pct"] == Decimal("0.0000")


def test_money_has_two_decimal_places() -> None:
    row = to_snapshot_rows(one(inventory_value=Decimal("19688.5")))[0]
    assert row["inventory_value"] == Decimal("19688.50")
    assert row["inventory_value"].as_tuple().exponent == -2


@pytest.mark.parametrize(
    "name",
    [
        "product_id",
        "warehouse_id",
        "on_hand",
        "committed",
        "available",
        "incoming_in_lt",
        "lead_time_days",
        "safety_stock",
        "reorder_point",
        "reorder_qty",
    ],
)
def test_integers_stay_python_ints(name: str) -> None:
    frame = one().astype({name: "int64"})
    value = to_snapshot_rows(frame)[0][name]
    assert type(value) is int


def test_available_can_be_negative() -> None:
    assert to_snapshot_rows(one(available=-29))[0]["available"] == -29


def test_booleans_and_strings_are_plain_python() -> None:
    row = to_snapshot_rows(one(is_slow_moving=np.True_, is_dead_stock=np.False_))[0]
    assert row["is_slow_moving"] is True
    assert row["is_dead_stock"] is False
    assert type(row["risk_class"]) is str
    assert type(row["risk_reason_code"]) is str


def test_is_high_demand_is_not_persisted() -> None:
    assert "is_high_demand" not in to_snapshot_rows(one())[0]


def test_one_dict_per_row_in_order() -> None:
    frame = pd.concat([one(product_id=7), one(product_id=3)], ignore_index=True)
    assert [r["product_id"] for r in to_snapshot_rows(frame)] == [7, 3]


def test_empty_frame_gives_no_rows() -> None:
    assert to_snapshot_rows(one().iloc[0:0]) == []
