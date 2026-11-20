"""Roll-up and dashboard KPIs (BP 7.4, FR-A1)."""

from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from app.analytics.rollup import dashboard_kpis, risk_distribution, rollup_by_product


def row(product_id: int, wh: str, **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "product_id": product_id,
        "sku": f"SKU-{product_id:03d}",
        "warehouse_id": {"WH-BLR": 1, "WH-DEL": 2, "WH-MUM": 3}[wh],
        "warehouse_code": wh,
        "on_hand": 100,
        "committed": 10,
        "available": 90,
        "incoming_in_lt": 0,
        "inventory_value": Decimal("1000.00"),
        "ads_30": 9.0,
        "ads_90": 9.0,
        "risk_class": "LOW",
        "is_slow_moving": False,
        "is_dead_stock": False,
    }
    return {**base, **over}


def metrics(*rows: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def products(*specs: tuple[int, int, bool]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"id": pid, "category_id": cat, "is_active": active} for pid, cat, active in specs]
    )


# --- roll-up ---


def test_rollup_sums_the_additive_columns() -> None:
    out = rollup_by_product(
        metrics(
            row(1, "WH-BLR", on_hand=100, committed=10, available=90, incoming_in_lt=5),
            row(1, "WH-MUM", on_hand=50, committed=0, available=50, incoming_in_lt=7),
        )
    )
    r = out.iloc[0]
    assert (r["on_hand"], r["committed"], r["available"], r["incoming_in_lt"]) == (150, 10, 140, 12)
    assert r["inventory_value"] == Decimal("2000.00")
    assert r["ads_30"] == 18.0


def test_rollup_cover_is_recomputed_not_averaged() -> None:
    """WH-BLR: available 100, ADS 1 -> DoC 100.  WH-MUM: available 10, ADS 9 -> DoC 1.11.

    Average of the two ratios = (100 + 1.11) / 2 = 50.56. Recomputed: 110 / 10 = 11.0.
    """
    frame = metrics(
        row(1, "WH-BLR", available=100, ads_30=1.0),
        row(1, "WH-MUM", available=10, ads_30=9.0),
    )
    per_row = (frame["available"] / frame["ads_30"]).mean()
    out = rollup_by_product(frame)
    assert round(per_row, 2) == 50.56
    assert out["days_of_cover"][0] == 11.0
    assert out["days_of_cover"][0] != per_row


def test_rollup_cover_floors_negative_available_at_zero() -> None:
    out = rollup_by_product(
        metrics(
            row(1, "WH-BLR", available=-30, ads_30=5.0),
            row(1, "WH-MUM", available=10, ads_30=5.0),
        )
    )
    assert out["days_of_cover"][0] == 0.0  # max(0, -20) / 10


def test_rollup_cover_is_null_without_demand() -> None:
    out = rollup_by_product(metrics(row(1, "WH-BLR", ads_30=0.0), row(1, "WH-MUM", ads_30=0.0)))
    assert np.isnan(out["days_of_cover"][0])


def test_rollup_picks_the_most_severe_class_and_its_warehouse() -> None:
    out = rollup_by_product(
        metrics(
            row(1, "WH-BLR", risk_class="OVERSTOCK"),
            row(1, "WH-DEL", risk_class="CRITICAL"),
            row(1, "WH-MUM", risk_class="MEDIUM"),
        )
    )
    assert (out["risk_class"][0], out["risk_warehouse_code"][0]) == ("CRITICAL", "WH-DEL")


def test_rollup_severity_order_is_the_full_ladder() -> None:
    ladder = ["LOW", "OVERSTOCK", "MEDIUM", "HIGH", "CRITICAL", "STOCKOUT"]
    for worse_index in range(1, len(ladder)):
        out = rollup_by_product(
            metrics(
                row(1, "WH-BLR", risk_class=ladder[worse_index - 1]),
                row(1, "WH-MUM", risk_class=ladder[worse_index]),
            )
        )
        assert out["risk_class"][0] == ladder[worse_index]


def test_rollup_tie_goes_to_the_lowest_warehouse_code() -> None:
    out = rollup_by_product(
        metrics(
            row(1, "WH-MUM", risk_class="HIGH"),
            row(1, "WH-BLR", risk_class="HIGH"),
            row(1, "WH-DEL", risk_class="HIGH"),
        )
    )
    assert out["risk_warehouse_code"][0] == "WH-BLR"


def test_rollup_flags_are_any() -> None:
    out = rollup_by_product(
        metrics(
            row(1, "WH-BLR", is_slow_moving=True),
            row(1, "WH-MUM"),
            row(2, "WH-BLR", is_dead_stock=True),
            row(2, "WH-MUM"),
            row(3, "WH-BLR"),
        )
    ).set_index("product_id")
    assert out["is_slow_moving"].to_dict() == {1: True, 2: False, 3: False}
    assert out["is_dead_stock"].to_dict() == {1: False, 2: True, 3: False}


def test_rollup_has_one_row_per_product_sorted() -> None:
    out = rollup_by_product(metrics(row(2, "WH-BLR"), row(1, "WH-BLR"), row(2, "WH-MUM")))
    assert out["product_id"].tolist() == [1, 2]
    assert out["sku"].tolist() == ["SKU-001", "SKU-002"]


