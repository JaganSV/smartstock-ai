"""Seed orchestration and CLI: ``python -m data.seed.generator`` (run from ``backend/``).

Exit codes: 0 success, 1 coverage failure, 2 environment refusal or bad arguments, 3 DB error.
One RNG (``numpy.random.default_rng(seed)``) feeds the whole data path. This module may import
``app.models`` and ``app.core.config`` only; ``app`` never imports ``data``.
"""

import argparse
import sys
import time
from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import Engine, create_engine, delete, func, insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    Category,
    IncomingStock,
    InventoryLevel,
    InventoryPolicy,
    Product,
    SalesDaily,
    Supplier,
    Warehouse,
)
from app.models.base import Base
from data.seed.catalog import CATEGORIES, SUPPLIERS, WAREHOUSES, build_products
from data.seed.demand import generate_demand, sales_rows
from data.seed.report import (
    TABLE_COLUMNS,
    Dataset,
    TableRows,
    all_passed,
    canonical_rows,
    checksums,
    failures,
    fmt_bool,
    fmt_dec,
    fmt_dt,
    fmt_opt,
    min_counts,
    render_markdown,
    run_checks,
)
from data.seed.stock import build_stock

DEFAULT_SEED = 42
DEFAULT_AS_OF = date(2026, 9, 30)
DEFAULT_REPORT_PATH = "../docs/evidence/seed_report.md"
ALLOWED_ENVS = ("local", "test")

# Seeded tables, children first (reverse FK order) for deletion.
SEEDED_MODELS = (
    SalesDaily,
    IncomingStock,
    InventoryLevel,
    InventoryPolicy,
    Product,
    Warehouse,
    Supplier,
    Category,
)
# Tables that are not seeded in P1 and must stay empty.
UNSEEDED_TABLES = (
    "metric_snapshots",
    "product_metrics",
    "replenishment_recommendations",
    "approval_decisions",
    "executive_reports",
    "documents",
    "ai_interactions",
    "audit_log",
    "users",
)


class ChecksumMismatchError(RuntimeError):
    """Stored data does not match the generated data (the transaction is rolled back)."""


def build_dataset(seed: int, as_of: date) -> Dataset:
    """Generate everything in memory from one RNG. Pure and deterministic."""
    rng = np.random.default_rng(seed)
    products = build_products(rng, as_of)
    demand = generate_demand(rng, as_of)
    stock = build_stock(rng, products, demand, as_of)
    return Dataset(seed=seed, as_of=as_of, products=products, demand=demand, stock=stock)


# --- database writing (single transaction, owned by the caller) ---


def delete_seeded(session: Session) -> None:
    for model in SEEDED_MODELS:
        session.execute(delete(model))


def _id_map(result: Iterable[Sequence[Any]]) -> dict[str, int]:
    """natural key -> surrogate id from an INSERT ... RETURNING (code/sku, id)."""
    return {str(row[0]): int(row[1]) for row in result}


def insert_masters(session: Session) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    category_ids = _id_map(
        session.execute(
            insert(Category).returning(Category.code, Category.id),
            [{"code": c.code, "name": c.name, "description": c.description} for c in CATEGORIES],
        )
    )
    supplier_ids = _id_map(
        session.execute(
            insert(Supplier).returning(Supplier.code, Supplier.id),
            [
                {
                    "code": s.code,
                    "name": s.name,
                    "default_lead_time_days": s.lead_time_days,
                    "lead_time_std_days": s.lead_time_std_days,
                    "min_order_qty": s.min_order_qty,
                    "reliability_pct": s.reliability_pct,
                    "contact_email": s.contact_email,
                }
                for s in SUPPLIERS
            ],
        )
    )
    warehouse_ids = _id_map(
        session.execute(
            insert(Warehouse).returning(Warehouse.code, Warehouse.id),
            [
                {"code": w.code, "name": w.name, "city": w.city, "region": w.region}
                for w in WAREHOUSES
            ],
        )
    )
    return category_ids, supplier_ids, warehouse_ids


def insert_products(
    session: Session, ds: Dataset, category_ids: dict[str, int], supplier_ids: dict[str, int]
) -> dict[str, int]:
    return _id_map(
        session.execute(
            insert(Product).returning(Product.sku, Product.id),
            [
                {
                    "sku": p.sku,
                    "name": p.name,
                    "category_id": category_ids[p.category_code],
                    "supplier_id": supplier_ids[p.supplier_code],
                    "unit_cost": p.unit_cost,
                    "unit_price": p.unit_price,
                    "case_pack": p.case_pack,
                    "created_at": p.created_at,
                }
                for p in ds.products
            ],
        )
    )


