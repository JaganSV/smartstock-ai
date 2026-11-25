"""Exact explanations and risk detail: recompute, verify against the snapshot, then serve (FR-B6).

``recompute_rows`` reloads the raw data as of the snapshot's ``data_as_of_date`` through the
recalculation's own loader (``load_metric_inputs``), restricted to the requested products and
warehouses, rebuilds the snapshot's ``AnalyticsParams`` from its ``params_json`` and runs the
analytics pipeline. Every compared value is put on the storage scale (``to_snapshot_rows``: 4 dp /
2 dp, integers, enums) and compared with the stored ``product_metrics`` row. Any difference raises
``SnapshotStaleError`` (409, field names only), so an explanation never disagrees with the stored
numbers. All numbers come from ``app.analytics``; nothing is calculated here.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.analytics.errors import AnalyticsError
from app.analytics.explain import explain_row
from app.analytics.numeric import round_decimal
from app.analytics.params import AnalyticsParams
from app.analytics.pipeline import run_analytics
from app.analytics.projection import projected_stock, projected_stockout_day
from app.analytics.snapshot import FOUR_DP_COLUMNS, to_snapshot_rows
from app.models.analytics import MetricSnapshot
from app.repositories.products import ProductRepository
from app.schemas.analytics import ExplainItem, ExplainOut, RiskTrace, RuleCheck
from app.schemas.risk import (
    OpenIncomingOut,
    ProjectionOut,
    ProjectionPoint,
    RiskDetailOut,
)
from app.services.analytics_service import load_metric_inputs
from app.services.errors import NotFoundError, SnapshotStaleError
from app.services.inventory_service import ensure_exists
from app.services.snapshot_context import (
    SnapshotContext,
    frame_records,
    load_snapshot,
    load_snapshot_context,
    snapshot_params,
)

Pair = tuple[int, int]  # (product_id, warehouse_id)

# The stored values an explanation or risk detail must reproduce (BOB-P3-02b 7.2, step 3).
VERIFIED_FIELDS = (
    "available",
    "incoming_in_lt",
    "ads_30",
    "ads_90",
    "demand_std_30",
    "lead_time_days",
    "safety_stock",
    "reorder_point",
    "days_of_cover",
    "inventory_position",
    "reorder_qty",
    "risk_class",
)


@dataclass(frozen=True)
class VerifiedRow:
    """A recomputed row proven equal to the stored one, with what explanations need."""

    params: AnalyticsParams
    row: dict[str, Any]  # the ``run_analytics`` row (unrounded floats, context columns)
    open_incoming: list[tuple[date, int]]  # (arrival date, quantity), OPEN and after t0
    stored: dict[str, Any]  # the stored row as served (``SnapshotContext.metrics`` record)


def _storage_value(field: str, value: Any) -> Any:
    """``value`` on the storage scale: None for null, 4-dp Decimal, str for the class, else int."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if field in FOUR_DP_COLUMNS:
        return round_decimal(value, 4)
    if field == "risk_class":
        return str(value)
    return int(value)


def _stored_values(stored: Mapping[str, Any]) -> dict[str, Any]:
    derived = {"inventory_position": int(stored["available"]) + int(stored["incoming_in_lt"])}
    return {f: _storage_value(f, derived.get(f, stored.get(f))) for f in VERIFIED_FIELDS}


