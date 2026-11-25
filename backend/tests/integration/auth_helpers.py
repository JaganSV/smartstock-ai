"""Helpers for the authentication integration tests. All values are generated per run."""

import secrets
from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_access_token
from app.models.governance import AuditLog, User
from tests.conftest import TEST_JWT_SECRET

USERNAMES = ("admin", "manager", "analyst", "executive")
ROLES = {
    "admin": "ADMIN",
    "manager": "INVENTORY_MANAGER",
    "analyst": "ANALYST",
    "executive": "EXECUTIVE",
}
# Throw-away passwords for this test run (never a real credential, never printed).
DEMO_PASSWORDS = {name: secrets.token_urlsafe(16) for name in USERNAMES}


def demo_settings(app_env: str = "test", **overrides: Any) -> Settings:
    """Settings carrying the four demo passwords; ``overrides`` replace any field."""
    values: dict[str, Any] = {
        "postgres_password": "x",
        "jwt_secret": TEST_JWT_SECRET,
        "app_env": app_env,
        "seed_user_password_admin": DEMO_PASSWORDS["admin"],
        "seed_user_password_manager": DEMO_PASSWORDS["manager"],
        "seed_user_password_analyst": DEMO_PASSWORDS["analyst"],
        "seed_user_password_executive": DEMO_PASSWORDS["executive"],
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


@dataclass
class Api:
    client: TestClient
    engine: Engine

    def login(self, username: str, password: str | None = None) -> Any:
        body = {"username": username, "password": password or DEMO_PASSWORDS[username]}
        return self.client.post("/api/v1/auth/login", json=body)

    def token(self, username: str) -> str:
        """A valid token for a seeded user, made directly (no login, no audit row)."""
        with Session(self.engine) as session:
            user = session.scalars(select(User).where(User.username == username)).one()
            return create_access_token(user)[0]

    def headers(self, username: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token(username)}"}

    def audit(self, action: str | None = None) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        with Session(self.engine) as session:
            return list(session.scalars(stmt).all())
