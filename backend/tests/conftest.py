"""Test configuration. Env vars are set before `app` is imported; no real DB is needed."""

import os
from collections.abc import Iterator

os.environ.setdefault("POSTGRES_PASSWORD", "test-db-password")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-value-0123456789abcdef")

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
