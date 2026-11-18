"""One failing insert per CHECK / UNIQUE / FK rule in BOB-P1-01 §7.3 (plus positive controls).

Each negative test asserts the *name* of the violated constraint reported by PostgreSQL, so a
test cannot pass because of a different rule.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AiInteraction,
    ApprovalDecision,
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
from tests.integration.factories import (
    DUMMY_HASH,
    NOW,
    TODAY,
    make_product,
    make_snapshot,
    make_supplier,
    make_user,
    make_warehouse,
)


@dataclass
class Ctx:
    db: Session
    product: Product
    warehouse: Warehouse
    user: User
    snapshot: MetricSnapshot
    supplier: Supplier


@pytest.fixture
def ctx(db: Session) -> Ctx:
    product = make_product(db)
    return Ctx(
        db=db,
        product=product,
        warehouse=make_warehouse(db),
        user=make_user(db),
        snapshot=make_snapshot(db),
        supplier=make_supplier(db, code="SUP-X"),
    )


def violated(db: Session, *rows: Any) -> str:
    """Insert rows expecting an IntegrityError; return the violated constraint's name."""
    with pytest.raises(IntegrityError) as caught, db.begin_nested():
        db.add_all(rows)
        db.flush()
    name = caught.value.orig.diag.constraint_name
    assert name is not None
    return str(name)


def ok(db: Session, *rows: Any) -> None:
    with db.begin_nested():
        db.add_all(rows)
        db.flush()


# --- helpers building valid rows with one field broken ---------------------------------------


def supplier(**kw: Any) -> Supplier:
    values: dict[str, Any] = {
        "code": "S-NEW",
        "name": "S",
        "default_lead_time_days": 7,
        "min_order_qty": 1,
        "reliability_pct": Decimal("90"),
        "contact_email": "s@example.com",
    }
    values.update(kw)
    return Supplier(**values)


def product(c: Ctx, **kw: Any) -> Product:
    values: dict[str, Any] = {
        "sku": "SKU-NEW",
        "name": "P",
        "category_id": c.product.category_id,
        "supplier_id": c.supplier.id,
        "unit_cost": Decimal("1.00"),
        "unit_price": Decimal("2.00"),
    }
    values.update(kw)
    return Product(**values)


def policy(c: Ctx, **kw: Any) -> InventoryPolicy:
    values: dict[str, Any] = {"product_id": c.product.id, "warehouse_id": c.warehouse.id}
    values.update(kw)
    return InventoryPolicy(**values)


def level(c: Ctx, **kw: Any) -> InventoryLevel:
    values: dict[str, Any] = {
        "product_id": c.product.id,
        "warehouse_id": c.warehouse.id,
        "on_hand_qty": 5,
        "as_of": NOW,
    }
    values.update(kw)
    return InventoryLevel(**values)


def incoming(c: Ctx, **kw: Any) -> IncomingStock:
    values: dict[str, Any] = {
        "product_id": c.product.id,
        "warehouse_id": c.warehouse.id,
        "supplier_id": c.supplier.id,
        "quantity": 10,
        "order_date": TODAY,
        "expected_arrival_date": TODAY,
    }
    values.update(kw)
    return IncomingStock(**values)


def sales(c: Ctx, **kw: Any) -> SalesDaily:
    values: dict[str, Any] = {
        "product_id": c.product.id,
        "warehouse_id": c.warehouse.id,
        "sale_date": TODAY,
        "units_sold": 1,
        "revenue": Decimal("1.00"),
    }
    values.update(kw)
    return SalesDaily(**values)