def insert_policies(
    session: Session, ds: Dataset, product_ids: dict[str, int], warehouse_ids: dict[str, int]
) -> None:
    session.execute(
        insert(InventoryPolicy),
        [
            {
                "product_id": product_ids[r.sku],
                "warehouse_id": warehouse_ids[r.warehouse_code],
                "service_level": r.service_level,
                "review_period_days": r.review_period_days,
                "safety_stock_override": r.safety_stock_override,
                "lead_time_override_days": r.lead_time_override_days,
            }
            for r in ds.stock.policies
        ],
    )


def insert_levels(
    session: Session, ds: Dataset, product_ids: dict[str, int], warehouse_ids: dict[str, int]
) -> None:
    session.execute(
        insert(InventoryLevel),
        [
            {
                "product_id": product_ids[r.sku],
                "warehouse_id": warehouse_ids[r.warehouse_code],
                "on_hand_qty": r.on_hand,
                "committed_qty": r.committed,
                "as_of": r.as_of,
            }
            for r in ds.stock.levels
        ],
    )


def insert_incoming(
    session: Session,
    ds: Dataset,
    product_ids: dict[str, int],
    warehouse_ids: dict[str, int],
    supplier_ids: dict[str, int],
) -> None:
    session.execute(
        insert(IncomingStock),
        [
            {
                "product_id": product_ids[r.sku],
                "warehouse_id": warehouse_ids[r.warehouse_code],
                "supplier_id": supplier_ids[r.supplier_code],
                "quantity": r.quantity,
                "order_date": r.order_date,
                "expected_arrival_date": r.expected_arrival_date,
                "status": r.status,
            }
            for r in ds.stock.incoming
        ],
    )


def insert_sales(
    session: Session, ds: Dataset, product_ids: dict[str, int], warehouse_ids: dict[str, int]
) -> None:
    session.execute(
        insert(SalesDaily),
        [
            {
                "product_id": product_ids[sku],
                "warehouse_id": warehouse_ids[wh],
                "sale_date": day,
                "units_sold": units,
                "revenue": revenue,
            }
            for sku, wh, day, units, revenue in sales_rows(ds.products, ds.demand)
        ],
    )


def write_dataset(session: Session, ds: Dataset) -> None:
    """Delete the seeded tables (reverse FK order) and insert the dataset. No commit."""
    delete_seeded(session)
    category_ids, supplier_ids, warehouse_ids = insert_masters(session)
    product_ids = insert_products(session, ds, category_ids, supplier_ids)
    insert_policies(session, ds, product_ids, warehouse_ids)
    insert_levels(session, ds, product_ids, warehouse_ids)
    insert_incoming(session, ds, product_ids, warehouse_ids, supplier_ids)
    insert_sales(session, ds, product_ids, warehouse_ids)


# --- read-back (same canonical form as the in-memory rows) ---


def read_back_tables(session: Session) -> TableRows:
    """Canonical rows read from the DB, keyed by natural keys (no surrogate ids)."""
    p, w = Product, Warehouse
    cat = select(Category.id, Category.code).subquery()
    sup = select(Supplier.id, Supplier.code).subquery()
    tables: TableRows = {
        "categories": [
            (c.code, c.name, c.description or "")
            for c in session.execute(select(Category)).scalars()
        ],
        "warehouses": [
            (r.code, r.name, r.city, r.region) for r in session.execute(select(Warehouse)).scalars()
        ],
        "suppliers": [
            (
                s.code,
                s.name,
                str(s.default_lead_time_days),
                fmt_dec(s.lead_time_std_days, 2),
                str(s.min_order_qty),
                fmt_dec(s.reliability_pct, 2),
                s.contact_email,
                fmt_bool(s.is_active),
            )
            for s in session.execute(select(Supplier)).scalars()
        ],
        "products": [
            (
                prod.sku,
                prod.name,
                cat_code,
                sup_code,
                fmt_dec(prod.unit_cost, 2),
                fmt_dec(prod.unit_price, 2),
                str(prod.case_pack),
                fmt_bool(prod.is_active),
                fmt_dt(prod.created_at),
            )
            for prod, cat_code, sup_code in session.execute(
                select(Product, cat.c.code, sup.c.code)
                .join(cat, cat.c.id == Product.category_id)
                .join(sup, sup.c.id == Product.supplier_id)
            )
        ],
        "inventory_policies": [
            (
                sku,
                wh,
                fmt_dec(r.service_level, 3),
                str(r.review_period_days),
                fmt_opt(r.safety_stock_override),
                fmt_opt(r.lead_time_override_days),
            )
            for r, sku, wh in session.execute(
                select(InventoryPolicy, p.sku, w.code)
                .join(p, p.id == InventoryPolicy.product_id)
                .join(w, w.id == InventoryPolicy.warehouse_id)
            )
        ],
        "inventory_levels": [
            (sku, wh, str(r.on_hand_qty), str(r.committed_qty), fmt_dt(r.as_of))
            for r, sku, wh in session.execute(
                select(InventoryLevel, p.sku, w.code)
                .join(p, p.id == InventoryLevel.product_id)
                .join(w, w.id == InventoryLevel.warehouse_id)
            )
        ],
        "incoming_stock": [
            (
                sku,
                wh,
                sup_code,
                str(r.quantity),
                r.order_date.isoformat(),
                r.expected_arrival_date.isoformat(),
                r.status,
            )
            for r, sku, wh, sup_code in session.execute(
                select(IncomingStock, p.sku, w.code, sup.c.code)
                .join(p, p.id == IncomingStock.product_id)
                .join(w, w.id == IncomingStock.warehouse_id)
                .join(sup, sup.c.id == IncomingStock.supplier_id)
            )
        ],
        "sales_daily": [
            (sku, wh, r.sale_date.isoformat(), str(r.units_sold), fmt_dec(r.revenue, 2))
            for r, sku, wh in session.execute(
                select(SalesDaily, p.sku, w.code)
                .join(p, p.id == SalesDaily.product_id)
                .join(w, w.id == SalesDaily.warehouse_id)
            )
        ],
    }
    return {name: tables[name] for name in TABLE_COLUMNS}


