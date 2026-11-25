"""Dashboard response schemas (BP 6.2 #11-#13, 6.3 DashboardSummaryOut, FR-A1)."""

from pydantic import BaseModel, Field

from app.schemas.common import Money, SnapshotMeta


class DashboardSummaryOut(BaseModel):
    """KPI tiles, computed only by ``app.analytics.rollup.dashboard_kpis``."""

    total_products: int
    total_units: int
    inventory_value: Money
    low_stock_count: int = Field(description="Products rolled up to HIGH or MEDIUM.")
    stockout_risk_count: int = Field(description="Products rolled up to STOCKOUT, CRITICAL, HIGH.")
    slow_moving_count: int = Field(description="Products with any slow-moving warehouse row.")
    snapshot: SnapshotMeta


class RiskDistributionOut(BaseModel):
    """Counts per risk class. All six classes are always present (0 if none)."""

    rows: dict[str, int] = Field(description="Product x warehouse rows per class.")
    products: dict[str, int] = Field(description="Products per rolled-up (most severe) class.")
    snapshot: SnapshotMeta
