"""Test configuration. Env vars are set before `app` is imported; no real DB is needed."""

import os
import secrets
from collections.abc import Iterator

# A fresh 64-hex-character secret per test run (32 bytes of randomness; never a fixed string).
TEST_JWT_SECRET = os.environ.setdefault("JWT_SECRET", secrets.token_hex(32))
os.environ.setdefault("POSTGRES_PASSWORD", "test-db-password")
# No startup recalculation in tests (FR-B5); the startup tests switch it on explicitly.
os.environ["RECALC_ON_STARTUP"] = "false"

import pytest  # noqa: E402 - env vars must be set before app import
from fastapi import FastAPI  # noqa: E402 - env vars must be set before app import
from fastapi.testclient import TestClient  # noqa: E402 - env vars must be set before app import

from app.main import create_app  # noqa: E402 - env vars must be set before app import


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # raise_server_exceptions=False so unhandled errors go through the 500 handler.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
