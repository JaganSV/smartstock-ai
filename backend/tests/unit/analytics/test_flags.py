"""Flags (BP 7.5): each clause on its own, boundaries, and NaN handling."""

from typing import Any

import numpy as np
import pandas as pd

from app.analytics.flags import is_dead_stock, is_high_demand, is_slow_moving
from app.analytics.params import AnalyticsParams
from tests.unit.analytics.helpers import T0, units

PARAMS = AnalyticsParams(t0=T0)


def frame(**row: Any) -> pd.DataFrame:
    base: dict[str, Any] = {
        "on_hand": 100,
        "ads_30": 10.0,
        "ads_90": 10.0,
        "days_of_cover": 10.0,
        "demand_trend": 0.0,
        "units_by_day": units(5, earlier=5),
    }
    return pd.DataFrame([{**base, **row}])


def slow(**row: Any) -> bool:
    return bool(is_slow_moving(frame(**row), PARAMS)[0])


def dead(**row: Any) -> bool:
    return bool(is_dead_stock(frame(**row), PARAMS)[0])


def high(**row: Any) -> bool:
    return bool(is_high_demand(frame(**row), PARAMS)[0])


# --- slow moving ---


def test_slow_default_is_false() -> None:
    assert slow() is False


def test_slow_ads_clause_boundary_is_strict() -> None:
    assert slow(ads_30=5.0, ads_90=10.0) is False  # 5 < 0.5 x 10 is false (equal)
    assert slow(ads_30=4.99, ads_90=10.0) is True


def test_slow_cover_clause_boundary_is_strict() -> None:
    assert slow(days_of_cover=90.0) is False
    assert slow(days_of_cover=90.01) is True


def test_slow_requires_stock_on_hand() -> None:
    assert slow(on_hand=0, ads_30=1.0, ads_90=10.0) is False
    assert slow(on_hand=0, days_of_cover=500.0) is False


def test_slow_null_cover_is_not_above_the_threshold_but_the_ads_clause_applies() -> None:
    assert slow(days_of_cover=np.nan, ads_30=10.0, ads_90=10.0) is False
    assert slow(days_of_cover=None, ads_30=1.0, ads_90=10.0) is True
    assert slow(days_of_cover=np.nan, ads_30=0.0, ads_90=4.0) is True


def test_slow_with_no_demand_at_all_is_false() -> None:
    assert slow(days_of_cover=np.nan, ads_30=0.0, ads_90=0.0) is False


def test_slow_uses_the_params_thresholds() -> None:
    strict = AnalyticsParams(t0=T0, slow_ratio=0.9, slow_cover_days=30)
    assert bool(is_slow_moving(frame(ads_30=8.0, ads_90=10.0), strict)[0]) is True
    assert bool(is_slow_moving(frame(days_of_cover=31.0), strict)[0]) is True


# --- dead stock ---


def test_dead_when_stock_and_no_units_in_the_last_30_days() -> None:
    assert dead(units_by_day=units(0, earlier=5)) is True


def test_dead_one_unit_in_the_window_is_not_dead() -> None:
    recent = [0] * 29 + [1]
    assert dead(units_by_day=units(recent, earlier=5)) is False
    recent = [1] + [0] * 29  # the oldest day of the 30-day window
    assert dead(units_by_day=units(recent, earlier=5)) is False


def test_dead_sale_just_outside_the_window_does_not_count() -> None:
    series = np.zeros(90, dtype=np.int64)
    series[59] = 7  # 31 days before t0 (index 89 is t0)
    assert dead(units_by_day=series) is True
    series[60] = 7  # 30th day back: inside the window
    assert dead(units_by_day=series) is False


def test_dead_requires_stock_on_hand() -> None:
    assert dead(on_hand=0, units_by_day=units(0, earlier=0)) is False


def test_dead_window_comes_from_params() -> None:
    short = AnalyticsParams(t0=T0, dead_stock_days=5)
    sold_ten_days_ago = np.zeros(90, dtype=np.int64)
    sold_ten_days_ago[79] = 3
    assert bool(is_dead_stock(frame(units_by_day=sold_ten_days_ago), short)[0]) is True
    assert bool(is_dead_stock(frame(units_by_day=sold_ten_days_ago), PARAMS)[0]) is False


def test_dead_on_an_empty_frame() -> None:
    empty = frame().iloc[0:0]
    assert len(is_dead_stock(empty, PARAMS)) == 0


# --- high demand ---


def test_high_demand_boundary_is_inclusive() -> None:
    assert high(demand_trend=0.30) is True
    assert high(demand_trend=0.2999) is False


def test_high_demand_null_trend_is_false() -> None:
    assert high(demand_trend=np.nan) is False
    assert high(demand_trend=None) is False


def test_high_demand_uses_the_params_threshold() -> None:
    strict = AnalyticsParams(t0=T0, spike_threshold=0.6)
    assert bool(is_high_demand(frame(demand_trend=0.5), strict)[0]) is False


def test_flags_are_boolean_series_aligned_to_the_index() -> None:
    f = pd.concat([frame(), frame(on_hand=0)], ignore_index=True)
    for out in (is_slow_moving(f, PARAMS), is_dead_stock(f, PARAMS), is_high_demand(f, PARAMS)):
        assert out.dtype == bool
        assert out.index.equals(f.index)
