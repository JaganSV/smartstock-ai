"""Analytics response schemas (BP 6.2 #14-#17, FR-B5, FR-B6).

Explanation values come from ``app.analytics.explain.explain_row`` on a recomputed row that was
verified equal to the stored snapshot row (``explain_service``); nothing here computes a number.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import RiskClass
from app.schemas.common import Page, SnapshotMeta
from app.schemas.inventory import ProductMetricOut

# --- metrics list (#14) ---


class MetricPage(Page[ProductMetricOut]):
    """``Page[ProductMetricOut]`` plus the snapshot the rows come from."""

    snapshot: SnapshotMeta


# --- explanation (#15) and the rule trace shared with #19 ---


class ExplainItem(BaseModel):
    """One metric's formula, inputs and result (BP 7). Money-like inputs are 2-dp strings."""

    metric: str
    formula: str
    inputs: dict[str, Any]
    result: Any
    source: str = Field(description='Blueprint section, e.g. "BP 7.2".')


class RuleCheck(BaseModel):
    rule: str = Field(description='Rule id, "R1" to "R6" (BP 7.4 order).')
    risk_class: RiskClass = Field(serialization_alias="class")
    matched: bool


class RiskTrace(BaseModel):
    """BP 7.4 trace: the rules checked in order up to and including the one that fired."""

    risk_class: RiskClass = Field(serialization_alias="class")
    reason_code: str
    rule_fired: str = Field(description='Id of the first matching rule, e.g. "R2".')
    rules_checked: list[RuleCheck]


class ExplainOut(BaseModel):
    product_id: int
    sku: str
    warehouse_id: int
    warehouse_code: str
    snapshot: SnapshotMeta
    metrics: list[ExplainItem] = Field(description="BP 7.2 metrics, then risk_class (BP 7.4).")
    risk: RiskTrace


# --- recalculation (#16) ---


class RecalculateOut(BaseModel):
    snapshot_id: int
    data_as_of_date: date = Field(description="t0 of the new snapshot (ADR-012).")
    row_count: int
    risk_distribution: dict[str, int] = Field(description="Rows per class, all six classes.")
    duration_ms: int


# --- snapshot history (#17) ---


class SnapshotOut(BaseModel):
    """One snapshot. Its ``params_json`` is deliberately not exposed."""

    snapshot_id: int
    calculated_at: datetime
    data_as_of_date: date
    triggered_by: str
    row_count: int
    risk_distribution: dict[str, int] = Field(description="Rows per class, all six classes.")
