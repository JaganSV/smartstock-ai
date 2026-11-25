"""Recalculation service: load -> analyse -> persist one dated snapshot (BP 7, ADR-012).

``RecalculationService.run`` owns the transaction. It first takes a PostgreSQL advisory
transaction lock (one recalculation at a time, BOB-P3-02b), then writes one ``metric_snapshots``
row, one ``product_metrics`` row per product x warehouse and one ``audit_log`` row, or nothing at
all. A refused lock writes one ``ANALYTICS_RECALC_REJECTED`` audit row instead.
Repositories return plain rows; the DataFrame conversion happens here. All numbers come from
``app.analytics`` (pure functions); this module only moves data in and out.
"""

import logging
import re
import time
from collections.abc import Collection, Iterable, Mapping, Sequence
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
from app.models.enums import RISK_SEVERITY
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
from app.schemas.analytics import SnapshotOut
from app.schemas.common import Page, PageParams
from app.services.errors import NoDataError, RecalculationError, RecalculationLockedError
from app.services.snapshot_context import metrics_frame

logger = logging.getLogger(__name__)

AUDIT_ACTION = "ANALYTICS_RECALCULATED"
REJECTED_ACTION = "ANALYTICS_RECALC_REJECTED"
AUDIT_ENTITY_TYPE = "metric_snapshot"
TRIGGERED_BY_PATTERN = re.compile(r"[a-z0-9_:-]{1,64}")
# Fixed key of the advisory lock that serialises recalculations (ASCII "SSAI").
RECALC_LOCK_KEY = 0x53534149


@dataclass(frozen=True)
class AuditContext:
    """Who asked for the recalculation, for the audit row. The CLI and startup pass none."""

    user_id: int | None = None
    request_id: str | None = None
    ip_address: str | None = None


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


