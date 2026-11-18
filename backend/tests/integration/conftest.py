"""Integration fixtures: test database migrated once; one rolled-back transaction per test.

If TEST_DATABASE_URL is unset or the database is unreachable, every integration test is skipped
with a clear message instead of failing with a stack trace.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _test_url() -> str | None:
    try:
        settings = Settings()
    except ValidationError:
        return None
    secret = settings.test_database_url
    return secret.get_secret_value() if secret else None


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Everything under tests/integration is an integration test."""
    for item in items:
        if "tests/integration" in item.nodeid.replace("\\", "/"):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = _test_url()
    if url is None:
        pytest.skip("Integration tests skipped: TEST_DATABASE_URL is not set.")
    assert url is not None
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except SQLAlchemyError:
        pytest.skip(
            "Integration tests skipped: the test database (TEST_DATABASE_URL) is unreachable."
        )
    return url


def alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # '%' must be escaped for ConfigParser interpolation.
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def migrated_engine(test_database_url: str) -> Iterator[Engine]:
    """Test DB upgraded to head once per session."""
    previous = os.environ.get("TEST_DATABASE_URL")
    command.upgrade(alembic_config(test_database_url), "head")
    engine = create_engine(test_database_url)
    yield engine
    engine.dispose()
    if previous is not None:
        os.environ["TEST_DATABASE_URL"] = previous


@pytest.fixture
def db(migrated_engine: Engine) -> Iterator[Session]:
    """A session bound to one outer transaction that is rolled back after the test.

    ``join_transaction_mode="create_savepoint"`` lets tests trigger and survive IntegrityErrors
    (rolled back to a savepoint) without ending the outer transaction.
    """
    connection = migrated_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
