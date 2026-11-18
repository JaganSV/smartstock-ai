"""Import every model so `Base.metadata` is complete (used by Alembic autogenerate)."""

from app.models.analytics import MetricSnapshot, ProductMetric
from app.models.base import Base
from app.models.governance import AiInteraction, AuditLog, User
from app.models.inventory import IncomingStock, InventoryLevel
from app.models.knowledge import Document
from app.models.product import InventoryPolicy, Product
from app.models.reference import Category, Supplier, Warehouse
from app.models.replenishment import ApprovalDecision, ReplenishmentRecommendation
from app.models.reports import ExecutiveReport
from app.models.sales import SalesDaily

__all__ = [
    "AiInteraction",
    "ApprovalDecision",
    "AuditLog",
    "Base",
    "Category",
    "Document",
    "ExecutiveReport",
    "IncomingStock",
    "InventoryLevel",
    "InventoryPolicy",
    "MetricSnapshot",
    "Product",
    "ProductMetric",
    "ReplenishmentRecommendation",
    "SalesDaily",
    "Supplier",
    "User",
    "Warehouse",
]
