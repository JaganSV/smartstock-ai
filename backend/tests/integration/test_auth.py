"""Login, /auth/me, lockout (ADR-015), identity from the database, audit rows and log hygiene."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from httpx import Response
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

import app.services.auth_service as service
from app.models.governance import AuditLog, User
from app.services.user_seed_service import seed_users
from tests.integration.auth_helpers import (
    DEMO_PASSWORDS,
    ROLES,
    USERNAMES,
    Api,
    demo_settings,
)

pytestmark = pytest.mark.integration

BAD = "not-the-password-0000"
GENERIC = "Invalid username or password."


def _backdate(engine: Engine, minutes: int, action: str | None = None) -> None:
    """Move audit rows into the past (simulates the lock window passing)."""
    with Session(engine) as session, session.begin():
        stmt = update(AuditLog).values(occurred_at=datetime.now(UTC) - timedelta(minutes=minutes))
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        session.execute(stmt)


def _without_request_id(response: Response) -> dict[str, object]:
    return {k: v for k, v in response.json()["error"].items() if k != "request_id"}


def _fail(api: Api, username: str, times: int) -> None:
    for _ in range(times):
        assert api.login(username, BAD).status_code == 401


# --- success ---


@pytest.mark.parametrize("username", USERNAMES)
def test_each_seeded_user_can_log_in_and_me_returns_the_role(api: Api, username: str) -> None:
    response = api.login(username)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 3600
    assert body["user"]["username"] == username and body["user"]["role"] == ROLES[username]
    me = api.client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json() == {
        "id": body["user"]["id"],
        "username": username,
        "role": ROLES[username],
        "is_active": True,
    }
    assert "X-Request-ID" in response.headers


def test_username_is_case_insensitive(api: Api) -> None:
    response = api.client.post(
        "/api/v1/auth/login",
        json={"username": "ANALYST", "password": DEMO_PASSWORDS["analyst"]},
    )
    assert response.status_code == 200 and response.json()["user"]["username"] == "analyst"


# --- no user enumeration ---


def test_unknown_user_and_wrong_password_give_the_same_response(api: Api) -> None:
    unknown = api.login("nobody-here", BAD)
    wrong = api.login("analyst", BAD)
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.headers["WWW-Authenticate"] == wrong.headers["WWW-Authenticate"] == "Bearer"
    assert _without_request_id(unknown) == _without_request_id(wrong)
    assert unknown.json()["error"]["code"] == "UNAUTHENTICATED"
    assert unknown.json()["error"]["message"] == GENERIC


def test_an_inactive_user_gets_the_same_message_even_with_the_right_password(api: Api) -> None:
    with Session(api.engine) as session, session.begin():
        session.execute(update(User).where(User.username == "executive").values(is_active=False))
    response = api.login("executive")  # correct password
    assert response.status_code == 401
    assert response.json()["error"]["message"] == GENERIC
    reasons = {row.details["reason"] for row in api.audit("LOGIN_FAILED")}
    assert reasons == {"inactive"}


def test_failure_reasons_are_audited_but_never_returned(api: Api) -> None:
    api.login("analyst", BAD)
    api.login("ghost-user", BAD)
    rows = api.audit("LOGIN_FAILED")
    assert [r.details for r in rows] == [{"reason": "bad_credentials"}] * 2
    assert [r.entity_id for r in rows] == ["analyst", "ghost-user"]
    assert rows[0].user_id is not None and rows[1].user_id is None


# --- validation ---


@pytest.mark.parametrize(
    "body",
    [
        {"username": "ab", "password": "x"},
        {"username": "a" * 51, "password": "x"},
        {"username": "bad name!", "password": "x"},
        {"username": "analyst", "password": ""},
        {"username": "analyst", "password": "p" * 73},
        {"username": "analyst", "password": "\u00e9" * 37},
        {"username": "analyst"},
        {"username": "analyst", "password": "x", "extra": 1},
    ],
)
def test_invalid_login_bodies_are_422_with_the_envelope(api: Api, body: dict[str, object]) -> None:
    response = api.client.post("/api/v1/auth/login", json=body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR" and error["request_id"]
    assert "p" * 73 not in response.text  # the submitted password is never echoed


def test_a_422_login_writes_no_audit_row(api: Api) -> None:
    api.client.post("/api/v1/auth/login", json={"username": "ab", "password": "x"})
    assert api.audit() == []


# --- lockout ---


def test_six_attempts_lock_the_account_and_the_password_is_not_checked(api: Api) -> None:
    _fail(api, "manager", 5)
    locked = api.login("manager")  # the CORRECT password
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "RATE_LIMITED"
    assert locked.json()["error"]["message"] == "Too many failed login attempts. Try again later."
    assert locked.json()["error"]["request_id"] == locked.headers["X-Request-ID"]
    retry = int(locked.headers["Retry-After"])
    assert 1 <= retry <= 15 * 60
    assert len(api.audit("LOGIN_LOCKED")) == 1
    assert api.audit("LOGIN_LOCKED")[0].details["reason"] == "too_many_failures"
    assert api.audit("LOGIN_SUCCESS") == []  # the correct password was not accepted


def test_the_lock_does_not_check_the_password_so_no_bcrypt_work_is_done(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fail(api, "manager", 5)
    calls: list[str] = []
    monkeypatch.setattr(service, "verify_password", lambda *a, **k: calls.append("checked") or True)
    assert api.login("manager").status_code == 429
    assert calls == []


def test_four_failures_do_not_lock(api: Api) -> None:
    _fail(api, "manager", 4)
    assert api.login("manager").status_code == 200


def test_retry_after_counts_down_to_the_oldest_failure_ageing_out(api: Api) -> None:
    _fail(api, "manager", 5)
    _backdate(api.engine, 10, "LOGIN_FAILED")  # the oldest failures are 10 minutes old
    retry = int(api.login("manager").headers["Retry-After"])
    assert 4 * 60 <= retry <= 5 * 60 + 2  # about 5 minutes left of the 15-minute window


def test_login_works_again_after_the_lock_window_passes(api: Api) -> None:
    _fail(api, "manager", 5)
    assert api.login("manager").status_code == 429
    _backdate(api.engine, 16)  # everything is now older than 15 minutes
    assert api.login("manager").status_code == 200


def test_a_success_resets_the_count(api: Api) -> None:
    _fail(api, "manager", 4)
    assert api.login("manager").status_code == 200  # success after 4 failures
    _fail(api, "manager", 4)  # four more: still below 5 since the last success
    assert api.login("manager").status_code == 200


def test_failures_before_the_last_success_do_not_count_towards_a_lock(api: Api) -> None:
    _fail(api, "manager", 3)
    assert api.login("manager").status_code == 200
    _fail(api, "manager", 2)
    assert api.login("manager").status_code == 200  # 3 + 2 would be 5 without the reset


def test_lockout_is_per_username(api: Api) -> None:
    _fail(api, "manager", 5)
    assert api.login("manager").status_code == 429
    assert api.login("analyst").status_code == 200


def test_lockout_also_applies_to_a_non_existent_username(api: Api) -> None:
    _fail(api, "ghost-user", 5)
    locked = api.login("ghost-user", BAD)
    assert locked.status_code == 429 and "Retry-After" in locked.headers
    assert locked.json()["error"]["message"] == "Too many failed login attempts. Try again later."


def test_lockout_is_case_insensitive_on_the_username(api: Api) -> None:
    _fail(api, "manager", 5)
    response = api.client.post(
        "/api/v1/auth/login", json={"username": "MANAGER", "password": DEMO_PASSWORDS["manager"]}
    )
    assert response.status_code == 429


# --- identity comes from the database on every request ---


def test_a_deactivated_users_existing_token_gets_401_on_the_next_request(api: Api) -> None:
    headers = api.headers("analyst")
    assert api.client.get("/api/v1/auth/me", headers=headers).status_code == 200
    with Session(api.engine) as session, session.begin():
        session.execute(update(User).where(User.username == "analyst").values(is_active=False))
    response = api.client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_a_role_change_takes_effect_on_the_next_request(api: Api) -> None:
    headers = api.headers("analyst")  # token minted while the user is an ANALYST
    assert api.client.get("/api/v1/admin/audit-log", headers=headers).status_code == 403
    with Session(api.engine) as session, session.begin():
        session.execute(update(User).where(User.username == "analyst").values(role="ADMIN"))
    assert api.client.get("/api/v1/auth/me", headers=headers).json()["role"] == "ADMIN"
    assert api.client.get("/api/v1/admin/audit-log", headers=headers).status_code == 200
    with Session(api.engine) as session, session.begin():
        session.execute(update(User).where(User.username == "analyst").values(role="ANALYST"))
    assert api.client.get("/api/v1/admin/audit-log", headers=headers).status_code == 403


def test_a_token_for_a_deleted_user_is_401(api: Api) -> None:
    headers = api.headers("executive")
    with Session(api.engine) as session, session.begin():
        user = session.scalars(select(User).where(User.username == "executive")).one()
        session.delete(user)
    try:
        assert api.client.get("/api/v1/auth/me", headers=headers).status_code == 401
    finally:  # put the user back for the following tests
        with Session(api.engine) as session:
            seed_users(session, demo_settings())


@pytest.mark.parametrize(
    "header",
    [None, "", "Bearer", "Bearer ", "Bearer not.a.token", "Basic abc", "bearer x.y.z", "Token abc"],
)
def test_missing_or_malformed_authorization_is_401(api: Api, header: str | None) -> None:
    headers = {} if header is None else {"Authorization": header}
    response = api.client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    error = response.json()["error"]
    assert error["code"] == "UNAUTHENTICATED" and error["request_id"]


# --- audit rows carry ip and request id and no secrets ---


def test_login_audit_rows_have_ip_and_request_id_and_no_secrets(api: Api) -> None:
    ok = api.client.post(
        "/api/v1/auth/login",
        json={"username": "analyst", "password": DEMO_PASSWORDS["analyst"]},
        headers={"X-Request-ID": "req-success-1"},
    )
    assert ok.status_code == 200
    api.client.post(
        "/api/v1/auth/login",
        json={"username": "analyst", "password": BAD},
        headers={"X-Request-ID": "req-failure-1"},
    )
    success = api.audit("LOGIN_SUCCESS")[0]
    failure = api.audit("LOGIN_FAILED")[0]
    assert (success.request_id, failure.request_id) == ("req-success-1", "req-failure-1")
    assert success.ip_address and failure.ip_address
    assert success.entity_type == failure.entity_type == "user"
    token = ok.json()["access_token"]
    for row in api.audit():
        text = f"{row.details} {row.entity_id} {row.action}"
        assert token not in text and BAD not in text
        assert not any(p in text for p in DEMO_PASSWORDS.values())


def test_locked_attempts_are_audited_with_request_id(api: Api) -> None:
    _fail(api, "manager", 5)
    api.client.post(
        "/api/v1/auth/login",
        json={"username": "manager", "password": BAD},
        headers={"X-Request-ID": "req-locked-1"},
    )
    (locked,) = api.audit("LOGIN_LOCKED")
    assert locked.request_id == "req-locked-1" and locked.ip_address


# --- logs never contain passwords or tokens (security requirement) ---


def test_logs_never_contain_the_password_or_the_token(
    api: Api, caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    caplog.set_level(logging.DEBUG)
    password = DEMO_PASSWORDS["analyst"]
    ok = api.login("analyst")
    token = ok.json()["access_token"]
    api.login("analyst", BAD)
    _fail(api, "manager", 5)
    api.login("manager")  # locked
    api.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    api.client.get("/api/v1/auth/me", headers={"Authorization": "Bearer tampered.token.value"})
    printed = capfd.readouterr()
    everything = caplog.text + printed.out + printed.err
    assert everything  # something was logged, so the assertions below mean something
    for secret in (password, token, BAD, *DEMO_PASSWORDS.values()):
        assert secret not in everything
    assert "Login failed" in caplog.text and "Login succeeded" in caplog.text
