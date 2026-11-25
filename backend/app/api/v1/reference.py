"""Reference lists (BP 6.2 #5-#7). Capability ``view_inventory``; not paginated."""

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, require_capability
from app.schemas.inventory import CategoryOut, SupplierOut, WarehouseOut
from app.services import inventory_service

router = APIRouter(
    prefix="/reference",
    tags=["reference"],
    dependencies=[Depends(require_capability("view_inventory"))],
)


@router.get("/categories", response_model=list[CategoryOut])
def categories(db: DbSession) -> list[CategoryOut]:
    """All categories, sorted by code."""
    return inventory_service.list_categories(db)


@router.get("/warehouses", response_model=list[WarehouseOut])
def warehouses(db: DbSession) -> list[WarehouseOut]:
    """All warehouses, sorted by code."""
    return inventory_service.list_warehouses(db)


@router.get("/suppliers", response_model=list[SupplierOut])
def suppliers(db: DbSession) -> list[SupplierOut]:
    """All suppliers, sorted by code. Contact e-mail addresses are not included."""
    return inventory_service.list_suppliers(db)
