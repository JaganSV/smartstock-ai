"""Inventory levels, policies and incoming stock."""

from collections.abc import Collection, Sequence
from datetime import date

from sqlalchemy import RowMapping, and_, select

from app.models.enums import IncomingStatus
from app.models.inventory import IncomingStock, InventoryLevel
from app.models.product import InventoryPolicy
from app.repositories.base import Repository, where_in


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

    def level_rows(
        self,
        product_ids: Collection[int] | None = None,
        warehouse_ids: Collection[int] | None = None,
    ) -> Sequence[RowMapping]:
        """Plain rows (product_id, warehouse_id, on_hand_qty, committed_qty), ordered by ids.
        ``product_ids`` / ``warehouse_ids`` restrict the rows (None: all)."""
        stmt = select(
            InventoryLevel.product_id,
            InventoryLevel.warehouse_id,
            InventoryLevel.on_hand_qty,
            InventoryLevel.committed_qty,
        ).order_by(InventoryLevel.product_id, InventoryLevel.warehouse_id)
        stmt = where_in(stmt, InventoryLevel.product_id, product_ids)
        stmt = where_in(stmt, InventoryLevel.warehouse_id, warehouse_ids)
        return self.session.execute(stmt).mappings().all()

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

    def rows(
        self,
        product_ids: Collection[int] | None = None,
        warehouse_ids: Collection[int] | None = None,
    ) -> Sequence[RowMapping]:
        """Plain rows: product_id, warehouse_id, service_level, review_period_days,
        safety_stock_override, lead_time_override_days. Ordered by ids.
        ``product_ids`` / ``warehouse_ids`` restrict the rows (None: all)."""
        stmt = select(
            InventoryPolicy.product_id,
            InventoryPolicy.warehouse_id,
            InventoryPolicy.service_level,
            InventoryPolicy.review_period_days,
            InventoryPolicy.safety_stock_override,
            InventoryPolicy.lead_time_override_days,
        ).order_by(InventoryPolicy.product_id, InventoryPolicy.warehouse_id)
        stmt = where_in(stmt, InventoryPolicy.product_id, product_ids)
        stmt = where_in(stmt, InventoryPolicy.warehouse_id, warehouse_ids)
        return self.session.execute(stmt).mappings().all()

    def rows_for_product(self, product_id: int) -> Sequence[RowMapping]:
        """``rows()`` columns for one product. Ordered by warehouse id."""
        stmt = (
            select(
                InventoryPolicy.product_id,
                InventoryPolicy.warehouse_id,
                InventoryPolicy.service_level,
                InventoryPolicy.review_period_days,
                InventoryPolicy.safety_stock_override,
                InventoryPolicy.lead_time_override_days,
            )
            .where(InventoryPolicy.product_id == product_id)
            .order_by(InventoryPolicy.warehouse_id)
        )
        return self.session.execute(stmt).mappings().all()


class IncomingStockRepository(Repository[IncomingStock]):
    model = IncomingStock

    def open_rows_after(
        self,
        after_date: date,
        product_ids: Collection[int] | None = None,
        warehouse_ids: Collection[int] | None = None,
    ) -> Sequence[RowMapping]:
        """Plain rows (product_id, warehouse_id, quantity, expected_arrival_date, status) of OPEN
        orders expected strictly after ``after_date``.
        ``product_ids`` / ``warehouse_ids`` restrict the rows (None: all)."""
        stmt = (
            select(
                IncomingStock.product_id,
                IncomingStock.warehouse_id,
                IncomingStock.quantity,
                IncomingStock.expected_arrival_date,
                IncomingStock.status,
            )
            .where(
                IncomingStock.status == IncomingStatus.OPEN.value,
                IncomingStock.expected_arrival_date > after_date,
            )
            .order_by(IncomingStock.expected_arrival_date, IncomingStock.id)
        )
        stmt = where_in(stmt, IncomingStock.product_id, product_ids)
        stmt = where_in(stmt, IncomingStock.warehouse_id, warehouse_ids)
        return self.session.execute(stmt).mappings().all()
