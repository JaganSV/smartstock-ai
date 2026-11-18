"""Repository tests against the real test database (no mocks)."""

import inspect
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AiInteraction,
    ApprovalDecision,
    AuditLog,
    Category,
    Document,
    ExecutiveReport,
    IncomingStock,
    InventoryLevel,
    InventoryPolicy,
    MetricSnapshot,
    Product,
    ProductMetric,
    ReplenishmentRecommendation,
    SalesDaily,
    Supplier,
    User,
    Warehouse,
)
from app.repositories.ai_interactions import AiInteractionRepository
from app.repositories.audit import AuditRepository
from app.repositories.base import Repository
from app.repositories.documents import DocumentRepository
from app.repositories.inventory import (
    IncomingStockRepository,
    InventoryPolicyRepository,
    InventoryRepository,
)
from app.repositories.metrics import MetricsRepository, ProductMetricRepository
from app.repositories.products import ProductRepository
from app.repositories.reference import CategoryRepository, SupplierRepository, WarehouseRepository
from app.repositories.replenishment import ApprovalDecisionRepository, ReplenishmentRepository
from app.repositories.reports import ExecutiveReportRepository
from app.repositories.sales import SalesRepository
from app.repositories.users import UsersRepository
from tests.integration import factories as f
from tests.integration.factories import (
    NOW,
    TODAY,
    make_product,
    make_snapshot,
    make_supplier,
    make_user,
    make_warehouse,
)
from tests.integration.test_constraints import (
    Ctx,
    decision,
    document,
    incoming,
    interaction,
    level,
    metric,
    policy,
    recommendation,
    report,
    sales,
)


@pytest.fixture
def ctx(db: Session) -> Ctx:
    return Ctx(
        db=db,
        product=make_product(db),
        warehouse=make_warehouse(db),
        user=make_user(db),
        snapshot=make_snapshot(db),
        supplier=make_supplier(db, code="SUP-X"),
    )


# --- CRUD round trip for every base repository -------------------------------------------------

Builder = Callable[[Ctx], Any]


def _rec(c: Ctx) -> ReplenishmentRecommendation:
    row = recommendation(c)
    c.db.add(row)
    c.db.flush()
    return row


CASES: list[tuple[str, type[Repository[Any]], Builder]] = [
    ("category", CategoryRepository, lambda c: Category(code="NEWCAT", name="n")),
    (
        "supplier",
        SupplierRepository,
        lambda c: Supplier(
            code="NEWSUP",
            name="n",
            default_lead_time_days=3,
            min_order_qty=1,
            reliability_pct=Decimal("50"),
            contact_email="n@example.com",
        ),
    ),
    (
        "warehouse",
        WarehouseRepository,
        lambda c: Warehouse(code="NEWWH", name="n", city="c", region="r"),
    ),
    (
        "product",
        ProductRepository,
        lambda c: Product(
            sku="NEW-SKU",
            name="n",
            category_id=c.product.category_id,
            supplier_id=c.supplier.id,
            unit_cost=Decimal("1"),
            unit_price=Decimal("2"),
        ),
    ),
    ("policy", InventoryPolicyRepository, lambda c: policy(c)),
    ("level", InventoryRepository, lambda c: level(c)),
    ("incoming", IncomingStockRepository, lambda c: incoming(c)),
    (
        "snapshot",
        MetricsRepository,
        lambda c: MetricSnapshot(data_as_of_date=TODAY, params_json={}, triggered_by="t"),
    ),
    ("metric", ProductMetricRepository, lambda c: metric(c)),
    ("recommendation", ReplenishmentRepository, lambda c: recommendation(c)),
    ("decision", ApprovalDecisionRepository, lambda c: decision(c, _rec(c))),
    ("report", ExecutiveReportRepository, lambda c: report(c)),
    ("document", DocumentRepository, lambda c: document(c)),
    ("ai_interaction", AiInteractionRepository, lambda c: interaction()),
    ("audit", AuditRepository, lambda c: AuditLog(action="TEST", details={"k": "v"})),
    (
        "user",
        UsersRepository,
        lambda c: User(username="carol", password_hash=f.DUMMY_HASH, role="ADMIN"),
    ),
]


