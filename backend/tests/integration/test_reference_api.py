"""Reference endpoints #5-#7 (BOB-P3-02a, AC-3.1a): sorted by code, typed, no contact e-mail."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Supplier, Warehouse
from tests.integration.auth_helpers import USERNAMES, Api

pytestmark = pytest.mark.integration


def _count(api: Api, model: type[Category] | type[Supplier] | type[Warehouse]) -> int:
    with Session(api.engine) as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_categories_are_sorted_by_code_with_exact_fields(read_api: Api) -> None:
    response = read_api.client.get(
        "/api/v1/reference/categories", headers=read_api.headers("analyst")
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == _count(read_api, Category) > 0
    assert [c["code"] for c in body] == sorted(c["code"] for c in body)
    assert all(set(c) == {"id", "code", "name"} for c in body)


def test_warehouses_are_sorted_by_code_with_exact_fields(read_api: Api) -> None:
    response = read_api.client.get(
        "/api/v1/reference/warehouses", headers=read_api.headers("analyst")
    )
    assert response.status_code == 200
    body = response.json()
    assert [w["code"] for w in body] == ["WH-BLR", "WH-DEL", "WH-MUM"]
    assert all(set(w) == {"id", "code", "name", "city", "region"} for w in body)


def test_suppliers_are_sorted_and_never_expose_contact_email(read_api: Api) -> None:
    response = read_api.client.get(
        "/api/v1/reference/suppliers", headers=read_api.headers("analyst")
    )
    assert response.status_code == 200
    assert "contact_email" not in response.text and "@" not in response.text
    body = response.json()
    assert len(body) == _count(read_api, Supplier) > 0
    assert [s["code"] for s in body] == sorted(s["code"] for s in body)
    expected = {
        "id",
        "code",
        "name",
        "default_lead_time_days",
        "min_order_qty",
        "reliability_pct",
        "is_active",
    }
    assert all(set(s) == expected for s in body)
    assert all(isinstance(s["reliability_pct"], float | int) for s in body)


@pytest.mark.parametrize("username", USERNAMES)
def test_every_role_holds_view_inventory(read_api: Api, username: str) -> None:
    headers = read_api.headers(username)
    for path in ("categories", "warehouses", "suppliers"):
        assert read_api.client.get(f"/api/v1/reference/{path}", headers=headers).status_code == 200


def test_reference_reads_write_no_audit_rows(read_api: Api) -> None:
    before = len(read_api.audit())
    read_api.client.get("/api/v1/reference/suppliers", headers=read_api.headers("admin"))
    assert len(read_api.audit()) == before
