"""Helpers for the read-API tests (BOB-P3-02a): ids by natural key and the latest snapshot."""

import re
from datetime import date
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Category, MetricSnapshot, Product, Supplier, Warehouse

T0 = date(2026, 9, 30)  # seed 42 data_as_of_date (docs/evidence/p2_risk_distribution.md)
MONEY = re.compile(r"^-?\d+\.\d{2}$")
CLASSES = ("STOCKOUT", "CRITICAL", "HIGH", "MEDIUM", "OVERSTOCK", "LOW")


def product_id(engine: Engine, sku: str) -> int:
    with Session(engine) as session:
        return int(session.scalars(select(Product.id).where(Product.sku == sku)).one())


def warehouse_id(engine: Engine, code: str) -> int:
    with Session(engine) as session:
        return int(session.scalars(select(Warehouse.id).where(Warehouse.code == code)).one())


def category_id(engine: Engine, code: str) -> int:
    with Session(engine) as session:
        return int(session.scalars(select(Category.id).where(Category.code == code)).one())


def supplier_id(engine: Engine, code: str) -> int:
    with Session(engine) as session:
        return int(session.scalars(select(Supplier.id).where(Supplier.code == code)).one())


def latest_snapshot(engine: Engine) -> MetricSnapshot:
    with Session(engine, expire_on_commit=False) as session:
        stmt = select(MetricSnapshot).order_by(
            MetricSnapshot.calculated_at.desc(), MetricSnapshot.id.desc()
        )
        snapshot = session.scalars(stmt).first()
    assert snapshot is not None, "the read_api fixture guarantees a snapshot"
    return snapshot


def is_money(value: Any) -> bool:
    return isinstance(value, str) and MONEY.fullmatch(value) is not None
