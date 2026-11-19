"""Declarative scenario definitions and SKU assignment (BP section 2.4, BOB-P1-02 section 7.6).

Everything here is a GENERATOR DESIGN TARGET used only to shape synthetic raw data. It is not
business logic and must never be imported by ``app/`` (P2 implements the real formulas
independently). ``R`` is the BP 7.1 default review period, used here only to set targets.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

REVIEW_PERIOD_DAYS = 14  # R, design target only
FIRST_WAREHOUSE = "WH-MUM"


class Scenario(StrEnum):
    STOCKOUT = "STOCKOUT"
    CRITICAL = "CRITICAL"
    HIGH_DEMAND = "HIGH_DEMAND"
    OVERSTOCK = "OVERSTOCK"
    SLOW_MOVING = "SLOW_MOVING"
    DEAD_STOCK = "DEAD_STOCK"
    COVERED_BY_INCOMING = "COVERED_BY_INCOMING"
    COMMITTED_MASKING = "COMMITTED_MASKING"
    HEALTHY = "HEALTHY"


@dataclass(frozen=True)
class ScenarioDef:
    scenario: Scenario
    first_sku: int
    last_sku: int
    warehouse_code: str | None  # None = every warehouse
    target: str  # human-readable design target (for the report)


SCENARIOS = (
    ScenarioDef(Scenario.STOCKOUT, 1, 3, "WH-MUM",
                "committed >= on_hand; ADS30 > 0; no OPEN incoming arriving within L"),
    ScenarioDef(Scenario.CRITICAL, 4, 8, "WH-MUM",
                "0.3L <= DoC <= 0.8L; no OPEN incoming before day floor(DoC)"),
    ScenarioDef(Scenario.HIGH_DEMAND, 9, 12, "WH-BLR",
                "mean(last 14d) >= 1.5 x mean(prior 76d); L <= DoC <= L+R"),
    ScenarioDef(Scenario.OVERSTOCK, 13, 17, "WH-DEL", "150 <= DoC <= 300"),
    ScenarioDef(Scenario.SLOW_MOVING, 18, 20, "WH-MUM",
                "ADS30 <= 0.4 x ADS90; on_hand > 0; DoC > 90"),
    ScenarioDef(Scenario.DEAD_STOCK, 21, 23, "WH-BLR", "0 units in last 35d; on_hand > 0"),
    ScenarioDef(Scenario.COVERED_BY_INCOMING, 24, 26, "WH-MUM",
                "DoC < L; one OPEN order at t0+max(1,floor(DoC)-1) with qty >= ADS30 x (L+R)"),
    ScenarioDef(Scenario.COMMITTED_MASKING, 27, 29, "WH-DEL",
                "on_hand >= 2 x ADS30 x L; 0.2L <= DoC <= 0.7L"),
    ScenarioDef(Scenario.HEALTHY, 30, 50, None,
                "L+R+10 <= DoC <= 90; 0 <= committed <= 10% of on_hand"),
)  # fmt: skip

# BP section 2.4 minimum counts per scenario group (slow + dead are counted together).
MIN_COUNTS: tuple[tuple[str, tuple[Scenario, ...], int], ...] = (
    ("STOCKOUT", (Scenario.STOCKOUT,), 3),
    ("CRITICAL", (Scenario.CRITICAL,), 5),
    ("HIGH_DEMAND", (Scenario.HIGH_DEMAND,), 4),
    ("OVERSTOCK", (Scenario.OVERSTOCK,), 5),
    ("SLOW_MOVING + DEAD_STOCK", (Scenario.SLOW_MOVING, Scenario.DEAD_STOCK), 6),
    ("COVERED_BY_INCOMING", (Scenario.COVERED_BY_INCOMING,), 3),
    ("COMMITTED_MASKING", (Scenario.COMMITTED_MASKING,), 3),
)

# Demand-shape multipliers applied at the scenario's warehouse only.
SPIKE_MULT, SPIKE_DAYS = 1.8, 14
SLOW_MULT, SLOW_DAYS = 0.25, 30
DEAD_DAYS = 35


def sku_scenario(number: int) -> ScenarioDef:
    """The scenario definition a SKU number belongs to."""
    for definition in SCENARIOS:
        if definition.first_sku <= number <= definition.last_sku:
            return definition
    raise ValueError(f"SKU number out of range: {number}")


def scenario_at(number: int, warehouse_code: str) -> Scenario:
    """Scenario of a product at a warehouse: its own at the target warehouse, else HEALTHY."""
    definition = sku_scenario(number)
    if definition.warehouse_code is None or definition.warehouse_code != warehouse_code:
        return Scenario.HEALTHY
    return definition.scenario


@dataclass(frozen=True)
class DocBand:
    """Days-of-cover band: draw inside [draw_lo, draw_hi], then fit into [fit_lo, fit_hi]."""

    draw_lo: float
    draw_hi: float
    fit_lo: float
    fit_hi: float


# Scenario -> band as a function of (L, R). STOCKOUT and DEAD_STOCK have no DoC band.
DOC_BANDS: dict[Scenario, Callable[[int, int], DocBand]] = {
    Scenario.CRITICAL: lambda L, R: DocBand(0.35 * L, 0.75 * L, 0.3 * L, 0.8 * L),
    Scenario.HIGH_DEMAND: lambda L, R: DocBand(L + 1, L + R - 1, L, L + R),
    Scenario.OVERSTOCK: lambda L, R: DocBand(165, 285, 150, 300),
    Scenario.SLOW_MOVING: lambda L, R: DocBand(100, 250, 91, 400),
    Scenario.COVERED_BY_INCOMING: lambda L, R: DocBand(0.4 * L, 0.9 * L, 0.2 * L, 0.95 * L),
    Scenario.COMMITTED_MASKING: lambda L, R: DocBand(0.25 * L, 0.65 * L, 0.2 * L, 0.7 * L),
    Scenario.HEALTHY: lambda L, R: DocBand(L + R + 12, 88, L + R + 10, 90),
}
