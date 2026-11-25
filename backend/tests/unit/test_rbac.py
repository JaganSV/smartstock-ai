"""ROLE_MATRIX equals BP 10.2 (binding table, encoded here independently) and the dependencies."""

from collections.abc import Callable
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, require_capability, require_roles
from app.core.errors import register_exception_handlers
from app.core.rbac import ROLE_MATRIX, allowed_roles
from app.models.enums import UserRole
from app.models.governance import User

A, M, N, E = "ADMIN", "INVENTORY_MANAGER", "ANALYST", "EXECUTIVE"

# BP 10.2, as given by the architect (capability key -> roles that hold it).
BP_10_2 = {
    "view_inventory": {A, M, N, E},
    "ask_ai": {A, M, N, E},
    "generate_recommendations": {A, M},
    "decide_recommendations": {A, M},
    "export_approved_csv": {A, M},
    "generate_executive_report": {A, M, E},
    "manage_documents": {A},
    "recalculate_analytics": {A},
    "view_governance": {A},
}


def test_role_matrix_equals_bp_10_2_exactly() -> None:
    assert {k: {r.value for r in v} for k, v in ROLE_MATRIX.items()} == BP_10_2


def test_no_capability_is_added_removed_or_renamed() -> None:
    assert set(ROLE_MATRIX) == set(BP_10_2)
    assert len(ROLE_MATRIX) == 9


def test_every_capability_has_at_least_one_role_and_only_known_roles() -> None:
    for roles in ROLE_MATRIX.values():
        assert roles and roles <= set(UserRole)


def test_admin_holds_every_capability() -> None:
    assert all(UserRole.ADMIN in roles for roles in ROLE_MATRIX.values())


def test_governance_and_admin_actions_are_admin_only() -> None:
    for key in ("view_governance", "recalculate_analytics", "manage_documents"):
        assert allowed_roles(key) == {UserRole.ADMIN}


def test_executive_may_generate_reports_but_not_recommendations() -> None:
    assert UserRole.EXECUTIVE in allowed_roles("generate_executive_report")
    assert UserRole.EXECUTIVE not in allowed_roles("generate_recommendations")
    assert UserRole.ANALYST not in allowed_roles("generate_executive_report")


def test_unknown_capability_is_an_error() -> None:
    with pytest.raises(KeyError):
        allowed_roles("fly_to_the_moon")
    with pytest.raises(KeyError):
        require_capability("fly_to_the_moon")


# --- require_roles / require_capability give 403 (no database: get_current_user is overridden) ---


def _app_with(dependency: Callable[..., User], role: str) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    def probe(user: Annotated[User, Depends(dependency)]) -> dict[str, str]:
        return {"role": user.role}

    app.add_api_route("/probe", probe, methods=["GET"])
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1, username="u", password_hash="x", role=role, is_active=True
    )
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("role", [r.value for r in UserRole])
def test_require_capability_allows_exactly_the_matrix_roles(role: str) -> None:
    for capability, allowed in BP_10_2.items():
        client = _app_with(require_capability(capability), role)
        response = client.get("/probe")
        if role in allowed:
            assert response.status_code == 200, (capability, role)
        else:
            assert response.status_code == 403, (capability, role)
            body: dict[str, Any] = response.json()
            assert body["error"]["code"] == "FORBIDDEN"
            assert body["error"]["message"] == "You do not have permission to do this."


def test_require_roles_with_explicit_roles() -> None:
    check = require_roles(UserRole.EXECUTIVE)
    assert _app_with(check, "EXECUTIVE").get("/probe").status_code == 200
    assert _app_with(check, "ADMIN").get("/probe").status_code == 403
