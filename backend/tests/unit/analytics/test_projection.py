"""Lead-time projection and projected stockout day (BP 7.3), hand-calculated."""

from datetime import date, timedelta

import pytest

from app.analytics.projection import projected_stock, projected_stockout_day
from tests.unit.analytics.helpers import T0


def day(offset: int) -> date:
    return T0 + timedelta(days=offset)


def test_projected_stock_formula_without_incoming() -> None:
    # 100 - 10 k
    assert projected_stock(100, 10.0, [], T0, 5) == [100, 90, 80, 70, 60, 50]


def test_projected_stock_has_horizon_plus_one_points_and_starts_at_available() -> None:
    out = projected_stock(37, 2.5, [], T0, 9)
    assert len(out) == 10
    assert out[0] == 37


def test_projected_stock_adds_orders_from_their_arrival_day() -> None:
    # 100 - 10 k, plus 50 from day 3 and a further 20 from day 5:
    # k=0 100 | 1 90 | 2 80 | 3 70+50=120 | 4 60+50=110 | 5 50+70=120 | 6 40+70=110
    out = projected_stock(100, 10.0, [(day(3), 50), (day(5), 20)], T0, 6)
    assert out == [100, 90, 80, 120, 110, 120, 110]


def test_projected_stock_is_not_floored_at_zero() -> None:
    assert projected_stock(5, 10.0, [], T0, 2) == [5, -5, -15]


def test_projected_stock_with_zero_horizon() -> None:
    assert projected_stock(8, 3.0, [], T0, 0) == [8]


def test_arrival_on_day_zero_counts_from_day_zero() -> None:
    assert projected_stock(0, 1.0, [(day(0), 10)], T0, 1) == [10, 9]


def test_orders_after_the_horizon_are_ignored() -> None:
    assert projected_stock(10, 1.0, [(day(20), 999)], T0, 3) == [10, 9, 8, 7]


# --- projected_stockout_day ---


def test_stockout_before_lead_time() -> None:
    # 45 - 10 k <= 0 first at k = 5 (45 - 50 = -5); L = 9
    assert projected_stockout_day(45, 10.0, [], T0, 9) == 5


def test_stock_hitting_exactly_zero_counts_as_stockout() -> None:
    # 100 - 10 k = 0 at k = 10; L = 12
    assert projected_stockout_day(100, 10.0, [], T0, 12) == 10


def test_stockout_after_lead_time_is_none() -> None:
    # BP 7.6 worked example: available 100, ADS30 10, L 9 -> stock hits 0 on day 10 > L
    assert projected_stockout_day(100, 10.0, [], T0, 9) is None
    assert projected_stock(100, 10.0, [], T0, 10)[10] == 0  # the day-10 zero, outside L


def test_stockout_on_the_last_day_of_lead_time_is_reported() -> None:
    assert projected_stockout_day(100, 10.0, [], T0, 10) == 10


@pytest.mark.parametrize("available", [0, -1, -500])
def test_non_positive_available_with_demand_is_day_zero(available: int) -> None:
    assert projected_stockout_day(available, 4.0, [], T0, 7) == 0


def test_incoming_order_rescues_the_projection() -> None:
    # without help: 40 - 10 k <= 0 at k = 4. With 100 units arriving day 3: stays positive to L = 7
    assert projected_stockout_day(40, 10.0, [], T0, 7) == 4
    assert projected_stockout_day(40, 10.0, [(day(3), 100)], T0, 7) is None


def test_incoming_that_arrives_too_late_does_not_rescue() -> None:
    # stockout on day 4; the order arrives on day 5
    assert projected_stockout_day(40, 10.0, [(day(5), 100)], T0, 7) == 4


def test_incoming_on_the_stockout_day_rescues() -> None:
    # day 4 would be 0, but 100 arrive on day 4 (arrival <= t0 + k)
    assert projected_stockout_day(40, 10.0, [(day(4), 100)], T0, 7) is None


def test_zero_demand_never_stocks_out() -> None:
    assert projected_stockout_day(0, 0.0, [], T0, 14) is None
    assert projected_stockout_day(-50, 0.0, [], T0, 14) is None
    assert projected_stockout_day(100, 0.0, [], T0, 14) is None


def test_projection_uses_the_supplied_t0_not_the_wall_clock() -> None:
    other = date(2030, 1, 1)
    arrivals = [(other + timedelta(days=3), 100)]
    assert projected_stockout_day(40, 10.0, arrivals, other, 7) is None
    assert projected_stockout_day(40, 10.0, arrivals, T0, 7) == 4  # relative to a different t0


def test_fractional_ads_is_supported() -> None:
    # 10 - 2.5 k <= 0 at k = 4
    assert projected_stockout_day(10, 2.5, [], T0, 8) == 4
