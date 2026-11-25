"""``seed-users``: idempotent, validated before any write, local/test only, no password anywhere."""

import logging
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app import cli
from app.core.config import Settings
from app.core.security import verify_password
from app.models.governance import AuditLog, User
from app.repositories.audit import AuditRepository
from app.services.errors import SeedUsersRefusedError
from app.services.user_seed_service import seed_users
from tests.integration.auth_helpers import DEMO_PASSWORDS, ROLES, USERNAMES, Api, demo_settings

pytestmark = pytest.mark.integration


def _users(engine: Engine) -> dict[str, User]:
    with Session(engine) as session:
        return {u.username: u for u in session.scalars(select(User)).all()}


def _audit_rows(engine: Engine) -> list[AuditLog]:
    with Session(engine) as session:
        return list(session.scalars(select(AuditLog).order_by(AuditLog.id)).all())


def _run(engine: Engine, settings: Settings) -> list[Any]:
    with Session(engine) as session:
        return seed_users(session, settings)


# --- service ---


def test_creates_the_four_users_with_bcrypt_hashes_and_the_right_roles(no_users: Engine) -> None:
    result = _run(no_users, demo_settings())
    assert [(r.username, r.role, r.outcome) for r in result] == [
        (name, ROLES[name], "created") for name in USERNAMES
    ]
    users = _users(no_users)
    assert set(users) == set(USERNAMES)
    for name, user in users.items():
        assert user.role == ROLES[name] and user.is_active
        assert user.password_hash.startswith("$2b$12$") and len(user.password_hash) == 60
        assert verify_password(DEMO_PASSWORDS[name], user.password_hash)
        assert DEMO_PASSWORDS[name] not in user.password_hash


def test_a_second_run_updates_the_same_rows(no_users: Engine) -> None:
    _run(no_users, demo_settings())
    first = {n: (u.id, u.password_hash) for n, u in _users(no_users).items()}
    second_run = _run(no_users, demo_settings())
    assert {r.outcome for r in second_run} == {"updated"}
    second = {n: (u.id, u.password_hash) for n, u in _users(no_users).items()}
    assert len(second) == 4
    assert {n: i for n, (i, _) in second.items()} == {n: i for n, (i, _) in first.items()}
    assert all(second[n][1] != first[n][1] for n in USERNAMES)  # new salt, new hash


def test_a_second_run_restores_role_and_active_flag(no_users: Engine) -> None:
    _run(no_users, demo_settings())
    with Session(no_users) as session, session.begin():
        user = session.scalars(select(User).where(User.username == "analyst")).one()
        user.role, user.is_active = "ADMIN", False
    _run(no_users, demo_settings())
    analyst = _users(no_users)["analyst"]
    assert analyst.role == "ANALYST" and analyst.is_active


def test_every_user_is_audited_without_any_password(no_users: Engine) -> None:
    _run(no_users, demo_settings())
    _run(no_users, demo_settings())
    rows = _audit_rows(no_users)
    assert len(rows) == 8 and {r.action for r in rows} == {"USER_SEEDED"}
    assert [r.details["outcome"] for r in rows] == ["created"] * 4 + ["updated"] * 4
    assert {r.entity_type for r in rows} == {"user"}
    assert {r.entity_id for r in rows} == set(USERNAMES)
    dump = " ".join(str(r.details) for r in rows)
    assert all(password not in dump for password in DEMO_PASSWORDS.values())
    assert set(rows[0].details) == {"username", "role", "outcome"}


