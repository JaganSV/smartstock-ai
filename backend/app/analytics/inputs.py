"""Input-frame builder: raw table DataFrames -> one row per active product x warehouse.

Signature (stable; P2-02 calls it with frames loaded through repositories)::

    build_metric_inputs(products, warehouses, suppliers, policies, levels, incoming, sales, params)

Column names of each input frame are listed in ``app.analytics.types``. Output columns are
``types.INPUT_COLS``. All date logic uses ``params.t0`` (ADR-012); the wall clock is never read.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from app.analytics.errors import AnalyticsInputError
from app.analytics.params import AnalyticsParams
from app.analytics.types import (
    INCOMING_COLS,
    INPUT_COLS,
    LEVELS_COLS,
    POLICIES_COLS,
    PRODUCTS_COLS,
    SALES_COLS,
    SUPPLIERS_COLS,
    WAREHOUSES_COLS,
)

logger = logging.getLogger(__name__)

OPEN_STATUS = "OPEN"


def _require(frame: pd.DataFrame, name: str, columns: tuple[str, ...]) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise AnalyticsInputError(f"{name} frame is missing columns", missing)


def _pair_label(product_id: Any, warehouse_id: Any) -> str:
    return f"product_id={product_id},warehouse_id={warehouse_id}"


def _check_unique(frame: pd.DataFrame, name: str, key: list[str]) -> None:
    duplicated = frame.loc[frame.duplicated(subset=key, keep=False), key]
    if not duplicated.empty:
        labels = {
            ",".join(f"{k}={v}" for k, v in zip(key, row, strict=True))
            for row in duplicated.itertuples(index=False, name=None)
        }
        raise AnalyticsInputError(f"duplicate key in {name}", list(labels))


def _check_non_negative(frame: pd.DataFrame, name: str, column: str, key: list[str]) -> None:
    bad = frame.loc[frame[column] < 0, key]
    if not bad.empty:
        labels = [
            ",".join(f"{k}={v}" for k, v in zip(key, row, strict=True))
            for row in bad.itertuples(index=False, name=None)
        ]
        raise AnalyticsInputError(f"negative {column} in {name}", labels)


def _to_dates(series: pd.Series) -> pd.Series:
    """Normalise dates / timestamps / ISO strings to ``datetime.date`` objects."""
    return pd.to_datetime(series).dt.date


def _decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def build_metric_inputs(
    products: pd.DataFrame,
    warehouses: pd.DataFrame,
    suppliers: pd.DataFrame,
    policies: pd.DataFrame,
    levels: pd.DataFrame,
    incoming: pd.DataFrame,
    sales: pd.DataFrame,
    params: AnalyticsParams,
) -> pd.DataFrame:
    """Assemble the metric inputs: one row per active product x warehouse, sorted by ids.

    Output columns: product_id, warehouse_id, sku, warehouse_code, supplier_id, unit_cost
    (Decimal), case_pack, supplier_moq, supplier_lead_time_days, service_level,
    review_period_days, safety_stock_override, lead_time_override_days (nullable Int64),
    on_hand, committed, ``units_by_day`` (int64 array of length ``long_window``, oldest to
    newest, ending at t0; missing days are 0; the window is t0 - (long_window - 1) .. t0) and
    ``open_incoming`` (list of ``(arrival_date, quantity)`` for OPEN orders arriving after t0,
    sorted by date).

    Raises ``AnalyticsInputError`` (with the offending keys) for missing levels or policies,
    duplicate product x warehouse rows, and negative quantities. Sales outside the window are
    ignored.
    """
    for name, frame, cols in (
        ("products", products, PRODUCTS_COLS),
        ("warehouses", warehouses, WAREHOUSES_COLS),
        ("suppliers", suppliers, SUPPLIERS_COLS),
        ("policies", policies, POLICIES_COLS),
        ("levels", levels, LEVELS_COLS),
        ("incoming", incoming, INCOMING_COLS),
        ("sales", sales, SALES_COLS),
    ):
        _require(frame, name, cols)

    pair_key = ["product_id", "warehouse_id"]
    _check_unique(products, "products", ["id"])
    _check_unique(warehouses, "warehouses", ["id"])
    _check_unique(suppliers, "suppliers", ["id"])
    _check_unique(policies, "policies", pair_key)
    _check_unique(levels, "levels", pair_key)
    _check_non_negative(levels, "levels", "on_hand_qty", pair_key)
    _check_non_negative(levels, "levels", "committed_qty", pair_key)
    _check_non_negative(incoming, "incoming", "quantity", pair_key)
    _check_non_negative(sales, "sales", "units_sold", pair_key)

    active = products.loc[products["is_active"].astype(bool)]
    base = (
        active[["id", "sku", "supplier_id", "unit_cost", "case_pack"]]
        .rename(columns={"id": "product_id"})
        .merge(
            warehouses[["id", "code"]].rename(
                columns={"id": "warehouse_id", "code": "warehouse_code"}
            ),
            how="cross",
        )
        .merge(
            suppliers[["id", "default_lead_time_days", "min_order_qty"]].rename(
                columns={
                    "id": "supplier_id",
                    "default_lead_time_days": "supplier_lead_time_days",
                    "min_order_qty": "supplier_moq",
                }
            ),
            on="supplier_id",
            how="left",
            validate="m:1",
        )
    )
    unknown_supplier = base.loc[base["supplier_moq"].isna(), "sku"].unique().tolist()
    if unknown_supplier:
        raise AnalyticsInputError("products reference an unknown supplier", unknown_supplier)

    base = base.merge(
        policies[list(POLICIES_COLS)].astype(
            {"product_id": base["product_id"].dtype, "warehouse_id": base["warehouse_id"].dtype}
        ),
        on=pair_key,
        how="left",
        validate="1:1",
        indicator="_policy",
    )
    missing_policy = base.loc[base["_policy"] != "both", pair_key]
    if not missing_policy.empty:
        raise AnalyticsInputError(
            "missing inventory policy",
            [_pair_label(p, w) for p, w in missing_policy.itertuples(index=False, name=None)],
        )
    base = base.drop(columns="_policy").merge(
        levels[list(LEVELS_COLS)].rename(
            columns={"on_hand_qty": "on_hand", "committed_qty": "committed"}
        ),
        on=pair_key,
        how="left",
        validate="1:1",
        indicator="_level",
    )
    missing_level = base.loc[base["_level"] != "both", pair_key]
    if not missing_level.empty:
        raise AnalyticsInputError(
            "missing inventory level",
            [_pair_label(p, w) for p, w in missing_level.itertuples(index=False, name=None)],
        )
    base = base.drop(columns="_level").sort_values(pair_key).reset_index(drop=True)

    t0: date = params.t0
    window = params.long_window
    window_start = t0 - timedelta(days=window - 1)
    row_of = {
        (int(p), int(w)): i
        for i, (p, w) in enumerate(zip(base["product_id"], base["warehouse_id"], strict=True))
    }

    # --- units_by_day: (rows x window) array, zero-filled, oldest -> newest ---
    grid = np.zeros((len(base), window), dtype=np.int64)
    if len(sales):
        sale_dates = _to_dates(sales["sale_date"])
        in_window = ((sale_dates >= window_start) & (sale_dates <= t0)).to_numpy()
        for product_id, warehouse_id, day, units in zip(
            sales.loc[in_window, "product_id"],
            sales.loc[in_window, "warehouse_id"],
            sale_dates[in_window],
            sales.loc[in_window, "units_sold"],
            strict=True,
        ):
            row = row_of.get((int(product_id), int(warehouse_id)))
            if row is not None:  # sales for inactive products / unknown pairs are ignored
                grid[row, (day - window_start).days] += int(units)
    base["units_by_day"] = list(grid)

    # --- open_incoming: OPEN orders arriving after t0, sorted by date ---
    orders: dict[int, list[tuple[date, int]]] = {}
    if len(incoming):
        arrivals = _to_dates(incoming["expected_arrival_date"])
        is_open = ((incoming["status"] == OPEN_STATUS) & (arrivals > t0)).to_numpy()
        for product_id, warehouse_id, arrival, quantity in zip(
            incoming.loc[is_open, "product_id"],
            incoming.loc[is_open, "warehouse_id"],
            arrivals[is_open],
            incoming.loc[is_open, "quantity"],
            strict=True,
        ):
            row = row_of.get((int(product_id), int(warehouse_id)))
            if row is not None:
                orders.setdefault(row, []).append((arrival, int(quantity)))
    base["open_incoming"] = [sorted(orders.get(i, [])) for i in range(len(base))]

    base["unit_cost"] = base["unit_cost"].map(_decimal)
    for column in ("safety_stock_override", "lead_time_override_days"):
        base[column] = pd.array(
            [None if pd.isna(v) else int(v) for v in base[column]], dtype="Int64"
        )
    for column in (
        "on_hand",
        "committed",
        "case_pack",
        "supplier_moq",
        "supplier_lead_time_days",
        "review_period_days",
    ):
        base[column] = base[column].astype("int64")
    base["service_level"] = base["service_level"].map(float)
    logger.debug("built metric inputs: %d rows, window %s..%s", len(base), window_start, t0)
    return base[list(INPUT_COLS)]