def _recomputed_values(storage_row: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    derived = {"inventory_position": row["inventory_position"]}
    return {f: _storage_value(f, derived.get(f, storage_row.get(f))) for f in VERIFIED_FIELDS}


def mismatched_fields(stored: Mapping[str, Any], recomputed: Mapping[str, Any]) -> list[str]:
    """Verified fields whose storage-scale values differ, in ``VERIFIED_FIELDS`` order."""
    return [f for f in VERIFIED_FIELDS if stored[f] != recomputed[f]]


def recompute_rows(
    session: Session, snapshot: MetricSnapshot, stored: Mapping[Pair, Mapping[str, Any]]
) -> dict[Pair, VerifiedRow]:
    """Recompute the ``stored`` rows of ``snapshot`` and verify them (``SnapshotStaleError``).

    Only the requested products and warehouses are loaded and analysed (never all rows).
    """
    if not stored:
        return {}
    params = snapshot_params(snapshot)
    product_ids: Collection[int] = {p for p, _ in stored}
    warehouse_ids: Collection[int] = {w for _, w in stored}
    try:
        inputs = load_metric_inputs(session, params, product_ids, warehouse_ids)
        frame = run_analytics(inputs, params) if len(inputs) else None
    except AnalyticsError:
        # The current data no longer even forms valid inputs (e.g. a policy row is gone).
        raise SnapshotStaleError(list(VERIFIED_FIELDS)) from None
    if frame is None:
        raise SnapshotStaleError(list(VERIFIED_FIELDS))
    incoming = {
        (int(p), int(w)): list(orders)
        for p, w, orders in zip(
            inputs["product_id"], inputs["warehouse_id"], inputs["open_incoming"], strict=True
        )
    }
    storage_rows = to_snapshot_rows(frame)
    recomputed = {
        (int(r["product_id"]), int(r["warehouse_id"])): (r, s)
        for r, s in zip(frame.to_dict("records"), storage_rows, strict=True)
    }
    mismatched: set[str] = set()
    verified: dict[Pair, VerifiedRow] = {}
    for pair, stored_row in stored.items():
        if pair not in recomputed:
            mismatched.update(VERIFIED_FIELDS)
            continue
        row, storage_row = recomputed[pair]
        mismatched.update(
            mismatched_fields(_stored_values(stored_row), _recomputed_values(storage_row, row))
        )
        verified[pair] = VerifiedRow(
            params=params, row=row, open_incoming=incoming[pair], stored=dict(stored_row)
        )
    if mismatched:
        raise SnapshotStaleError([f for f in VERIFIED_FIELDS if f in mismatched])
    return verified


def _stored_row(context: SnapshotContext, product_id: int, warehouse_id: int) -> dict[str, Any]:
    metrics = context.metrics
    rows = metrics.loc[
        (metrics["product_id"] == product_id) & (metrics["warehouse_id"] == warehouse_id)
    ]
    if rows.empty:
        raise NotFoundError("No snapshot row for this product and warehouse.")
    return frame_records(rows)[0]


def recompute_for_snapshot(
    session: Session, context: SnapshotContext, product_id: int, warehouse_id: int
) -> VerifiedRow:
    """7.2 helper for one product x warehouse of the context's snapshot (404 / 409 as above)."""
    if ProductRepository(session).get(product_id) is None:
        raise NotFoundError("Unknown product_id.")
    ensure_exists(session, warehouse_id=warehouse_id)
    stored = _stored_row(context, product_id, warehouse_id)
    snapshot = load_snapshot(session, context.meta.snapshot_id)
    return recompute_rows(session, snapshot, {(product_id, warehouse_id): stored})[
        (product_id, warehouse_id)
    ]


def _risk_trace(payload: Mapping[str, Any]) -> RiskTrace:
    """The BP 7.4 trace of an ``explain_row`` payload (its last entry is risk_class)."""
    risk = payload["metrics"][-1]
    return RiskTrace(
        risk_class=risk["result"],
        reason_code=risk["reason_code"],
        rule_fired=f"R{risk['fired_rule']['order']}",
        rules_checked=[
            RuleCheck(rule=f"R{c['order']}", risk_class=c["risk_class"], matched=c["matched"])
            for c in risk["rules_checked"]
        ],
    )


# --- #15 explanation ---


def explain(session: Session, product_id: int, warehouse_id: int) -> ExplainOut:
    context = load_snapshot_context(session)
    verified = recompute_for_snapshot(session, context, product_id, warehouse_id)
    payload = explain_row(verified.row, verified.params)
    return ExplainOut(
        product_id=product_id,
        sku=payload["sku"],
        warehouse_id=warehouse_id,
        warehouse_code=payload["warehouse_code"],
        snapshot=context.meta,
        metrics=[ExplainItem.model_validate(item) for item in payload["metrics"]],
        risk=_risk_trace(payload),
    )


# --- #19 risk detail ---


def projection(verified: VerifiedRow) -> ProjectionOut:
    """BP 7.3 projection over k = 0 .. L from ``app.analytics.projection`` (no formula here)."""
    row, t0 = verified.row, verified.params.t0
    horizon = int(row["lead_time_days"])
    available, ads30 = float(row["available"]), float(row["ads_30"])
    units = projected_stock(available, ads30, verified.open_incoming, t0, horizon)
    return ProjectionOut(
        horizon_days=horizon,
        points=[
            ProjectionPoint(day=k, date=t0 + timedelta(days=k), projected_units=u)
            for k, u in enumerate(units)
        ],
        projected_stockout_day=projected_stockout_day(
            available, ads30, verified.open_incoming, t0, horizon
        ),
        open_incoming=[
            OpenIncomingOut(expected_arrival_date=arrival, quantity=quantity)
            for arrival, quantity in verified.open_incoming
        ],
    )


def risk_detail(session: Session, product_id: int, warehouse_id: int) -> RiskDetailOut:
    product = ProductRepository(session).get(product_id)
    if product is None:
        raise NotFoundError("Unknown product_id.")
    context = load_snapshot_context(session)
    verified = recompute_for_snapshot(session, context, product_id, warehouse_id)
    payload = explain_row(verified.row, verified.params)
    return RiskDetailOut.model_validate(
        {
            **verified.stored,
            "name": product.name,
            "rule_trace": _risk_trace(payload),
            "projection": projection(verified),
            "snapshot": context.meta,
        }
    )
