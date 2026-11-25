"""Analytics: metrics, explanations, recalculation, snapshot history (BP 6.2 #14-#17).

Capability ``view_inventory`` for every route; ``POST /recalculate`` also needs
``recalculate_analytics`` (ADMIN).
"""

import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import DbSession, require_capability
from app.api.errors import error_responses, service_errors
from app.models.enums import RiskClass
from app.models.governance import User
from app.schemas.analytics import ExplainOut, MetricPage, RecalculateOut, SnapshotOut
from app.schemas.common import Page, PageParams, page_params
from app.services import analytics_service, explain_service, risk_service
from app.services.analytics_service import AuditContext, RecalculationService
from app.services.errors import NoDataError, RecalculationError, RecalculationLockedError
from app.services.risk_service import MetricFilters, MetricSortKey, SortOrder

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_capability("view_inventory"))],
)

Paging = Annotated[PageParams, Depends(page_params)]
FilterId = Annotated[int | None, Query(ge=1)]
RequiredWarehouse = Annotated[int, Query(ge=1, description="Warehouse of the row (required).")]
Admin = Annotated[User, Depends(require_capability("recalculate_analytics"))]

STALE_409 = (
    "No analytics snapshot available, or the underlying data has changed since the snapshot "
    "(details.fields names the changed metrics). Run a recalculation."
)
METRIC_SORT_DESCRIPTION = (
    "`sku` (default), `risk` or `days_of_cover`. `risk` with `order=asc` puts the most severe "
    "first, ties by days_of_cover ascending (nulls last), then sku. `days_of_cover` puts nulls "
    "last in both orders. Remaining ties break by sku, then warehouse code."
)
UNSAFE_LABEL_CHARS = re.compile(r"[^a-z0-9_-]")


def triggered_by_label(username: str) -> str:
    """``api:<username>`` from the authenticated user, kept within ``[a-z0-9_:-]``."""
    return "api:" + UNSAFE_LABEL_CHARS.sub("-", username.lower())


@router.get("/metrics", response_model=MetricPage, responses=error_responses(404, 409))
def metrics(
    db: DbSession,
    paging: Paging,
    snapshot_id: Annotated[
        int | None, Query(ge=1, description="Snapshot to read (default: the latest).")
    ] = None,
    warehouse_id: FilterId = None,
    category_id: FilterId = None,
    risk_class: Annotated[list[RiskClass] | None, Query(description="Repeatable.")] = None,
    slow_moving: bool | None = None,
    dead_stock: bool | None = None,
    sort: Annotated[MetricSortKey, Query(description=METRIC_SORT_DESCRIPTION)] = "sku",
    order: SortOrder = "asc",
) -> MetricPage:
    """Product x warehouse rows of a snapshot (FR-B5)."""
    filters = MetricFilters(
        warehouse_id=warehouse_id,
        category_id=category_id,
        risk_classes=frozenset(r.value for r in risk_class or []),
        slow_moving=slow_moving,
        dead_stock=dead_stock,
    )
    with service_errors():
        return risk_service.list_metrics(db, snapshot_id, filters, sort, order, paging)


@router.get(
    "/metrics/{product_id}/explain",
    response_model=ExplainOut,
    responses=error_responses(404, 409, d409=STALE_409),
)
def explain(db: DbSession, product_id: int, warehouse_id: RequiredWarehouse) -> ExplainOut:
    """Formula, inputs and result of every metric of one row, recomputed and verified equal to
    the latest snapshot (FR-B6)."""
    with service_errors():
        return explain_service.explain(db, product_id, warehouse_id)


@router.post(
    "/recalculate",
    status_code=201,
    response_model=RecalculateOut,
    responses=error_responses(
        403, 409, d409="A recalculation is already running, or there is no sales data."
    ),
)
def recalculate(db: DbSession, request: Request, user: Admin) -> RecalculateOut:
    """Run the recalculation now (synchronous, under the advisory lock) and audit it."""
    context = AuditContext(
        user_id=user.id,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
    )
    try:
        result = RecalculationService(db).run(triggered_by_label(user.username), context)
    except RecalculationLockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NoDataError:
        raise HTTPException(status_code=409, detail="No sales data available.") from None
    except RecalculationError as exc:
        logger.error("API recalculation failed (%s)", exc.code)
        raise HTTPException(status_code=500, detail="Recalculation failed.") from None
    return RecalculateOut(
        snapshot_id=result.snapshot_id,
        data_as_of_date=result.t0,
        row_count=result.row_count,
        risk_distribution=result.risk_distribution,
        duration_ms=result.duration_ms,
    )


@router.get("/snapshots", response_model=Page[SnapshotOut])
def snapshots(db: DbSession, paging: Paging) -> Page[SnapshotOut]:
    """Snapshot history, newest first, with row counts and per-class counts."""
    return analytics_service.list_snapshots(db, paging)
