"""Migration tests: round trip, schema/model parity, table set, no vector extension (ADR-014)."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text

from app.models import Base
from tests.integration.conftest import alembic_config

EXPECTED_TABLES = {
    "ai_interactions",
    "approval_decisions",
    "audit_log",
    "categories",
    "documents",
    "executive_reports",
    "incoming_stock",
    "inventory_levels",
    "inventory_policies",
    "metric_snapshots",
    "product_metrics",
    "products",
    "replenishment_recommendations",
    "sales_daily",
    "suppliers",
    "users",
    "warehouses",
}


def _tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def test_head_has_exactly_the_17_tables(migrated_engine: Engine) -> None:
    assert _tables(migrated_engine) == EXPECTED_TABLES | {"alembic_version"}
    assert "document_chunks" not in _tables(migrated_engine)


def test_no_vector_extension(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        extensions = set(connection.execute(text("SELECT extname FROM pg_extension")).scalars())
    assert "vector" not in extensions


def test_autogenerate_diff_is_empty(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"compare_type": True, "compare_server_default": True}
        )
        assert compare_metadata(context, Base.metadata) == []


def test_metadata_covers_the_17_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_no_native_enum_types(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        enums = (
            connection.execute(text("SELECT typname FROM pg_type WHERE typtype = 'e'"))
            .scalars()
            .all()
        )
    assert enums == []


def test_downgrade_to_baseline_then_upgrade(
    test_database_url: str, migrated_engine: Engine
) -> None:
    """Runs last in this module; leaves the database at head again."""
    config = alembic_config(test_database_url)
    # Use a separate engine so the session-scoped engine holds no open connection during DDL.
    engine = create_engine(test_database_url)
    try:
        command.downgrade(config, "0000")
        assert _tables(engine) == {"alembic_version"}
        with engine.connect() as connection:
            version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == "0000"
        command.upgrade(config, "head")
        assert _tables(engine) == EXPECTED_TABLES | {"alembic_version"}
    finally:
        engine.dispose()


@pytest.mark.parametrize("table", sorted(EXPECTED_TABLES))
def test_every_foreign_key_column_is_indexed(migrated_engine: Engine, table: str) -> None:
    inspector = inspect(migrated_engine)
    leading_columns = {ix["column_names"][0] for ix in inspector.get_indexes(table)}
    pk_columns = inspector.get_pk_constraint(table)["constrained_columns"]
    unique_leading = {uc["column_names"][0] for uc in inspector.get_unique_constraints(table)}
    covered = leading_columns | unique_leading | set(pk_columns[:1])
    for fk in inspector.get_foreign_keys(table):
        assert fk["constrained_columns"][0] in covered, (table, fk["constrained_columns"])
