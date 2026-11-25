"""Risk response schemas (BP 6.2 #18-#20, FR-C1-C3).

Row-level items reuse ``ProductMetricOut``. ``projected_stockout_day`` and the projection come from
``app.analytics.projection`` on a recomputed row verified equal to the stored one.
"""

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.analytics import RiskTrace
from app.schemas.common import FourDp, Page, SnapshotMeta
from app.schemas.inventory import ProductMetricOut

# --- stockout risk list (#18) ---


class StockoutRiskOut(ProductMetricOut):
    projected_stockout_day: int | None = Field(
        description="First day k in 0..L with projected stock <= 0 (BP 7.3); null if none."
    )
    is_high_demand: bool


class StockoutRiskPage(Page[StockoutRiskOut]):
    snapshot: SnapshotMeta


# --- slow-moving list (#20) ---


class SlowMovingOut(ProductMetricOut):
    is_dead_stock: bool


class SlowMovingPage(Page[SlowMovingOut]):
    snapshot: SnapshotMeta


# --- risk detail (#19) ---


class ProjectionPoint(BaseModel):
    day: int = Field(description="k, days after t0.")
    date: date
    projected_units: FourDp = Field(description="May be negative (unmet demand).")


class OpenIncomingOut(BaseModel):
    expected_arrival_date: date
    quantity: int


class ProjectionOut(BaseModel):
    horizon_days: int = Field(description="L, the row's lead time.")
    points: list[ProjectionPoint] = Field(description="k = 0 .. horizon_days.")
    projected_stockout_day: int | None
    open_incoming: list[OpenIncomingOut] = Field(description="OPEN arrivals after t0, by date.")


class RiskDetailOut(ProductMetricOut):
    """FR-C2: the stored row's fields, its lead time and rule trace, and the BP 7.3 projection."""

    lead_time_days: int
    is_high_demand: bool
    rule_trace: RiskTrace
    projection: ProjectionOut
    snapshot: SnapshotMeta
