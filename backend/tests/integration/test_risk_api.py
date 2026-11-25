"""Risk endpoints #18-#20 (BOB-P3-02b, FR-C1-C3) on seed 42 + one recalculation."""

from datetime import timedelta
from typing import Any

import pytest

from tests.integration.auth_helpers import USERNAMES, Api
from tests.integration.read_helpers import T0, is_money, product_id, warehouse_id

pytestmark = pytest.mark.integration

SEVERITY = {"STOCKOUT": 0, "CRITICAL": 1, "HIGH": 2}


def _get(api: Api, path: str, **params: Any) -> Any:
    return api.client.get(f"/api/v1{path}", params=params, headers=api.headers("analyst"))


# --- #18 stockout risk ---


def test_stockout_list_is_the_15_risky_rows_in_severity_then_cover_order(read_api: Api) -> None:
    response = _get(read_api, "/risk/stockout", page_size=100)
    assert response.status_code == 200
    body = response.json()
    items = body["items"]
    assert body["total"] == 15 == len(items)
    classes = [i["risk_class"] for i in items]
    assert classes == ["STOCKOUT"] * 3 + ["CRITICAL"] * 8 + ["HIGH"] * 4
    assert [i["sku"] for i in items[:3]] == ["SKU-001", "SKU-002", "SKU-003"]
    critical_cover = [i["days_of_cover"] for i in items[3:11]]
    assert critical_cover == sorted(critical_cover)
    keys = [(SEVERITY[i["risk_class"]], i["days_of_cover"], i["sku"]) for i in items]
    assert keys == sorted(keys)
    assert all(
        "projected_stockout_day" in i and isinstance(i["is_high_demand"], bool) for i in items
    )
    assert all(i["projected_stockout_day"] == 0 for i in items[:3])  # available <= 0
    assert all(i["projected_stockout_day"] is not None for i in items[3:11])  # R2 fired
    assert all(is_money(i["inventory_value"]) for i in items)
    assert body["snapshot"]["verified"] is True


def test_stockout_list_filters_and_pages(read_api: Api) -> None:
    mum = warehouse_id(read_api.engine, "WH-MUM")
    by_warehouse = _get(read_api, "/risk/stockout", warehouse_id=mum, page_size=100).json()
    assert by_warehouse["total"] > 0
    assert {i["warehouse_code"] for i in by_warehouse["items"]} == {"WH-MUM"}
    page2 = _get(read_api, "/risk/stockout", page=2, page_size=5).json()
    full = _get(read_api, "/risk/stockout", page_size=100).json()
    assert [i["sku"] for i in page2["items"]] == [i["sku"] for i in full["items"][5:10]]
    assert page2["total"] == 15
    beyond = _get(read_api, "/risk/stockout", page=9, page_size=5).json()
    assert beyond["items"] == [] and beyond["total"] == 15


# --- #19 risk detail ---


def test_risk_detail_of_sku_004_at_mumbai_projects_a_stockout_on_day_11(read_api: Api) -> None:
    pid, mum = product_id(read_api.engine, "SKU-004"), warehouse_id(read_api.engine, "WH-MUM")
    response = _get(read_api, f"/risk/{pid}", warehouse_id=mum)
    assert response.status_code == 200
    body = response.json()
    for field in (
        "available",
        "on_hand",
        "committed",
        "incoming_in_lt",
        "ads_30",
        "lead_time_days",
        "safety_stock",
        "reorder_point",
        "days_of_cover",
        "risk_class",
        "risk_reason_code",
    ):
        assert field in body, field
    assert body["risk_class"] == "CRITICAL" and body["available"] == 223
    assert body["rule_trace"]["rule_fired"] == "R2"
    assert body["rule_trace"]["class"] == "CRITICAL"
    projection = body["projection"]
    assert projection["horizon_days"] == 14 == body["lead_time_days"]
    assert projection["projected_stockout_day"] == 11
    points = projection["points"]
    assert [p["day"] for p in points] == list(range(15))
    assert [p["date"] for p in points] == [(T0 + timedelta(days=k)).isoformat() for k in range(15)]
    assert points[0]["projected_units"] == 223
    assert points[11]["projected_units"] <= 0 < points[10]["projected_units"]
    assert body["snapshot"]["data_as_of_date"] == T0.isoformat()


def test_risk_detail_of_sku_024_at_mumbai_shows_the_open_arrival(read_api: Api) -> None:
    pid, mum = product_id(read_api.engine, "SKU-024"), warehouse_id(read_api.engine, "WH-MUM")
    body = _get(read_api, f"/risk/{pid}", warehouse_id=mum).json()
    projection = body["projection"]
    assert 115 in [o["quantity"] for o in projection["open_incoming"]]
    assert all(o["expected_arrival_date"] > T0.isoformat() for o in projection["open_incoming"])
    assert projection["projected_stockout_day"] is None
    assert body["rule_trace"]["rule_fired"] == "R4"


def test_risk_detail_errors(read_api: Api) -> None:
    pid, mum = product_id(read_api.engine, "SKU-004"), warehouse_id(read_api.engine, "WH-MUM")
    missing = _get(read_api, f"/risk/{pid}")
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _get(read_api, "/risk/999999", warehouse_id=mum).status_code == 404
    assert _get(read_api, f"/risk/{pid}", warehouse_id=99999).status_code == 404
    assert _get(read_api, f"/risk/{pid}", warehouse_id=0).status_code == 422


# --- #20 slow-moving ---


def test_slow_moving_list_puts_the_dead_stock_first(read_api: Api) -> None:
    body = _get(read_api, "/risk/slow-moving", page_size=100).json()
    items = body["items"]
    assert body["total"] == 11 == len(items)
    # The three dead-stock rows (ordered among themselves by inventory_value desc).
    assert sorted((i["sku"], i["warehouse_code"]) for i in items[:3]) == [
        ("SKU-021", "WH-BLR"),
        ("SKU-022", "WH-BLR"),
        ("SKU-023", "WH-BLR"),
    ]
    assert all(i["is_dead_stock"] for i in items[:3])
    assert not any(i["is_dead_stock"] for i in items[3:])
    assert all(i["is_slow_moving"] or i["is_dead_stock"] for i in items)
    for group in (items[:3], items[3:]):
        values = [float(i["inventory_value"]) for i in group]
        assert values == sorted(values, reverse=True)
    assert all("ads_90" in i for i in items)


# --- shared errors and roles ---


@pytest.mark.parametrize("path", ["/risk/stockout", "/risk/slow-moving"])
def test_list_filter_errors(read_api: Api, path: str) -> None:
    assert _get(read_api, path, warehouse_id=99999).status_code == 404
    assert _get(read_api, path, category_id=99999).status_code == 404
    assert _get(read_api, path, category_id=0).status_code == 422
    assert _get(read_api, path, page_size=101).status_code == 422


@pytest.mark.parametrize("username", USERNAMES)
def test_every_role_can_read_risk(read_api: Api, username: str) -> None:
    headers = read_api.headers(username)
    for path in ("stockout", "slow-moving"):
        assert read_api.client.get(f"/api/v1/risk/{path}", headers=headers).status_code == 200
