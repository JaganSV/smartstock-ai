"""Seed generator unit tests (pure generation, no database)."""

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

import pytest

from data.seed.catalog import CASE_PACKS, SUPPLIERS, WAREHOUSES
from data.seed.generator import DEFAULT_AS_OF, DEFAULT_SEED, build_dataset
from data.seed.report import (
    Dataset,
    all_passed,
    canonical_rows,
    checksums,
    min_counts,
    render_markdown,
    run_checks,
)
from data.seed.scenarios import Scenario
from data.seed.stock import POLICY_OVERRIDES

T0 = DEFAULT_AS_OF
SUPPLIER_LEAD = {s.code: s.lead_time_days for s in SUPPLIERS}
SUPPLIER_MOQ = {s.code: s.min_order_qty for s in SUPPLIERS}


@pytest.fixture(scope="module")
def ds() -> Dataset:
    return build_dataset(DEFAULT_SEED, T0)


def test_same_seed_gives_identical_overall_checksum(ds: Dataset) -> None:
    again = build_dataset(DEFAULT_SEED, T0)
    assert checksums(canonical_rows(again))[1] == checksums(canonical_rows(ds))[1]


def test_different_seed_gives_different_checksum(ds: Dataset) -> None:
    other = build_dataset(43, T0)
    assert checksums(canonical_rows(other))[1] != checksums(canonical_rows(ds))[1]


def test_exact_row_counts(ds: Dataset) -> None:
    counts = {name: len(rows) for name, rows in canonical_rows(ds).items()}
    assert counts == {
        "categories": 5,
        "incoming_stock": 113,  # deterministic for seed 42 with the pinned NumPy
        "inventory_levels": 150,
        "inventory_policies": 150,
        "products": 50,
        "sales_daily": 13_500,
        "suppliers": 5,
        "warehouses": 3,
    }


def test_category_and_supplier_distribution_is_ten_each(ds: Dataset) -> None:
    assert set(Counter(p.category_code for p in ds.products).values()) == {10}
    assert set(Counter(p.supplier_code for p in ds.products).values()) == {10}
    assert len(Counter(p.category_code for p in ds.products)) == 5
    assert len(Counter(p.supplier_code for p in ds.products)) == 5


def test_every_scenario_passes_at_its_target_warehouse(ds: Dataset) -> None:
    checks = run_checks(ds)
    assert len(checks) == 150
    assert [c for c in checks if not c.passed] == []
    assert all(m.passed for m in min_counts(checks))
    assert all_passed(checks)
    assert {c.scenario for c in checks} == set(Scenario)


def test_scenario_sku_ranges_match_the_spec(ds: Dataset) -> None:
    by_scenario: dict[Scenario, set[str]] = {}
    for c in run_checks(ds):
        if c.scenario is not Scenario.HEALTHY:
            by_scenario.setdefault(c.scenario, set()).add(c.sku)
    assert {k: len(v) for k, v in by_scenario.items()} == {
        Scenario.STOCKOUT: 3,
        Scenario.CRITICAL: 5,
        Scenario.HIGH_DEMAND: 4,
        Scenario.OVERSTOCK: 5,
        Scenario.SLOW_MOVING: 3,
        Scenario.DEAD_STOCK: 3,
        Scenario.COVERED_BY_INCOMING: 3,
        Scenario.COMMITTED_MASKING: 3,
    }


@pytest.mark.parametrize("seed", [1, 7, 43, 100])
def test_scenarios_pass_for_other_seeds(seed: int) -> None:
    """Deterministic fitting means coverage does not depend on a lucky seed."""
    assert all_passed(run_checks(build_dataset(seed, T0)))


def test_sales_window_is_exactly_90_days_ending_at_t0(ds: Dataset) -> None:
    days = sorted({row[2] for row in canonical_rows(ds)["sales_daily"]})
    assert days[0] == "2026-07-03"
    assert days[-1] == "2026-09-30"
    assert len(days) == 90
    assert ds.demand.days[0] == date(2026, 7, 3)
    assert ds.demand.days[-1] == T0


def test_sales_units_and_revenue(ds: Dataset) -> None:
    assert int(ds.demand.units.min()) >= 0
    price = {p.sku: p.unit_price for p in ds.products}
    for sku, _wh, _day, units, revenue in canonical_rows(ds)["sales_daily"]:
        assert Decimal(revenue) == (Decimal(units) * price[sku]).quantize(Decimal("0.01"))


def test_sales_rows_cover_every_product_warehouse_day(ds: Dataset) -> None:
    keys = {(r[0], r[1], r[2]) for r in canonical_rows(ds)["sales_daily"]}
    assert len(keys) == 50 * 3 * 90
    assert int((ds.demand.units == 0).sum()) > 0  # zero-unit days are stored as rows too


