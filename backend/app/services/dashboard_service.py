"""Dashboard reads: KPI summary, sales trend, risk distribution (BP 6.2 #11-#13, FR-A1).

The KPIs come only from ``app.analytics.rollup.dashboard_kpis``; the class counts only from
``risk_distribution`` (rows) and ``rollup_by_product`` + ``risk_distribution`` (products). Nothing
is written.
"""

import pandas as pd
from sqlalchemy.orm import Session

from app.analytics.rollup import dashboard_kpis, risk_distribution, rollup_by_product
from app.repositories.products import ProductRepository
from app.schemas.dashboard import DashboardSummaryOut, RiskDistributionOut
from app.schemas.inventory import SalesSeriesOut
from app.services.inventory_service import ensure_exists, sales_window
from app.services.snapshot_context import load_snapshot_context

PRODUCT_COLUMNS = ("id", "sku", "supplier_id", "category_id", "unit_cost", "case_pack", "is_active")


def _active_products(session: Session) -> pd.DataFrame:
    rows = [dict(r) for r in ProductRepository(session).active_rows()]
    return pd.DataFrame(rows, columns=list(PRODUCT_COLUMNS))


def _scoped_rows(
    metrics: pd.DataFrame,
    products: pd.DataFrame,
    warehouse_id: int | None,
    category_id: int | None,
) -> pd.DataFrame:
    """The metric rows ``dashboard_kpis`` counts: active products, then the optional filters."""
    active = products.loc[products["is_active"].astype(bool)]
    if category_id is not None:
        active = active.loc[active["category_id"] == category_id]
    rows = metrics.loc[metrics["product_id"].isin(active["id"])]
    if warehouse_id is not None:
        rows = rows.loc[rows["warehouse_id"] == warehouse_id]
    return rows


def summary(
    session: Session, warehouse_id: int | None = None, category_id: int | None = None
) -> DashboardSummaryOut:
    ensure_exists(session, warehouse_id=warehouse_id, category_id=category_id)
    context = load_snapshot_context(session)
    kpis = dashboard_kpis(context.metrics, _active_products(session), warehouse_id, category_id)
    return DashboardSummaryOut(
        total_products=kpis["total_products"],
        total_units=kpis["total_units"],
        inventory_value=kpis["inventory_value"],
        low_stock_count=kpis["low_stock_count"],
        stockout_risk_count=kpis["stockout_risk_count"],
        slow_moving_count=kpis["slow_moving_count"],
        snapshot=context.meta,
    )


def sales_trend(
    session: Session,
    days: int,
    category_id: int | None = None,
    warehouse_id: int | None = None,
) -> SalesSeriesOut:
    ensure_exists(session, category_id=category_id, warehouse_id=warehouse_id)
    return sales_window(session, days, warehouse_id=warehouse_id, category_id=category_id)


def risk_distribution_view(
    session: Session, warehouse_id: int | None = None, category_id: int | None = None
) -> RiskDistributionOut:
    ensure_exists(session, warehouse_id=warehouse_id, category_id=category_id)
    context = load_snapshot_context(session)
    products = _active_products(session)
    kpis = dashboard_kpis(context.metrics, products, warehouse_id, category_id)
    rolled = rollup_by_product(_scoped_rows(context.metrics, products, warehouse_id, category_id))
    return RiskDistributionOut(
        rows=kpis["risk_distribution"],
        products=risk_distribution(rolled),
        snapshot=context.meta,
    )
