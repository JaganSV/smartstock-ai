"""Dashboard endpoints #11-#13 and the no-snapshot behaviour (BOB-P3-02a, AC-3.1b/c/d).

The canonical values are those of docs/evidence/p2_risk_distribution.md (seed 42, t0 2026-09-30).
Each is also checked against a direct SQL aggregation of the latest snapshot.
"""

from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import Engine, case, func, select
from sqlalchemy.orm import Session

from app.models import Product, ProductMetric, SalesDaily
from tests.integration.auth_helpers import USERNAMES, Api
from tests.integration.conftest import clean_analytics_outputs
from tests.integration.read_helpers import (
    CLASSES,
    T0,
    category_id,
    is_money,
    latest_snapshot,
    product_id,
    warehouse_id,
)

pytestmark = pytest.mark.integration

CANONICAL_SUMMARY = {
    "total_products": 50,
    "total_units": 73484,
    "inventory_value": "89944367.37",
    "low_stock_count": 7,
    "stockout_risk_count": 15,
    "slow_moving_count": 11,
}
CANONICAL_ROWS = {"LOW": 121, "OVERSTOCK": 11, "CRITICAL": 8, "HIGH": 4, "MEDIUM": 3, "STOCKOUT": 3}


def _get(api: Api, path: str, **params: Any) -> Any:
    return api.client.get(f"/api/v1{path}", params=params, headers=api.headers("executive"))


def _sql_summary(engine: Engine, snapshot_id: int) -> dict[str, Any]:
    """The KPIs straight from SQL: sums, then the most severe class per product via MIN(rank)."""
    rank = case(
        *((ProductMetric.risk_class == c, i) for i, c in enumerate(CLASSES)), else_=len(CLASSES)
    )
    with Session(engine) as session:
        units, value = session.execute(
            select(func.sum(ProductMetric.on_hand), func.sum(ProductMetric.inventory_value)).where(
                ProductMetric.snapshot_id == snapshot_id
            )
        ).one()
        per_product = (
            select(
                func.min(rank).label("worst"),
                func.bool_or(ProductMetric.is_slow_moving).label("slow"),
            )
            .where(ProductMetric.snapshot_id == snapshot_id)
            .group_by(ProductMetric.product_id)
            .subquery()
        )
        worst = [int(w) for w in session.scalars(select(per_product.c.worst))]
        slow = session.scalar(select(func.count()).where(per_product.c.slow.is_(True)))
        active = session.scalar(select(func.count()).where(Product.is_active.is_(True)))
    by_class = [CLASSES[w] for w in worst]
    return {
        "total_products": active,
        "total_units": int(units),
        "inventory_value": str(Decimal(value)),
        "low_stock_count": sum(c in {"HIGH", "MEDIUM"} for c in by_class),
        "stockout_risk_count": sum(c in {"STOCKOUT", "CRITICAL", "HIGH"} for c in by_class),
        "slow_moving_count": slow,
    }


# --- /dashboard/summary ---


def test_summary_matches_the_p2_evidence_and_direct_sql(read_api: Api) -> None:
    response = _get(read_api, "/dashboard/summary")
    assert response.status_code == 200
    body = response.json()
    snapshot = latest_snapshot(read_api.engine)
    kpis = {k: v for k, v in body.items() if k != "snapshot"}
    assert kpis == CANONICAL_SUMMARY
    assert kpis == _sql_summary(read_api.engine, snapshot.id)
    assert body["snapshot"] == {
        "snapshot_id": snapshot.id,
        "calculated_at": body["snapshot"]["calculated_at"],
        "data_as_of_date": T0.isoformat(),
        "verified": True,
    }
    assert is_money(body["inventory_value"])


def test_summary_warehouse_and_category_filters(read_api: Api) -> None:
    mum = warehouse_id(read_api.engine, "WH-MUM")
    snapshot_id = latest_snapshot(read_api.engine).id
    with Session(read_api.engine) as session:
        units = session.scalar(
            select(func.sum(ProductMetric.on_hand)).where(
                ProductMetric.snapshot_id == snapshot_id, ProductMetric.warehouse_id == mum
            )
        )
    by_warehouse = _get(read_api, "/dashboard/summary", warehouse_id=mum).json()
    assert by_warehouse["total_units"] == units and by_warehouse["total_products"] == 50

    sport = category_id(read_api.engine, "SPORT")
    with Session(read_api.engine) as session:
        in_sport = session.scalar(select(func.count()).where(Product.category_id == sport))
    by_category = _get(read_api, "/dashboard/summary", category_id=sport).json()
    assert by_category["total_products"] == in_sport
    assert by_category["total_units"] < CANONICAL_SUMMARY["total_units"]


# --- /dashboard/risk-distribution ---


def test_risk_distribution_rows_and_products(read_api: Api) -> None:
    body = _get(read_api, "/dashboard/risk-distribution").json()
    assert body["rows"] == CANONICAL_ROWS
    assert list(body["rows"]) == list(CLASSES) and list(body["products"]) == list(CLASSES)
    assert body["products"] == {
        "STOCKOUT": 3,
        "CRITICAL": 8,
        "HIGH": 4,
        "MEDIUM": 3,
        "OVERSTOCK": 11,
        "LOW": 21,
    }
    snapshot_id = latest_snapshot(read_api.engine).id
    with Session(read_api.engine) as session:
        sql_rows = dict(
            session.execute(
                select(ProductMetric.risk_class, func.count())
                .where(ProductMetric.snapshot_id == snapshot_id)
                .group_by(ProductMetric.risk_class)
            ).all()
        )
    assert body["rows"] == {c: sql_rows.get(c, 0) for c in CLASSES}
    assert body["snapshot"]["snapshot_id"] == snapshot_id


