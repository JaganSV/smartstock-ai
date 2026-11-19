"""Per-function metric tests with hand-calculated expectations (BP 7.2 / 7.3).

Each table row is worked out by hand in a comment where the arithmetic is not obvious. The
property grid at the bottom runs 600 seeded random rows (3 seeds x 200) against the invariants
and against a scalar re-implementation of the formulas.
"""

import math
import warnings
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
import pytest

from app.analytics import metrics
from app.analytics.errors import AnalyticsInputError, UnsupportedServiceLevelError
from app.analytics.metrics import compute_metrics
from app.analytics.numeric import safe_ceil
from app.analytics.params import AnalyticsParams
from app.analytics.types import IDENTITY_COLS, METRIC_COLS
from tests.unit.analytics.helpers import T0, alternating, input_row, make_inputs, series_of, units

PARAMS = AnalyticsParams(t0=T0)
INT_COLUMNS = (
    "available",
    "incoming_in_lt",
    "lead_time_days",
    "safety_stock",
    "reorder_point",
    "inventory_position",
    "reorder_qty",
)


def day(offset: int) -> date:
    return T0 + timedelta(days=offset)


def close(actual: pd.Series, expected: list[float]) -> None:
    np.testing.assert_allclose(actual.to_numpy(dtype=float), expected, rtol=1e-12, equal_nan=True)


# --- ads ---


def test_ads_hand_calculated() -> None:
    s = series_of(
        units(5, 5),  # 5 every day
        units(2, 100),  # last 30 days = 2, earlier = 100
        units(0, 0),
        units(alternating(6, 14), 0),  # 15 x 6 + 15 x 14 = 300 over 30 days
    )
    close(metrics.ads(s, 30), [5.0, 2.0, 0.0, 10.0])
    # ADS90: (60 x 100 + 30 x 2) / 90 = 6060 / 90 ; (60 x 0 + 300) / 90
    close(metrics.ads(s, 90), [5.0, 6060 / 90, 0.0, 300 / 90])


def test_ads_only_uses_the_last_n_days_and_keeps_the_index() -> None:
    s = series_of(units(3, 1000))
    s.index = pd.Index([42])
    out = metrics.ads(s, 30)
    assert out.index.tolist() == [42]
    assert out.iloc[0] == 3.0  # the 1000s are outside the 30-day window


def test_ads_rejects_a_window_longer_than_the_series() -> None:
    with pytest.raises(AnalyticsInputError):
        metrics.ads(series_of(np.zeros(10)), 30)


def test_ads_and_demand_std_on_empty_input() -> None:
    empty = pd.Series([], dtype="object")
    assert metrics.ads(empty, 30).empty
    assert metrics.demand_std(empty).empty
    assert metrics.demand_trend(empty).empty


# --- demand_std ---


def test_demand_std_is_population_std() -> None:
    s = series_of(
        units(5, 5),  # constant -> 0
        units(alternating(6, 14), 0),  # mean 10, every day is 4 away -> std exactly 4
        units([0] * 29 + [30], 0),  # mean 1, variance (29 x 1 + 29^2) / 30 = 29 -> sqrt(29)
    )
    close(metrics.demand_std(s, 30), [0.0, 4.0, math.sqrt(29)])


def test_demand_std_uses_ddof_zero_not_ddof_one() -> None:
    s = series_of(units([0] * 29 + [30], 0))
    population, sample = math.sqrt(29), math.sqrt(30)  # 870/30 vs 870/29
    assert metrics.demand_std(s, 30).iloc[0] == pytest.approx(population)
    assert metrics.demand_std(s, 30).iloc[0] != pytest.approx(sample)


def test_demand_std_window_argument() -> None:
    s = series_of(units([0] * 28 + [0, 30], 7))
    assert metrics.demand_std(s, 2).iloc[0] == pytest.approx(15.0)  # values 0 and 30


# --- lead_time_days ---