def metric(c: Ctx, **kw: Any) -> ProductMetric:
    values: dict[str, Any] = {
        "snapshot_id": c.snapshot.id,
        "product_id": c.product.id,
        "warehouse_id": c.warehouse.id,
        "on_hand": 1,
        "committed": 0,
        "available": -3,  # may be negative
        "incoming_in_lt": 0,
        "ads_30": Decimal("1"),
        "ads_90": Decimal("1"),
        "demand_std_30": Decimal("0"),
        "lead_time_days": 7,
        "safety_stock": 1,
        "reorder_point": 2,
        "days_of_cover": None,  # null = no recent demand
        "reorder_qty": 0,
        "risk_class": "LOW",
        "risk_reason_code": "TEST",
        "is_slow_moving": False,
        "is_dead_stock": False,
        "demand_trend_pct": None,
        "inventory_value": Decimal("1.00"),
    }
    values.update(kw)
    return ProductMetric(**values)


def recommendation(c: Ctx, **kw: Any) -> ReplenishmentRecommendation:
    values: dict[str, Any] = {
        "snapshot_id": c.snapshot.id,
        "product_id": c.product.id,
        "warehouse_id": c.warehouse.id,
        "supplier_id": c.supplier.id,
        "proposed_qty": 10,
        "est_cost": Decimal("100.00"),
    }
    values.update(kw)
    return ReplenishmentRecommendation(**values)


def decision(c: Ctx, rec: ReplenishmentRecommendation, **kw: Any) -> ApprovalDecision:
    values: dict[str, Any] = {
        "recommendation_id": rec.id,
        "decided_by": c.user.id,
        "decision": "APPROVE",
        "previous_qty": 10,
    }
    values.update(kw)
    return ApprovalDecision(**values)


def report(c: Ctx, **kw: Any) -> ExecutiveReport:
    values: dict[str, Any] = {
        "snapshot_id": c.snapshot.id,
        "scope_type": "ALL",
        "verified_metrics_json": {},
        "narrative_md": "text",
        "created_by": c.user.id,
    }
    values.update(kw)
    return ExecutiveReport(**values)


def document(c: Ctx, **kw: Any) -> Document:
    values: dict[str, Any] = {
        "title": "Policy",
        "doc_type": "SOP",
        "source_filename": "policy.md",
        "sha256": "a" * 64,
        "uploaded_by": c.user.id,
    }
    values.update(kw)
    return Document(**values)


def interaction(**kw: Any) -> AiInteraction:
    values: dict[str, Any] = {
        "request_id": "req-1",
        "feature": "COPILOT",
        "model_id": "ibm/granite-3-3-8b-instruct",
        "prompt_template_id": "t1",
        "prompt_template_version": "1",
        "input_hash": "b" * 64,
        "validation_status": "PASSED",
    }
    values.update(kw)
    return AiInteraction(**values)


# --- master data -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"default_lead_time_days": 0}, "ck_suppliers_lead_time_positive"),
        ({"lead_time_std_days": Decimal("-0.01")}, "ck_suppliers_lead_time_std_nonneg"),
        ({"min_order_qty": 0}, "ck_suppliers_min_order_qty_positive"),
        ({"reliability_pct": Decimal("100.01")}, "ck_suppliers_reliability_range"),
        ({"reliability_pct": Decimal("-0.01")}, "ck_suppliers_reliability_range"),
    ],
)
def test_supplier_checks(ctx: Ctx, overrides: dict[str, Any], constraint: str) -> None:
    assert violated(ctx.db, supplier(**overrides)) == constraint


def test_supplier_boundaries_are_allowed(ctx: Ctx) -> None:
    ok(ctx.db, supplier(code="B0", reliability_pct=Decimal("0")))
    ok(ctx.db, supplier(code="B100", reliability_pct=Decimal("100")))


def test_unique_codes(ctx: Ctx) -> None:
    assert violated(ctx.db, supplier(code=ctx.supplier.code)) == "uq_suppliers_code"
    existing = ctx.db.get(Category, ctx.product.category_id)
    assert existing is not None
    assert violated(ctx.db, Category(code=existing.code, name="dup")) == "uq_categories_code"
    assert (
        violated(ctx.db, Warehouse(code=ctx.warehouse.code, name="dup", city="c", region="r"))
        == "uq_warehouses_code"
    )


# --- products ----------------------------------------------------------------------------------


