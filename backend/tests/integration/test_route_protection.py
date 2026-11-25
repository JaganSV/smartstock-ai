"""Global route protection (BOB-P3-01, AC-3.7).

Every route under ``/api/v1`` that is not in ``PUBLIC_ROUTES`` must answer 401 to a request with
no token, a tampered token, an expired token and an ``alg=none`` token. The list of routes comes
from ``app.routes``, so a route added later without authentication fails this test.
"""

import base64
import json
import re
from datetime import UTC, datetime, timedelta
from typing import cast

import jwt
import pytest
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts

from app.core.security import ISSUER
from tests.conftest import TEST_JWT_SECRET
from tests.integration.auth_helpers import Api

pytestmark = pytest.mark.integration

# The only routes reachable without a token. Changing this set is an architect decision.
PUBLIC_ROUTES = {"/api/v1/health", "/api/v1/health/ready", "/api/v1/auth/login"}
SKIPPED_METHODS = {"HEAD", "OPTIONS"}


def _app(api: Api) -> FastAPI:
    return cast(FastAPI, api.client.app)


def _api_routes(api: Api) -> list[tuple[str, str]]:
    """(method, path) for every route under /api/v1, in a stable order.

    FastAPI 0.163 keeps included routers as nested objects in ``app.routes``;
    ``iter_route_contexts`` is its public way to get the flattened routes with full paths.
    """
    pairs = {
        (method, context.path)
        for context in iter_route_contexts(_app(api).routes)
        if context.path is not None and context.path.startswith("/api/v1")
        for method in (context.methods or set()) - SKIPPED_METHODS
    }
    return sorted(pairs, key=lambda pair: (pair[1], pair[0]))


def _protected(api: Api) -> list[tuple[str, str]]:
    return [(m, p) for m, p in _api_routes(api) if p not in PUBLIC_ROUTES]


def _concrete(path: str) -> str:
    """Fill path parameters (`/x/{item_id}`) with a value so the route can be requested."""
    return re.sub(r"\{[^}]+\}", "1", path)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _claims(**changes: object) -> dict[str, object]:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": "1",
        "username": "admin",
        "role": "ADMIN",
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "jti": "route-protection-test",
        "iss": ISSUER,
    }
    claims.update(changes)
    return claims


def _alg_none_token() -> str:
    """Unsigned token claiming to be an admin, built by hand (the library refuses to verify it)."""
    header = _b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    exp = int((datetime.now(UTC) + timedelta(minutes=30)).timestamp())
    payload = {"sub": "1", "username": "admin", "role": "ADMIN", "exp": exp, "iss": ISSUER}
    return f"{header}.{_b64(json.dumps(payload).encode())}."


BAD_TOKEN_KINDS = [
    "no token",
    "tampered signature",
    "expired token",
    "alg=none token",
    "wrong secret",
    "wrong algorithm",
]


def _bad_tokens(valid: str) -> dict[str, str | None]:
    head, payload, signature = valid.split(".")
    flipped = "A" if signature[10] != "A" else "B"
    return {
        "no token": None,
        "tampered signature": f"{head}.{payload}.{signature[:10]}{flipped}{signature[11:]}",
        "expired token": jwt.encode(
            _claims(exp=datetime.now(UTC) - timedelta(minutes=1)), TEST_JWT_SECRET, "HS256"
        ),
        "alg=none token": _alg_none_token(),
        "wrong secret": jwt.encode(_claims(), "another-secret-" + "x" * 32, "HS256"),
        "wrong algorithm": jwt.encode(_claims(), TEST_JWT_SECRET, "HS512"),
    }


# --- guards: the test cannot pass by accident ---


def test_the_protected_set_is_not_empty_and_has_the_known_routes(api: Api) -> None:
    protected = {path for _, path in _protected(api)}
    assert {
        "/api/v1/auth/me",
        "/api/v1/admin/audit-log",
        "/api/v1/admin/ai-interactions",
    } <= protected


def test_the_route_walk_agrees_with_the_openapi_document(api: Api) -> None:
    """Two independent views of the routes must match, so an empty walk cannot pass silently."""
    from_walk = {(m.lower(), p) for m, p in _api_routes(api)}
    from_openapi = {
        (method, path) for path, item in _app(api).openapi()["paths"].items() for method in item
    }
    assert from_walk == from_openapi and len(from_walk) >= 5


def test_every_public_route_really_exists(api: Api) -> None:
    """A stale PUBLIC_ROUTES entry would silently exempt a future route with that path."""
    existing = {path for _, path in _api_routes(api)}
    assert PUBLIC_ROUTES <= existing


def test_only_the_listed_routes_are_public(api: Api) -> None:
    """Anything reachable without a token must be in PUBLIC_ROUTES, found by calling it."""
    open_routes = [
        (method, path)
        for method, path in _protected(api)
        if api.client.request(method, _concrete(path)).status_code != 401
    ]
    assert open_routes == [], f"routes answer without authentication: {open_routes}"


# --- the matrix: every protected route x every bad token ---


@pytest.mark.parametrize("kind", BAD_TOKEN_KINDS)
def test_every_protected_route_rejects_a_bad_token(api: Api, kind: str) -> None:
    token = _bad_tokens(api.token("admin"))[kind]
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    failures: list[str] = []
    for method, path in _protected(api):
        response = api.client.request(method, _concrete(path), headers=headers)
        if response.status_code != 401 or response.headers.get("WWW-Authenticate") != "Bearer":
            failures.append(f"{method} {path} -> {response.status_code}")
        elif response.json()["error"]["code"] != "UNAUTHENTICATED":
            failures.append(f"{method} {path} -> wrong error code")
    assert failures == [], f"{kind}: {failures}"


def test_a_valid_token_is_accepted_so_the_401s_above_are_about_the_token(api: Api) -> None:
    for method, path in _protected(api):
        response = api.client.request(method, _concrete(path), headers=api.headers("admin"))
        assert response.status_code != 401, f"{method} {path}"
