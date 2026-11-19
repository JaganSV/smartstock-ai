"""BP 7.6 worked example, reproduced exactly.

SKU-EX: on_hand 120, committed 20, ADS30 = 10, sigma_d = 4, L = 9, Z(0.95) = 1.65, R = 14,
no incoming, MOQ 50, case pack 12.

Construction of the demand series: the last 30 days alternate 6, 14, 6, 14, ... (15 x 6 and
15 x 14). The sum is 15 x 6 + 15 x 14 = 300, so ADS30 = 300 / 30 = 10 exactly. Every day is
exactly 4 away from the mean 10, so the population variance is 16 and sigma_d = 4 exactly. The
60 earlier days are a constant 10 (they only affect ADS90 and the trend, which BP 7.6 does not
use).
"""

import numpy as np
import pandas as pd

from app.analytics.metrics import compute_metrics
from app.analytics.params import AnalyticsParams
from app.analytics.projection import projected_stock
from tests.unit.analytics.helpers import T0, alternating, input_row, make_inputs, units


def _example() -> dict[str, object]:
    inputs = make_inputs(
        input_row(
            sku="SKU-EX",
            on_hand=120,
            committed=20,
            units_by_day=units(alternating(6, 14), earlier=10),
            supplier_lead_time_days=9,
            service_level=0.95,
            review_period_days=14,
            supplier_moq=50,
            case_pack=12,
            open_incoming=[],
        )
    )
    out = compute_metrics(inputs, AnalyticsParams(t0=T0))
    return out.iloc[0].to_dict()


def test_series_has_exactly_ads30_10_and_sigma_4() -> None:
    row = _example()
    assert row["ads_30"] == 10.0
    assert row["demand_std_30"] == 4.0
    assert row["ads_90"] == 10.0


def test_worked_example_reproduces_bp_7_6() -> None:
    row = _example()
    assert row["available"] == 100  # 120 - 20
    assert row["lead_time_days"] == 9
    assert row["incoming_in_lt"] == 0
    assert row["safety_stock"] == 20  # ceil(1.65 x 4 x sqrt(9)) = ceil(19.8)
    assert row["reorder_point"] == 110  # ceil(10 x 9) + 20
    assert row["days_of_cover"] == 10.0  # 100 / 10
    assert row["inventory_position"] == 100  # 100 + 0
    assert row["reorder_qty"] == 156  # Q_raw = ceil(10 x 23) + 20 - 100 = 150 -> 13 packs of 12
    assert row["demand_trend"] == 0.0
    assert str(row["inventory_value"]) == "12000.00"  # 120 x 100.00


def test_worked_example_intermediate_q_raw_is_150() -> None:
    """Q_raw = ceil(ADS30 x (L + R)) + SS - IP = 230 + 20 - 100 = 150 (> MOQ 50); 13 x 12 = 156."""
    from app.analytics.metrics import reorder_quantity_raw

    inputs = make_inputs(
        input_row(
            on_hand=120,
            committed=20,
            units_by_day=units(alternating(6, 14), earlier=10),
            supplier_lead_time_days=9,
            supplier_moq=50,
            case_pack=12,
        )
    )
    frame = inputs.assign(
        ads_30=10.0,
        lead_time_days=9,
        safety_stock=20,
        inventory_position=100,
    )
    assert reorder_quantity_raw(frame).tolist() == [150]


def test_worked_example_has_no_stockout_within_lead_time() -> None:
    row = _example()
    assert pd.isna(row["projected_stockout_day"])  # no stockout day within L = 9
    # stock reaches 0 on day 10, which is after L
    projection = projected_stock(100, 10.0, [], T0, 12)
    assert projection[9] == 10
    assert projection[10] == 0
    assert int(np.argmax(np.array(projection) <= 0)) == 10
