"""Slow-moving, dead-stock and high-demand flags (BP 7.5). One definition each.

``is_high_demand`` is NOT persisted (BP 5.3 has no column); P3 derives it from
``demand_trend_pct`` with this same rule.
"""

import pandas as pd

from app.analytics.metrics import _last, _stack
from app.analytics.numeric import float_array
from app.analytics.params import AnalyticsParams


def is_slow_moving(df: pd.DataFrame, params: AnalyticsParams) -> pd.Series:
    """slow = on_hand > 0 and (ADS30 < slow_ratio x ADS90 or DoC > slow_cover_days).

    A null DoC (ADS30 = 0) is "not above the threshold"; the ADS clause still applies.
    Needs: on_hand, ads_30, ads_90, days_of_cover.
    """
    ads30, ads90, cover = (
        float_array(df, "ads_30"),
        float_array(df, "ads_90"),
        float_array(df, "days_of_cover"),
    )
    slow = (float_array(df, "on_hand") > 0) & (
        (ads30 < params.slow_ratio * ads90) | (cover > params.slow_cover_days)
    )
    return pd.Series(slow, index=df.index, dtype=bool)


def is_dead_stock(df: pd.DataFrame, params: AnalyticsParams) -> pd.Series:
    """dead = on_hand > 0 and the units sold over the last ``dead_stock_days`` days sum to 0.

    Needs: on_hand, units_by_day (equal-length arrays, oldest to newest, ending at t0).
    """
    if len(df) == 0:
        return pd.Series([], index=df.index, dtype=bool)
    recent = _last(_stack(df["units_by_day"]), params.dead_stock_days).sum(axis=1)
    return pd.Series((float_array(df, "on_hand") > 0) & (recent == 0), index=df.index, dtype=bool)


def is_high_demand(df: pd.DataFrame, params: AnalyticsParams) -> pd.Series:
    """high demand = demand_trend >= spike_threshold (a null trend is False).

    ``demand_trend`` is the ratio (0.30 = +30%), the same value stored as ``demand_trend_pct``.
    Needs: demand_trend.
    """
    return pd.Series(
        float_array(df, "demand_trend") >= params.spike_threshold, index=df.index, dtype=bool
    )
