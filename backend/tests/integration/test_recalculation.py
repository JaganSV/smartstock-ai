"""Recalculation against the real PostgreSQL test database (strict mode applies via conftest).

The service commits, so the ``seeded_engine`` / ``empty_engine`` fixtures remove snapshots and
audit rows around every test and leave the other integration tests a clean database.
"""

import time
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app import cli
from app.analytics.rollup import dashboard_kpis
from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app
from app.models import AuditLog, MetricSnapshot, ProductMetric
from app.repositories.metrics import MetricsRepository
from app.services.analytics_service import (
    STARTUP_ERROR,
    STARTUP_OK,
    RecalculationService,
    recalculate_on_startup,
)
from app.services.errors import NoDataError

pytestmark = pytest.mark.integration


def _factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _count(engine: Engine, model: Any) -> int:
    with Session(engine) as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _broken_engine(url: str) -> Engine:
    """An engine that points at a port nothing listens on (fails fast)."""
    return create_engine(
        make_url(url).set(port=1), connect_args={"connect_timeout": 1}, pool_pre_ping=False
    )


def test_run_writes_one_snapshot_150_rows_and_one_audit_row(seeded_engine: Engine) -> None:
    with _factory(seeded_engine)() as session:
        result = RecalculationService(session).run("test")
    assert result.t0 == date(2026, 9, 30)
    assert result.row_count == 150
    assert sum(result.risk_distribution.values()) == 150
    assert _count(seeded_engine, MetricSnapshot) == 1
    assert _count(seeded_engine, ProductMetric) == 150
    with Session(seeded_engine) as session:
        audit = session.scalars(select(AuditLog)).one()
        snapshot = session.scalars(select(MetricSnapshot)).one()
    assert audit.action == "ANALYTICS_RECALCULATED"
    assert audit.entity_type == "metric_snapshot"
    assert audit.entity_id == str(snapshot.id) == str(result.snapshot_id)
    assert audit.details["rows"] == 150
    assert audit.details["t0"] == "2026-09-30"
    assert audit.details["triggered_by"] == "test"
    assert isinstance(audit.details["duration_ms"], int)
    assert snapshot.data_as_of_date == date(2026, 9, 30)
    assert snapshot.triggered_by == "test"


def test_two_runs_give_identical_metric_values(seeded_engine: Engine) -> None:
    with _factory(seeded_engine)() as session:
        service = RecalculationService(session)
        first = service.run("test")
        second = service.run("test")
        frame_a = service.stored_metrics(first.snapshot_id)
        frame_b = service.stored_metrics(second.snapshot_id)
    assert first.snapshot_id != second.snapshot_id
    assert _count(seeded_engine, MetricSnapshot) == 2  # old snapshots are never deleted
    pd.testing.assert_frame_equal(frame_a, frame_b)


def test_failure_in_the_middle_of_the_insert_rolls_everything_back(
    seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = MetricsRepository.add_snapshot_metrics

    def insert_then_fail(self: MetricsRepository, snapshot_id: int, rows: Any) -> int:
        original(self, snapshot_id, rows)
        raise RuntimeError("forced failure after the metric rows were flushed")

    monkeypatch.setattr(MetricsRepository, "add_snapshot_metrics", insert_then_fail)
    with _factory(seeded_engine)() as session, pytest.raises(RuntimeError):
        RecalculationService(session).run("test")
    assert _count(seeded_engine, MetricSnapshot) == 0
    assert _count(seeded_engine, ProductMetric) == 0
    assert _count(seeded_engine, AuditLog) == 0


def test_empty_database_raises_no_data_and_writes_nothing(empty_engine: Engine) -> None:
    with _factory(empty_engine)() as session, pytest.raises(NoDataError) as caught:
        RecalculationService(session).run("test")
    assert caught.value.code == "NO_DATA"
    assert _count(empty_engine, MetricSnapshot) == 0
    assert _count(empty_engine, AuditLog) == 0


def test_run_completes_well_under_five_seconds(seeded_engine: Engine) -> None:
    started = time.perf_counter()
    with _factory(seeded_engine)() as session:
        RecalculationService(session).run("test")
    assert time.perf_counter() - started < 5.0  # NFR-03


def test_latest_snapshot_is_the_new_one(seeded_engine: Engine) -> None:
    with _factory(seeded_engine)() as session:
        assert MetricsRepository(session).latest_snapshot() is None
        first = RecalculationService(session).run("test")
        latest_first = MetricsRepository(session).latest_snapshot()
        assert latest_first is not None and latest_first.id == first.snapshot_id
        second = RecalculationService(session).run("test")
        latest = MetricsRepository(session).latest_snapshot()
        assert latest is not None and latest.id == second.snapshot_id
        assert MetricsRepository(session).count_snapshots() == 2


def test_kpis_equal_a_direct_sql_aggregation(seeded_engine: Engine) -> None:
    with _factory(seeded_engine)() as session:
        service = RecalculationService(session)
        result = service.run("test")
        kpis = dashboard_kpis(service.stored_metrics(result.snapshot_id), service.active_products())
        units, value = session.execute(
            text("SELECT sum(on_hand), sum(inventory_value) FROM product_metrics")
        ).one()
        products = session.execute(text("SELECT count(*) FROM products WHERE is_active")).scalar()
    assert kpis["total_products"] == products == 50
    assert kpis["total_units"] == int(units)
    assert kpis["inventory_value"] == Decimal(value)
    assert sum(kpis["risk_distribution"].values()) == 150


def test_invalid_triggered_by_writes_nothing(seeded_engine: Engine) -> None:
    with _factory(seeded_engine)() as session:
        with pytest.raises(Exception, match="triggered_by"):
            RecalculationService(session).run("Bad Value;")
    assert _count(seeded_engine, MetricSnapshot) == 0


# --- startup recalculation (FR-B5) ---


@pytest.fixture
def startup_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    monkeypatch.setenv("RECALC_ON_STARTUP", "true")
    get_settings.cache_clear()
    yield monkeypatch
    monkeypatch.undo()
    get_settings.cache_clear()


def test_startup_recalculation_creates_a_snapshot(seeded_engine: Engine) -> None:
    assert recalculate_on_startup(_factory(seeded_engine)) == STARTUP_OK
    assert _count(seeded_engine, MetricSnapshot) == 1
    with Session(seeded_engine) as session:
        assert session.scalars(select(MetricSnapshot)).one().triggered_by == "startup"
        assert session.scalars(select(AuditLog)).one().details["triggered_by"] == "startup"


def test_app_startup_creates_a_snapshot_and_ready_reports_analytics_ok(
    seeded_engine: Engine, startup_env: pytest.MonkeyPatch
) -> None:
    factory = _factory(seeded_engine)
    app = create_app(factory)

    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        assert app.state.startup_recalc == STARTUP_OK
        ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "database": "ok",
        "ai": "not_configured",
        "analytics": "ok",
    }
    assert _count(seeded_engine, MetricSnapshot) == 1


