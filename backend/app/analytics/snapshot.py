"""Pure mapping from the analytics frame to ``product_metrics`` rows (BP 5.3 scales)."""

from decimal import Decimal
from typing import Any

import pandas as pd

from app.analytics.numeric import money, round_decimal

FOUR_DP_COLUMNS = ("ads_30", "ads_90", "demand_std_30", "days_of_cover")
INT_COLUMNS = (
    "product_id",
    "warehouse_id",
    "on_hand",
    "committed",
    "available",
    "incoming_in_lt",
    "lead_time_days",
    "safety_stock",
    "reorder_point",
    "reorder_qty",
)


def _null_or(value: Any, convert: Any) -> Any:
    return None if pd.isna(value) else convert(value)


def to_snapshot_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """One dict per row with the ``product_metrics`` column names (no ``snapshot_id``).

    Scales: ads_30, ads_90, demand_std_30, days_of_cover and demand_trend_pct are Decimal with 4 dp
    (ROUND_HALF_UP via Decimal); inventory_value is Decimal with 2 dp; integers are Python ints;
    NaN / <NA> becomes None (days_of_cover, demand_trend_pct). ``demand_trend_pct`` stores the
    RATIO (0.25 = +25%), not a percentage, despite the column name.
    """
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict("records"):
        row: dict[str, Any] = {name: int(record[name]) for name in INT_COLUMNS}
        for name in ("ads_30", "ads_90", "demand_std_30"):
            row[name] = round_decimal(record[name], 4)
        row["days_of_cover"] = _null_or(record["days_of_cover"], lambda v: round_decimal(v, 4))
        row["demand_trend_pct"] = _null_or(record["demand_trend"], lambda v: round_decimal(v, 4))
        row["inventory_value"] = money(Decimal(record["inventory_value"]))
        row["risk_class"] = str(record["risk_class"])
        row["risk_reason_code"] = str(record["risk_reason_code"])
        row["is_slow_moving"] = bool(record["is_slow_moving"])
        row["is_dead_stock"] = bool(record["is_dead_stock"])
        rows.append(row)
    return rows
