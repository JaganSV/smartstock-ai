"""Row-level (product x warehouse) reads of a snapshot: metrics, stockout risk, slow-moving.

BP 6.2 #14, #18 (FR-C1) and #20. Rows are the stored ``product_metrics`` rows of the snapshot
(``snapshot_context``), joined to the catalogue for the name and the category filter. The stockout
list adds ``projected_stockout_day`` from a recompute verified against the stored rows
(``explain_service.recompute_rows``), so it never disagrees with the snapshot. Nothing is written.
"""

from dataclasses import dataclass
from typing import Literal

import pandas as pd
from sqlalchemy.orm import Session

from app.analytics.rollup import STOCKOUT_RISK_CLASSES
from app.repositories.products import ProductRepository
from app.schemas.analytics import MetricPage
from app.schemas.common import PageParams
from app.schemas.inventory import ProductMetricOut
from app.schemas.risk import SlowMovingOut, SlowMovingPage, StockoutRiskOut, StockoutRiskPage
from app.services.explain_service import recompute_rows
from app.services.inventory_service import ensure_exists, sort_frame
from app.services.snapshot_context import (
    SnapshotContext,
    frame_records,
    load_snapshot,
    load_snapshot_context,
)

MetricSortKey = Literal["sku", "risk", "days_of_cover"]
SortOrder = Literal["asc", "desc"]
ROW_TIES = ("warehouse_code",)


@dataclass(frozen=True)
class MetricFilters:
    warehouse_id: int | None = None
    category_id: int | None = None
    risk_classes: frozenset[str] = frozenset()
    slow_moving: bool | None = None
    dead_stock: bool | None = None


def _rows(
    session: Session,
    context: SnapshotContext,
    warehouse_id: int | None,
    category_id: int | None,
) -> pd.DataFrame:
    """The context's rows of the products in the catalogue (category filter), with ``name``."""
    catalogue = pd.DataFrame(
        [dict(r) for r in ProductRepository(session).catalogue_rows(category_id=category_id)],
        columns=["id", "sku", "name", "category_code", "supplier_code"],
    )
    rows = context.metrics
    if warehouse_id is not None:
        rows = rows.loc[rows["warehouse_id"] == warehouse_id]
    names = catalogue.set_index("id")["name"]
    rows = rows.loc[rows["product_id"].isin(names.index)]
    return rows.assign(name=rows["product_id"].map(names))


def _page(frame: pd.DataFrame, paging: PageParams) -> pd.DataFrame:
    return frame.iloc[paging.offset : paging.offset + paging.page_size]


# --- #14 metrics ---


def list_metrics(
    session: Session,
    snapshot_id: int | None,
    filters: MetricFilters,
    sort: MetricSortKey,
    order: SortOrder,
    paging: PageParams,
) -> MetricPage:
    ensure_exists(session, warehouse_id=filters.warehouse_id, category_id=filters.category_id)
    context = load_snapshot_context(session, snapshot_id)
    rows = _rows(session, context, filters.warehouse_id, filters.category_id)
    if filters.risk_classes:
        rows = rows.loc[rows["risk_class"].isin(filters.risk_classes)]
    if filters.slow_moving is not None:
        rows = rows.loc[rows["is_slow_moving"] == filters.slow_moving]
    if filters.dead_stock is not None:
        rows = rows.loc[rows["is_dead_stock"] == filters.dead_stock]
    ordered = sort_frame(rows, sort, order, ROW_TIES)
    return MetricPage(
        items=[ProductMetricOut.model_validate(r) for r in frame_records(_page(ordered, paging))],
        page=paging.page,
        page_size=paging.page_size,
        total=len(ordered),
        snapshot=context.meta,
    )


# --- #18 stockout risk (FR-C1) ---


def stockout_risk(
    session: Session, warehouse_id: int | None, category_id: int | None, paging: PageParams
) -> StockoutRiskPage:
    """STOCKOUT, CRITICAL and HIGH rows: severity, then days_of_cover asc (nulls last), then sku.

    ``projected_stockout_day`` comes from the verified recompute of the page's rows (409 if the
    data changed since the snapshot).
    """
    ensure_exists(session, warehouse_id=warehouse_id, category_id=category_id)
    context = load_snapshot_context(session)
    rows = _rows(session, context, warehouse_id, category_id)
    rows = rows.loc[rows["risk_class"].isin(STOCKOUT_RISK_CLASSES)]
    ordered = sort_frame(rows, "risk", "asc", ROW_TIES)
    records = frame_records(_page(ordered, paging))
    stored = {(int(r["product_id"]), int(r["warehouse_id"])): r for r in records}
    verified = recompute_rows(session, load_snapshot(session, context.meta.snapshot_id), stored)
    items = []
    for record in records:
        row = verified[(int(record["product_id"]), int(record["warehouse_id"]))].row
        day = row["projected_stockout_day"]
        items.append(
            StockoutRiskOut.model_validate(
                {**record, "projected_stockout_day": None if pd.isna(day) else int(day)}
            )
        )
    return StockoutRiskPage(
        items=items,
        page=paging.page,
        page_size=paging.page_size,
        total=len(ordered),
        snapshot=context.meta,
    )


# --- #20 slow-moving and dead stock ---


def slow_moving(
    session: Session, warehouse_id: int | None, category_id: int | None, paging: PageParams
) -> SlowMovingPage:
    """Rows flagged slow-moving or dead stock: dead stock first, then inventory_value desc, sku."""
    ensure_exists(session, warehouse_id=warehouse_id, category_id=category_id)
    context = load_snapshot_context(session)
    rows = _rows(session, context, warehouse_id, category_id)
    rows = rows.loc[rows["is_slow_moving"] | rows["is_dead_stock"]]
    ordered = rows.sort_values(
        ["is_dead_stock", "inventory_value", "sku", "warehouse_code"],
        ascending=[False, False, True, True],
        kind="mergesort",
    )
    return SlowMovingPage(
        items=[SlowMovingOut.model_validate(r) for r in frame_records(_page(ordered, paging))],
        page=paging.page,
        page_size=paging.page_size,
        total=len(ordered),
        snapshot=context.meta,
    )