def test_lead_time_override_beats_supplier_lead_time() -> None:
    df = pd.DataFrame(
        {
            "lead_time_override_days": pd.array([None, 3, None, 21], dtype="Int64"),
            "supplier_lead_time_days": [7, 14, 5, 5],
        },
        index=[10, 11, 12, 13],
    )
    out = metrics.lead_time_days(df)
    assert out.tolist() == [7, 3, 5, 21]
    assert out.index.tolist() == [10, 11, 12, 13]
    assert out.dtype == np.dtype("int64")


# --- available ---


def test_available_can_be_negative() -> None:
    df = pd.DataFrame({"on_hand": [120, 10, 0, 50], "committed": [20, 30, 0, 50]})
    assert metrics.available(df).tolist() == [100, -20, 0, 0]


# --- incoming_in_lead_time ---


def test_incoming_boundaries_around_t0_and_t0_plus_lead_time() -> None:
    df = pd.DataFrame(
        {
            "open_incoming": [
                [(day(7), 10), (day(8), 20)],  # arrival exactly t0 + L counted; t0 + L + 1 not
                [(day(0), 5), (day(1), 7)],  # arrival = t0 is already in on_hand: not counted
                [],
                [(day(2), 1), (day(14), 2), (day(15), 4), (day(-1), 100)],  # -1 and +15 excluded
                [(day(3), 6), (day(3), 4)],  # two orders on the same day both count
            ],
            "lead_time_days": [7, 7, 3, 14, 3],
        },
        index=[10, 11, 12, 13, 14],
    )
    out = metrics.incoming_in_lead_time(df, T0)
    assert out.tolist() == [10, 7, 0, 3, 10]
    assert out.index.tolist() == [10, 11, 12, 13, 14]
    assert out.dtype == np.dtype("int64")


# --- safety_stock ---


def test_safety_stock_hand_calculated_and_overrides() -> None:
    df = pd.DataFrame(
        {
            "safety_stock_override": pd.array([None, 0, 25, None, None, None], dtype="Int64"),
            "service_level": [0.95, 0.95, 0.99, 0.99, 0.90, 0.95],
            "demand_std_30": [4.0, 4.0, 9.0, 2.0, 0.0, 10.0],
            "lead_time_days": [9, 9, 9, 16, 7, 1],
        }
    )
    out = metrics.safety_stock(df, PARAMS)
    # 1.65 x 4 x sqrt(9) = 19.8 -> 20 | override 0 -> 0 | override 25 -> 25
    # 2.33 x 2 x sqrt(16) = 18.64 -> 19 | sigma 0 -> 0 | 1.65 x 10 x 1 = 16.5 -> 17
    assert out.tolist() == [20, 0, 25, 19, 0, 17]
    assert out.dtype == np.dtype("int64")


def test_safety_stock_override_skips_the_z_lookup() -> None:
    df = pd.DataFrame(
        {
            "safety_stock_override": pd.array([5], dtype="Int64"),
            "service_level": [0.97],  # not in the Z table
            "demand_std_30": [3.0],
            "lead_time_days": [4],
        }
    )
    assert metrics.safety_stock(df, PARAMS).tolist() == [5]
    df["safety_stock_override"] = pd.array([None], dtype="Int64")
    with pytest.raises(UnsupportedServiceLevelError):
        metrics.safety_stock(df, PARAMS)


def test_safety_stock_float_artefact_is_not_rounded_up() -> None:
    """z x sigma x sqrt(L) = (0.1 x 3) x 10 x 1 = 3.0000000000000004 must give 3, not 4."""
    params = AnalyticsParams(t0=T0, z_table={0.95: 0.1 * 3})
    assert math.ceil(0.1 * 3 * 10 * math.sqrt(1)) == 4  # the naive result
    df = pd.DataFrame(
        {
            "safety_stock_override": pd.array([None], dtype="Int64"),
            "service_level": [0.95],
            "demand_std_30": [10.0],
            "lead_time_days": [1],
        }
    )
    assert metrics.safety_stock(df, params).tolist() == [3]


# --- reorder_point ---