def load_metric_inputs(
    session: Session,
    params: AnalyticsParams,
    product_ids: Collection[int] | None = None,
    warehouse_ids: Collection[int] | None = None,
) -> pd.DataFrame:
    """Raw data as of ``params.t0`` through the repositories -> ``build_metric_inputs`` frame.

    The one loader of the recalculation and of the explanation recompute (BOB-P3-02b 7.2).
    ``product_ids`` / ``warehouse_ids`` restrict every input to those products and warehouses
    (None: all); suppliers are always loaded in full (a few rows).
    """
    window_start = params.t0 - timedelta(days=params.long_window - 1)
    return build_metric_inputs(
        products=_frame(ProductRepository(session).active_rows(product_ids), PRODUCTS_COLS),
        warehouses=_frame(WarehouseRepository(session).rows(warehouse_ids), WAREHOUSES_COLS),
        suppliers=_frame(SupplierRepository(session).rows(), SUPPLIERS_COLS),
        policies=_frame(
            InventoryPolicyRepository(session).rows(product_ids, warehouse_ids), POLICIES_COLS
        ),
        levels=_frame(
            InventoryRepository(session).level_rows(product_ids, warehouse_ids), LEVELS_COLS
        ),
        incoming=_frame(
            IncomingStockRepository(session).open_rows_after(params.t0, product_ids, warehouse_ids),
            INCOMING_COLS,
        ),
        sales=_frame(
            SalesRepository(session).window_rows(
                window_start, params.t0, product_ids, warehouse_ids
            ),
            SALES_COLS,
        ),
        params=params,
    )


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
        return params, run_analytics(load_metric_inputs(self.session, params), params)

    def stored_metrics(self, snapshot_id: int) -> pd.DataFrame:
        """The persisted rows of a snapshot as a frame (what the API and the UI will read).

        Same column names as ``product_metrics`` plus ``sku`` and ``warehouse_code``;
        ``demand_trend``
        is the stored ``demand_trend_pct`` ratio; 4-dp Decimals become float64 (NULL -> NaN);
        ``inventory_value`` stays Decimal.
        """
        return metrics_frame(self.metrics.snapshot_metric_rows(snapshot_id))

    def active_products(self) -> pd.DataFrame:
        """Active products (id, sku, category_id, ...) for KPI filtering."""
        return _frame(
            ProductRepository(self.session).active_rows(),
            ("id", "sku", "supplier_id", "category_id", "unit_cost", "case_pack", "is_active"),
        )

    # --- write side ---

    def _reject(self, triggered_by: str, context: AuditContext) -> None:
        """Audit a refused run (lock held) in its own small transaction. Never raises."""
        try:
            self.audit.add(
                AuditLog(
                    action=REJECTED_ACTION,
                    user_id=context.user_id,
                    entity_type=AUDIT_ENTITY_TYPE,
                    details={"reason": "lock_held", "triggered_by": triggered_by},
                    request_id=context.request_id,
                    ip_address=context.ip_address,
                )
            )
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            logger.error("Could not audit a rejected recalculation", exc_info=exc)

    def run(self, triggered_by: str, context: AuditContext | None = None) -> SnapshotResult:
        """Recalculate and persist one snapshot in a single transaction (committed at the end).

        The transaction first takes ``pg_try_advisory_xact_lock(RECALC_LOCK_KEY)``; if another
        recalculation holds it, nothing runs, an ``ANALYTICS_RECALC_REJECTED`` audit row is written
        and ``RecalculationLockedError`` is raised. Any other failure rolls the whole transaction
        back (no partial snapshot, no audit row). ``NoDataError`` and ``RecalculationError`` (code
        of the cause) are service errors; database errors propagate unchanged after the rollback.
        ``context`` (user, request id, IP) goes into the audit row; the CLI and startup pass none.
        """
        if not TRIGGERED_BY_PATTERN.fullmatch(triggered_by):
            raise RecalculationError(
                "triggered_by must match [a-z0-9_:-] and be at most 64 characters",
                "INVALID_TRIGGERED_BY",
            )
        audit_context = context or AuditContext()
        started = time.perf_counter()
        try:
            if not self.metrics.try_advisory_xact_lock(RECALC_LOCK_KEY):
                raise RecalculationLockedError()
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
                    user_id=audit_context.user_id,
                    entity_type=AUDIT_ENTITY_TYPE,
                    entity_id=str(snapshot.id),
                    details={
                        "rows": written,
                        "t0": params.t0.isoformat(),
                        "duration_ms": duration_ms,
                        "triggered_by": triggered_by,
                    },
                    request_id=audit_context.request_id,
                    ip_address=audit_context.ip_address,
                )
            )
            self.session.commit()
        except RecalculationLockedError:
            self.session.rollback()
            logger.warning("Recalculation refused: lock held (triggered_by=%s)", triggered_by)
            self._reject(triggered_by, audit_context)
            raise
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


def list_snapshots(session: Session, paging: PageParams) -> Page[SnapshotOut]:
    """Snapshots newest first with their row count and per-class counts (one grouped query).

    ``params_json`` is not exposed.
    """
    repository = MetricsRepository(session)
    snapshots, total = repository.snapshot_page(paging.offset, paging.page_size)
    counts: dict[int, dict[str, int]] = {}
    for row in repository.class_counts([s.id for s in snapshots]):
        counts.setdefault(row["snapshot_id"], {})[row["risk_class"]] = int(row["rows"])
    items = []
    for snapshot in snapshots:
        by_class = counts.get(snapshot.id, {})
        items.append(
            SnapshotOut(
                snapshot_id=snapshot.id,
                calculated_at=snapshot.calculated_at,
                data_as_of_date=snapshot.data_as_of_date,
                triggered_by=snapshot.triggered_by,
                row_count=sum(by_class.values()),
                risk_distribution={r.value: by_class.get(r.value, 0) for r in RISK_SEVERITY},
            )
        )
    return Page[SnapshotOut](items=items, page=paging.page, page_size=paging.page_size, total=total)


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
