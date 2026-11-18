"""Daily sales history."""

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SalesDaily(Base):
    __tablename__ = "sales_daily"
    __table_args__ = (
        CheckConstraint("units_sold >= 0", name="units_sold_nonneg"),
        CheckConstraint("revenue >= 0", name="revenue_nonneg"),
    )

    # Composite PK (product_id, warehouse_id, sale_date); product_id is its leading column.
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
    sale_date: Mapped[date] = mapped_column(primary_key=True, index=True)
    units_sold: Mapped[int]
    revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2))
