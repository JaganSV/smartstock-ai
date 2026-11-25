"""snapshot_context (BOB-P3-02a): frame building and the snapshot-specific high-demand flag.

No database: the snapshot is a plain object and the rows are dicts shaped like
``MetricsRepository.snapshot_metric_rows``.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

import pytest
from sqlalchemy.orm import Session

from app.analytics.params import AnalyticsParams
from app.services import snapshot_context
from app.services.errors import NoSnapshotError, NotFoundError
from app.services.snapshot_context import (
    METRIC_COLUMNS,
    build_context,
    load_snapshot_context,
    metrics_frame,
    snapshot_params,
)

T0 = date(2026, 9, 30)
STORED = AnalyticsParams(t0=T0).to_json()  # what RecalculationService stores


def stored(**overrides: Any) -> dict[str, Any]:
    return {**STORED, **overrides}


@dataclass
class FakeSnapshot:
    id: int = 7
    calculated_at: datetime = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)
    data_as_of_date: date = T0
    params_json: dict[str, Any] = field(default_factory=stored)


def _row(product_id: int, trend: str | None, **extra: Any) -> dict[str, Any]:
    return {
        "product_id": product_id,
        "warehouse_id": 1,
        "sku": f"SKU-{product_id:03d}",
        "warehouse_code": "WH-MUM",
        "ads_30": Decimal("10.0000"),
        "ads_90": Decimal("9.5000"),
        "demand_std_30": Decimal("2.0000"),
        "days_of_cover": None,
        "demand_trend_pct": None if trend is None else Decimal(trend),
        "inventory_value": Decimal("123.45"),
        "risk_class": "LOW",
        **extra,
    }


ROWS = [_row(1, "0.2999"), _row(2, "0.3000"), _row(3, "0.6000"), _row(4, None)]


def test_high_demand_uses_the_threshold_of_the_snapshot() -> None:
    default = build_context(FakeSnapshot(), ROWS).metrics
    assert default["is_high_demand"].tolist() == [False, True, True, False]  # >= 0.30; null False
    strict = build_context(FakeSnapshot(params_json=stored(spike_threshold=0.99)), ROWS).metrics
    assert strict["is_high_demand"].tolist() == [False, False, False, False]
    loose = build_context(FakeSnapshot(params_json=stored(spike_threshold=0.0)), ROWS).metrics
    assert loose["is_high_demand"].tolist() == [True, True, True, False]


def test_snapshot_params_read_t0_and_spike_threshold_from_the_snapshot() -> None:
    params = snapshot_params(FakeSnapshot(params_json=stored(spike_threshold=0.45)))
    assert params.t0 == T0 and params.spike_threshold == 0.45


def test_snapshot_params_rebuild_every_stored_parameter_exactly() -> None:
    """BOB-P3-02b 7.2: the recompute uses the snapshot's own parameters, z_table included."""
    changed = stored(
        overstock_cover_days=150, review_period_days=7, z_table={"0.9": 1.3, "0.95": 1.7}
    )
    params = snapshot_params(FakeSnapshot(data_as_of_date=date(2026, 8, 31), params_json=changed))
    assert params.t0 == date(2026, 8, 31)
    assert params.overstock_cover_days == 150 and params.review_period_days == 7
    assert params.z_table == {0.9: 1.3, 0.95: 1.7}
    assert snapshot_params(FakeSnapshot()) == AnalyticsParams(t0=T0)  # round trip of to_json


def test_snapshot_without_a_spike_threshold_is_an_error_not_a_silent_default() -> None:
    with pytest.raises(KeyError):
        snapshot_params(FakeSnapshot(params_json={}))
    missing = {k: v for k, v in STORED.items() if k != "slow_ratio"}
    with pytest.raises(KeyError):
        snapshot_params(FakeSnapshot(params_json=missing))


def test_meta_carries_the_snapshot_identity_and_verified_true() -> None:
    meta = build_context(FakeSnapshot(), ROWS).meta
    assert meta.snapshot_id == 7 and meta.data_as_of_date == T0 and meta.verified is True
    assert meta.calculated_at == FakeSnapshot().calculated_at


def test_metrics_frame_converts_types_and_renames_the_trend() -> None:
    frame = metrics_frame(ROWS)
    assert "demand_trend" in frame and "demand_trend_pct" not in frame
    assert frame["ads_30"].dtype == "float64" and frame["ads_30"].iloc[0] == 10.0
    assert frame["days_of_cover"].isna().all()  # NULL -> NaN
    assert frame["inventory_value"].iloc[0] == Decimal("123.45")  # money stays Decimal


def test_metrics_frame_of_no_rows_still_has_every_column() -> None:
    frame = metrics_frame([])
    assert frame.empty
    expected = [c if c != "demand_trend_pct" else "demand_trend" for c in METRIC_COLUMNS]
    assert list(frame.columns) == expected


def test_load_raises_no_snapshot_error_when_there_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    class EmptyRepository:
        def __init__(self, session: object) -> None:
            pass

        def latest_snapshot(self) -> None:
            return None

    monkeypatch.setattr(snapshot_context, "MetricsRepository", EmptyRepository)
    with pytest.raises(NoSnapshotError) as error:
        load_snapshot_context(cast(Session, object()))  # the stub never touches the session
    assert error.value.code == "CONFLICT"
    assert str(error.value) == "No analytics snapshot available. Run a recalculation."


def test_load_an_unknown_snapshot_id_is_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    class EmptyRepository:
        def __init__(self, session: object) -> None:
            pass

        def get(self, snapshot_id: int) -> None:
            return None

    monkeypatch.setattr(snapshot_context, "MetricsRepository", EmptyRepository)
    with pytest.raises(NotFoundError) as error:
        load_snapshot_context(cast(Session, object()), snapshot_id=999)
    assert str(error.value) == "Unknown snapshot_id."
