"""Read-only inventory reads: reference lists, products, detail, sales series (BP 6.2 #5-#10).

Every number comes from the latest snapshot through ``app.analytics.rollup.rollup_by_product`` or
from raw ``sales_daily`` rows. Nothing is written: no commits, no audit rows.
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

import pandas as pd
from sqlalchemy.orm import Session

from app.analytics.rollup import rollup_by_product
from app.models.enums import RISK_RANK
from app.models.reference import Category, Supplier, Warehouse
from app.repositories.inventory import InventoryPolicyRepository
from app.repositories.products import ProductRepository
from app.repositories.reference import (
    CategoryRepository,
    SupplierRepository,
    WarehouseRepository,
)
from app.repositories.sales import SalesRepository
from app.schemas.common import PageParams
from app.schemas.inventory import (
    CategoryOut,
    CategoryRef,
    PolicyOut,
    ProductDetailOut,
    ProductOut,
    ProductPage,
    ProductSalesOut,
    ProductSummaryOut,
    SalesPoint,
    SalesSeriesOut,
    SupplierOut,
    SupplierRef,
    WarehouseMetricOut,
    WarehouseOut,
)
from app.services.errors import NoSalesDataError, NotFoundError
from app.services.snapshot_context import (
    SnapshotContext,
    latest_snapshot_t0,
    load_snapshot_context,
)

SortKey = Literal["sku", "name", "risk", "days_of_cover"]
SortOrder = Literal["asc", "desc"]


@dataclass(frozen=True)
class ProductFilters:
    category_id: int | None = None
    supplier_id: int | None = None
    warehouse_id: int | None = None
    risk_classes: frozenset[str] = frozenset()
    slow_moving: bool | None = None
    q: str | None = None


def _clean(value: Any) -> Any:
    """NaN / NA -> None; everything else unchanged (pandas ``to_dict`` gives Python scalars)."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [{k: _clean(v) for k, v in row.items()} for row in frame.to_dict("records")]


# --- existence checks (unknown ids are 404, never an empty result) ---


def ensure_exists(session: Session, **ids: int | None) -> None:
    """``NotFoundError`` for the first given id that does not exist.

    Keys: ``category_id``, ``supplier_id``, ``warehouse_id``.
    """
    models: dict[str, type[Category] | type[Supplier] | type[Warehouse]] = {
        "category_id": Category,
        "supplier_id": Supplier,
        "warehouse_id": Warehouse,
    }
    for key, value in ids.items():
        if value is not None and session.get(models[key], value) is None:
            raise NotFoundError(f"Unknown {key}.")


# --- reference lists (#5-#7) ---


def list_categories(session: Session) -> list[CategoryOut]:
    return [
        CategoryOut.model_validate(dict(r)) for r in CategoryRepository(session).reference_rows()
    ]


def list_warehouses(session: Session) -> list[WarehouseOut]:
    rows = WarehouseRepository(session).reference_rows()
    return [WarehouseOut.model_validate(dict(r)) for r in rows]


def list_suppliers(session: Session) -> list[SupplierOut]:
    rows = SupplierRepository(session).reference_rows()
    return [SupplierOut.model_validate(dict(r)) for r in rows]


# --- product roll-up shared by the list and the detail ---


def product_summaries(
    metrics: pd.DataFrame, catalogue: Sequence[Mapping[Any, Any]]
) -> pd.DataFrame:
    """``rollup_by_product`` over ``metrics`` joined to the catalogue rows (inner join).

    Adds ``is_high_demand`` (any included warehouse row), name, category_code and supplier_code.
    """
    products = pd.DataFrame(
        [dict(r) for r in catalogue],
        columns=["id", "sku", "name", "category_code", "supplier_code"],
    ).rename(columns={"id": "product_id"})
    metrics = metrics.loc[metrics["product_id"].isin(products["product_id"])]
    rolled = rollup_by_product(metrics)
    high_demand = metrics.groupby("product_id")["is_high_demand"].any()
    rolled["is_high_demand"] = rolled["product_id"].map(high_demand).fillna(False).astype(bool)
    return rolled.merge(products.drop(columns=["sku"]), on="product_id", how="inner")


def _sort(frame: pd.DataFrame, sort: SortKey, order: SortOrder) -> pd.DataFrame:
    """Stable sort. ``risk`` asc = most severe first, ties by days_of_cover asc then sku.
    ``days_of_cover`` keeps nulls last in both orders. Other ties break by sku asc."""
    ascending = order == "asc"
    if sort == "risk":
        work = frame.assign(_rank=frame["risk_class"].map(RISK_RANK))
        return work.sort_values(
            ["_rank", "days_of_cover", "sku"],
            ascending=[ascending, True, True],
            na_position="last",
            kind="mergesort",
        ).drop(columns="_rank")
    if sort == "days_of_cover":
        return frame.sort_values(
            ["days_of_cover", "sku"], ascending=[ascending, True], na_position="last"
        )
    if sort == "name":
        return frame.sort_values(["name", "sku"], ascending=[ascending, True])
    return frame.sort_values("sku", ascending=ascending)


# --- product list (#8) ---