def test_reorder_point_hand_calculated() -> None:
    df = pd.DataFrame(
        {
            "ads_30": [10.0, 0.0, 4.2, 0.1 * 3, 10.0, 0.5],
            "lead_time_days": [9, 7, 7, 10, 9, 1],
            "safety_stock": [20, 0, 5, 2, 0, 0],
        }
    )
    out = metrics.reorder_point(df)
    # 10 x 9 = 90 (+20) | 0 | 4.2 x 7 = 29.4 -> 30 (+5) | (0.1 x 3) x 10 = 3.0000000000000004 -> 3
    # (+2) | 10 x 9 = 90 exactly (not 91) | 0.5 x 1 = 0.5 -> 1
    assert out.tolist() == [110, 0, 35, 5, 90, 1]
    assert out.dtype == np.dtype("int64")


# --- days_of_cover ---


def test_days_of_cover_hand_calculated_without_runtime_warnings() -> None:
    df = pd.DataFrame(
        {
            "available": [100, -20, 0, 50, -5, 7],
            "ads_30": [10.0, 5.0, 4.0, 0.0, 0.0, 2.0],
        }
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # a divide-by-zero RuntimeWarning would fail the test
        out = metrics.days_of_cover(df)
    # 100/10 | max(0,-20)/5 = 0 | 0/4 = 0 | no demand -> NaN | no demand -> NaN | 7/2
    close(out, [10.0, 0.0, 0.0, math.nan, math.nan, 3.5])


# --- inventory_position ---


def test_inventory_position() -> None:
    df = pd.DataFrame({"available": [100, -20, 0], "incoming_in_lt": [0, 50, 7]})
    assert metrics.inventory_position(df).tolist() == [100, 30, 7]


# --- reorder_quantity_raw / reorder_quantity ---

REORDER_TABLE = pd.DataFrame(
    {
        "ads_30": [10.0, 10.0, 10.0, 1.0, 2.0, 1.0, 3.3, 0.1 * 3, 5.0, 0.0],
        "lead_time_days": [9, 9, 9, 5, 6, 5, 7, 3, 10, 7],
        "review_period_days": [14, 14, 14, 5, 6, 5, 14, 7, 14, 14],
        "safety_stock": [20, 20, 20, 0, 0, 0, 4, 0, 10, 5],
        "inventory_position": [100, 400, 250, 0, 0, 0, 10, 0, -29, -3],
        "supplier_moq": [50, 50, 50, 50, 10, 48, 24, 1, 24, 24],
        "case_pack": [12, 12, 12, 12, 12, 12, 1, 1, 6, 12],
    }
)
# raw: 230+20-100 = 150 | 230+20-400 = -150 | 230+20-250 = 0 | 10 | 24 | 10 |
#      ceil(69.3)=70, 70+4-10 = 64 | ceil(3.0000000000000004)=3 -> 3 | 120+10+29 = 159 | 0+5+3 = 8
RAW = [150, -150, 0, 10, 24, 10, 64, 3, 159, 8]
# Q:   150 -> 13 packs of 12 = 156 | raw <= 0 -> 0 | 0 -> 0 | 10 < MOQ 50 -> 50 -> 5 packs = 60 |
#      24 (2 packs) | 10 < MOQ 48 -> 48 (4 packs) | 64 (pack 1) | 3 (pack 1) |
#      159 -> 27 packs of 6 = 162 | 8 < MOQ 24 -> 24 (2 packs)
QTY = [156, 0, 0, 60, 24, 48, 64, 3, 162, 24]


def test_reorder_quantity_raw_hand_calculated() -> None:
    out = metrics.reorder_quantity_raw(REORDER_TABLE)
    assert out.tolist() == RAW
    assert out.dtype == np.dtype("int64")


def test_reorder_quantity_hand_calculated() -> None:
    out = metrics.reorder_quantity(REORDER_TABLE)
    assert out.tolist() == QTY
    assert out.dtype == np.dtype("int64")


def test_reorder_quantity_is_zero_when_raw_is_not_positive() -> None:
    raw = metrics.reorder_quantity_raw(REORDER_TABLE)
    qty = metrics.reorder_quantity(REORDER_TABLE)
    assert (qty[raw <= 0] == 0).all()
    assert (qty[raw > 0] > 0).all()


# --- demand_trend ---


def test_demand_trend_hand_calculated() -> None:
    s = series_of(
        [10] * 76 + [18] * 14,  # 18 / 10 - 1 = +0.8 (a +80% spike)
        [10] * 90,  # flat -> 0
        [10] * 76 + [0] * 14,  # -1.0
        [0] * 76 + [5] * 14,  # prior mean 0 -> NaN
        [0] * 90,  # both zero -> NaN
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = metrics.demand_trend(s)
    close(out, [0.8, 0.0, -1.0, math.nan, math.nan])


def test_demand_trend_custom_windows_and_longer_series() -> None:
    assert metrics.demand_trend(series_of([4] * 23 + [8] * 7), 7, 23).iloc[0] == pytest.approx(1.0)
    longer = series_of([999] * 10 + [10] * 76 + [18] * 14)  # only the last 90 days count
    assert metrics.demand_trend(longer).iloc[0] == pytest.approx(0.8)


def test_demand_trend_rejects_a_short_series() -> None:
    with pytest.raises(AnalyticsInputError):
        metrics.demand_trend(series_of([1] * 30))


# --- inventory_value ---


def test_inventory_value_is_decimal_two_dp_half_up() -> None:
    df = pd.DataFrame(
        {
            "on_hand": [100, 3, 0, 1, 3],
            "unit_cost": [
                Decimal("12.345"),  # 1234.500 -> 1234.50
                Decimal("0.335"),  # 1.005 -> 1.01 (a float would give 1.00)
                Decimal("99.99"),  # 0 -> 0.00
                Decimal("0.005"),  # -> 0.01
                Decimal("19.99"),  # 59.97
            ],
        }
    )
    out = metrics.inventory_value(df)
    assert [str(v) for v in out] == ["1234.50", "1.01", "0.00", "0.01", "59.97"]
    assert all(isinstance(v, Decimal) for v in out)


# --- compute_metrics end to end ---


def _table() -> pd.DataFrame:
    return make_inputs(
        input_row(),  # 0: normal, constant demand 5
        input_row(units_by_day=units(0, 0), on_hand=50),  # 1: zero demand
        input_row(on_hand=10, committed=30),  # 2: negative available
        input_row(lead_time_override_days=3, safety_stock_override=25),  # 3: overrides
        input_row(open_incoming=[(day(7), 40), (day(8), 99)]),  # 4: incoming boundary
    )


def test_compute_metrics_hand_calculated_rows() -> None:
    out = compute_metrics(_table(), PARAMS)
    # row 0: ADS 5, sigma 0 -> SS 0, L 7: ROP 35, DoC 20, IP 100, Q = ceil(5 x 21) - 100 = 5
    # row 1: ADS 0 -> ROP 0, DoC NaN, trend NaN, Q = 0 + 0 - 50 < 0 -> 0
    # row 2: available -20 -> DoC 0, IP -20, Q = 105 + 20 = 125, stockout day 0
    # row 3: L 3, SS 25 -> ROP = 15 + 25 = 40, Q = ceil(5 x 17) + 25 - 100 = 10
    # row 4: only the order at t0 + 7 counts: incoming 40, IP 140, Q = 105 - 140 < 0 -> 0
    expected = {
        "available": [100, 50, -20, 100, 100],
        "incoming_in_lt": [0, 0, 0, 0, 40],
        "lead_time_days": [7, 7, 7, 3, 7],
        "safety_stock": [0, 0, 0, 25, 0],
        "reorder_point": [35, 0, 35, 40, 35],
        "inventory_position": [100, 50, -20, 100, 140],
        "reorder_qty": [5, 0, 125, 10, 0],
    }
    for column, values in expected.items():
        assert out[column].tolist() == values, column
    close(out["ads_30"], [5.0, 0.0, 5.0, 5.0, 5.0])
    close(out["ads_90"], [5.0, 0.0, 5.0, 5.0, 5.0])
    close(out["demand_std_30"], [0.0] * 5)
    close(out["days_of_cover"], [20.0, math.nan, 0.0, 20.0, 20.0])
    close(out["demand_trend"], [0.0, math.nan, 0.0, 0.0, 0.0])
    assert [str(v) for v in out["inventory_value"]] == [
        "10000.00",
        "5000.00",
        "1000.00",
        "10000.00",
        "10000.00",
    ]
    assert out["projected_stockout_day"].isna().tolist() == [True, True, False, True, True]
    assert out["projected_stockout_day"].iloc[2] == 0


def test_compute_metrics_output_schema_and_dtypes() -> None:
    out = compute_metrics(_table(), PARAMS)
    assert list(out.columns) == [*IDENTITY_COLS, *METRIC_COLS]
    assert out.index.tolist() == list(range(len(out)))
    for column in INT_COLUMNS:
        assert out[column].dtype == np.dtype("int64"), column
    assert str(out["projected_stockout_day"].dtype) == "Int64"
    assert out["ads_30"].dtype == np.dtype("float64")


def test_compute_metrics_does_not_mutate_its_input_and_is_deterministic() -> None:
    inputs = _table()
    columns_before = list(inputs.columns)
    first = compute_metrics(inputs, PARAMS)
    second = compute_metrics(inputs, PARAMS)
    assert list(inputs.columns) == columns_before
    pd.testing.assert_frame_equal(first, second)


def test_compute_metrics_on_an_empty_frame() -> None:
    out = compute_metrics(make_inputs(), PARAMS)
    assert out.empty
    assert list(out.columns) == [*IDENTITY_COLS, *METRIC_COLS]


def test_compute_metrics_emits_no_numpy_warnings_with_zero_demand() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        compute_metrics(_table(), PARAMS)


def test_compute_metrics_propagates_an_unsupported_service_level() -> None:
    with pytest.raises(UnsupportedServiceLevelError):
        compute_metrics(make_inputs(input_row(service_level=0.97)), PARAMS)


# --- property grid: 3 seeds x 200 random rows = 600 cases ---


def _random_rows(seed: int, count: int) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for _ in range(count):
        lam = float(rng.choice([0.0, 0.3, 1.5, 6.0, 25.0, 60.0]))
        # open_incoming contract: only OPEN orders arriving after t0 (build_metric_inputs filters)
        orders = sorted(
            (day(int(rng.integers(1, 40))), int(rng.integers(1, 500)))
            for _ in range(int(rng.integers(0, 4)))
        )
        pick = float(rng.random())
        ss_override = None if pick < 0.6 else (0 if pick < 0.8 else int(rng.integers(1, 80)))
        lead_override = None if rng.random() < 0.8 else int(rng.integers(1, 30))
        rows.append(
            input_row(
                on_hand=int(rng.integers(0, 2000)),
                committed=int(rng.integers(0, 2500)),  # can exceed on_hand: negative available
                units_by_day=rng.poisson(lam, size=90).astype(np.int64),
                service_level=float(rng.choice([0.90, 0.95, 0.975, 0.99])),
                review_period_days=int(rng.choice([7, 14, 21])),
                supplier_lead_time_days=int(rng.choice([5, 7, 10, 14, 21])),
                safety_stock_override=ss_override,
                lead_time_override_days=lead_override,
                supplier_moq=int(rng.choice([1, 24, 36, 50, 100, 200])),
                case_pack=int(rng.choice([1, 6, 12, 24])),
                open_incoming=orders,
            )
        )
    return rows


def _oracle(row: dict[str, Any]) -> dict[str, int]:
    """Scalar re-implementation of BP 7.2 for one row (independent of the vectorised code)."""
    u = np.asarray(row["units_by_day"])
    ads30 = float(u[-30:].sum()) / 30
    sigma = float(np.std(u[-30:]))
    lead = row["lead_time_override_days"] or row["supplier_lead_time_days"]
    z = PARAMS.z_for(row["service_level"])
    override = row["safety_stock_override"]
    ss = override if override is not None else safe_ceil(z * sigma * math.sqrt(lead))
    avail = row["on_hand"] - row["committed"]
    incoming = sum(q for arrival, q in row["open_incoming"] if T0 < arrival <= day(lead))
    ip = avail + incoming
    raw = safe_ceil(ads30 * (lead + row["review_period_days"])) + ss - ip
    pack, moq = row["case_pack"], row["supplier_moq"]
    qty = 0 if raw <= 0 else pack * math.ceil(max(raw, moq) / pack)
    return {
        "available": avail,
        "incoming_in_lt": incoming,
        "lead_time_days": lead,
        "safety_stock": ss,
        "reorder_point": safe_ceil(ads30 * lead) + ss,
        "inventory_position": ip,
        "reorder_qty": qty,
    }


@pytest.fixture(scope="module", params=[11, 22, 33])
def grid(request: pytest.FixtureRequest) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    rows = _random_rows(request.param, 200)
    return rows, compute_metrics(make_inputs(*rows), PARAMS)


def test_property_grid_matches_the_scalar_oracle(
    grid: tuple[list[dict[str, Any]], pd.DataFrame],
) -> None:
    rows, out = grid
    expected = pd.DataFrame([_oracle(r) for r in rows])
    for column in expected.columns:
        assert out[column].tolist() == expected[column].tolist(), column


def test_property_reorder_point_is_at_least_safety_stock(
    grid: tuple[list[dict[str, Any]], pd.DataFrame],
) -> None:
    _, out = grid
    assert (out["reorder_point"] >= out["safety_stock"]).all()


def test_property_safety_stock_is_non_negative(
    grid: tuple[list[dict[str, Any]], pd.DataFrame],
) -> None:
    _, out = grid
    assert (out["safety_stock"] >= 0).all()


def test_property_reorder_qty_is_a_pack_multiple_and_respects_moq(
    grid: tuple[list[dict[str, Any]], pd.DataFrame],
) -> None:
    rows, out = grid
    pack = np.array([r["case_pack"] for r in rows])
    moq = np.array([r["supplier_moq"] for r in rows])
    qty = out["reorder_qty"].to_numpy()
    assert (qty % pack == 0).all()
    assert ((qty == 0) | (qty >= moq)).all()
    assert (qty >= 0).all()


def test_property_positive_reorder_qty_means_position_is_below_target(
    grid: tuple[list[dict[str, Any]], pd.DataFrame],
) -> None:
    rows, out = grid
    for row, (_, metric) in zip(rows, out.iterrows(), strict=True):
        lead = metric["lead_time_days"]
        target = safe_ceil(metric["ads_30"] * (lead + row["review_period_days"]))
        if metric["reorder_qty"] > 0:
            assert metric["inventory_position"] < target + metric["safety_stock"]


def test_property_days_of_cover_is_non_negative_or_nan(
    grid: tuple[list[dict[str, Any]], pd.DataFrame],
) -> None:
    _, out = grid
    doc = out["days_of_cover"]
    assert ((doc >= 0) | doc.isna()).all()
    assert (doc.isna() == (out["ads_30"] == 0)).all()


def test_property_integer_outputs_are_integer_typed(
    grid: tuple[list[dict[str, Any]], pd.DataFrame],
) -> None:
    _, out = grid
    for column in INT_COLUMNS:
        assert out[column].dtype == np.dtype("int64"), column
        assert isinstance(out[column].iloc[0], int | np.integer), column


def test_property_projected_stockout_day_is_within_lead_time_and_needs_demand(
    grid: tuple[list[dict[str, Any]], pd.DataFrame],
) -> None:
    _, out = grid
    day_ = out["projected_stockout_day"]
    assert day_[out["ads_30"] == 0].isna().all()
    known = day_.notna()
    assert (day_[known] >= 0).all()
    assert (day_[known].astype(int) <= out.loc[known, "lead_time_days"]).all()
    assert (day_[known & (out["available"] <= 0)] == 0).all()


def test_property_grid_covers_the_interesting_regimes(
    grid: tuple[list[dict[str, Any]], pd.DataFrame],
) -> None:
    """Guards the grid itself: it must actually contain each edge regime."""
    _, out = grid
    assert (out["available"] < 0).any()
    assert (out["ads_30"] == 0).any()
    assert (out["reorder_qty"] == 0).any() and (out["reorder_qty"] > 0).any()
    assert (out["incoming_in_lt"] > 0).any()
    assert out["projected_stockout_day"].notna().any()
