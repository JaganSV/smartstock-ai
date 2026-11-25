"""Product endpoints #8-#10 (BOB-P3-02a): list, detail, sales series, high-demand flag source.

Seed 42 with one recalculation (``read_api``). Expected values come from the database itself or
from docs/evidence/p2_risk_distribution.md, never from the code under test.
"""

from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import delete, func, insert, literal, select
from sqlalchemy.orm import Session

from app.models import InventoryPolicy, MetricSnapshot, Product, ProductMetric, SalesDaily
from app.models.enums import RISK_RANK
from tests.integration.auth_helpers import Api
from tests.integration.read_helpers import (
    T0,
    category_id,
    is_money,
    latest_snapshot,
    product_id,
    supplier_id,
    warehouse_id,
)

pytestmark = pytest.mark.integration

PRODUCTS = "/api/v1/products"


def _get(api: Api, path: str, **params: Any) -> Any:
    return api.client.get(path, params=params, headers=api.headers("analyst"))


def _all(api: Api, **params: Any) -> list[dict[str, Any]]:
    response = _get(api, PRODUCTS, page_size=100, **params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == len(body["items"])
    return list(body["items"])


def _rolled_classes(api: Api) -> dict[str, str]:
    """sku -> most severe class, computed here from the raw snapshot rows."""
    snapshot_id = latest_snapshot(api.engine).id
    with Session(api.engine) as session:
        rows = session.execute(
            select(Product.sku, ProductMetric.risk_class)
            .join(Product, Product.id == ProductMetric.product_id)
            .where(ProductMetric.snapshot_id == snapshot_id)
        ).all()
    worst: dict[str, str] = {}
    for sku, risk in rows:
        if sku not in worst or RISK_RANK[risk] < RISK_RANK[worst[sku]]:
            worst[sku] = risk
    return worst


# --- GET /products ---


def test_list_has_50_products_typed_money_and_snapshot_meta(read_api: Api) -> None:
    response = _get(read_api, PRODUCTS)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 50 and body["page"] == 1 and body["page_size"] == 25
    assert len(body["items"]) == 25
    snapshot = latest_snapshot(read_api.engine)
    assert body["snapshot"]["snapshot_id"] == snapshot.id
    assert body["snapshot"]["data_as_of_date"] == T0.isoformat()
    assert body["snapshot"]["verified"] is True
    item = body["items"][0]
    assert is_money(item["inventory_value"])
    assert isinstance(item["ads_30"], float | int) and isinstance(item["on_hand"], int)
    assert item["risk_class"] in RISK_RANK


def test_default_sort_is_sku_ascending_and_pages_continue(read_api: Api) -> None:
    first = _get(read_api, PRODUCTS, page=1, page_size=20).json()["items"]
    third = _get(read_api, PRODUCTS, page=3, page_size=20).json()
    assert [i["sku"] for i in first] == [f"SKU-{n:03d}" for n in range(1, 21)]
    assert len(third["items"]) == 10 and third["total"] == 50


def test_risk_class_filter_returns_exactly_the_rolled_up_classes(read_api: Api) -> None:
    items = _all(read_api, risk_class=["STOCKOUT", "CRITICAL"])
    expected = {s for s, c in _rolled_classes(read_api).items() if c in {"STOCKOUT", "CRITICAL"}}
    assert {i["sku"] for i in items} == expected
    assert len(expected) == 11  # 3 STOCKOUT + 8 CRITICAL products (P2 evidence)


def test_warehouse_filter_rolls_up_that_warehouse_only(read_api: Api) -> None:
    mum = warehouse_id(read_api.engine, "WH-MUM")
    items = _all(read_api, warehouse_id=mum)
    assert len(items) == 50
    assert {i["risk_warehouse_code"] for i in items} == {"WH-MUM"}
    snapshot_id = latest_snapshot(read_api.engine).id
    with Session(read_api.engine) as session:
        on_hand = session.scalar(
            select(ProductMetric.on_hand).where(
                ProductMetric.snapshot_id == snapshot_id,
                ProductMetric.warehouse_id == mum,
                ProductMetric.product_id == product_id(read_api.engine, "SKU-004"),
            )
        )
    assert next(i for i in items if i["sku"] == "SKU-004")["on_hand"] == on_hand


def test_category_and_supplier_filters(read_api: Api) -> None:
    sport = category_id(read_api.engine, "SPORT")
    assert {i["category_code"] for i in _all(read_api, category_id=sport)} == {"SPORT"}
    sup_a = supplier_id(read_api.engine, "SUP-A")
    assert {i["supplier_code"] for i in _all(read_api, supplier_id=sup_a)} == {"SUP-A"}


def test_slow_moving_filter_matches_the_kpi(read_api: Api) -> None:
    slow = _all(read_api, slow_moving="true")
    assert len(slow) == 11 and all(i["is_slow_moving"] for i in slow)
    assert len(_all(read_api, slow_moving="false")) == 39


def test_q_is_a_case_insensitive_match_on_sku_or_name(read_api: Api) -> None:
    items = _all(read_api, q="sku-00")
    assert [i["sku"] for i in items] == [f"SKU-00{n}" for n in range(1, 10)]
    by_name = _all(read_api, q="yoga MAT")
    assert [i["sku"] for i in by_name] == ["SKU-004"]


@pytest.mark.parametrize("q", ["%_'", "%", "_", "\\", "' OR 1=1 --"])
def test_q_wildcards_and_quotes_are_literal_and_safe(read_api: Api, q: str) -> None:
    """``%`` and ``_`` are escaped (else they would match every product); quotes are bound."""
    response = _get(read_api, PRODUCTS, q=q)
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_sort_by_risk_puts_the_most_severe_first(read_api: Api) -> None:
    items = _all(read_api, sort="risk")
    assert [i["sku"] for i in items[:3]] == ["SKU-001", "SKU-002", "SKU-003"]
    ranks = [RISK_RANK[i["risk_class"]] for i in items]
    assert ranks == sorted(ranks)
    for a, b in zip(items, items[1:], strict=False):  # ties: days_of_cover asc (nulls last), sku
        if a["risk_class"] == b["risk_class"] and None not in (
            a["days_of_cover"],
            b["days_of_cover"],
        ):
            assert (a["days_of_cover"], a["sku"]) <= (b["days_of_cover"], b["sku"])
    descending = _all(read_api, sort="risk", order="desc")
    assert descending[0]["risk_class"] == "LOW" and descending[-1]["risk_class"] == "STOCKOUT"


@pytest.mark.parametrize("order", ["asc", "desc"])
def test_days_of_cover_sort_puts_nulls_last(read_api: Api, order: str) -> None:
    blr = warehouse_id(read_api.engine, "WH-BLR")  # dead-stock rows there have ADS30 = 0
    items = _all(read_api, warehouse_id=blr, sort="days_of_cover", order=order)
    covers = [i["days_of_cover"] for i in items]
    nulls = covers.count(None)
    assert nulls >= 3
    assert covers[-nulls:] == [None] * nulls
    values = covers[:-nulls]
    assert values == sorted(values, reverse=order == "desc")


def test_name_sort(read_api: Api) -> None:
    names = [i["name"] for i in _all(read_api, sort="name")]
    assert names == sorted(names)


@pytest.mark.parametrize(
    "params",
    [
        {"page_size": 101},
        {"page": 0},
        {"risk_class": "SEVERE"},
        {"risk_class": "stockout"},
        {"sort": "price"},
        {"order": "up"},
        {"category_id": "abc"},
        {"category_id": 0},
        {"q": ""},
        {"q": "x" * 51},
    ],
)
def test_invalid_parameters_give_422(read_api: Api, params: dict[str, Any]) -> None:
    response = _get(read_api, PRODUCTS, **params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["request_id"]


@pytest.mark.parametrize("key", ["category_id", "supplier_id", "warehouse_id"])
def test_unknown_filter_ids_give_404_not_an_empty_list(read_api: Api, key: str) -> None:
    response = _get(read_api, PRODUCTS, **{key: 99999})
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND" and key in error["message"] and error["request_id"]


# --- GET /products/{id} ---


def test_detail_of_sku_004_matches_product_metrics(read_api: Api) -> None:
    pid = product_id(read_api.engine, "SKU-004")
    response = _get(read_api, f"{PRODUCTS}/{pid}")
    assert response.status_code == 200
    body = response.json()
    assert body["product"]["sku"] == "SKU-004"
    assert is_money(body["product"]["unit_cost"]) and is_money(body["product"]["unit_price"])
    assert set(body["product"]["category"]) == {"id", "code", "name"}
    assert set(body["product"]["supplier"]) == {
        "id",
        "code",
        "name",
        "default_lead_time_days",
        "min_order_qty",
    }
    assert [w["warehouse_code"] for w in body["warehouses"]] == ["WH-BLR", "WH-DEL", "WH-MUM"]
    mum = next(w for w in body["warehouses"] if w["warehouse_code"] == "WH-MUM")
    assert mum["risk_class"] == "CRITICAL"

    snapshot = latest_snapshot(read_api.engine)
    with Session(read_api.engine) as session:
        stored = session.scalars(
            select(ProductMetric).where(
                ProductMetric.snapshot_id == snapshot.id,
                ProductMetric.product_id == pid,
                ProductMetric.warehouse_id == mum["warehouse_id"],
            )
        ).one()
        policy = session.scalars(
            select(InventoryPolicy).where(
                InventoryPolicy.product_id == pid,
                InventoryPolicy.warehouse_id == mum["warehouse_id"],
            )
        ).one()
    for field in (
        "on_hand",
        "committed",
        "available",
        "incoming_in_lt",
        "safety_stock",
        "reorder_point",
        "reorder_qty",
        "risk_class",
        "risk_reason_code",
        "is_slow_moving",
    ):
        assert mum[field] == getattr(stored, field), field
    for field in ("ads_30", "ads_90", "days_of_cover"):
        assert Decimal(str(mum[field])) == getattr(stored, field), field
    assert mum["inventory_value"] == str(stored.inventory_value)
    assert mum["policy"] == {
        "service_level": float(policy.service_level),
        "review_period_days": policy.review_period_days,
        "safety_stock_override": policy.safety_stock_override,
        "lead_time_override_days": policy.lead_time_override_days,
    }
    rollup = body["rollup"]
    assert rollup["risk_class"] == "CRITICAL" and rollup["risk_warehouse_code"] == "WH-MUM"
    assert rollup["on_hand"] == sum(w["on_hand"] for w in body["warehouses"])
    assert body["snapshot"]["snapshot_id"] == snapshot.id


def test_detail_of_an_unknown_product_is_404_and_bad_id_is_422(read_api: Api) -> None:
    assert _get(read_api, f"{PRODUCTS}/99999").json()["error"]["code"] == "NOT_FOUND"
    assert _get(read_api, f"{PRODUCTS}/abc").status_code == 422


# --- GET /products/{id}/sales ---


def _sql_units(api: Api, pid: int, start: Any, wid: int | None = None) -> tuple[int, Decimal]:
    stmt = select(
        func.coalesce(func.sum(SalesDaily.units_sold), 0),
        func.coalesce(func.sum(SalesDaily.revenue), 0),
    ).where(SalesDaily.product_id == pid, SalesDaily.sale_date >= start, SalesDaily.sale_date <= T0)
    if wid is not None:
        stmt = stmt.where(SalesDaily.warehouse_id == wid)
    with Session(api.engine) as session:
        units, revenue = session.execute(stmt).one()
    return int(units), Decimal(revenue)


def test_sales_series_is_90_days_ending_at_t0_and_sums_match_sql(read_api: Api) -> None:
    pid = product_id(read_api.engine, "SKU-004")
    body = _get(read_api, f"{PRODUCTS}/{pid}/sales").json()
    series = body["series"]
    assert body["product_id"] == pid and body["warehouse_id"] is None
    assert body["end_date"] == T0.isoformat() and len(series) == 90
    start = T0 - timedelta(days=89)
    assert body["start_date"] == start.isoformat() == series[0]["date"]
    assert [p["date"] for p in series] == [
        (start + timedelta(days=n)).isoformat() for n in range(90)
    ]
    units, revenue = _sql_units(read_api, pid, start)
    assert sum(p["units"] for p in series) == units
    assert sum(Decimal(p["revenue"]) for p in series) == revenue
    assert all(is_money(p["revenue"]) for p in series)


def test_sales_series_7_days_and_warehouse_filter(read_api: Api) -> None:
    pid = product_id(read_api.engine, "SKU-004")
    mum = warehouse_id(read_api.engine, "WH-MUM")
    week = _get(read_api, f"{PRODUCTS}/{pid}/sales", days=7).json()
    assert len(week["series"]) == 7 and week["series"][-1]["date"] == T0.isoformat()
    one = _get(read_api, f"{PRODUCTS}/{pid}/sales", warehouse_id=mum).json()
    assert one["warehouse_id"] == mum
    assert (
        sum(p["units"] for p in one["series"])
        == _sql_units(read_api, pid, T0 - timedelta(days=89), mum)[0]
    )


def test_sales_series_is_zero_filled(read_api: Api) -> None:
    """SKU-021 at WH-BLR is dead stock: no sales in the last 30 days, yet every day is present."""
    pid = product_id(read_api.engine, "SKU-021")
    blr = warehouse_id(read_api.engine, "WH-BLR")
    body = _get(read_api, f"{PRODUCTS}/{pid}/sales", days=30, warehouse_id=blr).json()
    assert len(body["series"]) == 30
    assert all(p["units"] == 0 and p["revenue"] == "0.00" for p in body["series"])


@pytest.mark.parametrize("params", [{"days": 6}, {"days": 91}, {"warehouse_id": "x"}])
def test_sales_bad_parameters_give_422(read_api: Api, params: dict[str, Any]) -> None:
    pid = product_id(read_api.engine, "SKU-004")
    assert _get(read_api, f"{PRODUCTS}/{pid}/sales", **params).status_code == 422


def test_sales_unknown_product_or_warehouse_give_404(read_api: Api) -> None:
    pid = product_id(read_api.engine, "SKU-004")
    assert _get(read_api, f"{PRODUCTS}/99999/sales").status_code == 404
    assert _get(read_api, f"{PRODUCTS}/{pid}/sales", warehouse_id=99999).status_code == 404


# --- is_high_demand comes from the snapshot's own params_json ---


@pytest.fixture
def strict_spike_snapshot(read_api: Api) -> Iterator[int]:
    """A newer copy of the latest snapshot whose params_json has spike_threshold 0.99."""
    original = latest_snapshot(read_api.engine)
    with Session(read_api.engine) as session, session.begin():
        copy = MetricSnapshot(
            calculated_at=original.calculated_at + timedelta(minutes=1),
            data_as_of_date=original.data_as_of_date,
            params_json={**original.params_json, "spike_threshold": 0.99},
            triggered_by="test",
        )
        session.add(copy)
        session.flush()
        columns = [
            c for c in ProductMetric.__table__.columns if c.name not in {"id", "snapshot_id"}
        ]
        session.execute(
            insert(ProductMetric).from_select(
                ["snapshot_id", *(c.name for c in columns)],
                select(literal(copy.id).label("snapshot_id"), *columns).where(
                    ProductMetric.snapshot_id == original.id
                ),
            )
        )
        copy_id = copy.id
    yield copy_id
    with Session(read_api.engine) as session, session.begin():
        session.execute(delete(ProductMetric).where(ProductMetric.snapshot_id == copy_id))
        session.execute(delete(MetricSnapshot).where(MetricSnapshot.id == copy_id))


def _blr(api: Api, sku: str) -> dict[str, Any]:
    pid = product_id(api.engine, sku)
    body = _get(api, f"{PRODUCTS}/{pid}").json()
    return {
        "snapshot_id": body["snapshot"]["snapshot_id"],
        "row": next(w for w in body["warehouses"] if w["warehouse_code"] == "WH-BLR"),
        "rollup": body["rollup"],
    }


def _stored_trend(api: Api, sku: str, snapshot_id: int) -> Decimal:
    with Session(api.engine) as session:
        trend = session.scalar(
            select(ProductMetric.demand_trend_pct).where(
                ProductMetric.snapshot_id == snapshot_id,
                ProductMetric.product_id == product_id(api.engine, sku),
                ProductMetric.warehouse_id == warehouse_id(api.engine, "WH-BLR"),
            )
        )
    assert trend is not None
    return trend


def test_is_high_demand_uses_the_snapshots_spike_threshold(read_api: Api) -> None:
    """HIGH_DEMAND seed band at WH-BLR: both rows are flagged at the default threshold 0.30."""
    for sku in ("SKU-009", "SKU-011"):
        before = _blr(read_api, sku)
        assert before["row"]["is_high_demand"] is True, sku
        assert before["rollup"]["is_high_demand"] is True, sku


def test_a_snapshot_with_a_stricter_threshold_changes_the_flag(
    read_api: Api, strict_spike_snapshot: int
) -> None:
    """With spike_threshold 0.99 in the newer snapshot's params_json, only trends >= 0.99 stay
    flagged: SKU-011 (trend ~0.60) turns off, SKU-009 (trend ~1.34) stays on."""
    assert Decimal("0.30") <= _stored_trend(read_api, "SKU-011", strict_spike_snapshot) < 1
    assert _stored_trend(read_api, "SKU-009", strict_spike_snapshot) >= Decimal("0.99")
    off = _blr(read_api, "SKU-011")
    assert off["snapshot_id"] == strict_spike_snapshot
    assert off["row"]["is_high_demand"] is False
    assert off["rollup"]["is_high_demand"] is False
    assert _all(read_api, q="SKU-011")[0]["is_high_demand"] is False
    on = _blr(read_api, "SKU-009")
    assert on["row"]["is_high_demand"] is True
    assert on["rollup"]["is_high_demand"] is True
