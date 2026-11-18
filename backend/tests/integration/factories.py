"""Row builders for integration tests. Synthetic values only; hashes are dummy strings."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    Category,
    MetricSnapshot,
    Product,
    Supplier,
    User,
    Warehouse,
)
from app.models.enums import UserRole

DUMMY_HASH = "dummy-fixed-hash-not-a-real-credential"
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
TODAY = date(2026, 11, 18)


def make_category(db: Session, code: str = "CAT1") -> Category:
    row = Category(code=code, name=f"Category {code}")
    db.add(row)
    db.flush()
    return row


def make_supplier(db: Session, code: str = "SUP1", **overrides: Any) -> Supplier:
    values: dict[str, Any] = {
        "code": code,
        "name": f"Supplier {code}",
        "default_lead_time_days": 14,
        "min_order_qty": 10,
        "reliability_pct": Decimal("95.00"),
        "contact_email": f"{code.lower()}@example.com",
    }
    values.update(overrides)
    row = Supplier(**values)
    db.add(row)
    db.flush()
    return row


def make_warehouse(db: Session, code: str = "WH1") -> Warehouse:
    row = Warehouse(code=code, name=f"Warehouse {code}", city="Springfield", region="North")
    db.add(row)
    db.flush()
    return row


def make_user(db: Session, username: str = "alice", role: str = UserRole.ANALYST.value) -> User:
    row = User(username=username, password_hash=DUMMY_HASH, role=role)
    db.add(row)
    db.flush()
    return row


def make_product(db: Session, sku: str = "SKU-1", **overrides: Any) -> Product:
    category = make_category(db, code=f"C-{sku}"[:16])
    supplier = make_supplier(db, code=f"S-{sku}"[:16])
    values: dict[str, Any] = {
        "sku": sku,
        "name": f"Product {sku}",
        "category_id": category.id,
        "supplier_id": supplier.id,
        "unit_cost": Decimal("10.00"),
        "unit_price": Decimal("15.00"),
    }
    values.update(overrides)
    row = Product(**values)
    db.add(row)
    db.flush()
    return row


def make_snapshot(db: Session, calculated_at: datetime | None = None) -> MetricSnapshot:
    row = MetricSnapshot(
        data_as_of_date=TODAY, params_json={"service_level": 0.95}, triggered_by="test"
    )
    if calculated_at is not None:
        row.calculated_at = calculated_at
    db.add(row)
    db.flush()
    return row
