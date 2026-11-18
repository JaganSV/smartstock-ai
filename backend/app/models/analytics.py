"""Analytics outputs: metric snapshots and per-product metrics."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_now, pk_id
from app.models.enums import RiskClass, check_in


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id: Mapped[int] = pk_id()
    calculated_at: Mapped[datetime] = created_now()
    data_as_of_date: Mapped[date]
    params_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    triggered_by: Mapped[str] = mapped_column(String(64))


class ProductMetric(Base):
    __tablename__ = "product_metrics"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "product_id", "warehouse_id"),
        CheckConstraint("reorder_qty >= 0", name="reorder_qty_nonneg"),
        CheckConstraint(check_in("risk_class", RiskClass), name="risk_class_values"),
        Index("ix_product_metrics_snapshot_id_risk_class", "snapshot_id", "risk_class"),
    )

    id: Mapped[int] = pk_id()
    # snapshot_id is covered by the leading column of the UNIQUE(snapshot_id, ...) index.
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("metric_snapshots.id", ondelete="CASCADE")
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    on_hand: Mapped[int]
    committed: Mapped[int]
    available: Mapped[int]  # may be negative
    incoming_in_lt: Mapped[int]
    ads_30: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    ads_90: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    demand_std_30: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    lead_time_days: Mapped[int]
    safety_stock: Mapped[int]
    reorder_point: Mapped[int]
    days_of_cover: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))  # null = no recent demand
    reorder_qty: Mapped[int]
    risk_class: Mapped[str] = mapped_column(String(32))
    risk_reason_code: Mapped[str] = mapped_column(String(64))
    is_slow_moving: Mapped[bool] = mapped_column(Boolean)
    is_dead_stock: Mapped[bool] = mapped_column(Boolean)
    demand_trend_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    inventory_value: Mapped[Decimal] = mapped_column(Numeric(14, 2))
