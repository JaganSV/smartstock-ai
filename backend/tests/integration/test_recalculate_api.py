"""POST /analytics/recalculate (#16, BOB-P3-02b): ADMIN only, advisory lock, audit, rollback."""

from typing import Any

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.analytics.errors import AnalyticsInputError
from app.api.v1.analytics import triggered_by_label
from app.models import MetricSnapshot, User
from app.services import analytics_service
from app.services.analytics_service import (
    RECALC_LOCK_KEY,
    REJECTED_ACTION,
    RecalculationService,
)
from app.services.errors import RecalculationLockedError
from tests.integration.auth_helpers import Api
from tests.integration.read_helpers import T0

pytestmark = pytest.mark.integration

URL = "/api/v1/analytics/recalculate"
CANONICAL_ROWS = {"STOCKOUT": 3, "CRITICAL": 8, "HIGH": 4, "MEDIUM": 3, "OVERSTOCK": 11, "LOW": 121}


def _snapshot_ids(engine: Engine) -> list[int]:
    with Session(engine) as session:
        return list(session.scalars(select(MetricSnapshot.id).order_by(MetricSnapshot.id)))


def _user_id(engine: Engine, username: str) -> int:
    with Session(engine) as session:
        return int(session.scalars(select(User.id).where(User.username == username)).one())


def test_admin_recalculates_and_the_audit_row_names_user_and_request(read_api: Api) -> None:
    before = _snapshot_ids(read_api.engine)
    response = read_api.client.post(URL, headers=read_api.headers("admin"))
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "snapshot_id",
        "data_as_of_date",
        "row_count",
        "risk_distribution",
        "duration_ms",
    }
    assert body["snapshot_id"] not in before and body["snapshot_id"] in _snapshot_ids(
        read_api.engine
    )
    assert body["data_as_of_date"] == T0.isoformat() and body["row_count"] == 150
    assert body["risk_distribution"] == CANONICAL_ROWS
    assert 0 <= body["duration_ms"] < 5000

    audits = read_api.audit("ANALYTICS_RECALCULATED")
    assert len(audits) == 1
    audit = audits[0]
    assert audit.user_id == _user_id(read_api.engine, "admin")
    assert audit.request_id == response.headers["X-Request-ID"]
    assert audit.ip_address  # the client address (TestClient: "testclient")
    assert audit.entity_id == str(body["snapshot_id"])
    assert audit.details["triggered_by"] == "api:admin"

    # The P3-02a read endpoints now serve the new snapshot.
    summary = read_api.client.get("/api/v1/dashboard/summary", headers=read_api.headers("analyst"))
    assert summary.json()["snapshot"]["snapshot_id"] == body["snapshot_id"]


@pytest.mark.parametrize("username", ["manager", "analyst", "executive"])
def test_other_roles_get_403_and_nothing_runs(read_api: Api, username: str) -> None:
    before = _snapshot_ids(read_api.engine)
    response = read_api.client.post(URL, headers=read_api.headers(username))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert _snapshot_ids(read_api.engine) == before
    assert read_api.audit("ANALYTICS_RECALCULATED") == []


def test_a_held_lock_gives_409_and_a_rejected_audit_row(read_api: Api) -> None:
    before = _snapshot_ids(read_api.engine)
    with read_api.engine.connect() as other, other.begin():
        assert other.execute(select(func.pg_try_advisory_xact_lock(RECALC_LOCK_KEY))).scalar_one()
        response = read_api.client.post(URL, headers=read_api.headers("admin"))
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "CONFLICT"
    assert error["message"] == "A recalculation is already running."
    assert _snapshot_ids(read_api.engine) == before
    assert read_api.audit("ANALYTICS_RECALCULATED") == []
    rejected = read_api.audit(REJECTED_ACTION)
    assert len(rejected) == 1
    assert rejected[0].details == {"reason": "lock_held", "triggered_by": "api:admin"}
    assert rejected[0].user_id == _user_id(read_api.engine, "admin")
    assert rejected[0].request_id == response.headers["X-Request-ID"]
    # The lock was released with the other transaction: the next run goes through.
    assert read_api.client.post(URL, headers=read_api.headers("admin")).status_code == 201


def test_the_cli_and_startup_path_also_respects_the_lock(read_api: Api) -> None:
    factory = sessionmaker(bind=read_api.engine, autoflush=False, expire_on_commit=False)
    with read_api.engine.connect() as other, other.begin():
        other.execute(select(func.pg_advisory_xact_lock(RECALC_LOCK_KEY)))
        with factory() as session, pytest.raises(RecalculationLockedError) as caught:
            RecalculationService(session).run("cli")
    assert caught.value.code == "LOCK_HELD"
    rejected = read_api.audit(REJECTED_ACTION)
    assert [(r.user_id, r.details["triggered_by"]) for r in rejected] == [(None, "cli")]


def test_a_failure_rolls_back_and_answers_500_without_internals(
    read_api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*_args: Any) -> Any:
        raise RuntimeError("internal-detail-xyz")

    before = _snapshot_ids(read_api.engine)
    monkeypatch.setattr(analytics_service, "to_snapshot_rows", explode)
    response = read_api.client.post(URL, headers=read_api.headers("admin"))
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR" and error["request_id"]
    assert "internal-detail-xyz" not in response.text and "Traceback" not in response.text
    assert _snapshot_ids(read_api.engine) == before
    assert read_api.audit("ANALYTICS_RECALCULATED") == []
    monkeypatch.undo()
    assert read_api.client.post(URL, headers=read_api.headers("admin")).status_code == 201


def test_an_analytics_failure_answers_500_recalculation_failed(
    read_api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    def bad_input(*_args: Any) -> Any:
        raise AnalyticsInputError("missing inventory policy", ["product_id=1,warehouse_id=1"])

    monkeypatch.setattr(analytics_service, "run_analytics", bad_input)
    response = read_api.client.post(URL, headers=read_api.headers("admin"))
    assert response.status_code == 500
    assert response.json()["error"]["message"] == "Recalculation failed."
    assert "product_id" not in response.text
    assert read_api.audit("ANALYTICS_RECALCULATED") == []


@pytest.mark.parametrize(
    ("username", "label"),
    [("admin", "api:admin"), ("Jane.Doe", "api:jane-doe"), ("ops_1-a", "api:ops_1-a")],
)
def test_triggered_by_comes_from_the_username_within_the_allowed_characters(
    username: str, label: str
) -> None:
    assert triggered_by_label(username) == label
    assert analytics_service.TRIGGERED_BY_PATTERN.fullmatch(triggered_by_label("x" * 50))


def test_no_body_or_client_triggered_by_is_used(read_api: Api) -> None:
    response = read_api.client.post(
        URL,
        params={"triggered_by": "evil"},
        json={"triggered_by": "evil"},
        headers=read_api.headers("admin"),
    )
    assert response.status_code == 201
    assert read_api.audit("ANALYTICS_RECALCULATED")[0].details["triggered_by"] == "api:admin"


def test_with_no_sales_data_the_recalculation_gives_409(api: Api, empty_engine: Engine) -> None:
    """Runs last in this module; ``read_api`` re-seeds for any later test."""
    del empty_engine  # requested for its side effect: no seeded data
    response = api.client.post(URL, headers=api.headers("admin"))
    assert response.status_code == 409
    assert response.json()["error"]["message"] == "No sales data available."
