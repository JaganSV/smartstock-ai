"""Product-level roll-up and dashboard KPIs (BP 7.4, FR-A1).

Ratios are recomputed from summed components, never averaged across warehouses.
"""

from decimal import Decimal
from typing import Any

import pandas as pd

from app.analytics.numeric import money
from app.models.enums import RISK_RANK, RISK_SEVERITY, RiskClass

LOW_STOCK_CLASSES = frozenset({RiskClass.HIGH.value, RiskClass.MEDIUM.value})
STOCKOUT_RISK_CLASSES = frozenset(
    {RiskClass.STOCKOUT.value, RiskClass.CRITICAL.value, RiskClass.HIGH.value}
)

ROLLUP_COLUMNS = (
    "product_id",
    "sku",
    "on_hand",
    "committed",
    "available",
    "incoming_in_lt",
    "inventory_value",
    "ads_30",
    "ads_90",
    "days_of_cover",
    "risk_class",
    "risk_warehouse_code",
    "is_slow_moving",
    "is_dead_stock",
)


def _decimal_sum(values: pd.Series) -> Decimal:
    return money(sum((Decimal(v) for v in values), Decimal(0)))


def rollup_by_product(metrics: pd.DataFrame) -> pd.DataFrame:
    """One row per product from the per-warehouse rows.

    Sums: on_hand, committed, available, incoming_in_lt, inventory_value, ads_30, ads_90.
    ``days_of_cover`` = max(0, sum(available)) / sum(ads_30), NaN when sum(ads_30) = 0.
    ``risk_class`` = the most severe class across warehouses (STOCKOUT > CRITICAL > HIGH > MEDIUM >
    OVERSTOCK > LOW); ``risk_warehouse_code`` = the warehouse that drove it (ties: lowest code).
    ``is_slow_moving`` / ``is_dead_stock`` = any warehouse. Needs: product_id, sku, warehouse_code,
    risk_class and the summed columns.
    """
    if metrics.empty:
        return pd.DataFrame(columns=list(ROLLUP_COLUMNS))
    work = metrics.assign(_rank=metrics["risk_class"].map(RISK_RANK))
    grouped = work.groupby("product_id", sort=True)
    summed = grouped[
        ["on_hand", "committed", "available", "incoming_in_lt", "ads_30", "ads_90"]
    ].sum()
    summed["inventory_value"] = grouped["inventory_value"].agg(_decimal_sum)
    ads_total = summed["ads_30"].where(summed["ads_30"] > 0)  # zero demand -> NaN before dividing
    summed["days_of_cover"] = (summed["available"].clip(lower=0) / ads_total).astype("float64")

    driver = work.sort_values(["product_id", "_rank", "warehouse_code"]).drop_duplicates(
        "product_id"
    )
    summed["sku"] = grouped["sku"].first()
    summed["risk_class"] = driver.set_index("product_id")["risk_class"]
    summed["risk_warehouse_code"] = driver.set_index("product_id")["warehouse_code"]
    summed["is_slow_moving"] = grouped["is_slow_moving"].any()
    summed["is_dead_stock"] = grouped["is_dead_stock"].any()
    return summed.reset_index()[list(ROLLUP_COLUMNS)]


def risk_distribution(metrics: pd.DataFrame) -> dict[str, int]:
    """Count of product x warehouse rows per class (all six classes present, severity order)."""
    counts = metrics["risk_class"].value_counts() if "risk_class" in metrics else pd.Series()
    return {risk.value: int(counts.get(risk.value, 0)) for risk in RISK_SEVERITY}


def dashboard_kpis(
    metrics: pd.DataFrame,
    products: pd.DataFrame,
    warehouse_id: int | None = None,
    category_id: int | None = None,
) -> dict[str, Any]:
    """Dashboard KPIs (FR-A1).

    ``products`` needs: id, is_active and (for the category filter) category_id. Only active
    products count. With ``warehouse_id`` the product-level counts use that warehouse's rows only;
    with ``category_id`` only that category's products are included.

    Returns total_products, total_units, inventory_value (Decimal, 2 dp), low_stock_count (products
    rolled up to HIGH or MEDIUM), stockout_risk_count (STOCKOUT, CRITICAL or HIGH),
    slow_moving_count (products with any slow-moving row) and risk_distribution (rows per class).
    """
    active = products.loc[products["is_active"].astype(bool)]
    if category_id is not None:
        active = active.loc[active["category_id"] == category_id]
    rows = metrics.loc[metrics["product_id"].isin(active["id"])]
    if warehouse_id is not None:
        rows = rows.loc[rows["warehouse_id"] == warehouse_id]
    rolled = rollup_by_product(rows)
    classes = rolled["risk_class"] if len(rolled) else pd.Series([], dtype=object)
    total_value = _decimal_sum(rows["inventory_value"]) if len(rows) else money(0)
    return {
        "total_products": int(len(active)),
        "total_units": int(rows["on_hand"].sum()) if len(rows) else 0,
        "inventory_value": total_value,
        "low_stock_count": int(classes.isin(LOW_STOCK_CLASSES).sum()),
        "stockout_risk_count": int(classes.isin(STOCKOUT_RISK_CLASSES).sum()),
        "slow_moving_count": int(rolled["is_slow_moving"].sum()) if len(rolled) else 0,
        "risk_distribution": risk_distribution(rows),
    }
