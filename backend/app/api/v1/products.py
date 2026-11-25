"""Products: list, detail and daily sales (BP 6.2 #8-#10). Capability ``view_inventory``."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_capability
from app.api.errors import error_responses, service_errors
from app.models.enums import RiskClass
from app.schemas.common import PageParams, page_params
from app.schemas.inventory import ProductDetailOut, ProductPage, ProductSalesOut
from app.services import inventory_service
from app.services.inventory_service import ProductFilters, SortKey, SortOrder

router = APIRouter(
    prefix="/products",
    tags=["products"],
    dependencies=[Depends(require_capability("view_inventory"))],
)

Paging = Annotated[PageParams, Depends(page_params)]
FilterId = Annotated[int | None, Query(ge=1)]
Days = Annotated[int, Query(ge=7, le=90, description="Number of days ending at t0 (7-90).")]

SORT_DESCRIPTION = (
    "`sku` (default), `name`, `risk` or `days_of_cover`. `risk` sorts by severity: with "
    "`order=asc` the most severe come first (STOCKOUT, CRITICAL, HIGH, MEDIUM, OVERSTOCK, LOW); "
    "ties break by days_of_cover ascending (nulls last), then sku. `days_of_cover` puts nulls last "
    "in both orders. Other ties break by sku ascending."
)


@router.get("", response_model=ProductPage, responses=error_responses(404, 409))
def list_products(
    db: DbSession,
    paging: Paging,
    category_id: FilterId = None,
    supplier_id: FilterId = None,
    warehouse_id: Annotated[
        int | None,
        Query(ge=1, description="Roll up only this warehouse's rows (one row per product)."),
    ] = None,
    risk_class: Annotated[
        list[RiskClass] | None, Query(description="Rolled-up class; repeatable.")
    ] = None,
    slow_moving: bool | None = None,
    q: Annotated[
        str | None,
        Query(min_length=1, max_length=50, description="Case-insensitive match on sku or name."),
    ] = None,
    sort: Annotated[SortKey, Query(description=SORT_DESCRIPTION)] = "sku",
    order: SortOrder = "asc",
) -> ProductPage:
    """Paged products rolled up from the latest snapshot (FR-A1, FR-A3)."""
    filters = ProductFilters(
        category_id=category_id,
        supplier_id=supplier_id,
        warehouse_id=warehouse_id,
        risk_classes=frozenset(r.value for r in risk_class or []),
        slow_moving=slow_moving,
        q=q,
    )
    with service_errors():
        return inventory_service.list_products(db, filters, sort, order, paging)


@router.get("/{product_id}", response_model=ProductDetailOut, responses=error_responses(404, 409))
def product_detail(db: DbSession, product_id: int) -> ProductDetailOut:
    """One product with its per-warehouse metrics, policies and roll-up."""
    with service_errors():
        return inventory_service.product_detail(db, product_id)


@router.get(
    "/{product_id}/sales", response_model=ProductSalesOut, responses=error_responses(404, 409)
)
def product_sales(
    db: DbSession,
    product_id: int,
    days: Days = 90,
    warehouse_id: FilterId = None,
) -> ProductSalesOut:
    """Daily units and revenue ending at t0, zero-filled, summed across warehouses unless one is
    given."""
    with service_errors():
        return inventory_service.product_sales(db, product_id, days, warehouse_id)
