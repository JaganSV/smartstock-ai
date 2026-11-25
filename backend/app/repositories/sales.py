"""Daily sales repository."""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import RowMapping, func, select

from app.models.product import Product
from app.models.sales import SalesDaily
from app.repositories.base import Repository


class SalesRepository(Repository[SalesDaily]):
    """``get`` takes the composite key ``(product_id, warehouse_id, sale_date)``."""

    model = SalesDaily

    def latest_sale_date(self) -> date | None:
        """``max(sale_date)``: the data's own "now" (ADR-012). None when there are no sales."""
        return self.session.execute(select(func.max(SalesDaily.sale_date))).scalar_one()

    def window_rows(self, start_date: date, end_date: date) -> Sequence[RowMapping]:
        """Plain rows (product_id, warehouse_id, sale_date, units_sold), start..end inclusive."""
        stmt = (
            select(
                SalesDaily.product_id,
                SalesDaily.warehouse_id,
                SalesDaily.sale_date,
                SalesDaily.units_sold,
            )
            .where(SalesDaily.sale_date >= start_date, SalesDaily.sale_date <= end_date)
            .order_by(SalesDaily.product_id, SalesDaily.warehouse_id, SalesDaily.sale_date)
        )
        return self.session.execute(stmt).mappings().all()

    def series_rows(
        self,
        start_date: date,
        end_date: date,
        product_id: int | None = None,
        warehouse_id: int | None = None,
        category_id: int | None = None,
    ) -> Sequence[RowMapping]:
        """Plain rows (sale_date, units_sold, revenue), start..end inclusive, optionally filtered by
        product, warehouse and the product's category. Not aggregated. Ordered by date."""
        stmt = select(SalesDaily.sale_date, SalesDaily.units_sold, SalesDaily.revenue).where(
            SalesDaily.sale_date >= start_date, SalesDaily.sale_date <= end_date
        )
        if product_id is not None:
            stmt = stmt.where(SalesDaily.product_id == product_id)
        if warehouse_id is not None:
            stmt = stmt.where(SalesDaily.warehouse_id == warehouse_id)
        if category_id is not None:
            stmt = stmt.join(Product, Product.id == SalesDaily.product_id).where(
                Product.category_id == category_id
            )
        return self.session.execute(stmt.order_by(SalesDaily.sale_date)).mappings().all()

    def daily_series(
        self,
        start_date: date,
        end_date: date,
        product_id: int | None = None,
        warehouse_id: int | None = None,
    ) -> Sequence[SalesDaily]:
        """Rows with ``start_date <= sale_date <= end_date``, optionally filtered."""
        stmt = select(SalesDaily).where(
            SalesDaily.sale_date >= start_date, SalesDaily.sale_date <= end_date
        )
        if product_id is not None:
            stmt = stmt.where(SalesDaily.product_id == product_id)
        if warehouse_id is not None:
            stmt = stmt.where(SalesDaily.warehouse_id == warehouse_id)
        stmt = stmt.order_by(SalesDaily.sale_date, SalesDaily.product_id, SalesDaily.warehouse_id)
        return self.session.scalars(stmt).all()