@pytest.mark.parametrize(("name", "repo_cls", "build"), CASES, ids=[c[0] for c in CASES])
def test_add_get_list_round_trip(
    ctx: Ctx, name: str, repo_cls: type[Repository[Any]], build: Builder
) -> None:
    repo = repo_cls(ctx.db)
    entity = build(ctx)
    added = repo.add(entity)
    assert added is entity
    pk = tuple(getattr(entity, col.key) for col in entity.__mapper__.primary_key)
    assert all(value is not None for value in pk)  # flush populated generated ids
    ctx.db.expunge(entity)  # force a real read, not the identity map
    fetched = repo.get(pk[0] if len(pk) == 1 else pk)
    assert fetched is not None
    assert tuple(getattr(fetched, col.key) for col in fetched.__mapper__.primary_key) == pk
    assert any(
        tuple(getattr(row, col.key) for col in row.__mapper__.primary_key) == pk
        for row in repo.list(offset=0, limit=100)
    )


def test_get_missing_returns_none(ctx: Ctx) -> None:
    assert CategoryRepository(ctx.db).get(999_999) is None
    assert AiInteractionRepository(ctx.db).get(uuid.uuid4()) is None


def test_list_offset_and_limit(ctx: Ctx) -> None:
    repo = CategoryRepository(ctx.db)
    for i in range(5):
        repo.add(Category(code=f"L{i}", name=f"cat {i}"))
    everything = repo.list(offset=0, limit=100)
    assert len(everything) >= 5
    page = repo.list(offset=1, limit=2)
    assert [c.id for c in page] == [c.id for c in everything][1:3]


@pytest.mark.parametrize(("offset", "limit"), [(0, 101), (0, 0), (0, -1), (-1, 10)])
def test_list_rejects_bad_paging(ctx: Ctx, offset: int, limit: int) -> None:
    with pytest.raises(ValueError):
        CategoryRepository(ctx.db).list(offset=offset, limit=limit)


def test_list_accepts_limit_of_exactly_100(ctx: Ctx) -> None:
    assert len(CategoryRepository(ctx.db).list(offset=0, limit=100)) <= 100


def test_repository_never_commits(ctx: Ctx) -> None:
    """add() flushes only: rolling back the session discards the row."""
    repo = CategoryRepository(ctx.db)
    saved = repo.add(Category(code="NOCOMMIT", name="x"))
    assert saved.id is not None
    assert ctx.db.in_transaction()


def test_integrity_errors_are_not_swallowed(ctx: Ctx) -> None:
    repo = CategoryRepository(ctx.db)
    repo.add(Category(code="DUPE", name="a"))
    with pytest.raises(IntegrityError), ctx.db.begin_nested():
        repo.add(Category(code="DUPE", name="b"))


# --- query methods -----------------------------------------------------------------------------


def test_daily_series_filters_by_date_product_and_warehouse(ctx: Ctx) -> None:
    other_product = make_product(ctx.db, sku="SKU-2")
    other_wh = make_warehouse(ctx.db, code="WH-2")
    repo = SalesRepository(ctx.db)
    days = [TODAY - timedelta(days=n) for n in (4, 3, 2, 1, 0)]
    for day in days:
        repo.add(sales(ctx, sale_date=day, units_sold=1))
    repo.add(sales(ctx, sale_date=TODAY, product_id=other_product.id, units_sold=2))
    repo.add(sales(ctx, sale_date=TODAY, warehouse_id=other_wh.id, units_sold=3))

    window = repo.daily_series(days[1], days[3])  # inclusive on both ends
    assert [r.sale_date for r in window] == days[1:4]

    assert {r.product_id for r in repo.daily_series(TODAY, TODAY, product_id=other_product.id)} == {
        other_product.id
    }
    only_wh = repo.daily_series(TODAY, TODAY, warehouse_id=other_wh.id)
    assert [r.units_sold for r in only_wh] == [3]
    both = repo.daily_series(
        days[0], TODAY, product_id=ctx.product.id, warehouse_id=ctx.warehouse.id
    )
    assert len(both) == 5
    assert repo.daily_series(TODAY + timedelta(days=1), TODAY + timedelta(days=9)) == []


def test_sales_get_by_composite_key(ctx: Ctx) -> None:
    repo = SalesRepository(ctx.db)
    repo.add(sales(ctx))
    ctx.db.expunge_all()
    row = repo.get((ctx.product.id, ctx.warehouse.id, TODAY))
    assert isinstance(row, SalesDaily)


def test_latest_snapshot_returns_newest(ctx: Ctx) -> None:
    repo = MetricsRepository(ctx.db)
    assert repo.latest_snapshot() is not None  # the fixture's snapshot
    old = make_snapshot(ctx.db, calculated_at=NOW - timedelta(days=30))
    newest = make_snapshot(ctx.db, calculated_at=datetime(2030, 1, 1, tzinfo=UTC))
    middle = make_snapshot(ctx.db, calculated_at=datetime(2029, 1, 1, tzinfo=UTC))
    latest = repo.latest_snapshot()
    assert latest is not None
    assert latest.id == newest.id
    assert latest.id not in {old.id, middle.id}


