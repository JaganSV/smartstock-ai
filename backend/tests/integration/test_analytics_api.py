"""Analytics endpoints #14, #15 and #17 (BOB-P3-02b) on seed 42 + one recalculation."""

from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import ProductMetric
from app.services.analytics_service import RecalculationService
from tests.integration.auth_helpers import USERNAMES, Api
from tests.integration.read_helpers import (
    CLASSES,
    category_id,
    latest_snapshot,
    product_id,
    warehouse_id,
)

pytestmark = pytest.mark.integration

CANONICAL_ROWS = {"STOCKOUT": 3, "CRITICAL": 8, "HIGH": 4, "MEDIUM": 3, "OVERSTOCK": 11, "LOW": 121}


def _get(api: Api, path: str, **params: Any) -> Any:
    return api.client.get(f"/api/v1{path}", params=params, headers=api.headers("analyst"))


def _recalculate(engine: Engine) -> int:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        return RecalculationService(session).run("test").snapshot_id


# --- #14 metrics ---


def test_metrics_lists_all_150_rows_sorted_by_sku(read_api: Api) -> None:
    body = _get(read_api, "/analytics/metrics", page_size=100).json()
    assert body["total"] == 150 and len(body["items"]) == 100
    keys = [(i["sku"], i["warehouse_code"]) for i in body["items"]]
    assert keys == sorted(keys)
    assert body["snapshot"]["snapshot_id"] == latest_snapshot(read_api.engine).id


@pytest.mark.parametrize(
    ("params", "total"),
    [
        ({"risk_class": "HIGH"}, 4),
        ({"risk_class": ["STOCKOUT", "CRITICAL"]}, 11),
        ({"dead_stock": "true"}, 3),
        ({"slow_moving": "true", "dead_stock": "false"}, None),
    ],
)
def test_metrics_filters(read_api: Api, params: dict[str, Any], total: int | None) -> None:
    body = _get(read_api, "/analytics/metrics", page_size=100, **params).json()
    if total is not None:
        assert body["total"] == total
    if "risk_class" in params:
        wanted = params["risk_class"]
        wanted = {wanted} if isinstance(wanted, str) else set(wanted)
        assert {i["risk_class"] for i in body["items"]} == wanted
    if params.get("slow_moving") == "true":
        assert body["total"] > 0 and all(i["is_slow_moving"] for i in body["items"])


def test_metrics_warehouse_and_category_filters(read_api: Api) -> None:
    mum = warehouse_id(read_api.engine, "WH-MUM")
    by_warehouse = _get(read_api, "/analytics/metrics", warehouse_id=mum, page_size=100).json()
    assert by_warehouse["total"] == 50
    assert {i["warehouse_code"] for i in by_warehouse["items"]} == {"WH-MUM"}
    sport = category_id(read_api.engine, "SPORT")
    by_category = _get(read_api, "/analytics/metrics", category_id=sport, page_size=100).json()
    assert 0 < by_category["total"] < 150 and by_category["total"] % 3 == 0


def test_metrics_sort_by_risk_and_days_of_cover(read_api: Api) -> None:
    risk = _get(read_api, "/analytics/metrics", sort="risk", page_size=15).json()["items"]
    assert [i["risk_class"] for i in risk] == ["STOCKOUT"] * 3 + ["CRITICAL"] * 8 + ["HIGH"] * 4
    cover = _get(read_api, "/analytics/metrics", sort="days_of_cover", page_size=100, page=2)
    covers = [i["days_of_cover"] for i in cover.json()["items"]]
    present = [c for c in covers if c is not None]
    assert present == sorted(present) and covers[len(present) :] == [None] * (
        len(covers) - len(present)
    )


def test_metrics_of_an_older_snapshot_and_unknown_ids(read_api: Api) -> None:
    older = latest_snapshot(read_api.engine).id
    newer = _recalculate(read_api.engine)
    assert newer != older
    body = _get(read_api, "/analytics/metrics", snapshot_id=older).json()
    assert body["snapshot"]["snapshot_id"] == older and body["total"] == 150
    latest = _get(read_api, "/analytics/metrics").json()
    assert latest["snapshot"]["snapshot_id"] == newer
    unknown = _get(read_api, "/analytics/metrics", snapshot_id=999999)
    assert unknown.status_code == 404
    assert unknown.json()["error"]["message"] == "Unknown snapshot_id."
    assert _get(read_api, "/analytics/metrics", warehouse_id=99999).status_code == 404
    assert _get(read_api, "/analytics/metrics", category_id=99999).status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"snapshot_id": 0},
        {"risk_class": "BAD"},
        {"sort": "name"},
        {"order": "up"},
        {"dead_stock": "maybe"},
    ],
)
def test_metrics_bad_parameters_give_422(read_api: Api, params: dict[str, Any]) -> None:
    assert _get(read_api, "/analytics/metrics", **params).status_code == 422


# --- #15 explain ---