def test_rollup_of_nothing_is_empty() -> None:
    assert len(rollup_by_product(metrics(row(1, "WH-BLR")).iloc[0:0])) == 0


# --- KPIs ---


def _fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = metrics(
        row(1, "WH-BLR", risk_class="HIGH", on_hand=10, inventory_value=Decimal("100.10")),
        row(1, "WH-MUM", risk_class="LOW", on_hand=20, inventory_value=Decimal("200.20")),
        row(2, "WH-BLR", risk_class="MEDIUM", on_hand=30, inventory_value=Decimal("300.30")),
        row(2, "WH-MUM", risk_class="MEDIUM", on_hand=40, inventory_value=Decimal("400.40")),
        row(3, "WH-BLR", risk_class="STOCKOUT", on_hand=0, is_slow_moving=True),
        row(3, "WH-MUM", risk_class="OVERSTOCK", on_hand=50, is_slow_moving=True),
        row(4, "WH-BLR", risk_class="CRITICAL", on_hand=60),
        row(5, "WH-BLR", risk_class="LOW", on_hand=70),
    )
    prods = products((1, 10, True), (2, 10, True), (3, 20, True), (4, 20, True), (5, 20, False))
    return frame, prods


def test_kpis_without_filters() -> None:
    frame, prods = _fixture()
    kpis = dashboard_kpis(frame, prods)
    assert kpis["total_products"] == 4  # product 5 is inactive
    assert kpis["total_units"] == 10 + 20 + 30 + 40 + 0 + 50 + 60  # inactive product excluded
    # products 1-4: 100.10 + 200.20 + 300.30 + 400.40 + 1000 + 1000 + 1000 (inactive 5 excluded)
    assert kpis["inventory_value"] == Decimal("4001.00")
    assert kpis["low_stock_count"] == 2  # product 1 (HIGH), product 2 (MEDIUM)
    assert kpis["stockout_risk_count"] == 3  # 1 (HIGH), 3 (STOCKOUT), 4 (CRITICAL)
    assert kpis["slow_moving_count"] == 1  # product 3
    assert kpis["risk_distribution"] == {
        "STOCKOUT": 1,
        "CRITICAL": 1,
        "HIGH": 1,
        "MEDIUM": 2,
        "OVERSTOCK": 1,
        "LOW": 1,
    }


def test_kpi_inventory_value_is_a_two_dp_decimal_sum() -> None:
    frame = metrics(
        row(1, "WH-BLR", inventory_value=Decimal("0.10")),
        row(1, "WH-MUM", inventory_value=Decimal("0.20")),
    )
    kpis = dashboard_kpis(frame, products((1, 1, True)))
    assert kpis["inventory_value"] == Decimal("0.30")
    assert isinstance(kpis["inventory_value"], Decimal)


def test_kpis_with_a_warehouse_filter_use_only_that_warehouses_rows() -> None:
    frame, prods = _fixture()
    kpis = dashboard_kpis(frame, prods, warehouse_id=3)  # WH-MUM
    assert kpis["total_units"] == 20 + 40 + 50
    # product-level counts use WH-MUM rows only: 1 LOW, 2 MEDIUM, 3 OVERSTOCK
    assert kpis["low_stock_count"] == 1
    assert kpis["stockout_risk_count"] == 0
    assert kpis["slow_moving_count"] == 1
    assert sum(kpis["risk_distribution"].values()) == 3


def test_kpis_with_a_category_filter() -> None:
    frame, prods = _fixture()
    kpis = dashboard_kpis(frame, prods, category_id=10)
    assert kpis["total_products"] == 2
    assert kpis["total_units"] == 100
    assert kpis["low_stock_count"] == 2
    assert kpis["stockout_risk_count"] == 1


def test_kpis_with_both_filters() -> None:
    frame, prods = _fixture()
    kpis = dashboard_kpis(frame, prods, warehouse_id=1, category_id=20)
    assert kpis["total_products"] == 2  # products 3 and 4 (5 is inactive)
    assert kpis["total_units"] == 0 + 60
    assert kpis["stockout_risk_count"] == 2


def test_kpis_when_nothing_matches() -> None:
    frame, prods = _fixture()
    kpis = dashboard_kpis(frame, prods, category_id=999)
    assert kpis["total_products"] == 0
    assert kpis["total_units"] == 0
    assert kpis["inventory_value"] == Decimal("0.00")
    assert kpis["risk_distribution"] == dict.fromkeys(
        ["STOCKOUT", "CRITICAL", "HIGH", "MEDIUM", "OVERSTOCK", "LOW"], 0
    )


def test_risk_distribution_lists_all_six_classes_in_severity_order() -> None:
    out = risk_distribution(metrics(row(1, "WH-BLR", risk_class="HIGH")))
    assert list(out) == ["STOCKOUT", "CRITICAL", "HIGH", "MEDIUM", "OVERSTOCK", "LOW"]
    assert out["HIGH"] == 1
    assert sum(out.values()) == 1