def test_duplicate_sku(ctx: Ctx) -> None:
    assert violated(ctx.db, product(ctx, sku=ctx.product.sku)) == "uq_products_sku"


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"unit_cost": Decimal("0")}, "ck_products_unit_cost_positive"),
        ({"unit_price": Decimal("0")}, "ck_products_unit_price_positive"),
        ({"case_pack": 0}, "ck_products_case_pack_positive"),
    ],
)
def test_product_checks(ctx: Ctx, overrides: dict[str, Any], constraint: str) -> None:
    assert violated(ctx.db, product(ctx, **overrides)) == constraint


def test_product_foreign_keys(ctx: Ctx) -> None:
    assert (
        violated(ctx.db, product(ctx, category_id=999_999)) == "fk_products_category_id_categories"
    )
    assert (
        violated(ctx.db, product(ctx, supplier_id=999_999)) == "fk_products_supplier_id_suppliers"
    )


# --- inventory policies ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"service_level": Decimal("0.799")}, "ck_inventory_policies_service_level_range"),
        ({"service_level": Decimal("1.000")}, "ck_inventory_policies_service_level_range"),
        ({"review_period_days": 0}, "ck_inventory_policies_review_period_positive"),
        ({"safety_stock_override": -1}, "ck_inventory_policies_safety_stock_override_nonneg"),
        ({"lead_time_override_days": 0}, "ck_inventory_policies_lead_time_override_positive"),
    ],
)
def test_policy_checks(ctx: Ctx, overrides: dict[str, Any], constraint: str) -> None:
    assert violated(ctx.db, policy(ctx, **overrides)) == constraint


def test_policy_defaults_and_uniqueness(ctx: Ctx) -> None:
    row = policy(ctx)
    ok(ctx.db, row)
    ctx.db.refresh(row)
    assert row.service_level == Decimal("0.950")
    assert row.review_period_days == 14
    assert violated(ctx.db, policy(ctx)) == "uq_inventory_policies_product_id"


def test_policy_service_level_boundaries_allowed(ctx: Ctx) -> None:
    ok(ctx.db, policy(ctx, service_level=Decimal("0.800")))
    other = make_warehouse(ctx.db, code="WH2")
    ok(ctx.db, policy(ctx, warehouse_id=other.id, service_level=Decimal("0.999")))


# --- users -------------------------------------------------------------------------------------


def test_user_role_and_unique_username(ctx: Ctx) -> None:
    bad_role = User(username="bob", password_hash=DUMMY_HASH, role="SUPERUSER")
    assert violated(ctx.db, bad_role) == "ck_users_role_values"
    dup = User(username=ctx.user.username, password_hash=DUMMY_HASH, role="ADMIN")
    assert violated(ctx.db, dup) == "uq_users_username"


# --- inventory levels / incoming stock / sales -------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"on_hand_qty": -1}, "ck_inventory_levels_on_hand_nonneg"),
        ({"committed_qty": -1}, "ck_inventory_levels_committed_nonneg"),
    ],
)
def test_level_checks(ctx: Ctx, overrides: dict[str, Any], constraint: str) -> None:
    assert violated(ctx.db, level(ctx, **overrides)) == constraint


def test_level_unique_and_fk(ctx: Ctx) -> None:
    ok(ctx.db, level(ctx))
    assert violated(ctx.db, level(ctx)) == "uq_inventory_levels_product_id"
    other = make_warehouse(ctx.db, code="WH3")
    assert (
        violated(ctx.db, level(ctx, warehouse_id=other.id, product_id=999_999))
        == "fk_inventory_levels_product_id_products"
    )


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"quantity": 0}, "ck_incoming_stock_quantity_positive"),
        ({"status": "LOST"}, "ck_incoming_stock_status_values"),
        (
            {"order_date": TODAY.replace(day=18), "expected_arrival_date": TODAY.replace(day=17)},
            "ck_incoming_stock_arrival_after_order",
        ),
    ],
)
def test_incoming_checks(ctx: Ctx, overrides: dict[str, Any], constraint: str) -> None:
    assert violated(ctx.db, incoming(ctx, **overrides)) == constraint