def test_risk_distribution_keeps_all_six_classes_when_filtered(read_api: Api) -> None:
    del_id = warehouse_id(read_api.engine, "WH-DEL")
    body = _get(read_api, "/dashboard/risk-distribution", warehouse_id=del_id).json()
    assert set(body["rows"]) == set(CLASSES) == set(body["products"])
    assert sum(body["rows"].values()) == 50 == sum(body["products"].values())
    assert body["rows"]["STOCKOUT"] == 0  # all three STOCKOUT rows are at WH-MUM


# --- /dashboard/sales-trend ---


def _sql_units(engine: Engine, start: Any, category: int | None = None) -> int:
    stmt = select(func.coalesce(func.sum(SalesDaily.units_sold), 0)).where(
        SalesDaily.sale_date >= start, SalesDaily.sale_date <= T0
    )
    if category is not None:
        stmt = stmt.join(Product, Product.id == SalesDaily.product_id).where(
            Product.category_id == category
        )
    with Session(engine) as session:
        return int(session.scalar(stmt) or 0)


def test_sales_trend_is_90_days_to_t0_and_sums_match_sql(read_api: Api) -> None:
    body = _get(read_api, "/dashboard/sales-trend").json()
    start = T0 - timedelta(days=89)
    assert body["end_date"] == T0.isoformat() and body["start_date"] == start.isoformat()
    assert len(body["series"]) == 90
    assert sum(p["units"] for p in body["series"]) == _sql_units(read_api.engine, start)
    sport = category_id(read_api.engine, "SPORT")
    filtered = _get(read_api, "/dashboard/sales-trend", category_id=sport, days=7).json()
    assert len(filtered["series"]) == 7
    assert sum(p["units"] for p in filtered["series"]) == _sql_units(
        read_api.engine, T0 - timedelta(days=6), sport
    )


# --- errors ---


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/dashboard/summary", {"warehouse_id": 99999}),
        ("/dashboard/summary", {"category_id": 99999}),
        ("/dashboard/risk-distribution", {"warehouse_id": 99999}),
        ("/dashboard/sales-trend", {"category_id": 99999}),
        ("/dashboard/sales-trend", {"warehouse_id": 99999}),
    ],
)
def test_unknown_filter_ids_give_404(read_api: Api, path: str, params: dict[str, int]) -> None:
    response = _get(read_api, path, **params)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/dashboard/summary", {"warehouse_id": "x"}),
        ("/dashboard/summary", {"category_id": 0}),
        ("/dashboard/sales-trend", {"days": 6}),
        ("/dashboard/sales-trend", {"days": 91}),
        ("/dashboard/risk-distribution", {"category_id": -1}),
    ],
)
def test_bad_parameters_give_422(read_api: Api, path: str, params: dict[str, Any]) -> None:
    response = _get(read_api, path, **params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("username", USERNAMES)
def test_every_role_can_read_the_dashboard(read_api: Api, username: str) -> None:
    headers = read_api.headers(username)
    for path in ("summary", "sales-trend", "risk-distribution"):
        response = read_api.client.get(f"/api/v1/dashboard/{path}", headers=headers)
        assert response.status_code == 200, (username, path)


# --- no snapshot yet (409 for snapshot-derived data; reference and sales still work) ---


@pytest.fixture
def no_snapshot(read_api: Api) -> Iterator[Api]:
    """Analytics tables emptied; ``read_api`` recalculates again for the next test."""
    clean_analytics_outputs(read_api.engine)
    yield read_api
    clean_analytics_outputs(read_api.engine)


def test_without_a_snapshot_derived_endpoints_give_409(no_snapshot: Api) -> None:
    pid = product_id(no_snapshot.engine, "SKU-004")
    for path in (
        "/dashboard/summary",
        "/dashboard/risk-distribution",
        "/products",
        f"/products/{pid}",
    ):
        response = _get(no_snapshot, path)
        assert response.status_code == 409, path
        error = response.json()["error"]
        assert error["code"] == "CONFLICT"
        assert error["message"] == "No analytics snapshot available. Run a recalculation."
        assert error["request_id"]


def test_without_a_snapshot_reference_and_sales_still_work(no_snapshot: Api) -> None:
    pid = product_id(no_snapshot.engine, "SKU-004")
    for path in ("/reference/categories", "/reference/warehouses", "/reference/suppliers"):
        assert _get(no_snapshot, path).status_code == 200, path
    sales = _get(no_snapshot, f"/products/{pid}/sales", days=7)
    trend = _get(no_snapshot, "/dashboard/sales-trend", days=7)
    assert sales.status_code == 200 and trend.status_code == 200
    # t0 falls back to max(sale_date) (ADR-012), which is the same date for seed 42.
    assert sales.json()["end_date"] == trend.json()["end_date"] == T0.isoformat()


def test_with_no_sales_data_at_all_the_series_give_409(
    no_snapshot: Api, empty_engine: Engine
) -> None:
    """No snapshot and an empty sales_daily: t0 cannot be derived, so 409 (never the wall clock).

    Runs last in this module; ``read_api`` re-seeds for any later test.
    """
    del empty_engine  # requested for its side effect: no seeded data and no analytics output
    response = _get(no_snapshot, "/dashboard/sales-trend")
    assert response.status_code == 409
    assert response.json()["error"]["message"] == "No sales data available."
