"""Integration fixtures: test database migrated once; one rolled-back transaction per test.

If TEST_DATABASE_URL is unset or the database is unreachable, every integration test is skipped
with a clear message, unless REQUIRE_TEST_DB=1 (strict mode, the default under `make test`), in
which case they fail with the same message. See docs/TEST_STRATEGY.md.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Engine, create_engine, delete, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.session import get_db
from app.main import create_app
from app.models import AiInteraction, AuditLog, MetricSnapshot, ProductMetric, User
from app.services.analytics_service import RecalculationService
from app.services.user_seed_service import seed_users
from data.seed.generator import (
    DEFAULT_AS_OF,
    DEFAULT_SEED,
    build_dataset,
    count_rows,
    delete_seeded,
    seed_database,
)
from tests.integration.auth_helpers import ROLES, Api, demo_settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _require_db() -> bool:
    return os.environ.get("REQUIRE_TEST_DB", "0") == "1"


def _unavailable(reason: str) -> NoReturn:
    """Skip, or fail when strict mode (REQUIRE_TEST_DB=1) is on."""
    if _require_db():
        pytest.fail(
            f"Integration tests FAILED: {reason} "
            "(REQUIRE_TEST_DB=1; set REQUIRE_TEST_DB=0 to skip instead)",
            pytrace=False,
        )
    pytest.skip(f"Integration tests skipped: {reason}")


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
        _unavailable("TEST_DATABASE_URL is not set.")
    assert url is not None
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except SQLAlchemyError:
        _unavailable("the test database (TEST_DATABASE_URL) is unreachable.")
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


# --- analytics fixtures (BOB-P2-02): seeded data plus cleanup of what recalculation writes ---


def clean_analytics_outputs(engine: Engine) -> None:
    """Remove snapshots, metric rows and audit rows (the service commits, so tests clean up)."""
    with Session(engine) as session, session.begin():
        session.execute(delete(ProductMetric))
        session.execute(delete(MetricSnapshot))
        session.execute(delete(AuditLog))


def _clean_all(engine: Engine) -> None:
    clean_analytics_outputs(engine)  # product_metrics -> products is RESTRICT, so these go first
    with Session(engine) as session, session.begin():
        delete_seeded(session)


@pytest.fixture
def empty_engine(migrated_engine: Engine) -> Iterator[Engine]:
    """Test DB with no seeded data and no analytics output."""
    _clean_all(migrated_engine)
    yield migrated_engine
    _clean_all(migrated_engine)


@pytest.fixture(scope="module")
def _seeded_module_engine(migrated_engine: Engine) -> Iterator[Engine]:
    _clean_all(migrated_engine)
    seed_database(migrated_engine, build_dataset(DEFAULT_SEED, DEFAULT_AS_OF))
    yield migrated_engine
    _clean_all(migrated_engine)


@pytest.fixture
def seeded_engine(_seeded_module_engine: Engine) -> Iterator[Engine]:
    """Seed 42 (loaded once per module, reloaded if a test emptied it); outputs cleaned per test."""
    clean_analytics_outputs(_seeded_module_engine)
    with Session(_seeded_module_engine) as session:
        empty = count_rows(session, ["products"])["products"] == 0
    if empty:
        seed_database(_seeded_module_engine, build_dataset(DEFAULT_SEED, DEFAULT_AS_OF))
    yield _seeded_module_engine
    clean_analytics_outputs(_seeded_module_engine)


# --- authentication fixtures (BOB-P3-01): the 4 demo users seeded through the real service ---


def _clean_users(engine: Engine) -> None:
    with Session(engine) as session, session.begin():
        session.execute(delete(AuditLog))
        session.execute(delete(AiInteraction))
        session.execute(delete(User))


@pytest.fixture
def no_users(migrated_engine: Engine) -> Iterator[Engine]:
    """Test DB with no users, audit rows or AI interactions, before and after."""
    _clean_users(migrated_engine)
    yield migrated_engine
    _clean_users(migrated_engine)


@pytest.fixture(scope="module")
def _demo_users_module(migrated_engine: Engine) -> Iterator[Engine]:
    _clean_users(migrated_engine)
    with Session(migrated_engine) as session:
        seed_users(session, demo_settings())
    yield migrated_engine
    _clean_users(migrated_engine)


def _reset_users(engine: Engine) -> None:
    """Undo what a test did to the four users (role, active flag) and drop its audit rows."""
    with Session(engine) as session, session.begin():
        session.execute(delete(AuditLog))
        session.execute(delete(AiInteraction))
        for username, role in ROLES.items():
            user = session.scalars(select(User).where(User.username == username)).one()
            user.role, user.is_active = role, True


@pytest.fixture
def api(_demo_users_module: Engine) -> Iterator[Api]:
    """An app on the test database with the four demo users and an empty audit log."""
    engine = _demo_users_module
    _reset_users(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    app = create_app(factory)

    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app, raise_server_exceptions=False) as client:
        yield Api(client=client, engine=engine)
    _reset_users(engine)


# --- read API fixtures (BOB-P3-02a): seed 42 + one recalculation, the demo users, a client ---


def _ensure_snapshot(engine: Engine) -> None:
    """Re-seed if a test emptied the data, then recalculate unless a snapshot already exists."""
    with Session(engine) as session:
        empty = count_rows(session, ["products"])["products"] == 0
    if empty:
        seed_database(engine, build_dataset(DEFAULT_SEED, DEFAULT_AS_OF))
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        if session.scalar(select(MetricSnapshot.id).limit(1)) is None:
            RecalculationService(session).run("test")


@pytest.fixture(scope="module")
def _analysed_module_engine(_seeded_module_engine: Engine) -> Iterator[Engine]:
    clean_analytics_outputs(_seeded_module_engine)
    _ensure_snapshot(_seeded_module_engine)
    yield _seeded_module_engine
    clean_analytics_outputs(_seeded_module_engine)


@pytest.fixture
def read_api(_analysed_module_engine: Engine, api: Api) -> Api:
    """``api`` on seed 42 with one snapshot (re-seeded / recalculated if a test removed them)."""
    _ensure_snapshot(_analysed_module_engine)
    return api
