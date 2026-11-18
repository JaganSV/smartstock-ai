"""Product repository."""

from app.models.product import Product
from app.repositories.base import Repository


class ProductRepository(Repository[Product]):
    model = Product
