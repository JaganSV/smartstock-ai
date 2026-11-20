"""Product repository."""

from collections.abc import Sequence

from sqlalchemy import RowMapping, func, select

from app.models.product import Product
from app.repositories.base import Repository


class ProductRepository(Repository[Product]):
    model = Product

    def active_rows(self) -> Sequence[RowMapping]:
        """Active products as plain rows: id, sku, supplier_id, category_id, unit_cost, case_pack,
        is_active. Ordered by id."""
        stmt = (
            select(
                Product.id,
                Product.sku,
                Product.supplier_id,
                Product.category_id,
                Product.unit_cost,
                Product.case_pack,
                Product.is_active,
            )
            .where(Product.is_active.is_(True))
            .order_by(Product.id)
        )
        return self.session.execute(stmt).mappings().all()

    def count_active(self) -> int:
        stmt = select(func.count()).select_from(Product).where(Product.is_active.is_(True))
        return int(self.session.execute(stmt).scalar_one())
