"""Risk: stockout list, slow-moving list, risk detail (BP 6.2 #18-#20). ``view_inventory``.

The fixed paths are declared before ``/{product_id}`` so they are never read as an id.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_capability
from app.api.errors import error_responses, service_errors
from app.api.v1.analytics import STALE_409
from app.schemas.common import PageParams, page_params
from app.schemas.risk import RiskDetailOut, SlowMovingPage, StockoutRiskPage
from app.services import explain_service, risk_service

router = APIRouter(
    prefix="/risk",
    tags=["risk"],
    dependencies=[Depends(require_capability("view_inventory"))],
)

Paging = Annotated[PageParams, Depends(page_params)]
FilterId = Annotated[int | None, Query(ge=1)]


@router.get(
    "/stockout",
    response_model=StockoutRiskPage,
    responses=error_responses(404, 409, d409=STALE_409),
)
def stockout(
    db: DbSession, paging: Paging, warehouse_id: FilterId = None, category_id: FilterId = None
) -> StockoutRiskPage:
    """FR-C1: STOCKOUT, CRITICAL and HIGH rows of the latest snapshot, most severe first, then
    days_of_cover ascending (nulls last), then sku."""
    with service_errors():
        return risk_service.stockout_risk(db, warehouse_id, category_id, paging)


@router.get("/slow-moving", response_model=SlowMovingPage, responses=error_responses(404, 409))
def slow_moving(
    db: DbSession, paging: Paging, warehouse_id: FilterId = None, category_id: FilterId = None
) -> SlowMovingPage:
    """Slow-moving or dead-stock rows: dead stock first, then inventory_value descending, sku."""
    with service_errors():
        return risk_service.slow_moving(db, warehouse_id, category_id, paging)


@router.get(
    "/{product_id}",
    response_model=RiskDetailOut,
    responses=error_responses(404, 409, d409=STALE_409),
)
def risk_detail(
    db: DbSession,
    product_id: int,
    warehouse_id: Annotated[int, Query(ge=1, description="Warehouse of the row (required).")],
) -> RiskDetailOut:
    """FR-C2/C3: one row's risk inputs, rule trace and lead-time projection, recomputed and
    verified equal to the latest snapshot."""
    with service_errors():
        return explain_service.risk_detail(db, product_id, warehouse_id)
