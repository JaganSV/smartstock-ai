"""Recalculation service: load -> analyse -> persist one dated snapshot (BP 7, ADR-012).

``RecalculationService.run`` owns the transaction. It writes one ``metric_snapshots`` row, one
``product_metrics`` row per product x warehouse and one ``audit_log`` row, or nothing at all.
Repositories return plain rows; the DataFrame conversion happens here. All numbers come from
``app.analytics`` (pure functions); this module only moves data in and out.
"""

import logging
import re
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.analytics.errors import AnalyticsError
from app.analytics.inputs import build_metric_inputs
from app.analytics.params import AnalyticsParams
from app.analytics.pipeline import run_analytics
from app.analytics.rollup import risk_distribution
from app.analytics.snapshot import to_snapshot_rows
from app.analytics.types import (
    INCOMING_COLS,
    LEVELS_COLS,
    POLICIES_COLS,
    PRODUCTS_COLS,
    SALES_COLS,
    SUPPLIERS_COLS,
    WAREHOUSES_COLS,
)
from app.models.analytics import MetricSnapshot
from app.models.governance import AuditLog
from app.repositories.audit import AuditRepository
from app.repositories.inventory import (
    IncomingStockRepository,
    InventoryPolicyRepository,
    InventoryRepository,
)
from app.repositories.metrics import MetricsRepository
from app.repositories.products import ProductRepository
from app.repositories.reference import SupplierRepository, WarehouseRepository
from app.repositories.sales import SalesRepository
from app.services.errors import NoDataError, RecalculationError

logger = logging.getLogger(__name__)

AUDIT_ACTION = "ANALYTICS_RECALCULATED"
AUDIT_ENTITY_TYPE = "metric_snapshot"
TRIGGERED_BY_PATTERN = re.compile(r"[a-z0-9_:-]{1,64}")


@dataclass(frozen=True)
class SnapshotResult:
    snapshot_id: int
    t0: date
    row_count: int
    risk_distribution: dict[str, int]
    duration_ms: int


def _frame(rows: Iterable[Mapping[Any, Any]], columns: Sequence[str]) -> pd.DataFrame:
    """Plain repository rows -> DataFrame with exactly ``columns`` (also when there are no rows)."""
    return pd.DataFrame([dict(row) for row in rows], columns=list(columns))


class RecalculationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.sales = SalesRepository(session)
        self.metrics = MetricsRepository(session)
        self.audit = AuditRepository(session)

    # --- read side (no writes) ---

    def analyze(self) -> tuple[AnalyticsParams, pd.DataFrame]:
        """t0 from the data, load through repositories, run the whole pipeline. Writes nothing.

        Returns ``(params, frame)`` where ``frame`` is the ``run_analytics`` frame (metrics, risk
        class and reason, flags, and the context columns that ``explain_row`` needs).
        """
        t0 = self.sales.latest_sale_date()
        if t0 is None:
            raise NoDataError("sales_daily is empty, so t0 (data_as_of_date) cannot be derived")
        params = AnalyticsParams(t0=t0)
        window_start = t0 - timedelta(days=params.long_window - 1)
        inputs = build_metric_inputs(
            products=_frame(ProductRepository(self.session).active_rows(), PRODUCTS_COLS),
            warehouses=_frame(WarehouseRepository(self.session).rows(), WAREHOUSES_COLS),
            suppliers=_frame(SupplierRepository(self.session).rows(), SUPPLIERS_COLS),
            policies=_frame(InventoryPolicyRepository(self.session).rows(), POLICIES_COLS),
            levels=_frame(InventoryRepository(self.session).level_rows(), LEVELS_COLS),
            incoming=_frame(
                IncomingStockRepository(self.session).open_rows_after(t0), INCOMING_COLS
            ),
            sales=_frame(self.sales.window_rows(window_start, t0), SALES_COLS),
            params=params,
        )
        return params, run_analytics(inputs, params)

    def stored_metrics(self, snapshot_id: int) -> pd.DataFrame:
        """The persisted rows of a snapshot as a frame (what the API and the UI will read).

        Same column names as ``product_metrics`` plus ``sku`` and ``warehouse_code``;
        ``demand_trend``
        is the stored ``demand_trend_pct`` ratio; 4-dp Decimals become float64 (NULL -> NaN);
        ``inventory_value`` stays Decimal.
        """
        rows = [dict(row) for row in self.metrics.snapshot_metric_rows(snapshot_id)]
        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        frame = frame.rename(columns={"demand_trend_pct": "demand_trend"})
        for column in ("ads_30", "ads_90", "demand_std_30", "days_of_cover", "demand_trend"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("float64")
        return frame

    def active_products(self) -> pd.DataFrame:
        """Active products (id, sku, category_id, ...) for KPI filtering."""
        return _frame(
            ProductRepository(self.session).active_rows(),
            ("id", "sku", "supplier_id", "category_id", "unit_cost", "case_pack", "is_active"),
        )

    # --- write side ---

    def run(self, triggered_by: str) -> SnapshotResult:
        """Recalculate and persist one snapshot in a single transaction (committed at the end).

        Any failure rolls the whole transaction back (no partial snapshot, no audit row).
        ``NoDataError`` and ``RecalculationError`` (code of the cause) are service errors; database
        errors propagate unchanged after the rollback.
        """
        if not TRIGGERED_BY_PATTERN.fullmatch(triggered_by):
            raise RecalculationError(
                "triggered_by must match [a-z0-9_:-] and be at most 64 characters",
                "INVALID_TRIGGERED_BY",
            )
        started = time.perf_counter()
        try:
            params, frame = self.analyze()
            rows = to_snapshot_rows(frame)
            snapshot = self.metrics.add(
                MetricSnapshot(
                    data_as_of_date=params.t0,
                    params_json=params.to_json(),
                    triggered_by=triggered_by,
                )
            )
            written = self.metrics.add_snapshot_metrics(snapshot.id, rows)
            duration_ms = int((time.perf_counter() - started) * 1000)
            self.audit.add(
                AuditLog(
                    action=AUDIT_ACTION,
                    entity_type=AUDIT_ENTITY_TYPE,
                    entity_id=str(snapshot.id),
                    details={
                        "rows": written,
                        "t0": params.t0.isoformat(),
                        "duration_ms": duration_ms,
                        "triggered_by": triggered_by,
                    },
                )
            )
            self.session.commit()
        except NoDataError:
            self.session.rollback()
            logger.error("Recalculation failed: no sales data (triggered_by=%s)", triggered_by)
            raise
        except AnalyticsError as exc:
            self.session.rollback()
            logger.error(
                "Recalculation failed: %s (triggered_by=%s)", exc.code, triggered_by, exc_info=exc
            )
            raise RecalculationError(f"Analytics failed: {exc}", exc.code) from exc
        except Exception as exc:
            self.session.rollback()
            logger.error("Recalculation failed (triggered_by=%s)", triggered_by, exc_info=exc)
            raise
        result = SnapshotResult(
            snapshot_id=snapshot.id,
            t0=params.t0,
            row_count=written,
            risk_distribution=risk_distribution(frame),
            duration_ms=duration_ms,
        )
        logger.info(
            "Recalculated snapshot %d: %d rows, t0 %s, %d ms",
            result.snapshot_id,
            result.row_count,
            result.t0,
            result.duration_ms,
        )
        return result


STARTUP_OK = "ok"
STARTUP_SKIPPED = "skipped"
STARTUP_ERROR = "error"


def analytics_status(session: Session, startup_failed: bool) -> str:
    """Readiness of the analytics output: ``"ok"`` | ``"no_snapshot"`` | ``"error"``.

    ``"ok"`` when a snapshot exists. Without one: ``"error"`` if the startup recalculation failed,
    else ``"no_snapshot"``. A failing snapshot query is ``"error"``.
    """
    try:
        snapshot = MetricsRepository(session).latest_snapshot()
    except SQLAlchemyError as exc:
        logger.error("Analytics readiness check failed", exc_info=exc)
        return "error"
    if snapshot is not None:
        return "ok"
    return "error" if startup_failed else "no_snapshot"


def recalculate_on_startup(session_factory: sessionmaker[Session]) -> str:
    """FR-B5: recalculate once when the app starts, if products exist. Never raises.

    Returns ``"ok"``, ``"skipped"`` (no active products) or ``"error"``. A failure is logged as an
    error with its trace and the caller keeps starting.
    """
    try:
        with session_factory() as session:
            if ProductRepository(session).count_active() == 0:
                logger.info("Startup recalculation skipped: no products")
                return STARTUP_SKIPPED
            RecalculationService(session).run(triggered_by="startup")
        return STARTUP_OK
    except Exception as exc:
        logger.error("Startup recalculation failed; the app keeps running", exc_info=exc)
        return STARTUP_ERROR
