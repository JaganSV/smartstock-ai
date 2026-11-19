"""Metric functions: one per BP 7.2 formula, vectorised over a whole DataFrame.

Each function returns a Series aligned to the input index. Formulas are the BP 7.2 formulas
exactly; the docstring of each function states its formula. Calculations are float64 with no
intermediate rounding; every ceiling goes through ``safe_ceil_array``. Division by zero is
handled with explicit masks (a zero denominator becomes NaN before dividing).

``df`` arguments are frames that already hold the columns each function lists (built up in
``compute_metrics``). ``units_by_day`` arguments are Series whose items are equal-length arrays of
daily units, oldest to newest, ending at t0.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import numpy.typing as npt
import pandas as pd

from app.analytics.errors import AnalyticsInputError
from app.analytics.numeric import money, safe_ceil_array
from app.analytics.params import AnalyticsParams
from app.analytics.projection import projected_stockout_day
from app.analytics.types import IDENTITY_COLS, METRIC_COLS

logger = logging.getLogger(__name__)


def _stack(units_by_day: pd.Series) -> npt.NDArray[np.int64]:
    """Series of equal-length arrays -> 2-D int64 array (rows x days); callers skip empty input."""
    return np.vstack(units_by_day.to_list()).astype(np.int64)


def _last(units: npt.NDArray[np.int64], n: int) -> npt.NDArray[np.int64]:
    if n <= 0 or n > units.shape[1]:
        raise AnalyticsInputError(f"window of {n} days does not fit a series of {units.shape[1]}")
    return units[:, -n:]


def _empty(index: pd.Index) -> pd.Series:
    return pd.Series([], index=index, dtype="float64")


def ads(units_by_day: pd.Series, n: int) -> pd.Series:
    """ADS_n = (sum of the last n days) / n. Days without sales count as zero."""
    if len(units_by_day) == 0:
        return _empty(units_by_day.index)
    values = _last(_stack(units_by_day), n).sum(axis=1) / n
    return pd.Series(values, index=units_by_day.index, dtype="float64")


def demand_std(units_by_day: pd.Series, n: int = 30) -> pd.Series:
    """sigma_d = population standard deviation (ddof = 0) of the last n days of units."""
    if len(units_by_day) == 0:
        return _empty(units_by_day.index)
    values = _last(_stack(units_by_day), n).std(axis=1, ddof=0)
    return pd.Series(values, index=units_by_day.index, dtype="float64")


def lead_time_days(df: pd.DataFrame) -> pd.Series:
    """L = lead_time_override_days if not null, else supplier_lead_time_days.

    Needs columns: lead_time_override_days, supplier_lead_time_days.
    """
    override = pd.to_numeric(df["lead_time_override_days"], errors="coerce").astype("float64")
    supplier = df["supplier_lead_time_days"].astype("float64")
    return override.where(override.notna(), supplier).astype("int64")


def available(df: pd.DataFrame) -> pd.Series:
    """available = on_hand - committed (may be negative). Needs: on_hand, committed."""
    return (df["on_hand"].astype("int64") - df["committed"].astype("int64")).astype("int64")


def incoming_in_lead_time(df: pd.DataFrame, t0: date) -> pd.Series:
    """incoming_in_LT = sum of OPEN quantities with t0 < arrival <= t0 + L (L per row).

    Arrival exactly at t0 + L counts; arrival at t0 (already in on_hand) or after t0 + L does not.
    Needs: open_incoming, lead_time_days.
    """
    totals = []
    for orders, lead in zip(df["open_incoming"], df["lead_time_days"], strict=True):
        horizon = t0 + timedelta(days=int(lead))
        totals.append(sum(qty for arrival, qty in orders if t0 < arrival <= horizon))
    return pd.Series(totals, index=df.index, dtype="int64")


def safety_stock(df: pd.DataFrame, params: AnalyticsParams) -> pd.Series:
    """SS = safety_stock_override if not null, else ceil(Z(service_level) * sigma_d30 * sqrt(L)).

    Z comes from ``params.z_table`` (exact match, no interpolation); it is only looked up for rows
    without an override. Needs: safety_stock_override, service_level, demand_std_30,
    lead_time_days. (``params`` is needed only to resolve Z.)
    """
    override = pd.to_numeric(df["safety_stock_override"], errors="coerce").astype("float64")
    has_override = override.notna().to_numpy()
    computed = np.zeros(len(df), dtype=np.int64)
    needs = ~has_override
    if needs.any():
        z = df.loc[needs, "service_level"].map(params.z_for).to_numpy(dtype=np.float64)
        sigma = df.loc[needs, "demand_std_30"].to_numpy(dtype=np.float64)
        lead = df.loc[needs, "lead_time_days"].to_numpy(dtype=np.float64)
        computed[needs] = safe_ceil_array(z * sigma * np.sqrt(lead))
    result = np.where(has_override, override.fillna(0.0).to_numpy(), computed).astype(np.int64)
    return pd.Series(result, index=df.index, dtype="int64")


def reorder_point(df: pd.DataFrame) -> pd.Series:
    """ROP = ceil(ADS30 * L) + SS. Needs: ads_30, lead_time_days, safety_stock."""
    ads30 = df["ads_30"].to_numpy(dtype=np.float64)
    lead = df["lead_time_days"].to_numpy(dtype=np.float64)
    rop = safe_ceil_array(ads30 * lead) + df["safety_stock"].to_numpy(dtype=np.int64)
    return pd.Series(rop, index=df.index, dtype="int64")


def days_of_cover(df: pd.DataFrame) -> pd.Series:
    """DoC = max(0, available) / ADS30; NaN when ADS30 = 0 ("no recent demand").

    Needs: available, ads_30.
    """
    ads30 = df["ads_30"].astype("float64")
    safe_ads = ads30.where(ads30 > 0)  # zero demand -> NaN before dividing (no ZeroDivision)
    return (df["available"].clip(lower=0) / safe_ads).astype("float64")


def inventory_position(df: pd.DataFrame) -> pd.Series:
    """IP = available + incoming_in_LT. Needs: available, incoming_in_lt."""
    return (df["available"].astype("int64") + df["incoming_in_lt"].astype("int64")).astype("int64")


def reorder_quantity_raw(df: pd.DataFrame) -> pd.Series:
    """Q_raw = ceil(ADS30 * (L + R)) + SS - IP (R = policy review_period_days).

    Needs: ads_30, lead_time_days, review_period_days, safety_stock, inventory_position.
    """
    ads30 = df["ads_30"].to_numpy(dtype=np.float64)
    horizon = (df["lead_time_days"] + df["review_period_days"]).to_numpy(dtype=np.float64)
    raw = (
        safe_ceil_array(ads30 * horizon)
        + df["safety_stock"].to_numpy(dtype=np.int64)
        - df["inventory_position"].to_numpy(dtype=np.int64)
    )
    return pd.Series(raw, index=df.index, dtype="int64")


def reorder_quantity(df: pd.DataFrame) -> pd.Series:
    """Q = 0 if Q_raw <= 0, else case_pack * ceil(max(Q_raw, MOQ) / case_pack).

    Needs the columns of ``reorder_quantity_raw`` plus supplier_moq and case_pack.
    """
    raw = reorder_quantity_raw(df).to_numpy(dtype=np.int64)
    moq = df["supplier_moq"].to_numpy(dtype=np.int64)
    pack = df["case_pack"].to_numpy(dtype=np.int64)
    packs = safe_ceil_array(np.maximum(raw, moq) / pack)
    return pd.Series(np.where(raw <= 0, 0, pack * packs), index=df.index, dtype="int64")


def demand_trend(units_by_day: pd.Series, recent_days: int = 14, prior_days: int = 76) -> pd.Series:
    """trend = mean(last 14 days) / mean(prior 76 days) - 1; NaN when the prior mean is 0.

    The prior window is the ``prior_days`` days immediately before the recent window.
    """
    if len(units_by_day) == 0:
        return _empty(units_by_day.index)
    units = _last(_stack(units_by_day), recent_days + prior_days)
    recent = units[:, -recent_days:].mean(axis=1)
    prior = units[:, :-recent_days].mean(axis=1)
    safe_prior = np.where(prior > 0, prior, np.nan)  # zero prior mean -> NaN before dividing
    return pd.Series(recent / safe_prior - 1.0, index=units_by_day.index, dtype="float64")


def inventory_value(df: pd.DataFrame) -> pd.Series:
    """value = on_hand * unit_cost as Decimal, 2 dp, ROUND_HALF_UP. Needs: on_hand, unit_cost."""
    values = [
        money(Decimal(int(on_hand)) * Decimal(str(cost)))
        for on_hand, cost in zip(df["on_hand"], df["unit_cost"], strict=True)
    ]
    return pd.Series(values, index=df.index, dtype="object")


def compute_metrics(inputs: pd.DataFrame, params: AnalyticsParams) -> pd.DataFrame:
    """All BP 7.2/7.3 metrics for a ``build_metric_inputs`` frame.

    Returns the identity columns (product_id, warehouse_id, sku, warehouse_code) plus
    ``METRIC_COLS``: available, incoming_in_lt, ads_30, ads_90, demand_std_30, lead_time_days,
    safety_stock, reorder_point, days_of_cover, inventory_position, reorder_qty, demand_trend,
    inventory_value, projected_stockout_day (nullable Int64). Integer metrics are int64.
    """
    df = inputs.copy()
    df["available"] = available(df)
    df["lead_time_days"] = lead_time_days(df)
    df["incoming_in_lt"] = incoming_in_lead_time(df, params.t0)
    df["ads_30"] = ads(df["units_by_day"], params.short_window)
    df["ads_90"] = ads(df["units_by_day"], params.long_window)
    df["demand_std_30"] = demand_std(df["units_by_day"], params.short_window)
    df["safety_stock"] = safety_stock(df, params)
    df["reorder_point"] = reorder_point(df)
    df["days_of_cover"] = days_of_cover(df)
    df["inventory_position"] = inventory_position(df)
    df["reorder_qty"] = reorder_quantity(df)
    df["demand_trend"] = demand_trend(
        df["units_by_day"], params.trend_recent_days, params.trend_prior_days
    )
    df["inventory_value"] = inventory_value(df)
    df["projected_stockout_day"] = pd.array(
        [
            projected_stockout_day(float(avail), float(rate), orders, params.t0, int(lead))
            for avail, rate, orders, lead in zip(
                df["available"],
                df["ads_30"],
                df["open_incoming"],
                df["lead_time_days"],
                strict=True,
            )
        ],
        dtype="Int64",
    )
    logger.debug("computed metrics for %d product-warehouses", len(df))
    return df[[*IDENTITY_COLS, *METRIC_COLS]].reset_index(drop=True)
