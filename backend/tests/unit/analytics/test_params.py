"""AnalyticsParams (BP 7.1) and the Z lookup."""

import dataclasses
import json
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from app.analytics.errors import AnalyticsError, UnsupportedServiceLevelError
from app.analytics.params import DEFAULT_Z_TABLE, AnalyticsParams

T0 = date(2026, 9, 30)


def test_defaults_match_bp_7_1() -> None:
    p = AnalyticsParams(t0=T0)
    assert (p.short_window, p.long_window, p.review_period_days) == (30, 90, 14)
    assert (p.overstock_cover_days, p.slow_ratio, p.slow_cover_days) == (120, 0.5, 90)
    assert (p.dead_stock_days, p.spike_threshold) == (30, 0.30)
    assert (p.trend_recent_days, p.trend_prior_days) == (14, 76)
    assert p.z_table == {0.90: 1.28, 0.95: 1.65, 0.975: 1.96, 0.99: 2.33}
    assert p.t0 == T0


def test_trend_windows_add_up_to_the_long_window() -> None:
    p = AnalyticsParams(t0=T0)
    assert p.trend_recent_days + p.trend_prior_days == p.long_window


def test_t0_is_required() -> None:
    constructor: Any = AnalyticsParams  # untyped handle: the call is deliberately incomplete
    with pytest.raises(TypeError):
        constructor()


def test_params_are_frozen() -> None:
    p: Any = AnalyticsParams(t0=T0)  # untyped handle: the assignment is deliberately illegal
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.short_window = 7


def test_each_instance_has_its_own_z_table() -> None:
    a, b = AnalyticsParams(t0=T0), AnalyticsParams(t0=T0)
    a.z_table[0.95] = 9.99
    assert b.z_table[0.95] == 1.65
    assert DEFAULT_Z_TABLE[0.95] == 1.65


@pytest.mark.parametrize(("level", "z"), [(0.90, 1.28), (0.95, 1.65), (0.975, 1.96), (0.99, 2.33)])
def test_z_for_exact_table_values(level: float, z: float) -> None:
    assert AnalyticsParams(t0=T0).z_for(level) == z


@pytest.mark.parametrize("level", [0.95, Decimal("0.950"), 0.9500001, 0.9499999, Decimal("0.95")])
def test_z_for_rounds_to_three_decimals_before_matching(level: float | Decimal) -> None:
    assert AnalyticsParams(t0=T0).z_for(level) == 1.65


@pytest.mark.parametrize("level", [0.80, 0.92, 0.96, 0.97, 0.98, 0.999, 0.925, 0.5])
def test_unsupported_service_levels_raise_and_never_interpolate(level: float) -> None:
    with pytest.raises(UnsupportedServiceLevelError) as info:
        AnalyticsParams(t0=T0).z_for(level)
    assert info.value.code == "UNSUPPORTED_SERVICE_LEVEL"
    assert isinstance(info.value, AnalyticsError)
    assert str(level) in str(info.value)


def test_to_json_is_serialisable_and_complete() -> None:
    payload = AnalyticsParams(t0=T0).to_json()
    assert json.loads(json.dumps(payload)) == payload
    assert payload["t0"] == "2026-09-30"
    assert payload["z_table"] == {"0.9": 1.28, "0.95": 1.65, "0.975": 1.96, "0.99": 2.33}
    expected = {f.name for f in dataclasses.fields(AnalyticsParams)}
    assert set(payload) == expected


def test_custom_overrides_flow_into_json() -> None:
    p = AnalyticsParams(t0=T0, short_window=7, review_period_days=21)
    assert p.to_json()["short_window"] == 7
    assert p.to_json()["review_period_days"] == 21