def test_app_keeps_running_when_the_startup_recalculation_fails(
    seeded_engine: Engine, test_database_url: str, startup_env: pytest.MonkeyPatch
) -> None:
    broken = _factory(_broken_engine(test_database_url))
    app = create_app(broken)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert app.state.startup_recalc == STARTUP_ERROR
        health = client.get("/api/v1/health")
        ready = client.get("/api/v1/health/ready")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 503
    assert ready.json()["error"]["code"] == "INTERNAL_ERROR"
    assert ready.json()["error"]["message"] == "Database unavailable"


def test_ready_reports_analytics_error_when_startup_failed_but_the_database_is_up(
    seeded_engine: Engine, startup_env: pytest.MonkeyPatch
) -> None:
    """Database reachable now, but the startup run failed and no snapshot exists."""
    factory = _factory(seeded_engine)
    app = create_app(factory)

    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        app.state.startup_recalc = STARTUP_ERROR
        with factory() as session:  # make sure no snapshot exists at this point
            session.execute(text("DELETE FROM product_metrics"))
            session.execute(text("DELETE FROM metric_snapshots"))
            session.commit()
        ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json()["analytics"] == "error"


# --- CLI (exit codes 0 / 1 / 3) ---


def test_cli_recalc_exits_0_prints_the_summary_and_writes_the_report(
    seeded_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(cli, "get_session_factory", lambda: _factory(seeded_engine))
    report = tmp_path / "out" / "risk.md"
    assert cli.main(["recalc", "--triggered-by", "cli", "--report", str(report)]) == 0
    out = capsys.readouterr().out
    assert "Snapshot " in out and "150 rows" in out and "t0 2026-09-30" in out
    text_ = report.read_text(encoding="utf-8")
    assert "Overall Table 7.8: **PASS**" in text_
    assert "All six classes present: **PASS**" in text_
    assert _count(seeded_engine, MetricSnapshot) == 1


def test_cli_exits_1_on_no_data_and_3_on_a_database_error(
    empty_engine: Engine,
    test_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "get_session_factory", lambda: _factory(empty_engine))
    assert cli.main(["recalc"]) == 1
    assert "NO_DATA" in capsys.readouterr().err

    monkeypatch.setattr(
        cli, "get_session_factory", lambda: _factory(_broken_engine(test_database_url))
    )
    assert cli.main(["recalc"]) == 3
    assert "Database error" in capsys.readouterr().err


def test_cli_exits_1_on_an_invalid_triggered_by(
    seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "get_session_factory", lambda: _factory(seeded_engine))
    assert cli.main(["recalc", "--triggered-by", "BAD VALUE"]) == 1
    assert "INVALID_TRIGGERED_BY" in capsys.readouterr().err
    assert _count(seeded_engine, MetricSnapshot) == 0


def test_cli_bad_arguments_exit_2() -> None:
    with pytest.raises(SystemExit) as caught:
        cli.main(["nonsense"])
    assert caught.value.code == 2
