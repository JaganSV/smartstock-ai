"""Admin governance endpoints: ADMIN only, pagination, filters, metadata-only AI list."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, update
from sqlalchemy.orm import Session

from app.models.governance import AiInteraction, AuditLog
from tests.integration.auth_helpers import Api

pytestmark = pytest.mark.integration

AUDIT = "/api/v1/admin/audit-log"
AI = "/api/v1/admin/ai-interactions"


def _add_audit(
    engine: Engine, count: int, action: str = "TEST_ACTION", entity: str = "thing"
) -> None:
    with Session(engine) as session, session.begin():
        for index in range(count):
            session.add(
                AuditLog(
                    action=action,
                    entity_type=entity,
                    entity_id=str(index),
                    details={"n": index},
                    request_id=f"req-{index}",
                    ip_address="203.0.113.9",
                )
            )


def _add_ai(engine: Engine, feature: str, status: str, count: int = 1) -> None:
    with Session(engine) as session, session.begin():
        for _ in range(count):
            session.add(
                AiInteraction(
                    id=uuid.uuid4(),
                    request_id="req-ai",
                    user_id=None,
                    feature=feature,
                    model_id="ibm/granite-test",
                    prompt_template_id="tmpl-1",
                    prompt_template_version="1",
                    input_hash="0" * 64,
                    sanitized_user_input="SECRET-USER-INPUT",
                    raw_output="SECRET-RAW-OUTPUT",
                    parsed_output={"secret": "SECRET-PARSED"},
                    validation_status=status,
                    input_tokens=10,
                    output_tokens=20,
                    latency_ms=300,
                )
            )


@pytest.mark.parametrize("path", [AUDIT, AI])
def test_admin_gets_200_and_everyone_else_403(api: Api, path: str) -> None:
    assert api.client.get(path, headers=api.headers("admin")).status_code == 200
    for username in ("manager", "analyst", "executive"):
        response = api.client.get(path, headers=api.headers(username))
        assert response.status_code == 403, username
        error = response.json()["error"]
        assert error["code"] == "FORBIDDEN" and error["request_id"]
        assert response.headers["X-Request-ID"] == error["request_id"]


@pytest.mark.parametrize("path", [AUDIT, AI])
def test_no_token_is_401(api: Api, path: str) -> None:
    response = api.client.get(path)
    assert response.status_code == 401 and response.headers["WWW-Authenticate"] == "Bearer"


def test_audit_log_pagination_and_newest_first(api: Api) -> None:
    _add_audit(api.engine, 7)
    headers = api.headers("admin")
    first = api.client.get(AUDIT, params={"page_size": 3}, headers=headers).json()
    assert (first["page"], first["page_size"], first["total"]) == (1, 3, 7)
    assert len(first["items"]) == 3
    ids = [item["id"] for item in first["items"]]
    assert ids == sorted(ids, reverse=True)  # newest first
    third = api.client.get(AUDIT, params={"page": 3, "page_size": 3}, headers=headers).json()
    assert len(third["items"]) == 1 and third["page"] == 3
    beyond = api.client.get(AUDIT, params={"page": 9, "page_size": 3}, headers=headers).json()
    assert beyond["items"] == [] and beyond["total"] == 7


def test_audit_log_defaults_are_page_1_size_25(api: Api) -> None:
    body = api.client.get(AUDIT, headers=api.headers("admin")).json()
    assert (body["page"], body["page_size"]) == (1, 25)


@pytest.mark.parametrize(
    "params",
    [{"page_size": 101}, {"page_size": 0}, {"page": 0}, {"page": -1}, {"page_size": "x"}],
)
@pytest.mark.parametrize("path", [AUDIT, AI])
def test_out_of_range_paging_is_422_with_the_envelope(
    api: Api, path: str, params: dict[str, object]
) -> None:
    response = api.client.get(path, params=params, headers=api.headers("admin"))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR" and error["request_id"]


def test_page_size_100_is_the_allowed_maximum(api: Api) -> None:
    assert (
        api.client.get(AUDIT, params={"page_size": 100}, headers=api.headers("admin")).status_code
        == 200
    )


def test_audit_filters_by_action_entity_type_and_time(api: Api) -> None:
    _add_audit(api.engine, 2, action="ALPHA", entity="widget")
    _add_audit(api.engine, 3, action="BETA", entity="gadget")
    headers = api.headers("admin")
    alpha = api.client.get(AUDIT, params={"action": "ALPHA"}, headers=headers).json()
    assert alpha["total"] == 2 and {i["action"] for i in alpha["items"]} == {"ALPHA"}
    assert api.client.get(AUDIT, params={"action": "alph"}, headers=headers).json()["total"] == 0
    gadget = api.client.get(AUDIT, params={"entity_type": "gadget"}, headers=headers).json()
    assert gadget["total"] == 3
    both = api.client.get(
        AUDIT, params={"action": "ALPHA", "entity_type": "gadget"}, headers=headers
    )
    assert both.json()["total"] == 0

    with Session(api.engine) as session, session.begin():
        session.execute(
            update(AuditLog)
            .where(AuditLog.action == "ALPHA")
            .values(occurred_at=datetime.now(UTC) - timedelta(days=3))
        )
    cutoff = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    recent = api.client.get(AUDIT, params={"from": cutoff, "action": "ALPHA"}, headers=headers)
    assert recent.json()["total"] == 0
    old = api.client.get(AUDIT, params={"to": cutoff, "action": "ALPHA"}, headers=headers)
    assert old.json()["total"] == 2
    bad = api.client.get(AUDIT, params={"from": "not-a-date"}, headers=headers)
    assert bad.status_code == 422


def test_audit_items_have_the_documented_fields_and_a_joined_username(api: Api) -> None:
    api.login("analyst", "wrong-password-0000")  # creates a LOGIN_FAILED row with user_id
    body = api.client.get(
        AUDIT, params={"action": "LOGIN_FAILED"}, headers=api.headers("admin")
    ).json()
    item = body["items"][0]
    assert set(item) == {
        "id", "occurred_at", "user_id", "username", "action", "entity_type",
        "entity_id", "details", "request_id", "ip_address",
    }  # fmt: skip
    assert item["username"] == "analyst" and item["details"] == {"reason": "bad_credentials"}
    assert item["ip_address"] and item["request_id"]


def test_audit_username_is_null_when_there_is_no_user(api: Api) -> None:
    _add_audit(api.engine, 1)
    item = api.client.get(
        AUDIT, params={"action": "TEST_ACTION"}, headers=api.headers("admin")
    ).json()["items"][0]
    assert item["user_id"] is None and item["username"] is None


def test_ai_interactions_empty_list_for_now(api: Api) -> None:
    body = api.client.get(AI, headers=api.headers("admin")).json()
    assert body == {"items": [], "page": 1, "page_size": 25, "total": 0}


def test_ai_interactions_return_metadata_only_never_prompts_or_outputs(api: Api) -> None:
    _add_ai(api.engine, "COPILOT", "PASSED")
    response = api.client.get(AI, headers=api.headers("admin"))
    item = response.json()["items"][0]
    assert set(item) == {
        "id", "created_at", "user_id", "feature", "model_id", "prompt_template_id",
        "prompt_template_version", "validation_status", "input_tokens", "output_tokens",
        "latency_ms", "feedback",
    }  # fmt: skip
    for secret in ("SECRET-USER-INPUT", "SECRET-RAW-OUTPUT", "SECRET-PARSED"):
        assert secret not in response.text
    assert (item["input_tokens"], item["output_tokens"], item["latency_ms"]) == (10, 20, 300)


def test_ai_interactions_filters_and_pagination(api: Api) -> None:
    _add_ai(api.engine, "COPILOT", "PASSED", 3)
    _add_ai(api.engine, "KNOWLEDGE", "FAILED_GROUNDING", 2)
    headers = api.headers("admin")
    assert api.client.get(AI, headers=headers).json()["total"] == 5
    assert api.client.get(AI, params={"feature": "KNOWLEDGE"}, headers=headers).json()["total"] == 2
    failed = api.client.get(AI, params={"validation_status": "FAILED_GROUNDING"}, headers=headers)
    assert failed.json()["total"] == 2
    page = api.client.get(AI, params={"page_size": 2}, headers=headers).json()
    assert len(page["items"]) == 2 and page["total"] == 5
    assert api.client.get(AI, params={"feature": "NOPE"}, headers=headers).status_code == 422
    assert (
        api.client.get(AI, params={"validation_status": "NOPE"}, headers=headers).status_code == 422
    )