def test_saturday_demand_exceeds_tuesday(ds: Dataset) -> None:
    saturday = [i for i, d in enumerate(ds.demand.days) if d.weekday() == 5]
    tuesday = [i for i, d in enumerate(ds.demand.days) if d.weekday() == 1]
    network = ds.demand.units.sum(axis=(0, 1))  # units per day, whole network
    assert network[saturday].mean() > network[tuesday].mean()


def test_incoming_quantities_respect_case_pack_and_moq(ds: Dataset) -> None:
    case_pack = {p.sku: p.case_pack for p in ds.products}
    assert {p.case_pack for p in ds.products} <= set(CASE_PACKS)
    for order in ds.stock.incoming:
        assert order.quantity % case_pack[order.sku] == 0
        assert order.quantity >= SUPPLIER_MOQ[order.supplier_code]
        assert order.expected_arrival_date >= order.order_date


def test_incoming_status_mix_and_dates(ds: Dataset) -> None:
    by_status = Counter(o.status for o in ds.stock.incoming)
    assert by_status["CANCELLED"] == 4
    assert by_status["OPEN"] == 3 + 10
    received = [o for o in ds.stock.incoming if o.status == "RECEIVED"]
    per_product = Counter(o.sku for o in received)
    assert set(per_product) == {p.sku for p in ds.products}
    assert all(1 <= n <= 3 for n in per_product.values())
    assert all(ds.demand.days[0] <= o.expected_arrival_date <= T0 for o in received)
    assert all(o.order_date <= T0 for o in ds.stock.incoming)
    assert all(o.expected_arrival_date > T0 for o in ds.stock.incoming if o.status == "OPEN")


def test_healthy_open_orders_arrive_after_t0_plus_lead_time(ds: Dataset) -> None:
    covered = {"SKU-024", "SKU-025", "SKU-026"}
    healthy_open = [o for o in ds.stock.incoming if o.status == "OPEN" and o.sku not in covered]
    assert len(healthy_open) == 10
    assert len({(o.sku, o.warehouse_code) for o in healthy_open}) == 10
    for order in healthy_open:
        assert order.expected_arrival_date > T0 + timedelta(days=SUPPLIER_LEAD[order.supplier_code])


def test_policies_and_overrides(ds: Dataset) -> None:
    policies = ds.stock.policies
    assert len(policies) == 150
    assert {p.review_period_days for p in policies} == {14}
    with_overrides = {
        (p.sku, p.warehouse_code): (p.safety_stock_override, p.lead_time_override_days)
        for p in policies
        if p.safety_stock_override is not None or p.lead_time_override_days is not None
    }
    assert with_overrides == {
        ("SKU-031", "WH-MUM"): (25, None),
        ("SKU-032", "WH-BLR"): (0, None),
        ("SKU-033", "WH-DEL"): (None, 3),
    }
    assert len(POLICY_OVERRIDES) == 3


def test_service_level_is_99_for_the_ten_highest_lambda_products(ds: Dataset) -> None:
    ranked = sorted(range(50), key=lambda i: (-float(ds.demand.lam[i]), i))
    expected = {ds.products[i].sku for i in ranked[:10]}
    high = {p.sku for p in ds.stock.policies if p.service_level == Decimal("0.990")}
    assert high == expected
    assert {p.service_level for p in ds.stock.policies} == {Decimal("0.990"), Decimal("0.950")}
    assert Counter(p.sku for p in ds.stock.policies if p.service_level == Decimal("0.990")) == {
        sku: 3 for sku in expected
    }


def test_master_data_is_fictional_and_in_bounds(ds: Dataset) -> None:
    assert [w.code for w in WAREHOUSES] == ["WH-MUM", "WH-BLR", "WH-DEL"]
    assert sum(w.demand_share for w in WAREHOUSES) == pytest.approx(1.0)
    assert all(s.contact_email.endswith("@example.com") for s in SUPPLIERS)
    assert all("(fictional)" in s.name for s in SUPPLIERS)
    bands = {
        "ELEC": (150, 2500),
        "HOME": (200, 3000),
        "PCARE": (80, 900),
        "SPORT": (250, 4000),
        "STAT": (20, 600),
    }
    for p in ds.products:
        low, high = bands[p.category_code]
        assert low <= p.unit_cost <= high
        ratio = p.unit_price / p.unit_cost
        assert Decimal("1.24") <= ratio <= Decimal("1.81")  # 1.25-1.80 margin, rounded to 2 dp
    assert [p.sku for p in ds.products] == [f"SKU-{n:03d}" for n in range(1, 51)]


def test_report_contains_required_sections(ds: Dataset) -> None:
    text = render_markdown(ds, run_checks(ds), "x.y.z")
    for needle in (
        "Seed: `42`",
        "2026-09-30",
        "## Row counts",
        "## Scenario coverage",
        "## Category and supplier distribution",
        "## Checksums",
        "**overall**",
        "Synthetic data — fictional entities only.",
        "Overall coverage result: **PASS**",
    ):
        assert needle in text
    assert "FAIL" not in text.replace("Overall coverage", "")
