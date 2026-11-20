"""Builders for analytics tests. Synthetic values only."""

from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from app.analytics.types import INPUT_COLS

T0 = date(2026, 9, 30)
WINDOW = 90


def units(recent: int | list[int] = 5, earlier: int = 5) -> npt.NDArray[np.int64]:
    """90 daily units: the first 60 days are ``earlier``; the last 30 are ``recent``.

    ``recent`` is either one constant or an explicit list of 30 values (oldest to newest).
    """
    last = np.full(30, recent, dtype=np.int64) if isinstance(recent, int) else np.array(recent)
    assert len(last) == 30
    return np.concatenate([np.full(60, earlier, dtype=np.int64), last.astype(np.int64)])


def alternating(low: int, high: int, days: int = 30) -> list[int]:
    """low, high, low, ... (``days`` values): mean (low+high)/2, population std (high-low)/2."""
    return [low if i % 2 == 0 else high for i in range(days)]


def series_of(*arrays: list[int] | npt.NDArray[np.int64]) -> pd.Series:
    """A Series whose items are int64 arrays (the ``units_by_day`` shape)."""
    return pd.Series([np.asarray(a, dtype=np.int64) for a in arrays], dtype="object")


def input_row(**overrides: Any) -> dict[str, Any]:
    """One ``build_metric_inputs``-shaped row with neutral defaults."""
    row: dict[str, Any] = {
        "product_id": 1,
        "warehouse_id": 1,
        "sku": "SKU-T",
        "warehouse_code": "WH-T",
        "supplier_id": 1,
        "unit_cost": Decimal("100.00"),
        "case_pack": 1,
        "supplier_moq": 1,
        "supplier_lead_time_days": 7,
        "service_level": 0.95,
        "review_period_days": 14,
        "safety_stock_override": None,
        "lead_time_override_days": None,
        "on_hand": 100,
        "committed": 0,
        "units_by_day": units(),
        "open_incoming": [],
    }
    row.update(overrides)
    return row


def make_inputs(*rows: dict[str, Any]) -> pd.DataFrame:
    """Frame with ``INPUT_COLS``; product ids are made unique per row."""
    frame = pd.DataFrame(
        [{**row, "product_id": row["product_id"] + i} for i, row in enumerate(rows)],
        columns=list(INPUT_COLS),
    )
    for column in ("safety_stock_override", "lead_time_override_days"):
        frame[column] = pd.array(list(frame[column]), dtype="Int64")
    for column in ("on_hand", "committed", "case_pack", "supplier_moq", "supplier_lead_time_days"):
        frame[column] = frame[column].astype("int64")
    frame["review_period_days"] = frame["review_period_days"].astype("int64")
    return frame


def risk_frame(*rows: dict[str, Any]) -> pd.DataFrame:
    """Frame with the columns ``classify_risk`` needs; defaults classify as LOW.

    Defaults: available 100, ADS30 5, no stockout day, IP 100 > ROP 50, DoC 50 (> L + R = 21,
    <= 120), L 7, R 14, on_hand 100.
    """
    base: dict[str, Any] = {
        "available": 100,
        "ads_30": 5.0,
        "projected_stockout_day": None,
        "inventory_position": 100,
        "reorder_point": 50,
        "days_of_cover": 50.0,
        "lead_time_days": 7,
        "review_period_days": 14,
        "on_hand": 100,
    }
    frame = pd.DataFrame([{**base, **row} for row in rows])
    frame["projected_stockout_day"] = pd.array(list(frame["projected_stockout_day"]), dtype="Int64")
    return frame
