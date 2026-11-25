"""Dashboard: KPI summary, sales trend, risk distribution (BP 6.2 #11-#13). ``view_inventory``."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_capability
from app.api.errors import error_responses, service_errors
from app.schemas.dashboard import DashboardSummaryOut, RiskDistributionOut
from app.schemas.inventory import SalesSeriesOut
from app.services import dashboard_service

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_capability("view_inventory"))],
)

FilterId = Annotated[int | None, Query(ge=1)]


@router.get("/summary", response_model=DashboardSummaryOut, responses=error_responses(404, 409))
def summary(
    db: DbSession, warehouse_id: FilterId = None, category_id: FilterId = None
) -> DashboardSummaryOut:
    """KPI tiles (FR-A1) from the latest snapshot."""
    with service_errors():
        return dashboard_service.summary(db, warehouse_id, category_id)


@router.get("/sales-trend", response_model=SalesSeriesOut, responses=error_responses(404, 409))
def sales_trend(
    db: DbSession,
    days: Annotated[int, Query(ge=7, le=90, description="Number of days ending at t0.")] = 90,
    category_id: FilterId = None,
    warehouse_id: FilterId = None,
) -> SalesSeriesOut:
    """Daily units and revenue across matching products, ending at t0, zero-filled."""
    with service_errors():
        return dashboard_service.sales_trend(db, days, category_id, warehouse_id)


@router.get(
    "/risk-distribution", response_model=RiskDistributionOut, responses=error_responses(404, 409)
)
def risk_distribution(
    db: DbSession, warehouse_id: FilterId = None, category_id: FilterId = None
) -> RiskDistributionOut:
    """Rows and products per risk class (all six classes always present)."""
    with service_errors():
        return dashboard_service.risk_distribution_view(db, warehouse_id, category_id)
