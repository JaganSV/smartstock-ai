"""build_metric_inputs: assembly, zero-filling, windowing, filtering and validation."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
import pytest

from app.analytics.errors import AnalyticsError, AnalyticsInputError
from app.analytics.inputs import build_metric_inputs
from app.analytics.params import AnalyticsParams
from app.analytics.types import INPUT_COLS
from tests.unit.analytics.helpers import T0

PARAMS = AnalyticsParams(t0=T0)
WINDOW_START = T0 - timedelta(days=89)  # 2026-07-03


def day(offset: int) -> date:
    return T0 + timedelta(days=offset)


class Frames:
    """Two products x two warehouses, one supplier; tests tweak a frame then build."""

    def __init__(self) -> None:
        self.products = pd.DataFrame(
            {
                "id": [1, 2],
                "sku": ["SKU-A", "SKU-B"],
                "supplier_id": [1, 1],
                "unit_cost": [Decimal("10.50"), Decimal("20.00")],
                "case_pack": [6, 12],
                "is_active": [True, True],
            }
        )
        self.warehouses = pd.DataFrame({"id": [1, 2], "code": ["WH-1", "WH-2"]})
        self.suppliers = pd.DataFrame(
            {"id": [1], "default_lead_time_days": [7], "min_order_qty": [24]}
        )
        pairs = [(p, w) for p in (1, 2) for w in (1, 2)]
        self.policies = pd.DataFrame(
            {
                "product_id": [p for p, _ in pairs],
                "warehouse_id": [w for _, w in pairs],
                "service_level": [Decimal("0.950")] * 4,
                "review_period_days": [14] * 4,
                "safety_stock_override": [None, 25, None, None],
                "lead_time_override_days": [None, None, 3, None],
            }
        )
        self.levels = pd.DataFrame(
            {
                "product_id": [p for p, _ in pairs],
                "warehouse_id": [w for _, w in pairs],
                "on_hand_qty": [100, 50, 0, 10],
                "committed_qty": [0, 60, 0, 10],
            }
        )
        self.incoming = pd.DataFrame(
            {
                "product_id": [1],
                "warehouse_id": [1],
                "quantity": [48],
                "expected_arrival_date": [day(5)],
                "status": ["OPEN"],
            }
        )
        self.sales = pd.DataFrame(
            {
                "product_id": [1, 1],
                "warehouse_id": [1, 1],
                "sale_date": [T0, day(-1)],
                "units_sold": [7, 3],
            }
        )

    def build(self) -> pd.DataFrame:
        return build_metric_inputs(
            self.products,
            self.warehouses,
            self.suppliers,
            self.policies,
            self.levels,
            self.incoming,
            self.sales,
            PARAMS,
        )


def row_of(frame: pd.DataFrame, product_id: int, warehouse_id: int) -> Any:
    match = frame[(frame["product_id"] == product_id) & (frame["warehouse_id"] == warehouse_id)]
    assert len(match) == 1
    return match.iloc[0]


def test_one_row_per_product_warehouse_with_documented_columns() -> None:
    out = Frames().build()
    assert len(out) == 4
    assert list(out.columns) == list(INPUT_COLS)
    assert out[["product_id", "warehouse_id"]].values.tolist() == [[1, 1], [1, 2], [2, 1], [2, 2]]


def test_values_are_joined_from_every_source() -> None:
    out = Frames().build()
    first = row_of(out, 1, 1)
    assert (first["sku"], first["warehouse_code"], first["supplier_id"]) == ("SKU-A", "WH-1", 1)
    assert first["unit_cost"] == Decimal("10.50")
    assert isinstance(first["unit_cost"], Decimal)
    assert (first["case_pack"], first["supplier_moq"], first["supplier_lead_time_days"]) == (
        6,
        24,
        7,
    )
    assert (first["service_level"], first["review_period_days"]) == (0.95, 14)
    assert (first["on_hand"], first["committed"]) == (100, 0)
    assert pd.isna(first["safety_stock_override"]) and pd.isna(first["lead_time_override_days"])
    assert row_of(out, 1, 2)["safety_stock_override"] == 25
    assert row_of(out, 2, 1)["lead_time_override_days"] == 3


def test_units_by_day_window_order_and_zero_fill() -> None:
    row = row_of(Frames().build(), 1, 1)
    units = row["units_by_day"]
    assert isinstance(units, np.ndarray) and units.dtype == np.int64
    assert len(units) == 90
    assert units[-1] == 7  # t0 is the newest day
    assert units[-2] == 3  # t0 - 1
    assert units[:-2].sum() == 0  # every missing day is zero
    assert row_of(Frames().build(), 2, 2)["units_by_day"].sum() == 0  # no sales at all


def test_window_is_t0_minus_89_through_t0_inclusive() -> None:
    f = Frames()
    f.sales = pd.DataFrame(
        {
            "product_id": [1] * 5,
            "warehouse_id": [1] * 5,
            "sale_date": [WINDOW_START - timedelta(days=1), WINDOW_START, T0, day(1), day(30)],
            "units_sold": [100, 11, 22, 200, 300],
        }
    )
    units = row_of(f.build(), 1, 1)["units_by_day"]
    assert units[0] == 11  # 2026-07-03, the oldest window day
    assert units[-1] == 22  # t0
    assert units.sum() == 33  # day before the window and the days after t0 are ignored


def test_duplicate_sales_rows_for_one_day_are_summed() -> None:
    f = Frames()
    f.sales = pd.DataFrame(
        {
            "product_id": [1, 1],
            "warehouse_id": [1, 1],
            "sale_date": [T0, T0],
            "units_sold": [4, 5],
        }
    )
    assert row_of(f.build(), 1, 1)["units_by_day"][-1] == 9


def test_sale_dates_may_be_strings_or_timestamps() -> None:
    f = Frames()
    f.sales = pd.DataFrame(
        {
            "product_id": [1, 1],
            "warehouse_id": [1, 1],
            "sale_date": ["2026-09-30", pd.Timestamp("2026-09-29")],
            "units_sold": [7, 3],
        }
    )
    units = row_of(f.build(), 1, 1)["units_by_day"]
    assert (units[-1], units[-2]) == (7, 3)


def test_open_incoming_only_open_orders_arriving_after_t0_sorted() -> None:
    f = Frames()
    f.incoming = pd.DataFrame(
        {
            "product_id": [1] * 7,
            "warehouse_id": [1] * 7,
            "quantity": [10, 20, 30, 40, 50, 60, 70],
            "expected_arrival_date": [day(9), day(2), day(3), day(0), day(-4), day(1), day(4)],
            "status": ["OPEN", "OPEN", "RECEIVED", "OPEN", "OPEN", "CANCELLED", "OPEN"],
        }
    )
    orders = row_of(f.build(), 1, 1)["open_incoming"]
    # RECEIVED / CANCELLED excluded; arrival = t0 and before t0 excluded; sorted by date
    assert orders == [(day(2), 20), (day(4), 70), (day(9), 10)]
    assert all(isinstance(q, int) for _, q in orders)
    assert row_of(f.build(), 2, 2)["open_incoming"] == []


def test_inactive_products_are_excluded() -> None:
    f = Frames()
    f.products["is_active"] = [True, False]
    out = f.build()
    assert set(out["product_id"]) == {1}
    assert len(out) == 2


def test_non_integer_inputs_are_normalised() -> None:
    f = Frames()
    f.levels["on_hand_qty"] = f.levels["on_hand_qty"].astype(float)
    f.products["unit_cost"] = [10.5, 20.0]  # floats from a loose caller
    out = f.build()
    assert out["on_hand"].dtype == np.dtype("int64")
    assert row_of(out, 1, 1)["unit_cost"] == Decimal("10.5")


# --- validation ---


def test_missing_policy_raises_with_the_offending_key() -> None:
    f = Frames()
    f.policies = f.policies.iloc[:3]  # drops product 2 @ warehouse 2
    with pytest.raises(AnalyticsInputError) as info:
        f.build()
    assert info.value.keys == ["product_id=2,warehouse_id=2"]
    assert "missing inventory policy" in str(info.value)
    assert info.value.code == "ANALYTICS_INPUT_ERROR"
    assert isinstance(info.value, AnalyticsError)


def test_missing_level_raises_with_the_offending_key() -> None:
    f = Frames()
    f.levels = f.levels[f.levels["warehouse_id"] != 2]
    with pytest.raises(AnalyticsInputError) as info:
        f.build()
    assert info.value.keys == ["product_id=1,warehouse_id=2", "product_id=2,warehouse_id=2"]
    assert "missing inventory level" in str(info.value)


@pytest.mark.parametrize("frame", ["levels", "policies"])
def test_duplicate_product_warehouse_raises(frame: str) -> None:
    f = Frames()
    setattr(f, frame, pd.concat([getattr(f, frame), getattr(f, frame).iloc[[0]]]))
    with pytest.raises(AnalyticsInputError) as info:
        f.build()
    assert info.value.keys == ["product_id=1,warehouse_id=1"]
    assert "duplicate key" in str(info.value)


@pytest.mark.parametrize(
    ("frame", "column"),
    [
        ("levels", "on_hand_qty"),
        ("levels", "committed_qty"),
        ("incoming", "quantity"),
        ("sales", "units_sold"),
    ],
)
def test_negative_quantities_raise(frame: str, column: str) -> None:
    f = Frames()
    getattr(f, frame).loc[0, column] = -1
    with pytest.raises(AnalyticsInputError) as info:
        f.build()
    assert info.value.keys == ["product_id=1,warehouse_id=1"]
    assert f"negative {column}" in str(info.value)


def test_missing_columns_raise() -> None:
    f = Frames()
    f.levels = f.levels.drop(columns="committed_qty")
    with pytest.raises(AnalyticsInputError) as info:
        f.build()
    assert info.value.keys == ["committed_qty"]


def test_unknown_supplier_raises() -> None:
    f = Frames()
    f.products["supplier_id"] = [1, 99]
    with pytest.raises(AnalyticsInputError) as info:
        f.build()
    assert info.value.keys == ["SKU-B"]


def test_error_messages_carry_keys_not_data_dumps() -> None:
    f = Frames()
    f.levels.loc[0, "on_hand_qty"] = -5
    with pytest.raises(AnalyticsInputError) as info:
        f.build()
    assert "-5" not in str(info.value)
    assert len(str(info.value)) < 120


def test_error_message_truncates_long_key_lists() -> None:
    err = AnalyticsInputError("too many", [f"k{i:02d}" for i in range(25)])
    assert "(+15 more)" in str(err)
    assert len(err.keys) == 25


def test_no_policy_rows_at_all_lists_every_pair() -> None:
    f = Frames()
    f.policies = f.policies.iloc[0:0]
    with pytest.raises(AnalyticsInputError) as info:
        f.build()
    assert len(info.value.keys) == 4


def test_empty_sales_and_incoming_frames_are_allowed() -> None:
    f = Frames()
    f.sales = f.sales.iloc[0:0]
    f.incoming = f.incoming.iloc[0:0]
    out = f.build()
    assert all(u.sum() == 0 for u in out["units_by_day"])
    assert all(o == [] for o in out["open_incoming"])


def test_input_frames_are_not_mutated() -> None:
    f = Frames()
    before = {name: getattr(f, name).copy() for name in ("levels", "policies", "sales")}
    f.build()
    for name, frame in before.items():
        pd.testing.assert_frame_equal(getattr(f, name), frame)
