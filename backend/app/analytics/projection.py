"""Lead-time projection and projected stockout day (BP 7.3).

    projected(k) = available - ADS30 * k + sum(open quantities with t0 < arrival <= t0 + k)

P2-02 uses ``projected_stockout_day`` for the CRITICAL rule; the P4 chart uses ``projected_stock``
with ``horizon_days = L``. All date logic uses the supplied ``t0`` (ADR-012). Arrivals dated on or
before t0 are ignored here as defence in depth (stock that arrived by t0 is already in on_hand).
"""

from collections.abc import Sequence
from datetime import date, timedelta


def projected_stock(
    available: float,
    ads30: float,
    open_incoming: Sequence[tuple[date, int]],
    t0: date,
    horizon_days: int,
) -> list[float]:
    """Projected stock for k = 0 .. horizon_days (inclusive): ``len == horizon_days + 1``.

    Formula: ``available - ads30 * k + sum(qty for (arrival, qty) if t0 < arrival <= t0 + k)``.
    Arrivals dated on or before ``t0`` are ignored. Stock may go negative (it is not floored):
    negative values mean unmet demand.
    """
    projection: list[float] = []
    for k in range(horizon_days + 1):
        cutoff = t0 + timedelta(days=k)
        arrived = sum(qty for arrival, qty in open_incoming if t0 < arrival <= cutoff)
        projection.append(available - ads30 * k + arrived)
    return projection


def projected_stockout_day(
    available: float,
    ads30: float,
    open_incoming: Sequence[tuple[date, int]],
    t0: date,
    lead_time_days: int,
) -> int | None:
    """First day k in 0 .. L where projected stock is <= 0, else None.

    None when ADS30 = 0 (no recent demand, so no projected stockout). When ``available <= 0`` and
    ADS30 > 0 the result is day 0.
    """
    if ads30 <= 0:
        return None
    for k, stock in enumerate(projected_stock(available, ads30, open_incoming, t0, lead_time_days)):
        if stock <= 0:
            return k
    return None
