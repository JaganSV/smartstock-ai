"""Risk classification (BP 7.4): six rules, evaluated in order, first match wins.

1. STOCKOUT   available <= 0 and ADS30 > 0                         R1_NO_AVAILABLE_STOCK
2. CRITICAL   ADS30 > 0 and projected_stockout_day is not null      R2_STOCKOUT_BEFORE_REPLENISHMENT
3. HIGH       inventory_position <= reorder_point                   R3_BELOW_REORDER_POINT
4. MEDIUM     days_of_cover not null and < L + R                    R4_COVER_BELOW_LEAD_PLUS_REVIEW
5. OVERSTOCK  days_of_cover > overstock_cover_days,
              or (ADS30 = 0 and on_hand > 0)                        R5_EXCESS_COVER
6. LOW        otherwise                                             R6_HEALTHY

R is the row's own policy ``review_period_days`` (a column of the input frame). Rule 3 applies even
when ADS30 = 0 (then ROP = SS). Thresholds are compared on the unrounded metric values.
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd

from app.analytics.numeric import float_array
from app.analytics.params import AnalyticsParams
from app.models.enums import RiskClass


@dataclass(frozen=True)
class RiskRule:
    order: int
    risk_class: RiskClass
    code: str
    condition: str


RISK_RULES: tuple[RiskRule, ...] = (
    RiskRule(1, RiskClass.STOCKOUT, "R1_NO_AVAILABLE_STOCK", "available <= 0 and ADS30 > 0"),
    RiskRule(
        2,
        RiskClass.CRITICAL,
        "R2_STOCKOUT_BEFORE_REPLENISHMENT",
        "ADS30 > 0 and projected_stockout_day is not null (stockout within L)",
    ),
    RiskRule(3, RiskClass.HIGH, "R3_BELOW_REORDER_POINT", "inventory_position <= reorder_point"),
    RiskRule(
        4,
        RiskClass.MEDIUM,
        "R4_COVER_BELOW_LEAD_PLUS_REVIEW",
        "days_of_cover is not null and days_of_cover < lead_time_days + review_period_days",
    ),
    RiskRule(
        5,
        RiskClass.OVERSTOCK,
        "R5_EXCESS_COVER",
        "days_of_cover > overstock_cover_days or (ADS30 = 0 and on_hand > 0)",
    ),
    RiskRule(6, RiskClass.LOW, "R6_HEALTHY", "otherwise"),
)

REQUIRED_COLUMNS = (
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


def rule_masks(df: pd.DataFrame, params: AnalyticsParams) -> list[npt.NDArray[np.bool_]]:
    """Boolean mask per rule R1..R6 (R6 is always true), each evaluated independently."""
    available = float_array(df, "available")
    ads30 = float_array(df, "ads_30")
    stockout_day = float_array(df, "projected_stockout_day")
    position = float_array(df, "inventory_position")
    rop = float_array(df, "reorder_point")
    cover = float_array(df, "days_of_cover")
    horizon = float_array(df, "lead_time_days") + float_array(df, "review_period_days")
    on_hand = float_array(df, "on_hand")

    has_demand = ads30 > 0
    has_cover = ~np.isnan(cover)
    return [
        (available <= 0) & has_demand,
        has_demand & ~np.isnan(stockout_day),
        position <= rop,
        has_cover & (cover < horizon),
        (has_cover & (cover > params.overstock_cover_days)) | ((ads30 == 0) & (on_hand > 0)),
        np.ones(len(df), dtype=np.bool_),
    ]


def classify_risk(metrics: pd.DataFrame, params: AnalyticsParams) -> pd.DataFrame:
    """Copy of ``metrics`` plus ``risk_class`` and ``risk_reason_code`` (numpy.select, vectorised).

    Needs the columns in ``REQUIRED_COLUMNS``. Rules are evaluated in BP 7.4 order; the first
    match wins.
    """
    masks = rule_masks(metrics, params)
    result = metrics.copy()
    result["risk_class"] = np.select(
        masks[:-1], [rule.risk_class.value for rule in RISK_RULES[:-1]], RISK_RULES[-1].risk_class
    ).astype(str)
    result["risk_reason_code"] = np.select(
        masks[:-1], [rule.code for rule in RISK_RULES[:-1]], RISK_RULES[-1].code
    ).astype(str)
    return result
