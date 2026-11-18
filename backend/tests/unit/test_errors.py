import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from app.core.config import Settings


class _Payload(BaseModel):
    quantity: int


def _add_test_routes(app: FastAPI) -> None:
    @app.post("/_test/validate")
    def validate(payload: _Payload) -> dict[str, int]:
        return {"quantity": payload.quantity}

    @app.get("/_test/boom")
    def boom() -> None:
        raise RuntimeError("sensitive internal detail")

    @app.get("/_test/forbidden")
    def forbidden() -> None:
        raise HTTPException(status_code=403, detail="Nope")


def test_validation_error_envelope(app: FastAPI, client: TestClient) -> None:
    _add_test_routes(app)
    response = client.post(
        "/_test/validate", json={"quantity": "not-a-number"}, headers={"X-Request-ID": "req-422"}
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["request_id"] == "req-422"
    assert isinstance(error["details"], list)
    assert "not-a-number" not in response.text  # submitted input is not echoed


def test_unhandled_exception_envelope_has_no_trace(app: FastAPI, client: TestClient) -> None:
    _add_test_routes(app)
    response = client.get("/_test/boom")
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert error["request_id"] == response.headers["X-Request-ID"]
    for leaked in ("Traceback", "RuntimeError", "sensitive internal detail", ".py"):
        assert leaked not in response.text


def test_http_exception_mapped(app: FastAPI, client: TestClient) -> None:
    _add_test_routes(app)
    response = client.get("/_test/forbidden")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert response.json()["error"]["message"] == "Nope"


def test_unknown_route_uses_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_settings_do_not_expose_secrets() -> None:
    settings = Settings(
        postgres_password="pg-super-secret",
        jwt_secret="jwt-super-secret-value",
        watsonx_api_key="wx-super-secret",
    )
    for rendered in (repr(settings), str(settings)):
        assert "pg-super-secret" not in rendered
        assert "jwt-super-secret-value" not in rendered
        assert "wx-super-secret" not in rendered
    assert settings.jwt_secret.get_secret_value() == "jwt-super-secret-value"
    assert "pg-super-secret" not in repr(settings.sqlalchemy_url)


def test_missing_watsonx_settings_do_not_block_startup() -> None:
    settings = Settings(
        postgres_password="x",
        jwt_secret="y",
        _env_file=None,
    )
    assert settings.watsonx_api_key is None


def test_wildcard_cors_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(
            postgres_password="x",
            jwt_secret="y",
            cors_allowed_origins="*",
        )
