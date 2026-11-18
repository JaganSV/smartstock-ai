"""Inventory levels, policies and incoming stock."""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import and_, select

from app.models.enums import IncomingStatus
from app.models.inventory import IncomingStock, InventoryLevel
from app.models.product import InventoryPolicy
from app.repositories.base import Repository


class InventoryRepository(Repository[InventoryLevel]):
    model = InventoryLevel

    def levels_with_policies(self) -> list[tuple[InventoryLevel, InventoryPolicy | None]]:
        """Every inventory level with its policy (None when the pair has no policy row)."""
        stmt = (
            select(InventoryLevel, InventoryPolicy)
            .outerjoin(
                InventoryPolicy,
                and_(
                    InventoryPolicy.product_id == InventoryLevel.product_id,
                    InventoryPolicy.warehouse_id == InventoryLevel.warehouse_id,
                ),
            )
            .order_by(InventoryLevel.product_id, InventoryLevel.warehouse_id)
        )
        return [(level, policy) for level, policy in self.session.execute(stmt).all()]

    def open_incoming(self, until_date: date) -> Sequence[IncomingStock]:
        """OPEN incoming stock expected on or before ``until_date``."""
        stmt = (
            select(IncomingStock)
            .where(
                IncomingStock.status == IncomingStatus.OPEN.value,
                IncomingStock.expected_arrival_date <= until_date,
            )
            .order_by(IncomingStock.expected_arrival_date, IncomingStock.id)
        )
        return self.session.scalars(stmt).all()


class InventoryPolicyRepository(Repository[InventoryPolicy]):
    model = InventoryPolicy


class IncomingStockRepository(Repository[IncomingStock]):
    model = IncomingStock