def test_no_password_reaches_the_logs(no_users: Engine, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        _run(no_users, demo_settings())
    text = caplog.text
    assert all(password not in text for password in DEMO_PASSWORDS.values())


# --- refusals: nothing is written ---


@pytest.mark.parametrize("username", USERNAMES)
@pytest.mark.parametrize(
    ("value", "reason"),
    [
        (None, "is not set"),
        ("short-1234", "at least 12 characters"),
        ("change_me", "at least 12 characters"),
        ("change_me_please_now", "placeholder"),
        ("CHANGE_ME_please_now", "placeholder"),
    ],
)
def test_a_missing_short_or_placeholder_password_is_refused_before_any_write(
    no_users: Engine, username: str, value: str | None, reason: str
) -> None:
    settings = demo_settings(**{f"seed_user_password_{username}": value})
    with pytest.raises(SeedUsersRefusedError) as raised:
        _run(no_users, settings)
    message = str(raised.value)
    assert f"SEED_USER_PASSWORD_{username.upper()}" in message and reason in message
    assert value is None or value not in message
    assert _users(no_users) == {} and _audit_rows(no_users) == []


def test_a_bad_last_password_still_writes_nothing_for_the_earlier_users(no_users: Engine) -> None:
    settings = demo_settings(seed_user_password_executive="short")
    with pytest.raises(SeedUsersRefusedError):
        _run(no_users, settings)
    assert _users(no_users) == {}


@pytest.mark.parametrize("env", ["production", "staging", "dev", ""])
def test_a_non_local_environment_is_refused(no_users: Engine, env: str) -> None:
    settings = demo_settings(app_env=env)
    with pytest.raises(SeedUsersRefusedError, match="seeding users only runs when it is"):
        _run(no_users, settings)
    assert _users(no_users) == {}


def test_local_is_allowed(no_users: Engine) -> None:
    assert len(_run(no_users, demo_settings(app_env="local"))) == 4


def test_a_database_failure_rolls_back_every_row(
    no_users: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 4th audit insert fails: no user and no audit row from this run may remain."""
    original = AuditRepository.add
    calls: list[int] = []

    def flaky(self: AuditRepository, row: AuditLog) -> AuditLog:
        calls.append(1)
        if len(calls) == 4:
            raise RuntimeError("simulated failure")
        return original(self, row)

    monkeypatch.setattr(AuditRepository, "add", flaky)
    with pytest.raises(RuntimeError, match="simulated failure"):
        _run(no_users, demo_settings())
    assert _users(no_users) == {} and _audit_rows(no_users) == []


# --- CLI: exit codes 0 / 2 / 3, nothing sensitive printed ---


def _factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def test_cli_exit_0_prints_the_outcome_and_no_password(
    no_users: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "get_settings", demo_settings)
    monkeypatch.setattr(cli, "get_session_factory", lambda: _factory(no_users))
    assert cli.main(["seed-users"]) == 0
    captured = capsys.readouterr()
    for name in USERNAMES:
        assert name in captured.out
    assert "4 demo users ready" in captured.out and ".env" in captured.out
    assert all(p not in captured.out + captured.err for p in DEMO_PASSWORDS.values())
    assert len(_users(no_users)) == 4


def test_cli_exit_2_when_refused_names_the_setting_but_not_its_value(
    no_users: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret_value = "change_me_but_long_enough"
    monkeypatch.setattr(
        cli, "get_settings", lambda: demo_settings(seed_user_password_admin=secret_value)
    )
    monkeypatch.setattr(cli, "get_session_factory", lambda: _factory(no_users))
    assert cli.main(["seed-users"]) == 2
    captured = capsys.readouterr()
    assert "SEED_USER_PASSWORD_ADMIN" in captured.err and "placeholder" in captured.err
    assert secret_value not in captured.out + captured.err
    assert _users(no_users) == {}


def test_cli_exit_2_when_the_environment_is_not_local_or_test(
    no_users: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: demo_settings(app_env="production"))
    monkeypatch.setattr(cli, "get_session_factory", lambda: _factory(no_users))
    assert cli.main(["seed-users"]) == 2
    assert "production" in capsys.readouterr().err
    assert _users(no_users) == {}


def test_cli_exit_3_when_the_database_is_unreachable(
    test_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    broken = create_engine(
        make_url(test_database_url).set(port=1), connect_args={"connect_timeout": 1}
    )
    monkeypatch.setattr(cli, "get_settings", demo_settings)
    monkeypatch.setattr(cli, "get_session_factory", lambda: _factory(broken))
    assert cli.main(["seed-users"]) == 3
    captured = capsys.readouterr()
    assert "Database error" in captured.err and "rolled back" in captured.err
    assert all(p not in captured.out + captured.err for p in DEMO_PASSWORDS.values())


# --- full-app behaviour that belongs with the P3-01 foundations ---


def test_an_oversized_login_body_gets_413_with_the_envelope_and_request_id(api: Api) -> None:
    body = b'{"username": "analyst", "password": "' + b"x" * 1_048_576 + b'"}'
    response = api.client.post(
        "/api/v1/auth/login",
        content=body,
        headers={"Content-Type": "application/json", "X-Request-ID": "size-limit-demo-1"},
    )
    assert response.status_code == 413
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR" and error["request_id"] == "size-limit-demo-1"
    assert response.headers["X-Request-ID"] == "size-limit-demo-1"
    assert api.audit() == []  # rejected before the route ran


def test_openapi_marks_exactly_the_protected_routes_with_the_bearer_scheme(api: Api) -> None:
    document = api.client.get("/openapi.json").json()
    assert document["components"]["securitySchemes"]  # HTTPBearer is registered
    public = {"/api/v1/health", "/api/v1/health/ready", "/api/v1/auth/login"}
    for path, item in document["paths"].items():
        for method, operation in item.items():
            secured = bool(operation.get("security"))
            assert secured == (path not in public), f"{method.upper()} {path}"


def test_the_seed_service_leaves_other_tables_alone(no_users: Engine) -> None:
    _run(no_users, demo_settings())
    with Session(no_users) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 4
