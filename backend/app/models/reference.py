"""Master data: categories, suppliers, warehouses."""

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Numeric, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pk_id


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = pk_id()
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint("default_lead_time_days > 0", name="lead_time_positive"),
        CheckConstraint("lead_time_std_days >= 0", name="lead_time_std_nonneg"),
        CheckConstraint("min_order_qty >= 1", name="min_order_qty_positive"),
        CheckConstraint("reliability_pct BETWEEN 0 AND 100", name="reliability_range"),
    )

    id: Mapped[int] = pk_id()
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    default_lead_time_days: Mapped[int]
    lead_time_std_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), server_default="0")
    min_order_qty: Mapped[int]
    reliability_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    contact_email: Mapped[str] = mapped_column(String(254))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = pk_id()
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(100))
