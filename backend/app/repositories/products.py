"""Product repository."""

from collections.abc import Sequence

from sqlalchemy import RowMapping, func, or_, select

from app.models.product import Product
from app.models.reference import Category, Supplier
from app.repositories.base import Repository

LIKE_ESCAPE = "\\"


def contains_pattern(text: str) -> str:
    """``%text%`` for LIKE with the escape character, ``%`` and ``_`` escaped (literal match)."""
    escaped = (
        text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )
    return f"%{escaped}%"


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

    def catalogue_rows(
        self,
        category_id: int | None = None,
        supplier_id: int | None = None,
        q: str | None = None,
    ) -> Sequence[RowMapping]:
        """Products with their category and supplier codes, optionally filtered.

        Columns: id, sku, name, category_id, category_code, supplier_id, supplier_code, is_active.
        ``q`` is a case-insensitive substring of sku or name, passed as a bound parameter with
        ``%`` and ``_`` escaped. Ordered by id.
        """
        stmt = (
            select(
                Product.id,
                Product.sku,
                Product.name,
                Product.category_id,
                Category.code.label("category_code"),
                Product.supplier_id,
                Supplier.code.label("supplier_code"),
                Product.is_active,
            )
            .join(Category, Category.id == Product.category_id)
            .join(Supplier, Supplier.id == Product.supplier_id)
            .order_by(Product.id)
        )
        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        if supplier_id is not None:
            stmt = stmt.where(Product.supplier_id == supplier_id)
        if q is not None:
            pattern = contains_pattern(q)
            stmt = stmt.where(
                or_(
                    Product.sku.ilike(pattern, escape=LIKE_ESCAPE),
                    Product.name.ilike(pattern, escape=LIKE_ESCAPE),
                )
            )
        return self.session.execute(stmt).mappings().all()

    def detail_row(self, product_id: int) -> RowMapping | None:
        """One product with its category and supplier reference fields, or None.

        Columns: the product columns, then category_code, category_name, supplier_code,
        supplier_name, supplier_lead_time_days, supplier_min_order_qty.
        """
        stmt = (
            select(
                Product.id,
                Product.sku,
                Product.name,
                Product.category_id,
                Product.supplier_id,
                Product.unit_cost,
                Product.unit_price,
                Product.case_pack,
                Product.is_active,
                Category.code.label("category_code"),
                Category.name.label("category_name"),
                Supplier.code.label("supplier_code"),
                Supplier.name.label("supplier_name"),
                Supplier.default_lead_time_days.label("supplier_lead_time_days"),
                Supplier.min_order_qty.label("supplier_min_order_qty"),
            )
            .join(Category, Category.id == Product.category_id)
            .join(Supplier, Supplier.id == Product.supplier_id)
            .where(Product.id == product_id)
        )
        return self.session.execute(stmt).mappings().first()

    def count_active(self) -> int:
        stmt = select(func.count()).select_from(Product).where(Product.is_active.is_(True))
        return int(self.session.execute(stmt).scalar_one())
