"""Startup recalculation (FR-B5) and the service's input guard, without a database."""

from collections.abc import Iterator
from types import TracebackType
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, get_settings
from app.main import create_app
from app.services.analytics_service import (
    STARTUP_ERROR,
    STARTUP_OK,
    STARTUP_SKIPPED,
    RecalculationService,
    recalculate_on_startup,
)
from app.services.errors import RecalculationError
from tests.conftest import TEST_JWT_SECRET


class _Result:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one(self) -> Any:
        return self._value


class _FakeSession:
    """Context-manager session whose only query result is the active-product count."""

    def __init__(self, active_products: int) -> None:
        self.active_products = active_products

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return _Result(self.active_products)


def _broken_factory() -> Any:
    raise OperationalError("SELECT", {}, Exception("connection refused: secret-host"))


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Lets a test change settings env vars; the settings cache is cleared before and after."""
    get_settings.cache_clear()
    yield monkeypatch
    monkeypatch.undo()
    get_settings.cache_clear()


# --- the RECALC_ON_STARTUP setting ---


@pytest.mark.parametrize(
    ("app_env", "explicit", "expected"),
    [
        ("local", None, True),
        ("test", None, False),
        ("production", None, False),
        ("local", False, False),
        ("test", True, True),
    ],
)
def test_recalc_on_startup_default_and_override(
    app_env: str, explicit: bool | None, expected: bool
) -> None:
    settings = Settings(
        postgres_password="x",
        jwt_secret=TEST_JWT_SECRET,
        app_env=app_env,
        recalc_on_startup=explicit,
        _env_file=None,
    )
    assert settings.recalc_on_startup_enabled is expected


# --- recalculate_on_startup never raises ---


def test_startup_is_skipped_without_products() -> None:
    assert recalculate_on_startup(lambda: _FakeSession(0)) == STARTUP_SKIPPED


def test_startup_failure_is_reported_not_raised() -> None:
    assert recalculate_on_startup(_broken_factory) == STARTUP_ERROR


def test_startup_ok_constant() -> None:
    assert STARTUP_OK == "ok"


# --- the lifespan keeps the app up ---


def test_app_starts_and_serves_health_when_startup_recalculation_fails(
    settings_env: pytest.MonkeyPatch,
) -> None:
    settings_env.setenv("RECALC_ON_STARTUP", "true")
    app = create_app(_broken_factory)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert app.state.startup_recalc == STARTUP_ERROR
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_startup_recalculation_is_not_attempted_when_disabled(
    settings_env: pytest.MonkeyPatch,
) -> None:
    settings_env.setenv("RECALC_ON_STARTUP", "false")
    app = create_app(_broken_factory)
    with TestClient(app, raise_server_exceptions=False):
        assert not hasattr(app.state, "startup_recalc")


def test_app_starts_with_no_products_and_marks_startup_skipped(
    settings_env: pytest.MonkeyPatch,
) -> None:
    settings_env.setenv("RECALC_ON_STARTUP", "true")
    app = create_app(lambda: _FakeSession(0))
    with TestClient(app, raise_server_exceptions=False):
        assert app.state.startup_recalc == STARTUP_SKIPPED


# --- triggered_by validation (security, section 11) ---


@pytest.mark.parametrize(
    "bad",
    ["", "UPPER", "has space", "semi;colon", "x" * 65, "quote'", "new\nline", "caf\u00e9"],
)
def test_triggered_by_is_validated_before_any_work(bad: str) -> None:
    service = RecalculationService(object())
    with pytest.raises(RecalculationError) as caught:
        service.run(bad)
    assert caught.value.code == "INVALID_TRIGGERED_BY"