def list_products(
    session: Session,
    filters: ProductFilters,
    sort: SortKey,
    order: SortOrder,
    paging: PageParams,
) -> ProductPage:
    ensure_exists(
        session,
        category_id=filters.category_id,
        supplier_id=filters.supplier_id,
        warehouse_id=filters.warehouse_id,
    )
    context = load_snapshot_context(session)
    metrics = context.metrics
    if filters.warehouse_id is not None:
        metrics = metrics.loc[metrics["warehouse_id"] == filters.warehouse_id]
    catalogue = ProductRepository(session).catalogue_rows(
        category_id=filters.category_id, supplier_id=filters.supplier_id, q=filters.q
    )
    rolled = product_summaries(metrics, catalogue)
    if filters.risk_classes:
        rolled = rolled.loc[rolled["risk_class"].isin(filters.risk_classes)]
    if filters.slow_moving is not None:
        rolled = rolled.loc[rolled["is_slow_moving"] == filters.slow_moving]
    ordered = _sort(rolled, sort, order)
    page = ordered.iloc[paging.offset : paging.offset + paging.page_size]
    return ProductPage(
        items=[ProductSummaryOut.model_validate(r) for r in _records(page)],
        page=paging.page,
        page_size=paging.page_size,
        total=len(ordered),
        snapshot=context.meta,
    )


# --- product detail (#9) ---


def _product_out(row: Mapping[Any, Any]) -> ProductOut:
    return ProductOut(
        id=row["id"],
        sku=row["sku"],
        name=row["name"],
        category=CategoryRef(
            id=row["category_id"], code=row["category_code"], name=row["category_name"]
        ),
        supplier=SupplierRef(
            id=row["supplier_id"],
            code=row["supplier_code"],
            name=row["supplier_name"],
            default_lead_time_days=row["supplier_lead_time_days"],
            min_order_qty=row["supplier_min_order_qty"],
        ),
        unit_cost=row["unit_cost"],
        unit_price=row["unit_price"],
        case_pack=row["case_pack"],
        is_active=row["is_active"],
    )


def _warehouse_rows(
    context: SnapshotContext, product: Mapping[Any, Any], policies: Iterable[Mapping[Any, Any]]
) -> list[WarehouseMetricOut]:
    by_warehouse = {p["warehouse_id"]: p for p in policies}
    rows = context.metrics.loc[context.metrics["product_id"] == product["id"]]
    out: list[WarehouseMetricOut] = []
    for record in sorted(_records(rows), key=lambda r: str(r["warehouse_code"])):
        policy = by_warehouse.get(record["warehouse_id"])
        out.append(
            WarehouseMetricOut.model_validate(
                {
                    **record,
                    "name": product["name"],
                    "policy": PolicyOut.model_validate(dict(policy)) if policy else None,
                }
            )
        )
    return out


def product_detail(session: Session, product_id: int) -> ProductDetailOut:
    product = ProductRepository(session).detail_row(product_id)
    if product is None:
        raise NotFoundError("Unknown product_id.")
    context = load_snapshot_context(session)
    catalogue = [
        {
            "id": product["id"],
            "sku": product["sku"],
            "name": product["name"],
            "category_code": product["category_code"],
            "supplier_code": product["supplier_code"],
        }
    ]
    rows = context.metrics.loc[context.metrics["product_id"] == product_id]
    rolled = _records(product_summaries(rows, catalogue))
    return ProductDetailOut(
        product=_product_out(product),
        warehouses=_warehouse_rows(
            context, product, InventoryPolicyRepository(session).rows_for_product(product_id)
        ),
        rollup=ProductSummaryOut.model_validate(rolled[0]) if rolled else None,
        snapshot=context.meta,
    )


# --- sales series (#10; #12 reuses build_series) ---


def series_end_date(session: Session) -> date:
    """t0 = the latest snapshot's ``data_as_of_date``, else ``max(sale_date)`` (ADR-012)."""
    t0 = latest_snapshot_t0(session)
    if t0 is None:
        t0 = SalesRepository(session).latest_sale_date()
    if t0 is None:
        raise NoSalesDataError()
    return t0


def build_series(
    rows: Iterable[Mapping[Any, Any]], start_date: date, end_date: date
) -> list[SalesPoint]:
    """Sum units and revenue per day; every day from start to end present (zero-filled)."""
    units: dict[date, int] = {}
    revenue: dict[date, Decimal] = {}
    for row in rows:
        day = row["sale_date"]
        units[day] = units.get(day, 0) + int(row["units_sold"])
        revenue[day] = revenue.get(day, Decimal(0)) + Decimal(row["revenue"])
    days = (end_date - start_date).days + 1
    return [
        SalesPoint(
            date=day,
            units=units.get(day, 0),
            revenue=revenue.get(day, Decimal(0)),
        )
        for day in (start_date + timedelta(days=offset) for offset in range(days))
    ]


def sales_window(
    session: Session,
    days: int,
    product_id: int | None = None,
    warehouse_id: int | None = None,
    category_id: int | None = None,
) -> SalesSeriesOut:
    end_date = series_end_date(session)
    start_date = end_date - timedelta(days=days - 1)
    rows = SalesRepository(session).series_rows(
        start_date,
        end_date,
        product_id=product_id,
        warehouse_id=warehouse_id,
        category_id=category_id,
    )
    return SalesSeriesOut(
        start_date=start_date, end_date=end_date, series=build_series(rows, start_date, end_date)
    )


def product_sales(
    session: Session, product_id: int, days: int, warehouse_id: int | None
) -> ProductSalesOut:
    if ProductRepository(session).get(product_id) is None:
        raise NotFoundError("Unknown product_id.")
    ensure_exists(session, warehouse_id=warehouse_id)
    window = sales_window(session, days, product_id=product_id, warehouse_id=warehouse_id)
    return ProductSalesOut(
        product_id=product_id,
        warehouse_id=warehouse_id,
        start_date=window.start_date,
        end_date=window.end_date,
        series=window.series,
    )
