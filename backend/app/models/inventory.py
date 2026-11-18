"""Stock on hand and incoming (open purchase) stock."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pk_id
from app.models.enums import IncomingStatus, check_in


class InventoryLevel(Base):
    __tablename__ = "inventory_levels"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id"),
        CheckConstraint("on_hand_qty >= 0", name="on_hand_nonneg"),
        CheckConstraint("committed_qty >= 0", name="committed_nonneg"),
    )

    id: Mapped[int] = pk_id()
    # product_id is covered by the leading column of the UNIQUE(product_id, warehouse_id) index.
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT")
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    on_hand_qty: Mapped[int]
    committed_qty: Mapped[int] = mapped_column(server_default="0")
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IncomingStock(Base):
    __tablename__ = "incoming_stock"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(check_in("status", IncomingStatus), name="status_values"),
        CheckConstraint("expected_arrival_date >= order_date", name="arrival_after_order"),
        Index("ix_incoming_stock_status_expected_arrival_date", "status", "expected_arrival_date"),
    )

    id: Mapped[int] = pk_id()
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int]
    order_date: Mapped[date]
    expected_arrival_date: Mapped[date]
    status: Mapped[str] = mapped_column(String(32), server_default=IncomingStatus.OPEN.value)
