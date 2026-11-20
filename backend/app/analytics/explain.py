"""Metric explanation payloads (FR-B6).

``explain_row`` turns one analytics row into a JSON-safe, per-metric trace::

    {"metric": ..., "formula": "<BP 7 formula>", "inputs": {name: value}, "result": value,
     "source": "BP 7.x"}

The values are the row's own values, so the payload is exactly consistent with the stored
numbers. Money-like Decimals are strings with 2 dp, the four 4-dp database columns are floats
rounded to 4 dp, NaN / <NA> / None are null. P3 serves this and P6 feeds it to Granite.
"""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from app.analytics.numeric import money, round_decimal, safe_ceil
from app.analytics.params import AnalyticsParams
from app.analytics.risk import REQUIRED_COLUMNS, RISK_RULES, rule_masks

FOUR_DP = frozenset({"ads_30", "ads_90", "demand_std_30", "days_of_cover"})
EXPLAINED_METRICS = (
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


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def json_safe(value: Any) -> Any:
    """Plain JSON value: Decimal -> str (2 dp), NaN / <NA> / None -> None, numpy -> Python."""
    if _is_null(value):
        return None
    if isinstance(value, Decimal):
        return str(money(value))
    if isinstance(value, bool | np.bool_):
        return bool(value)
    if isinstance(value, np.integer | int):
        return int(value)
    if isinstance(value, np.floating | float):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _value(name: str, raw: Any) -> Any:
    """Row value as it appears in the payload (4-dp metrics are rounded like the DB column)."""
    if _is_null(raw):
        return None
    if name in FOUR_DP:
        return float(round_decimal(raw, 4))
    return json_safe(raw)


def _entry(
    row: Mapping[str, Any],
    metric: str,
    formula: str,
    input_names: tuple[str, ...],
    source: str,
    extra_inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    inputs = {name: _value(name, row.get(name)) for name in input_names}
    inputs.update({k: json_safe(v) for k, v in (extra_inputs or {}).items()})
    return {
        "metric": metric,
        "formula": formula,
        "inputs": inputs,
        "result": _value(metric, row[metric]),
        "source": source,
    }


def _risk_trace(row: Mapping[str, Any], params: AnalyticsParams) -> dict[str, Any]:
    frame = pd.DataFrame([{name: row.get(name) for name in REQUIRED_COLUMNS}])
    masks = rule_masks(frame, params)
    fired = next(i for i, mask in enumerate(masks) if bool(mask[0]))
    checked = [
        {
            "order": rule.order,
            "risk_class": rule.risk_class.value,
            "reason_code": rule.code,
            "condition": rule.condition,
            "matched": bool(masks[i][0]),
        }
        for i, rule in enumerate(RISK_RULES[: fired + 1])
    ]
    return {
        "fired_rule": checked[-1],
        "rules_checked": checked,
        "reason_code": RISK_RULES[fired].code,
    }


def explain_row(
    metrics_row: Mapping[str, Any] | pd.Series, params: AnalyticsParams
) -> dict[str, Any]:
    """Explanation payload for one row of the ``run_analytics`` frame (or a stored equivalent).

    Returns ``{"sku", "warehouse_code", "t0", "metrics": [<12 entries, EXPLAINED_METRICS order>]}``.
    """
    row: dict[str, Any] = dict(metrics_row)
    has_override = not _is_null(row.get("safety_stock_override"))
    z_value = None if has_override else params.z_for(row["service_level"])
    review = int(row["review_period_days"])
    lead = int(row["lead_time_days"])
    q_raw = (
        safe_ceil(float(row["ads_30"]) * (lead + review))
        + int(row["safety_stock"])
        - int(row["inventory_position"])
    )

    metrics = [
        _entry(
            row, "available", "available = on_hand - committed", ("on_hand", "committed"), "BP 7.2"
        ),
        _entry(
            row,
            "incoming_in_lt",
            "incoming_in_LT = sum of OPEN incoming quantities with t0 < arrival <= t0 + L",
            ("lead_time_days",),
            "BP 7.2",
            {"t0": params.t0},
        ),
        _entry(
            row,
            "ads_30",
            "ADS30 = (units sold in the last 30 days) / 30",
            (),
            "BP 7.2",
            {"window_days": params.short_window},
        ),
        _entry(
            row,
            "ads_90",
            "ADS90 = (units sold in the last 90 days) / 90",
            (),
            "BP 7.2",
            {"window_days": params.long_window},
        ),
        _entry(
            row,
            "demand_std_30",
            "sigma_d = population standard deviation (ddof = 0) of the daily units, last 30 days",
            (),
            "BP 7.2",
            {"window_days": params.short_window},
        ),
        _entry(
            row,
            "lead_time_days",
            "L = lead_time_override_days if set, else the supplier default_lead_time_days",
            ("lead_time_override_days", "supplier_lead_time_days"),
            "BP 7.2",
        ),
        _entry(
            row,
            "safety_stock",
            "SS = safety_stock_override if set, else ceil(Z(service_level) x sigma_d x sqrt(L))",
            ("safety_stock_override", "service_level", "demand_std_30", "lead_time_days"),
            "BP 7.2",
            {"z": z_value},
        ),
        _entry(
            row,
            "reorder_point",
            "ROP = ceil(ADS30 x L) + SS",
            ("ads_30", "lead_time_days", "safety_stock"),
            "BP 7.2",
        ),
        _entry(
            row,
            "days_of_cover",
            "DoC = max(0, available) / ADS30 (null when ADS30 = 0)",
            ("available", "ads_30"),
            "BP 7.2",
        ),
        _entry(
            row,
            "inventory_position",
            "IP = available + incoming_in_LT",
            ("available", "incoming_in_lt"),
            "BP 7.2",
        ),
        _entry(
            row,
            "reorder_qty",
            "Q_raw = ceil(ADS30 x (L + R)) + SS - IP; "
            "Q = 0 if Q_raw <= 0, else case_pack x ceil(max(Q_raw, MOQ) / case_pack)",
            (
                "ads_30",
                "lead_time_days",
                "review_period_days",
                "safety_stock",
                "inventory_position",
                "supplier_moq",
                "case_pack",
            ),
            "BP 7.2",
            {"q_raw": q_raw},
        ),
    ]
    risk = {
        "metric": "risk_class",
        "formula": "first matching rule of BP 7.4, evaluated in order R1..R6",
        "inputs": {
            name: _value(name, row.get(name))
            for name in (
                "available",
                "ads_30",
                "projected_stockout_day",
                "inventory_position",
                "reorder_point",
                "days_of_cover",
                "lead_time_days",
                "review_period_days",
                "on_hand",
            )
        }
        | {"overstock_cover_days": params.overstock_cover_days},
        "result": json_safe(row["risk_class"]),
        "source": "BP 7.4",
        **_risk_trace(row, params),
    }
    metrics.append(risk)
    return {
        "sku": json_safe(row.get("sku")),
        "warehouse_code": json_safe(row.get("warehouse_code")),
        "t0": params.t0.isoformat(),
        "metrics": metrics,
    }
