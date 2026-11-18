import uuid
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import get_db


class _OkSession:
    def execute(self, *_args: object, **_kwargs: object) -> None:
        return None


class _FailingSession:
    def execute(self, *_args: object, **_kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused: secret-host"))


def _override(app: FastAPI, session: object) -> None:
    def _get_db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = _get_db


def test_health_body(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "smartstock-backend", "version": "0.1.0"}


def test_health_has_generated_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    request_id = response.headers["X-Request-ID"]
    assert str(uuid.UUID(request_id)) == request_id


def test_valid_incoming_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "abc-123-DEF"})
    assert response.headers["X-Request-ID"] == "abc-123-DEF"


def test_invalid_incoming_request_id_is_replaced(client: TestClient) -> None:
    for bad in ("bad id!", "x" * 65, "under_score"):
        response = client.get("/api/v1/health", headers={"X-Request-ID": bad})
        assert response.headers["X-Request-ID"] != bad
        uuid.UUID(response.headers["X-Request-ID"])


def test_ready_ok(app: FastAPI, client: TestClient) -> None:
    _override(app, _OkSession())
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok", "ai": "not_configured"}


def test_ready_db_down_returns_envelope(app: FastAPI, client: TestClient) -> None:
    _override(app, _FailingSession())
    response = client.get("/api/v1/health/ready", headers={"X-Request-ID": "req-503"})
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert error["message"] == "Database unavailable"
    assert error["request_id"] == "req-503"
    assert "secret-host" not in response.text


def test_health_still_ok_when_db_down(app: FastAPI, client: TestClient) -> None:
    _override(app, _FailingSession())
    assert client.get("/api/v1/health").status_code == 200


def test_cors_allows_only_configured_origin(client: TestClient) -> None:
    allowed = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in denied.headers
