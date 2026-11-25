"""FR-B6 / AC-3.10: explanations and risk detail always equal the stored snapshot numbers.

Every row of the snapshot recomputes to its stored values; when the underlying data changes, the
explain and risk-detail endpoints answer 409 with the changed field names (never values, never
wrong numbers) until a recalculation.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Engine, delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.analytics.errors import AnalyticsInputError
from app.models import InventoryLevel, Product, ProductMetric
from app.services import explain_service
from app.services.explain_service import VERIFIED_FIELDS, recompute_rows
from app.services.snapshot_context import frame_records, load_snapshot, load_snapshot_context
from tests.integration.auth_helpers import Api
from tests.integration.conftest import clean_analytics_outputs
from tests.integration.read_helpers import product_id, warehouse_id

pytestmark = pytest.mark.integration


def test_every_stored_row_recomputes_to_its_stored_values(read_api: Api) -> None:
    factory = sessionmaker(bind=read_api.engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        context = load_snapshot_context(session)
        stored = {
            (int(r["product_id"]), int(r["warehouse_id"])): r
            for r in frame_records(context.metrics)
        }
        verified = recompute_rows(session, load_snapshot(session), stored)
    assert len(verified) == len(stored) == 150  # raises SnapshotStaleError on any mismatch


def _committed(engine: Engine, pid: int, wid: int) -> int:
    with Session(engine) as session:
        return int(
            session.scalars(
                select(InventoryLevel.committed_qty).where(
                    InventoryLevel.product_id == pid, InventoryLevel.warehouse_id == wid
                )
            ).one()
        )


def _set_committed(engine: Engine, pid: int, wid: int, value: int) -> None:
    with Session(engine) as session, session.begin():
        session.execute(
            update(InventoryLevel)
            .where(InventoryLevel.product_id == pid, InventoryLevel.warehouse_id == wid)
            .values(committed_qty=value)
        )


@pytest.fixture
def changed_sku_024(read_api: Api) -> Iterator[tuple[Api, int, int]]:
    """SKU-024 @ WH-MUM with 40 more committed units than the snapshot saw; restored after."""
    pid, mum = product_id(read_api.engine, "SKU-024"), warehouse_id(read_api.engine, "WH-MUM")
    original = _committed(read_api.engine, pid, mum)
    _set_committed(read_api.engine, pid, mum, original + 40)
    yield read_api, pid, mum
    _set_committed(read_api.engine, pid, mum, original)
    clean_analytics_outputs(read_api.engine)  # the next read_api recalculates on the seed data


def test_changed_data_gives_409_with_field_names_until_a_recalculation(
    changed_sku_024: tuple[Api, int, int],
) -> None:
    api, pid, mum = changed_sku_024
    headers = api.headers("analyst")
    for path in (f"/api/v1/analytics/metrics/{pid}/explain", f"/api/v1/risk/{pid}"):
        response = api.client.get(path, params={"warehouse_id": mum}, headers=headers)
        assert response.status_code == 409, path
        error = response.json()["error"]
        assert error["code"] == "CONFLICT"
        assert error["message"] == (
            "Underlying data has changed since this snapshot. Run a recalculation."
        )
        fields = error["details"]["fields"]
        assert "available" in fields and "inventory_position" in fields
        assert set(fields) <= set(VERIFIED_FIELDS)
        assert error["request_id"]
        assert set(error["details"]) == {"fields"}  # names only, no values

    recalc = api.client.post("/api/v1/analytics/recalculate", headers=api.headers("admin"))
    assert recalc.status_code == 201
    for path in (f"/api/v1/analytics/metrics/{pid}/explain", f"/api/v1/risk/{pid}"):
        response = api.client.get(path, params={"warehouse_id": mum}, headers=headers)
        assert response.status_code == 200, path
    detail = api.client.get(f"/api/v1/risk/{pid}", params={"warehouse_id": mum}, headers=headers)
    assert detail.json()["committed"] == _committed(api.engine, pid, mum)


def test_unchanged_rows_still_explain_while_another_row_is_stale(
    changed_sku_024: tuple[Api, int, int],
) -> None:
    api, _, mum = changed_sku_024
    other = product_id(api.engine, "SKU-004")
    response = api.client.get(
        f"/api/v1/analytics/metrics/{other}/explain",
        params={"warehouse_id": mum},
        headers=api.headers("analyst"),
    )
    assert response.status_code == 200


@pytest.fixture
def isolated(read_api: Api) -> Iterator[Api]:
    """A test that edits data or the snapshot; outputs are cleaned so read_api recalculates."""
    yield read_api
    clean_analytics_outputs(read_api.engine)


def _explain(api: Api, sku: str) -> Any:
    pid, mum = product_id(api.engine, sku), warehouse_id(api.engine, "WH-MUM")
    return api.client.get(
        f"/api/v1/analytics/metrics/{pid}/explain",
        params={"warehouse_id": mum},
        headers=api.headers("analyst"),
    )


def test_a_product_deactivated_since_the_snapshot_is_stale(isolated: Api) -> None:
    pid = product_id(isolated.engine, "SKU-004")
    with Session(isolated.engine) as session, session.begin():
        session.execute(update(Product).where(Product.id == pid).values(is_active=False))
    try:
        response = _explain(isolated, "SKU-004")
    finally:
        with Session(isolated.engine) as session, session.begin():
            session.execute(update(Product).where(Product.id == pid).values(is_active=True))
    assert response.status_code == 409
    assert response.json()["error"]["details"]["fields"] == list(VERIFIED_FIELDS)


def test_inputs_that_no_longer_validate_are_stale(
    read_api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    def invalid(*_args: Any) -> Any:
        raise AnalyticsInputError("missing inventory policy", ["product_id=1,warehouse_id=1"])

    monkeypatch.setattr(explain_service, "run_analytics", invalid)
    response = _explain(read_api, "SKU-004")
    assert response.status_code == 409
    assert "product_id=1" not in response.text


def test_a_pair_without_a_snapshot_row_is_not_found(isolated: Api) -> None:
    pid, mum = product_id(isolated.engine, "SKU-004"), warehouse_id(isolated.engine, "WH-MUM")
    with Session(isolated.engine) as session, session.begin():
        session.execute(
            delete(ProductMetric).where(
                ProductMetric.product_id == pid, ProductMetric.warehouse_id == mum
            )
        )
    response = _explain(isolated, "SKU-004")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "No snapshot row for this product and warehouse."