def test_incoming_default_status_is_open(ctx: Ctx) -> None:
    row = incoming(ctx)
    ok(ctx.db, row)
    ctx.db.refresh(row)
    assert row.status == "OPEN"


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"units_sold": -1}, "ck_sales_daily_units_sold_nonneg"),
        ({"revenue": Decimal("-0.01")}, "ck_sales_daily_revenue_nonneg"),
    ],
)
def test_sales_checks(ctx: Ctx, overrides: dict[str, Any], constraint: str) -> None:
    assert violated(ctx.db, sales(ctx, **overrides)) == constraint


def test_sales_composite_primary_key(ctx: Ctx) -> None:
    ok(ctx.db, sales(ctx))
    assert violated(ctx.db, sales(ctx)) == "pk_sales_daily"


# --- analytics outputs -------------------------------------------------------------------------


def test_metric_checks_and_nullable_columns(ctx: Ctx) -> None:
    assert (
        violated(ctx.db, metric(ctx, risk_class="SEVERE")) == "ck_product_metrics_risk_class_values"
    )
    assert violated(ctx.db, metric(ctx, reorder_qty=-1)) == "ck_product_metrics_reorder_qty_nonneg"
    row = metric(ctx)  # negative available, null days_of_cover and demand_trend_pct are allowed
    ok(ctx.db, row)
    assert violated(ctx.db, metric(ctx)) == "uq_product_metrics_snapshot_id"


def test_metric_not_null_columns(ctx: Ctx) -> None:
    with pytest.raises(IntegrityError), ctx.db.begin_nested():
        ctx.db.add(metric(ctx, on_hand=None))
        ctx.db.flush()


def test_recommendation_checks(ctx: Ctx) -> None:
    assert violated(ctx.db, recommendation(ctx, proposed_qty=0)) == (
        "ck_replenishment_recommendations_proposed_qty_positive"
    )
    assert violated(ctx.db, recommendation(ctx, final_qty=0)) == (
        "ck_replenishment_recommendations_final_qty_positive"
    )
    assert violated(ctx.db, recommendation(ctx, status="DONE")) == (
        "ck_replenishment_recommendations_status_values"
    )
    row = recommendation(ctx)
    ok(ctx.db, row)
    ctx.db.refresh(row)
    assert row.status == "PENDING"


# --- approval decisions ------------------------------------------------------------------------


def test_decision_rules(ctx: Ctx) -> None:
    rec = recommendation(ctx)
    ok(ctx.db, rec)
    d = ctx.db
    assert (
        violated(d, decision(ctx, rec, decision="MAYBE")) == "ck_approval_decisions_decision_values"
    )
    # ADJUST without new_qty (reason is valid, so only new_qty_required can fire)
    assert violated(d, decision(ctx, rec, decision="ADJUST", reason="valid reason")) == (
        "ck_approval_decisions_new_qty_required"
    )
    # ADJUST without a reason
    assert violated(d, decision(ctx, rec, decision="ADJUST", new_qty=5)) == (
        "ck_approval_decisions_reason_required"
    )
    # REJECT with a 3-character reason
    assert violated(d, decision(ctx, rec, decision="REJECT", reason="abc")) == (
        "ck_approval_decisions_reason_required"
    )
    # REJECT with no reason
    assert violated(d, decision(ctx, rec, decision="REJECT")) == (
        "ck_approval_decisions_reason_required"
    )


def test_decision_valid_cases(ctx: Ctx) -> None:
    rec = recommendation(ctx)
    ok(ctx.db, rec)
    ok(ctx.db, decision(ctx, rec))  # APPROVE needs no reason
    ok(ctx.db, decision(ctx, rec, decision="REJECT", reason="12345"))  # exactly 5 chars
    ok(ctx.db, decision(ctx, rec, decision="ADJUST", new_qty=4, reason="too much"))


