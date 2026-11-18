"""Daily sales repository."""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select

from app.models.sales import SalesDaily
from app.repositories.base import Repository


class SalesRepository(Repository[SalesDaily]):
    """``get`` takes the composite key ``(product_id, warehouse_id, sale_date)``."""

    model = SalesDaily

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
