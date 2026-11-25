"""Request size limit middleware (BP 10.3): 413 over the limit, per-path override, envelope."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core.errors import register_exception_handlers
from app.core.middleware import RequestIdMiddleware, RequestSizeLimitMiddleware

LIMIT = 100


def _client(path_limits: dict[str, int] | None = None) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/echo")
    async def echo(request: Request) -> dict[str, int]:
        return {"bytes": len(await request.body())}

    @app.post("/upload")
    async def upload(request: Request) -> dict[str, int]:
        return {"bytes": len(await request.body())}

    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=LIMIT, path_limits=path_limits)
    app.add_middleware(RequestIdMiddleware)
    return TestClient(app, raise_server_exceptions=False)


def test_a_body_over_the_limit_gets_413_with_the_envelope_and_a_request_id() -> None:
    response = _client().post("/echo", content=b"x" * (LIMIT + 1))
    assert response.status_code == 413
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR" and error["message"] == "Request body too large"
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_a_body_at_the_limit_passes() -> None:
    assert _client().post("/echo", content=b"x" * LIMIT).json() == {"bytes": LIMIT}


def test_a_small_body_and_a_get_pass() -> None:
    client = _client()
    assert client.post("/echo", content=b"hi").status_code == 200
    assert client.get("/echo").status_code == 405  # reached the router, not blocked


def test_the_incoming_request_id_is_kept_on_the_413() -> None:
    response = _client().post(
        "/echo", content=b"x" * (LIMIT + 1), headers={"X-Request-ID": "abc-123"}
    )
    assert response.status_code == 413
    assert response.json()["error"]["request_id"] == "abc-123"


def test_a_per_path_override_raises_the_limit_for_that_path_only() -> None:
    client = _client({"/upload": 10 * LIMIT})
    assert client.post("/upload", content=b"x" * (5 * LIMIT)).status_code == 200
    assert client.post("/upload", content=b"x" * (10 * LIMIT + 1)).status_code == 413
    assert client.post("/echo", content=b"x" * (LIMIT + 1)).status_code == 413


def test_a_per_path_override_can_also_lower_the_limit() -> None:
    client = _client({"/echo": 5})
    assert client.post("/echo", content=b"123456").status_code == 413
    assert client.post("/echo", content=b"12345").status_code == 200


def test_a_malformed_content_length_is_a_400_envelope() -> None:
    response = _client().post("/echo", content=b"x", headers={"Content-Length": "abc"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"
