"""Reference data repositories."""

from app.models.reference import Category, Supplier, Warehouse
from app.repositories.base import Repository


class CategoryRepository(Repository[Category]):
    model = Category


class SupplierRepository(Repository[Supplier]):
    model = Supplier


class WarehouseRepository(Repository[Warehouse]):
    model = Warehouse
