"""Reference data repositories."""

from collections.abc import Collection, Sequence

from sqlalchemy import RowMapping, select

from app.models.reference import Category, Supplier, Warehouse
from app.repositories.base import Repository, where_in


class CategoryRepository(Repository[Category]):
    model = Category

    def reference_rows(self) -> Sequence[RowMapping]:
        """Plain rows: id, code, name. Ordered by code."""
        stmt = select(Category.id, Category.code, Category.name).order_by(Category.code)
        return self.session.execute(stmt).mappings().all()


class SupplierRepository(Repository[Supplier]):
    model = Supplier

    def rows(self) -> Sequence[RowMapping]:
        """Plain rows: id, default_lead_time_days, min_order_qty. Ordered by id."""
        stmt = select(
            Supplier.id, Supplier.default_lead_time_days, Supplier.min_order_qty
        ).order_by(Supplier.id)
        return self.session.execute(stmt).mappings().all()

    def reference_rows(self) -> Sequence[RowMapping]:
        """Plain rows without ``contact_email``: id, code, name, default_lead_time_days,
        min_order_qty, reliability_pct, is_active. Ordered by code."""
        stmt = select(
            Supplier.id,
            Supplier.code,
            Supplier.name,
            Supplier.default_lead_time_days,
            Supplier.min_order_qty,
            Supplier.reliability_pct,
            Supplier.is_active,
        ).order_by(Supplier.code)
        return self.session.execute(stmt).mappings().all()


class WarehouseRepository(Repository[Warehouse]):
    model = Warehouse

    def rows(self, warehouse_ids: Collection[int] | None = None) -> Sequence[RowMapping]:
        """Plain rows: id, code. Ordered by id. ``warehouse_ids`` restricts the rows (None: all)."""
        stmt = select(Warehouse.id, Warehouse.code).order_by(Warehouse.id)
        stmt = where_in(stmt, Warehouse.id, warehouse_ids)
        return self.session.execute(stmt).mappings().all()

    def reference_rows(self) -> Sequence[RowMapping]:
        """Plain rows: id, code, name, city, region. Ordered by code."""
        stmt = select(
            Warehouse.id, Warehouse.code, Warehouse.name, Warehouse.city, Warehouse.region
        ).order_by(Warehouse.code)
        return self.session.execute(stmt).mappings().all()