def test_latest_snapshot_none_when_empty(db: Session) -> None:
    assert MetricsRepository(db).latest_snapshot() is None


def test_get_by_username(ctx: Ctx) -> None:
    repo = UsersRepository(ctx.db)
    found = repo.get_by_username(ctx.user.username)
    assert found is not None and found.id == ctx.user.id
    assert repo.get_by_username("nobody") is None


def test_levels_with_policies_includes_unpolicied_levels(ctx: Ctx) -> None:
    other_wh = make_warehouse(ctx.db, code="WH-P")
    repo = InventoryRepository(ctx.db)
    repo.add(level(ctx))
    repo.add(level(ctx, warehouse_id=other_wh.id))
    InventoryPolicyRepository(ctx.db).add(policy(ctx, service_level=Decimal("0.900")))

    rows = repo.levels_with_policies()
    by_wh = {lvl.warehouse_id: pol for lvl, pol in rows}
    assert isinstance(by_wh[ctx.warehouse.id], InventoryPolicy)
    with_policy = by_wh[ctx.warehouse.id]
    assert with_policy is not None
    assert with_policy.service_level == Decimal("0.900")
    assert by_wh[other_wh.id] is None
    assert all(isinstance(lvl, InventoryLevel) for lvl, _ in rows)


def test_open_incoming_filters_status_and_date(ctx: Ctx) -> None:
    repo = InventoryRepository(ctx.db)
    stock = IncomingStockRepository(ctx.db)
    cutoff = date(2026, 12, 1)
    due = stock.add(incoming(ctx, expected_arrival_date=cutoff))
    early = stock.add(incoming(ctx, expected_arrival_date=cutoff - timedelta(days=5)))
    stock.add(incoming(ctx, expected_arrival_date=cutoff + timedelta(days=1)))  # too late
    stock.add(incoming(ctx, expected_arrival_date=cutoff - timedelta(days=1), status="RECEIVED"))
    stock.add(incoming(ctx, expected_arrival_date=cutoff - timedelta(days=1), status="CANCELLED"))

    result = repo.open_incoming(cutoff)
    assert [r.id for r in result] == [early.id, due.id]
    assert all(isinstance(r, IncomingStock) for r in result)


# --- insert-only repositories (BP §10.8) -------------------------------------------------------

MUTATORS = (
    "update",
    "delete",
    "remove",
    "merge",
    "save",
    "upsert",
    "set",
    "patch",
    "put",
    "commit",
)


def _public_methods(cls: type) -> set[str]:
    return {n for n, _ in inspect.getmembers(cls, inspect.isfunction) if not n.startswith("_")}


@pytest.mark.parametrize(
    "repo_cls", [AuditRepository, ApprovalDecisionRepository, AiInteractionRepository]
)
def test_insert_only_repositories_have_no_update_or_delete(repo_cls: type[Repository[Any]]) -> None:
    allowed = {"get", "list", "add"}
    if repo_cls is AiInteractionRepository:
        allowed = allowed | {"set_feedback"}  # the single permitted update
    assert _public_methods(repo_cls) == allowed
    for forbidden in MUTATORS:
        assert not hasattr(repo_cls, forbidden), forbidden


def test_set_feedback_is_the_only_update_and_enforces_check(ctx: Ctx) -> None:
    repo = AiInteractionRepository(ctx.db)
    row = repo.add(interaction())
    assert repo.set_feedback(row.id, 1) is True
    ctx.db.expire_all()
    reloaded = repo.get(row.id)
    assert reloaded is not None and reloaded.feedback == 1
    assert repo.set_feedback(row.id, -1) is True
    assert repo.set_feedback(uuid.uuid4(), 1) is False
    with pytest.raises(IntegrityError), ctx.db.begin_nested():
        repo.set_feedback(row.id, 0)
    assert isinstance(reloaded, AiInteraction)


def test_audit_and_decision_rows_round_trip_via_insert_only_api(ctx: Ctx) -> None:
    audit = AuditRepository(ctx.db).add(AuditLog(action="LOGIN", user_id=ctx.user.id))
    assert audit.id is not None
    assert audit.details == {}
    rec = ReplenishmentRepository(ctx.db).add(recommendation(ctx))
    dec = ApprovalDecisionRepository(ctx.db).add(decision(ctx, rec))
    assert isinstance(dec, ApprovalDecision)
    assert isinstance(ExecutiveReportRepository(ctx.db).add(report(ctx)), ExecutiveReport)
    assert isinstance(DocumentRepository(ctx.db).add(document(ctx)), Document)
    assert isinstance(ProductMetricRepository(ctx.db).add(metric(ctx)), ProductMetric)
