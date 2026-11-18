"""core schema: 17 tables (document_chunks and pgvector deferred to P7, ADR-014)

Generated with `alembic revision --autogenerate` and reviewed by hand (added the
audit_log.occurred_at index). No extensions, no data.

Revision ID: 0001_core_schema
Revises: 0000
Create Date: 2026-11-19 00:48:46.626461
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_core_schema"
down_revision: str | None = "0000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("code", name=op.f("uq_categories_code")),
    )
    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("data_as_of_date", sa.Date(), nullable=False),
        sa.Column("params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("triggered_by", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_metric_snapshots")),
    )
    op.create_table(
        "suppliers",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("default_lead_time_days", sa.Integer(), nullable=False),
        sa.Column(
            "lead_time_std_days",
            sa.Numeric(precision=6, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column("min_order_qty", sa.Integer(), nullable=False),
        sa.Column("reliability_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("contact_email", sa.String(length=254), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            "default_lead_time_days > 0", name=op.f("ck_suppliers_lead_time_positive")
        ),
        sa.CheckConstraint(
            "lead_time_std_days >= 0", name=op.f("ck_suppliers_lead_time_std_nonneg")
        ),
        sa.CheckConstraint("min_order_qty >= 1", name=op.f("ck_suppliers_min_order_qty_positive")),
        sa.CheckConstraint(
            "reliability_pct BETWEEN 0 AND 100", name=op.f("ck_suppliers_reliability_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_suppliers")),
        sa.UniqueConstraint("code", name=op.f("uq_suppliers_code")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('ADMIN', 'INVENTORY_MANAGER', 'ANALYST', 'EXECUTIVE')",
            name=op.f("ck_users_role_values"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "warehouses",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("region", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouses")),
        sa.UniqueConstraint("code", name=op.f("uq_warehouses_code")),
    )
    op.create_table(
        "ai_interactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("feature", sa.String(length=32), nullable=False),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("prompt_template_id", sa.String(length=64), nullable=False),
        sa.Column("prompt_template_version", sa.String(length=16), nullable=False),
        sa.Column("input_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("sanitized_user_input", sa.Text(), nullable=True),
        sa.Column(
            "context_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("parsed_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "feature IN ('COPILOT', 'KNOWLEDGE', 'REPLENISHMENT', 'REPORT', 'INTENT')",
            name=op.f("ck_ai_interactions_feature_values"),
        ),
        sa.CheckConstraint(
            "validation_status IN ('PASSED', 'FAILED_SCHEMA', 'FAILED_GROUNDING', 'BLOCKED_INPUT', 'ERROR')",
            name=op.f("ck_ai_interactions_validation_status_values"),
        ),
        sa.CheckConstraint("feedback IN (-1, 1)", name=op.f("ck_ai_interactions_feedback_values")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ai_interactions_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_interactions")),
    )
    op.create_index(
        "ix_ai_interactions_feature_created_at",
        "ai_interactions",
        ["feature", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_interactions_user_id"), "ai_interactions", ["user_id"], unique=False
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_audit_log_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"], unique=False)
    op.create_index(
        "ix_audit_log_entity_type_entity_id",
        "audit_log",
        ["entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(op.f("ix_audit_log_user_id"), "audit_log", ["user_id"], unique=False)
    op.create_table(
        "documents",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("doc_type", sa.String(length=32), nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), nullable=True),
        sa.Column("version", sa.String(length=32), server_default="1.0", nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="UPLOADED", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "injection_warning", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "doc_type IN ('SUPPLIER_POLICY', 'SOP')", name=op.f("ck_documents_doc_type_values")
        ),
        sa.CheckConstraint(
            "status IN ('UPLOADED', 'INDEXED', 'FAILED')", name=op.f("ck_documents_status_values")
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_documents_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            name=op.f("fk_documents_uploaded_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("sha256", name=op.f("uq_documents_sha256")),
    )
    op.create_index(op.f("ix_documents_supplier_id"), "documents", ["supplier_id"], unique=False)
    op.create_index(op.f("ix_documents_uploaded_by"), "documents", ["uploaded_by"], unique=False)
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("sku", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("case_pack", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("case_pack >= 1", name=op.f("ck_products_case_pack_positive")),
        sa.CheckConstraint("unit_cost > 0", name=op.f("ck_products_unit_cost_positive")),
        sa.CheckConstraint("unit_price > 0", name=op.f("ck_products_unit_price_positive")),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_products_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_products_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("sku", name=op.f("uq_products_sku")),
    )
    op.create_index(op.f("ix_products_category_id"), "products", ["category_id"], unique=False)
    op.create_index(op.f("ix_products_supplier_id"), "products", ["supplier_id"], unique=False)
    op.create_table(
        "executive_reports",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.BigInteger(), nullable=True),
        sa.Column("verified_metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("narrative_md", sa.Text(), nullable=False),
        sa.Column("ai_interaction_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(scope_type = 'ALL') = (scope_id IS NULL)",
            name=op.f("ck_executive_reports_scope_id_rule"),
        ),
        sa.CheckConstraint(
            "scope_type IN ('ALL', 'WAREHOUSE', 'CATEGORY')",
            name=op.f("ck_executive_reports_scope_type_values"),
        ),
        sa.ForeignKeyConstraint(
            ["ai_interaction_id"],
            ["ai_interactions.id"],
            name=op.f("fk_executive_reports_ai_interaction_id_ai_interactions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_executive_reports_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["metric_snapshots.id"],
            name=op.f("fk_executive_reports_snapshot_id_metric_snapshots"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_executive_reports")),
    )
    op.create_index(
        op.f("ix_executive_reports_ai_interaction_id"),
        "executive_reports",
        ["ai_interaction_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_executive_reports_created_by"), "executive_reports", ["created_by"], unique=False
    )
    op.create_index(
        op.f("ix_executive_reports_snapshot_id"), "executive_reports", ["snapshot_id"], unique=False
    )
    op.create_table(
        "incoming_stock",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("expected_arrival_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="OPEN", nullable=False),
        sa.CheckConstraint(
            "status IN ('OPEN', 'RECEIVED', 'CANCELLED')",
            name=op.f("ck_incoming_stock_status_values"),
        ),
        sa.CheckConstraint(
            "expected_arrival_date >= order_date",
            name=op.f("ck_incoming_stock_arrival_after_order"),
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_incoming_stock_quantity_positive")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_incoming_stock_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_incoming_stock_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_incoming_stock_warehouse_id_warehouses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incoming_stock")),
    )
    op.create_index(
        op.f("ix_incoming_stock_product_id"), "incoming_stock", ["product_id"], unique=False
    )
    op.create_index(
        "ix_incoming_stock_status_expected_arrival_date",
        "incoming_stock",
        ["status", "expected_arrival_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_incoming_stock_supplier_id"), "incoming_stock", ["supplier_id"], unique=False
    )
    op.create_index(
        op.f("ix_incoming_stock_warehouse_id"), "incoming_stock", ["warehouse_id"], unique=False
    )
    op.create_table(
        "inventory_levels",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), nullable=False),
        sa.Column("on_hand_qty", sa.Integer(), nullable=False),
        sa.Column("committed_qty", sa.Integer(), server_default="0", nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("committed_qty >= 0", name=op.f("ck_inventory_levels_committed_nonneg")),
        sa.CheckConstraint("on_hand_qty >= 0", name=op.f("ck_inventory_levels_on_hand_nonneg")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_inventory_levels_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_inventory_levels_warehouse_id_warehouses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_levels")),
        sa.UniqueConstraint(
            "product_id", "warehouse_id", name=op.f("uq_inventory_levels_product_id")
        ),
    )
    op.create_index(
        op.f("ix_inventory_levels_warehouse_id"), "inventory_levels", ["warehouse_id"], unique=False
    )
    op.create_table(
        "inventory_policies",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "service_level",
            sa.Numeric(precision=6, scale=3),
            server_default="0.950",
            nullable=False,
        ),
        sa.Column("review_period_days", sa.Integer(), server_default="14", nullable=False),
        sa.Column("safety_stock_override", sa.Integer(), nullable=True),
        sa.Column("lead_time_override_days", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "lead_time_override_days IS NULL OR lead_time_override_days > 0",
            name=op.f("ck_inventory_policies_lead_time_override_positive"),
        ),
        sa.CheckConstraint(
            "review_period_days > 0", name=op.f("ck_inventory_policies_review_period_positive")
        ),
        sa.CheckConstraint(
            "safety_stock_override IS NULL OR safety_stock_override >= 0",
            name=op.f("ck_inventory_policies_safety_stock_override_nonneg"),
        ),
        sa.CheckConstraint(
            "service_level BETWEEN 0.800 AND 0.999",
            name=op.f("ck_inventory_policies_service_level_range"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_inventory_policies_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_inventory_policies_warehouse_id_warehouses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_policies")),
        sa.UniqueConstraint(
            "product_id", "warehouse_id", name=op.f("uq_inventory_policies_product_id")
        ),
    )
    op.create_index(
        op.f("ix_inventory_policies_warehouse_id"),
        "inventory_policies",
        ["warehouse_id"],
        unique=False,
    )
    op.create_table(
        "product_metrics",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), nullable=False),
        sa.Column("on_hand", sa.Integer(), nullable=False),
        sa.Column("committed", sa.Integer(), nullable=False),
        sa.Column("available", sa.Integer(), nullable=False),
        sa.Column("incoming_in_lt", sa.Integer(), nullable=False),
        sa.Column("ads_30", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("ads_90", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("demand_std_30", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=False),
        sa.Column("safety_stock", sa.Integer(), nullable=False),
        sa.Column("reorder_point", sa.Integer(), nullable=False),
        sa.Column("days_of_cover", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("reorder_qty", sa.Integer(), nullable=False),
        sa.Column("risk_class", sa.String(length=32), nullable=False),
        sa.Column("risk_reason_code", sa.String(length=64), nullable=False),
        sa.Column("is_slow_moving", sa.Boolean(), nullable=False),
        sa.Column("is_dead_stock", sa.Boolean(), nullable=False),
        sa.Column("demand_trend_pct", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("inventory_value", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.CheckConstraint(
            "risk_class IN ('STOCKOUT', 'CRITICAL', 'HIGH', 'MEDIUM', 'OVERSTOCK', 'LOW')",
            name=op.f("ck_product_metrics_risk_class_values"),
        ),
        sa.CheckConstraint("reorder_qty >= 0", name=op.f("ck_product_metrics_reorder_qty_nonneg")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_metrics_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["metric_snapshots.id"],
            name=op.f("fk_product_metrics_snapshot_id_metric_snapshots"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_product_metrics_warehouse_id_warehouses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_metrics")),
        sa.UniqueConstraint(
            "snapshot_id", "product_id", "warehouse_id", name=op.f("uq_product_metrics_snapshot_id")
        ),
    )
    op.create_index(
        op.f("ix_product_metrics_product_id"), "product_metrics", ["product_id"], unique=False
    )
    op.create_index(
        "ix_product_metrics_snapshot_id_risk_class",
        "product_metrics",
        ["snapshot_id", "risk_class"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_metrics_warehouse_id"), "product_metrics", ["warehouse_id"], unique=False
    )
    op.create_table(
        "replenishment_recommendations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), nullable=False),
        sa.Column("proposed_qty", sa.Integer(), nullable=False),
        sa.Column("final_qty", sa.Integer(), nullable=True),
        sa.Column("est_cost", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="PENDING", nullable=False),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column("ai_interaction_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'ADJUSTED_APPROVED', 'REJECTED', 'EXPIRED')",
            name=op.f("ck_replenishment_recommendations_status_values"),
        ),
        sa.CheckConstraint(
            "final_qty IS NULL OR final_qty > 0",
            name=op.f("ck_replenishment_recommendations_final_qty_positive"),
        ),
        sa.CheckConstraint(
            "proposed_qty > 0", name=op.f("ck_replenishment_recommendations_proposed_qty_positive")
        ),
        sa.ForeignKeyConstraint(
            ["ai_interaction_id"],
            ["ai_interactions.id"],
            name=op.f("fk_replenishment_recommendations_ai_interaction_id_ai_interactions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_replenishment_recommendations_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["metric_snapshots.id"],
            name=op.f("fk_replenishment_recommendations_snapshot_id_metric_snapshots"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_replenishment_recommendations_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_replenishment_recommendations_warehouse_id_warehouses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_replenishment_recommendations")),
    )
    op.create_index(
        op.f("ix_replenishment_recommendations_ai_interaction_id"),
        "replenishment_recommendations",
        ["ai_interaction_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_replenishment_recommendations_product_id"),
        "replenishment_recommendations",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_replenishment_recommendations_snapshot_id"),
        "replenishment_recommendations",
        ["snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_replenishment_recommendations_status"),
        "replenishment_recommendations",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_replenishment_recommendations_supplier_id"),
        "replenishment_recommendations",
        ["supplier_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_replenishment_recommendations_warehouse_id"),
        "replenishment_recommendations",
        ["warehouse_id"],
        unique=False,
    )
    op.create_table(
        "sales_daily",
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), nullable=False),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("units_sold", sa.Integer(), nullable=False),
        sa.Column("revenue", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint("revenue >= 0", name=op.f("ck_sales_daily_revenue_nonneg")),
        sa.CheckConstraint("units_sold >= 0", name=op.f("ck_sales_daily_units_sold_nonneg")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_sales_daily_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_sales_daily_warehouse_id_warehouses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "product_id", "warehouse_id", "sale_date", name=op.f("pk_sales_daily")
        ),
    )
    op.create_index(op.f("ix_sales_daily_sale_date"), "sales_daily", ["sale_date"], unique=False)
    op.create_index(
        op.f("ix_sales_daily_warehouse_id"), "sales_daily", ["warehouse_id"], unique=False
    )
    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("recommendation_id", sa.BigInteger(), nullable=False),
        sa.Column("decided_by", sa.BigInteger(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("previous_qty", sa.Integer(), nullable=False),
        sa.Column("new_qty", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision <> 'ADJUST' OR new_qty IS NOT NULL",
            name=op.f("ck_approval_decisions_new_qty_required"),
        ),
        sa.CheckConstraint(
            "decision IN ('APPROVE', 'ADJUST', 'REJECT')",
            name=op.f("ck_approval_decisions_decision_values"),
        ),
        sa.CheckConstraint(
            "decision NOT IN ('ADJUST', 'REJECT') OR (reason IS NOT NULL AND length(reason) >= 5)",
            name=op.f("ck_approval_decisions_reason_required"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.id"],
            name=op.f("fk_approval_decisions_decided_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["replenishment_recommendations.id"],
            name=op.f("fk_approval_decisions_recommendation_id_replenishment_recommendations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_decisions")),
    )
    op.create_index(
        op.f("ix_approval_decisions_decided_by"), "approval_decisions", ["decided_by"], unique=False
    )
    op.create_index(
        op.f("ix_approval_decisions_recommendation_id"),
        "approval_decisions",
        ["recommendation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_approval_decisions_recommendation_id"), table_name="approval_decisions")
    op.drop_index(op.f("ix_approval_decisions_decided_by"), table_name="approval_decisions")
    op.drop_table("approval_decisions")
    op.drop_index(op.f("ix_sales_daily_warehouse_id"), table_name="sales_daily")
    op.drop_index(op.f("ix_sales_daily_sale_date"), table_name="sales_daily")
    op.drop_table("sales_daily")
    op.drop_index(
        op.f("ix_replenishment_recommendations_warehouse_id"),
        table_name="replenishment_recommendations",
    )
    op.drop_index(
        op.f("ix_replenishment_recommendations_supplier_id"),
        table_name="replenishment_recommendations",
    )
    op.drop_index(
        op.f("ix_replenishment_recommendations_status"), table_name="replenishment_recommendations"
    )
    op.drop_index(
        op.f("ix_replenishment_recommendations_snapshot_id"),
        table_name="replenishment_recommendations",
    )
    op.drop_index(
        op.f("ix_replenishment_recommendations_product_id"),
        table_name="replenishment_recommendations",
    )
    op.drop_index(
        op.f("ix_replenishment_recommendations_ai_interaction_id"),
        table_name="replenishment_recommendations",
    )
    op.drop_table("replenishment_recommendations")
    op.drop_index(op.f("ix_product_metrics_warehouse_id"), table_name="product_metrics")
    op.drop_index("ix_product_metrics_snapshot_id_risk_class", table_name="product_metrics")
    op.drop_index(op.f("ix_product_metrics_product_id"), table_name="product_metrics")
    op.drop_table("product_metrics")
    op.drop_index(op.f("ix_inventory_policies_warehouse_id"), table_name="inventory_policies")
    op.drop_table("inventory_policies")
    op.drop_index(op.f("ix_inventory_levels_warehouse_id"), table_name="inventory_levels")
    op.drop_table("inventory_levels")
    op.drop_index(op.f("ix_incoming_stock_warehouse_id"), table_name="incoming_stock")
    op.drop_index(op.f("ix_incoming_stock_supplier_id"), table_name="incoming_stock")
    op.drop_index("ix_incoming_stock_status_expected_arrival_date", table_name="incoming_stock")
    op.drop_index(op.f("ix_incoming_stock_product_id"), table_name="incoming_stock")
    op.drop_table("incoming_stock")
    op.drop_index(op.f("ix_executive_reports_snapshot_id"), table_name="executive_reports")
    op.drop_index(op.f("ix_executive_reports_created_by"), table_name="executive_reports")
    op.drop_index(op.f("ix_executive_reports_ai_interaction_id"), table_name="executive_reports")
    op.drop_table("executive_reports")
    op.drop_index(op.f("ix_products_supplier_id"), table_name="products")
    op.drop_index(op.f("ix_products_category_id"), table_name="products")
    op.drop_table("products")
    op.drop_index(op.f("ix_documents_uploaded_by"), table_name="documents")
    op.drop_index(op.f("ix_documents_supplier_id"), table_name="documents")
    op.drop_table("documents")
    op.drop_index(op.f("ix_audit_log_user_id"), table_name="audit_log")
    op.drop_index("ix_audit_log_entity_type_entity_id", table_name="audit_log")
    op.drop_index("ix_audit_log_occurred_at", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index(op.f("ix_ai_interactions_user_id"), table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_feature_created_at", table_name="ai_interactions")
    op.drop_table("ai_interactions")
    op.drop_table("warehouses")
    op.drop_table("users")
    op.drop_table("suppliers")
    op.drop_table("metric_snapshots")
    op.drop_table("categories")