# --- executive reports -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"scope_type": "ALL", "scope_id": 1}, "ck_executive_reports_scope_id_rule"),
        ({"scope_type": "WAREHOUSE", "scope_id": None}, "ck_executive_reports_scope_id_rule"),
        ({"scope_type": "CATEGORY", "scope_id": None}, "ck_executive_reports_scope_id_rule"),
        ({"scope_type": "REGION", "scope_id": 1}, "ck_executive_reports_scope_type_values"),
    ],
)
def test_report_scope_rules(ctx: Ctx, overrides: dict[str, Any], constraint: str) -> None:
    assert violated(ctx.db, report(ctx, **overrides)) == constraint


def test_report_valid_scopes(ctx: Ctx) -> None:
    ok(ctx.db, report(ctx))
    ok(ctx.db, report(ctx, scope_type="WAREHOUSE", scope_id=ctx.warehouse.id))
    ok(ctx.db, report(ctx, scope_type="CATEGORY", scope_id=ctx.product.category_id))


# --- documents ---------------------------------------------------------------------------------


def test_document_rules(ctx: Ctx) -> None:
    assert violated(ctx.db, document(ctx, doc_type="BLOG")) == "ck_documents_doc_type_values"
    assert violated(ctx.db, document(ctx, status="DELETED")) == "ck_documents_status_values"
    row = document(ctx)
    ok(ctx.db, row)
    ctx.db.refresh(row)
    assert (row.status, row.version, row.is_active, row.injection_warning) == (
        "UPLOADED",
        "1.0",
        True,
        False,
    )
    assert violated(ctx.db, document(ctx, title="other")) == "uq_documents_sha256"


# --- AI interactions ---------------------------------------------------------------------------


def test_ai_interaction_rules(ctx: Ctx) -> None:
    assert violated(ctx.db, interaction(feature="CHAT")) == "ck_ai_interactions_feature_values"
    assert violated(ctx.db, interaction(validation_status="OK")) == (
        "ck_ai_interactions_validation_status_values"
    )
    assert violated(ctx.db, interaction(feedback=0)) == "ck_ai_interactions_feedback_values"
    assert violated(ctx.db, interaction(feedback=2)) == "ck_ai_interactions_feedback_values"


def test_ai_interaction_valid_and_defaults(ctx: Ctx) -> None:
    up, down = interaction(feedback=1), interaction(feedback=-1)
    ok(ctx.db, up, down, interaction(user_id=ctx.user.id))
    ctx.db.refresh(up)
    assert up.context_refs == {}
    assert up.id is not None


def test_ai_interaction_unknown_user_is_fk_violation(ctx: Ctx) -> None:
    assert violated(ctx.db, interaction(user_id=999_999)) == "fk_ai_interactions_user_id_users"


# --- foreign key actions -----------------------------------------------------------------------


def test_restrict_blocks_deleting_referenced_product(ctx: Ctx) -> None:
    ok(ctx.db, sales(ctx))
    with pytest.raises(IntegrityError) as caught, ctx.db.begin_nested():
        ctx.db.delete(ctx.product)
        ctx.db.flush()
    assert caught.value.orig.diag.constraint_name == "fk_sales_daily_product_id_products"


def test_snapshot_delete_cascades_to_product_metrics(ctx: Ctx) -> None:
    row = metric(ctx)
    ok(ctx.db, row)
    ctx.db.expunge(row)
    ctx.db.query(MetricSnapshot).filter_by(id=ctx.snapshot.id).delete()
    assert ctx.db.query(ProductMetric).filter_by(snapshot_id=ctx.snapshot.id).count() == 0


def test_ai_interaction_delete_sets_references_null(ctx: Ctx) -> None:
    ai = interaction()
    ok(ctx.db, ai)
    rec = recommendation(ctx, ai_interaction_id=ai.id)
    ok(ctx.db, rec)
    ctx.db.expunge(rec)
    ctx.db.query(AiInteraction).filter_by(id=ai.id).delete()
    ctx.db.expire_all()
    reloaded = ctx.db.get(ReplenishmentRecommendation, rec.id)
    assert reloaded is not None
    assert reloaded.ai_interaction_id is None