def db_checksums(session: Session) -> tuple[dict[str, str], str]:
    return checksums(read_back_tables(session))


def count_rows(session: Session, tables: Sequence[str]) -> dict[str, int]:
    metadata = Base.metadata.tables
    return {
        name: int(session.execute(select(func.count()).select_from(metadata[name])).scalar_one())
        for name in tables
    }


def seed_database(engine: Engine, ds: Dataset) -> tuple[str, dict[str, int]]:
    """One transaction: delete, insert, verify checksums, commit; any error rolls back all.

    Returns the database overall checksum and the row counts of the seeded tables.
    """
    expected = checksums(canonical_rows(ds))[1]
    with Session(engine) as session, session.begin():
        write_dataset(session, ds)
        actual = db_checksums(session)[1]
        if actual != expected:
            raise ChecksumMismatchError("stored data does not match the generated data")
        return actual, count_rows(session, sorted(TABLE_COLUMNS))


# --- CLI ---


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m data.seed.generator",
        description="Deterministic synthetic seed generator (local/test only).",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--as-of", type=date.fromisoformat, default=DEFAULT_AS_OF, metavar="YYYY-MM-DD"
    )
    parser.add_argument("--dry-run", action="store_true", help="generate and check; no DB access")
    parser.add_argument("--report-path", default=DEFAULT_REPORT_PATH)
    return parser.parse_args(argv)  # argparse exits with code 2 on bad arguments


def _print_failures(ds: Dataset, checks_failed: list[str]) -> None:
    print("Coverage check FAILED; nothing was written to the database.", file=sys.stderr)
    for line in checks_failed:
        print(f"  FAIL {line}", file=sys.stderr)


def main(argv: Sequence[str] | None = None, app_env: str | None = None) -> int:
    args = _parse_args(argv)
    env = app_env if app_env is not None else get_settings().app_env
    if env not in ALLOWED_ENVS:
        print(
            f"Refusing to seed: APP_ENV={env!r}. Seeding only runs when APP_ENV is one of "
            f"{', '.join(ALLOWED_ENVS)}.",
            file=sys.stderr,
        )
        return 2

    started = time.perf_counter()
    ds = build_dataset(args.seed, args.as_of)
    checks = run_checks(ds)
    markdown = render_markdown(ds, checks, np.__version__)

    if not all_passed(checks):
        problems = [
            f"{c.sku} @ {c.warehouse} [{c.scenario.value}]: {c.measured} | target: {c.target}"
            for c in failures(checks)
        ] + [
            f"minimum count {m.group}: {m.actual} < {m.required}"
            for m in min_counts(checks)
            if not m.passed
        ]
        _print_failures(ds, problems)
        if args.dry_run:
            print(markdown)
        return 1

    if args.dry_run:
        print(markdown)
        print(f"Dry run complete in {time.perf_counter() - started:.2f}s; database untouched.")
        return 0

    engine = create_engine(
        get_settings().sqlalchemy_url, pool_pre_ping=True, connect_args={"connect_timeout": 5}
    )
    try:
        db_overall, counts = seed_database(engine, ds)
    except (SQLAlchemyError, ChecksumMismatchError) as exc:
        detail = str(getattr(exc, "orig", exc)).splitlines()[0]
        print(
            f"Database error ({type(exc).__name__}): {detail}\n"
            "The transaction was rolled back; the database is unchanged.",
            file=sys.stderr,
        )
        return 3
    finally:
        engine.dispose()

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown, encoding="utf-8", newline="\n")
    elapsed = time.perf_counter() - started
    print(f"Seeded seed={args.seed} as_of={args.as_of.isoformat()} in {elapsed:.2f}s")
    for name, count in counts.items():
        print(f"  {name:<20} {count:>7}")
    print(f"overall checksum (database): {db_overall}")
    print(f"report written to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