def _stored_row(engine: Engine, snapshot_id: int, pid: int, wid: int) -> ProductMetric:
    with Session(engine) as session:
        return session.scalars(
            select(ProductMetric).where(
                ProductMetric.snapshot_id == snapshot_id,
                ProductMetric.product_id == pid,
                ProductMetric.warehouse_id == wid,
            )
        ).one()


def _as_stored(value: Any) -> Any:
    return float(value) if isinstance(value, Decimal) else value


@pytest.mark.parametrize(("sku", "rule"), [("SKU-004", "R2"), ("SKU-024", "R4")])
def test_explain_values_equal_the_stored_row(read_api: Api, sku: str, rule: str) -> None:
    pid, mum = product_id(read_api.engine, sku), warehouse_id(read_api.engine, "WH-MUM")
    response = _get(read_api, f"/analytics/metrics/{pid}/explain", warehouse_id=mum)
    assert response.status_code == 200
    body = response.json()
    snapshot_id = latest_snapshot(read_api.engine).id
    stored = _stored_row(read_api.engine, snapshot_id, pid, mum)
    assert (body["product_id"], body["sku"], body["warehouse_id"], body["warehouse_code"]) == (
        pid,
        sku,
        mum,
        "WH-MUM",
    )
    assert body["snapshot"]["snapshot_id"] == snapshot_id
    results = {item["metric"]: item["result"] for item in body["metrics"]}
    expected = {
        name: _as_stored(getattr(stored, name))
        for name in (
            "available",
            "incoming_in_lt",
            "ads_30",
            "ads_90",
            "demand_std_30",
            "lead_time_days",
            "safety_stock",
            "reorder_point",
            "days_of_cover",
            "reorder_qty",
            "risk_class",
        )
    }
    expected["inventory_position"] = stored.available + stored.incoming_in_lt
    assert results == expected
    risk = body["risk"]
    assert risk["class"] == stored.risk_class and risk["reason_code"] == stored.risk_reason_code
    assert risk["rule_fired"] == rule
    checked = risk["rules_checked"]
    assert [c["rule"] for c in checked] == [f"R{n}" for n in range(1, int(rule[1]) + 1)]
    assert [c["matched"] for c in checked] == [False] * (len(checked) - 1) + [True]
    assert all(
        {"metric", "formula", "inputs", "result", "source"} <= set(i) for i in body["metrics"]
    )


def test_explain_errors(read_api: Api) -> None:
    pid, mum = product_id(read_api.engine, "SKU-004"), warehouse_id(read_api.engine, "WH-MUM")
    missing = _get(read_api, f"/analytics/metrics/{pid}/explain")
    assert missing.status_code == 422
    assert missing.json()["error"]["details"][0]["loc"] == ["query", "warehouse_id"]
    assert _get(read_api, "/analytics/metrics/999999/explain", warehouse_id=mum).status_code == 404
    unknown_wh = _get(read_api, f"/analytics/metrics/{pid}/explain", warehouse_id=99999)
    assert unknown_wh.status_code == 404
    assert unknown_wh.json()["error"]["message"] == "Unknown warehouse_id."


# --- #17 snapshots ---


def test_snapshots_newest_first_with_counts_and_no_params(read_api: Api) -> None:
    _recalculate(read_api.engine)
    response = _get(read_api, "/analytics/snapshots", page_size=100)
    assert response.status_code == 200
    assert "params_json" not in response.text
    body = response.json()
    items = body["items"]
    assert body["total"] == len(items) >= 2
    assert [i["snapshot_id"] for i in items] == sorted(
        (i["snapshot_id"] for i in items), reverse=True
    )
    assert items[0]["snapshot_id"] == latest_snapshot(read_api.engine).id
    for item in items:
        assert set(item) == {
            "snapshot_id",
            "calculated_at",
            "data_as_of_date",
            "triggered_by",
            "row_count",
            "risk_distribution",
        }
        assert item["row_count"] == 150
        assert item["risk_distribution"] == CANONICAL_ROWS
        assert list(item["risk_distribution"]) == list(CLASSES)
    paged = _get(read_api, "/analytics/snapshots", page_size=1, page=2).json()
    assert [i["snapshot_id"] for i in paged["items"]] == [items[1]["snapshot_id"]]


@pytest.mark.parametrize("username", USERNAMES)
def test_every_role_can_read_analytics(read_api: Api, username: str) -> None:
    headers = read_api.headers(username)
    for path in ("metrics", "snapshots"):
        assert read_api.client.get(f"/api/v1/analytics/{path}", headers=headers).status_code == 200


def test_analytics_reads_write_no_audit_rows(read_api: Api) -> None:
    pid, mum = product_id(read_api.engine, "SKU-004"), warehouse_id(read_api.engine, "WH-MUM")
    before = len(read_api.audit())
    _get(read_api, "/analytics/metrics")
    _get(read_api, f"/analytics/metrics/{pid}/explain", warehouse_id=mum)
    _get(read_api, "/analytics/snapshots")
    _get(read_api, f"/risk/{pid}", warehouse_id=mum)
    _get(read_api, "/risk/stockout")
    _get(read_api, "/risk/slow-moving")
    assert len(read_api.audit()) == before
