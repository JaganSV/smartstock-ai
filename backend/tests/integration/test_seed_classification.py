"""Table 7.8 against the persisted classification of the seed-42 dataset (AC-2.4, AC-2.7)."""

from collections.abc import Iterator

import pandas as pd
import pytest
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session, sessionmaker

from app.analytics.explain import explain_row
from app.analytics.params import AnalyticsParams
from app.models import AuditLog, MetricSnapshot, ProductMetric
from app.services.analytics_service import RecalculationService
from app.services.evidence import (
    SCENARIO_EXPECTATIONS,
    ScenarioExpectation,
    check_row,
    expectation_for,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def stored(_seeded_module_engine: Engine) -> Iterator[pd.DataFrame]:
    """One recalculation of the seeded database; the persisted rows read back as a frame."""
    factory = sessionmaker(bind=_seeded_module_engine, expire_on_commit=False)
    with factory() as session:
        service = RecalculationService(session)
        result = service.run("test")
        frame = service.stored_metrics(result.snapshot_id)
    yield frame
    with Session(_seeded_module_engine) as session, session.begin():
        session.execute(delete(ProductMetric))
        session.execute(delete(MetricSnapshot))
        session.execute(delete(AuditLog))


def _row(frame: pd.DataFrame, sku: str, code: str) -> pd.Series:
    match = frame[(frame["sku"] == sku) & (frame["warehouse_code"] == code)]
    assert len(match) == 1
    return match.iloc[0]


def test_every_row_matches_table_7_8(stored: pd.DataFrame) -> None:
    params = AnalyticsParams(t0=pd.Timestamp("2026-09-30").date())
    failures = [
        (row["sku"], row["warehouse_code"], check_row(row, params)[1])
        for _, row in stored.iterrows()
        if not check_row(row, params)[0]
    ]
    assert len(stored) == 150
    assert failures == []


def test_all_six_classes_are_present(stored: pd.DataFrame) -> None:
    assert set(stored["risk_class"]) == {
        "STOCKOUT",
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "OVERSTOCK",
        "LOW",
    }


@pytest.mark.parametrize("scenario", SCENARIO_EXPECTATIONS, ids=lambda item: item.scenario)
def test_each_scenario_band_has_the_expected_class(
    stored: pd.DataFrame, scenario: ScenarioExpectation
) -> None:
    numbers = stored["sku"].map(lambda sku: int(sku.split("-")[1]))
    in_band = (numbers >= scenario.first_sku) & (numbers <= scenario.last_sku)
    rows = stored[in_band & (stored["warehouse_code"] == scenario.warehouse_code)]
    assert len(rows) == scenario.last_sku - scenario.first_sku + 1
    assert set(rows["risk_class"]) <= scenario.risk_classes


def test_specific_rows(stored: pd.DataFrame) -> None:
    assert _row(stored, "SKU-001", "WH-MUM")["risk_class"] == "STOCKOUT"
    assert _row(stored, "SKU-004", "WH-MUM")["risk_class"] == "CRITICAL"
    assert _row(stored, "SKU-009", "WH-BLR")["risk_class"] == "HIGH"
    assert _row(stored, "SKU-013", "WH-DEL")["risk_class"] == "OVERSTOCK"
    dead = _row(stored, "SKU-021", "WH-BLR")
    assert dead["risk_reason_code"] == "R5_EXCESS_COVER"
    assert bool(dead["is_dead_stock"]) and bool(dead["is_slow_moving"])
    covered = _row(stored, "SKU-024", "WH-MUM")
    assert covered["risk_class"] == "MEDIUM" and covered["incoming_in_lt"] > 0
    assert _row(stored, "SKU-027", "WH-DEL")["risk_class"] == "CRITICAL"
    assert expectation_for("SKU-040", "WH-MUM") is None  # HEALTHY rows have no expectation


def test_explain_payload_matches_the_stored_metrics_for_five_rows(
    _seeded_module_engine: Engine, stored: pd.DataFrame
) -> None:
    """AC-2.7: explain_row (recomputed from the database) equals the persisted values."""
    factory = sessionmaker(bind=_seeded_module_engine, expire_on_commit=False)
    with factory() as session:
        params, frame = RecalculationService(session).analyze()
    spot = [
        ("SKU-001", "WH-MUM"),
        ("SKU-004", "WH-MUM"),
        ("SKU-009", "WH-BLR"),
        ("SKU-021", "WH-BLR"),
        ("SKU-024", "WH-MUM"),
    ]
    for sku, code in spot:
        persisted = _row(stored, sku, code)
        live = frame[(frame["sku"] == sku) & (frame["warehouse_code"] == code)].iloc[0]
        payload = explain_row(live, params)
        assert (payload["sku"], payload["warehouse_code"]) == (sku, code)
        entries = {entry["metric"]: entry for entry in payload["metrics"]}
        assert len(entries) == 12
        for name, entry in entries.items():
            if name == "inventory_position":  # not persisted (derived: available + incoming)
                assert entry["result"] == persisted["available"] + persisted["incoming_in_lt"]
                continue
            stored_value = persisted[name]
            if pd.isna(stored_value):
                assert entry["result"] is None, (sku, name)
            elif name == "risk_class":
                assert entry["result"] == stored_value
                assert entry["reason_code"] == persisted["risk_reason_code"]
            else:
                assert entry["result"] == pytest.approx(float(stored_value), abs=1e-9), (sku, name)
