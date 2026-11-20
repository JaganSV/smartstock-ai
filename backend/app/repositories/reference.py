"""Reference data repositories."""

from collections.abc import Sequence

from sqlalchemy import RowMapping, select

from app.models.reference import Category, Supplier, Warehouse
from app.repositories.base import Repository


class CategoryRepository(Repository[Category]):
    model = Category


class SupplierRepository(Repository[Supplier]):
    model = Supplier

    def rows(self) -> Sequence[RowMapping]:
        """Plain rows: id, default_lead_time_days, min_order_qty. Ordered by id."""
        stmt = select(
            Supplier.id, Supplier.default_lead_time_days, Supplier.min_order_qty
        ).order_by(Supplier.id)
        return self.session.execute(stmt).mappings().all()


class WarehouseRepository(Repository[Warehouse]):
    model = Warehouse

    def rows(self) -> Sequence[RowMapping]:
        """Plain rows: id, code. Ordered by id."""
        stmt = select(Warehouse.id, Warehouse.code).order_by(Warehouse.id)
        return self.session.execute(stmt).mappings().all()
