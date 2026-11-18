"""Products and per-warehouse inventory policies."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_now, pk_id


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("unit_cost > 0", name="unit_cost_positive"),
        CheckConstraint("unit_price > 0", name="unit_price_positive"),
        CheckConstraint("case_pack >= 1", name="case_pack_positive"),
    )

    id: Mapped[int] = pk_id()
    sku: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    case_pack: Mapped[int] = mapped_column(server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    created_at: Mapped[datetime] = created_now()


class InventoryPolicy(Base):
    __tablename__ = "inventory_policies"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id"),
        CheckConstraint("service_level BETWEEN 0.800 AND 0.999", name="service_level_range"),
        CheckConstraint("review_period_days > 0", name="review_period_positive"),
        CheckConstraint(
            "safety_stock_override IS NULL OR safety_stock_override >= 0",
            name="safety_stock_override_nonneg",
        ),
        CheckConstraint(
            "lead_time_override_days IS NULL OR lead_time_override_days > 0",
            name="lead_time_override_positive",
        ),
    )

    id: Mapped[int] = pk_id()
    # product_id is covered by the leading column of the UNIQUE(product_id, warehouse_id) index.
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT")
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    service_level: Mapped[Decimal] = mapped_column(Numeric(6, 3), server_default="0.950")
    review_period_days: Mapped[int] = mapped_column(server_default="14")
    safety_stock_override: Mapped[int | None]
    lead_time_override_days: Mapped[int | None]
