"""Analytics parameters (BP 7.1): one source of truth for every window, threshold and Z value."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.analytics.errors import UnsupportedServiceLevelError

DEFAULT_Z_TABLE: dict[float, float] = {0.90: 1.28, 0.95: 1.65, 0.975: 1.96, 0.99: 2.33}


@dataclass(frozen=True)
class AnalyticsParams:
    """BP 7.1 defaults. ``t0`` (data_as_of_date, ADR-012) is required: no wall clock anywhere."""

    t0: date
    short_window: int = 30
    long_window: int = 90
    review_period_days: int = 14
    overstock_cover_days: int = 120  # used from P2-02
    slow_ratio: float = 0.5  # used from P2-02
    slow_cover_days: int = 90  # used from P2-02
    dead_stock_days: int = 30  # used from P2-02
    spike_threshold: float = 0.30  # used from P2-02
    trend_recent_days: int = 14
    trend_prior_days: int = 76
    z_table: dict[float, float] = field(default_factory=lambda: dict(DEFAULT_Z_TABLE))

    def z_for(self, service_level: float | Decimal) -> float:
        """Z for a service level: exact match after rounding to 3 dp. Never interpolates."""
        key = round(float(service_level), 3)
        try:
            return self.z_table[key]
        except KeyError:
            raise UnsupportedServiceLevelError(key, sorted(self.z_table)) from None

    def to_json(self) -> dict[str, Any]:
        """JSON-serialisable form (stored in metric_snapshots.params_json by P2-02)."""
        return {
            "t0": self.t0.isoformat(),
            "short_window": self.short_window,
            "long_window": self.long_window,
            "review_period_days": self.review_period_days,
            "overstock_cover_days": self.overstock_cover_days,
            "slow_ratio": self.slow_ratio,
            "slow_cover_days": self.slow_cover_days,
            "dead_stock_days": self.dead_stock_days,
            "spike_threshold": self.spike_threshold,
            "trend_recent_days": self.trend_recent_days,
            "trend_prior_days": self.trend_prior_days,
            "z_table": {str(level): z for level, z in sorted(self.z_table.items())},
        }
