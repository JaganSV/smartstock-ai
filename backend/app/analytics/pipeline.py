"""Whole analytics pipeline: metrics -> risk classification -> flags (pure, no I/O)."""

import pandas as pd

from app.analytics.flags import is_dead_stock, is_high_demand, is_slow_moving
from app.analytics.metrics import compute_metrics
from app.analytics.params import AnalyticsParams
from app.analytics.risk import classify_risk
from app.analytics.types import KEY_COLS

# Input columns carried next to the metrics: risk rules need on_hand and review_period_days, the
# dead-stock flag needs units_by_day, and explanations show the rest as formula inputs.
CONTEXT_COLS = (
    "on_hand",
    "committed",
    "review_period_days",
    "service_level",
    "safety_stock_override",
    "lead_time_override_days",
    "supplier_lead_time_days",
    "supplier_moq",
    "case_pack",
    "units_by_day",
)


def run_analytics(inputs: pd.DataFrame, params: AnalyticsParams) -> pd.DataFrame:
    """``compute_metrics`` + context columns + ``risk_class``/``risk_reason_code`` + flags.

    ``inputs`` is a ``build_metric_inputs`` frame. Adds ``is_slow_moving``, ``is_dead_stock`` and
    the non-persisted ``is_high_demand``.
    """
    metrics = compute_metrics(inputs, params)
    context = inputs[[*KEY_COLS, *CONTEXT_COLS]]
    frame = metrics.merge(context, on=list(KEY_COLS), how="left", validate="1:1")
    frame = classify_risk(frame, params)
    frame["is_slow_moving"] = is_slow_moving(frame, params)
    frame["is_dead_stock"] = is_dead_stock(frame, params)
    frame["is_high_demand"] = is_high_demand(frame, params)
    return frame
