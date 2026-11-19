"""Daily demand series generation (BOB-P1-02 section 7.5).

units = Poisson(lambda x warehouse share x weekday factor x scenario multiplier(day)).
All randomness comes from the single ``numpy.random.Generator`` passed in by the orchestrator.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import numpy.typing as npt

from data.seed.catalog import NUM_PRODUCTS, WAREHOUSES, ProductRow
from data.seed.scenarios import (
    DEAD_DAYS,
    SLOW_DAYS,
    SLOW_MULT,
    SPIKE_DAYS,
    SPIKE_MULT,
    Scenario,
    scenario_at,
)

WINDOW_DAYS = 90
WEEKDAY_FACTORS = (0.9, 0.9, 1.0, 1.0, 1.1, 1.3, 1.2)  # Monday .. Sunday
LAMBDA_MIN, LAMBDA_MAX = 2.0, 120.0
LAMBDA_MEDIAN, LAMBDA_SIGMA = 15.0, 0.8  # log-normal parameters (design assumption)

IntArray = npt.NDArray[np.int64]
FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Demand:
    days: tuple[date, ...]  # 90 consecutive dates ending at t0
    lam: FloatArray  # (products,) network-wide base daily demand
    units: IntArray  # (products, warehouses, days)


def window_dates(as_of: date) -> tuple[date, ...]:
    start = as_of - timedelta(days=WINDOW_DAYS - 1)
    return tuple(start + timedelta(days=d) for d in range(WINDOW_DAYS))


def ads_of(row: IntArray, days: int) -> float:
    """Average daily sales over the last ``days`` days of one product-warehouse series."""
    return float(row[-days:].sum()) / days


def days_of_cover(on_hand: int, committed: int, ads30: float) -> float | None:
    """(on_hand - committed) / ADS30. A design-target measure, not the P2 business formula."""
    if ads30 <= 0:
        return None
    return (on_hand - committed) / ads30


def _apply_multiplier(row: FloatArray, scenario: Scenario) -> None:
    if scenario is Scenario.HIGH_DEMAND:
        row[-SPIKE_DAYS:] *= SPIKE_MULT
    elif scenario is Scenario.SLOW_MOVING:
        row[-SLOW_DAYS:] *= SLOW_MULT
    elif scenario is Scenario.DEAD_STOCK:
        row[-DEAD_DAYS:] = 0.0


def _fit_high_demand(row: IntArray) -> None:
    """Deterministically lift the last 14 days so mean(last 14) >= 1.5 x mean(prior 76)."""
    recent, prior = row[-SPIKE_DAYS:], row[:-SPIKE_DAYS]
    recent_sum, prior_sum = int(recent.sum()), int(prior.sum())
    need = -(-3 * SPIKE_DAYS * prior_sum // (2 * len(prior)))  # ceil(1.5 * 14 * prior_sum / 76)
    if recent_sum >= need:
        return
    if recent_sum == 0:
        recent[:] = -(-need // SPIKE_DAYS)
    else:
        recent[:] = (recent * need + recent_sum - 1) // recent_sum  # ceil scaling


def _fit_slow_moving(row: IntArray) -> None:
    """Deterministically thin the last 30 days so ADS30 <= 0.4 x ADS90 (13 x S30 <= 2 x S60)."""
    recent, prior = row[-SLOW_DAYS:], row[:-SLOW_DAYS]
    recent_sum = int(recent.sum())
    cap = (2 * int(prior.sum())) // 13
    if recent_sum > cap:
        recent[:] = (recent * cap) // recent_sum  # floor scaling: new sum <= cap


def generate_demand(rng: np.random.Generator, as_of: date) -> Demand:
    lam = np.round(
        np.clip(
            rng.lognormal(np.log(LAMBDA_MEDIAN), LAMBDA_SIGMA, NUM_PRODUCTS), LAMBDA_MIN, LAMBDA_MAX
        ),
        4,
    )
    days = window_dates(as_of)
    weekday = np.array([WEEKDAY_FACTORS[d.weekday()] for d in days], dtype=np.float64)
    share = np.array([w.demand_share for w in WAREHOUSES], dtype=np.float64)

    multiplier = np.ones((NUM_PRODUCTS, len(WAREHOUSES), WINDOW_DAYS), dtype=np.float64)
    for i in range(NUM_PRODUCTS):
        for j, warehouse in enumerate(WAREHOUSES):
            _apply_multiplier(multiplier[i, j], scenario_at(i + 1, warehouse.code))

    mean = lam[:, None, None] * share[None, :, None] * weekday[None, None, :] * multiplier
    units: IntArray = rng.poisson(mean).astype(np.int64)

    # Deterministic adjustment (never a redraw) so the raw-data design targets hold.
    for i in range(NUM_PRODUCTS):
        for j, warehouse in enumerate(WAREHOUSES):
            scenario = scenario_at(i + 1, warehouse.code)
            if scenario is Scenario.HIGH_DEMAND:
                _fit_high_demand(units[i, j])
            elif scenario is Scenario.SLOW_MOVING:
                _fit_slow_moving(units[i, j])
    return Demand(days=days, lam=lam, units=units)


def sales_rows(
    products: tuple[ProductRow, ...], demand: Demand
) -> list[tuple[str, str, date, int, Decimal]]:
    """One row per product x warehouse x day: (sku, warehouse_code, date, units, revenue)."""
    rows: list[tuple[str, str, date, int, Decimal]] = []
    for i, product in enumerate(products):
        for j, warehouse in enumerate(WAREHOUSES):
            for d, day in enumerate(demand.days):
                units = int(demand.units[i, j, d])
                revenue = (Decimal(units) * product.unit_price).quantize(Decimal("0.01"))
                rows.append((product.sku, warehouse.code, day, units, revenue))
    return rows
