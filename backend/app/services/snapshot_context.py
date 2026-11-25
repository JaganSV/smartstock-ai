"""The latest analytics snapshot as one per-request context (BOB-P3-02a, FR-A5).

``load_snapshot_context`` reads the newest ``metric_snapshot`` and its ``product_metrics`` rows once
and returns them as a DataFrame with the derived ``is_high_demand`` column. The flag uses
``app.analytics.flags.is_high_demand`` with the ``spike_threshold`` stored in THAT snapshot's
``params_json`` (BP 7.4 clarification), never the current defaults. No numbers are computed here.
"""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from datetime import date, datetime
from typing import Any, Protocol

import pandas as pd
from sqlalchemy.orm import Session

from app.analytics.flags import is_high_demand
from app.analytics.params import AnalyticsParams
from app.models.analytics import MetricSnapshot, ProductMetric
from app.repositories.metrics import MetricsRepository
from app.schemas.common import SnapshotMeta
from app.services.errors import NoSnapshotError, NotFoundError

# Stored 4-dp Decimals that the analytics functions read as float64 (NULL -> NaN).
FLOAT_COLUMNS = ("ads_30", "ads_90", "demand_std_30", "days_of_cover", "demand_trend")
METRIC_COLUMNS = (
    *(c.name for c in ProductMetric.__table__.columns if c.name not in {"id", "snapshot_id"}),
    "sku",
    "warehouse_code",
)


class SnapshotLike(Protocol):
    @property
    def id(self) -> int: ...
    @property
    def calculated_at(self) -> datetime: ...
    @property
    def data_as_of_date(self) -> date: ...
    @property
    def params_json(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class SnapshotContext:
    meta: SnapshotMeta
    metrics: pd.DataFrame  # one row per product x warehouse, plus ``is_high_demand``


def metrics_frame(rows: Iterable[Mapping[Any, Any]]) -> pd.DataFrame:
    """Stored metric rows -> frame. ``demand_trend_pct`` is renamed ``demand_trend`` (the ratio);
    4-dp columns become float64; ``inventory_value`` stays Decimal. Columns exist even if empty."""
    frame = pd.DataFrame([dict(row) for row in rows], columns=list(METRIC_COLUMNS))
    frame = frame.rename(columns={"demand_trend_pct": "demand_trend"})
    for column in FLOAT_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("float64")
    return frame


def _clean(value: Any) -> Any:
    """NaN / NA -> None; everything else unchanged (pandas ``to_dict`` gives Python scalars)."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def frame_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Frame rows as dicts for the response schemas, with NaN as None."""
    return [{k: _clean(v) for k, v in row.items()} for row in frame.to_dict("records")]


def snapshot_params(snapshot: SnapshotLike) -> AnalyticsParams:
    """The exact parameters the snapshot was calculated with, rebuilt from its ``params_json``.

    t0 is the snapshot's ``data_as_of_date``. Every other field must be stored (``KeyError`` if
    one is missing, never a silent default); ``z_table`` keys go back from strings to floats.
    """
    stored = snapshot.params_json
    scalars = {
        f.name: stored[f.name] for f in fields(AnalyticsParams) if f.name not in {"t0", "z_table"}
    }
    z_table = {float(level): float(z) for level, z in stored["z_table"].items()}
    return AnalyticsParams(t0=snapshot.data_as_of_date, z_table=z_table, **scalars)


def build_context(snapshot: SnapshotLike, rows: Iterable[Mapping[Any, Any]]) -> SnapshotContext:
    """Pure: snapshot + its stored rows -> context with the derived ``is_high_demand`` column."""
    frame = metrics_frame(rows)
    frame["is_high_demand"] = is_high_demand(frame, snapshot_params(snapshot))
    meta = SnapshotMeta(
        snapshot_id=snapshot.id,
        calculated_at=snapshot.calculated_at,
        data_as_of_date=snapshot.data_as_of_date,
    )
    return SnapshotContext(meta=meta, metrics=frame)


def load_snapshot(session: Session, snapshot_id: int | None = None) -> MetricSnapshot:
    """The snapshot ``snapshot_id`` (``NotFoundError``, 404, if unknown), or the latest one
    (``NoSnapshotError``, 409, when none exists)."""
    repository = MetricsRepository(session)
    if snapshot_id is not None:
        found = repository.get(snapshot_id)
        if found is None:
            raise NotFoundError("Unknown snapshot_id.")
        return found
    latest = repository.latest_snapshot()
    if latest is None:
        raise NoSnapshotError()
    return latest


def load_snapshot_context(session: Session, snapshot_id: int | None = None) -> SnapshotContext:
    """A snapshot (default: the latest) and its rows; errors as in ``load_snapshot``."""
    snapshot = load_snapshot(session, snapshot_id)
    rows = MetricsRepository(session).snapshot_metric_rows(snapshot.id)
    return build_context(snapshot, rows)


def latest_snapshot_t0(session: Session) -> date | None:
    """t0 of the latest snapshot, or None when there is none (no rows are loaded)."""
    snapshot = MetricsRepository(session).latest_snapshot()
    return snapshot.data_as_of_date if snapshot is not None else None
