"""Inventory levels, committed, incoming orders and policies from design targets (section 7.7).

The band formulas come from ``scenarios.py`` and are generator design targets only. All random
draws are fixed-size vectorised calls made up front, so the RNG sequence never depends on a
branch. Where a draw misses a band the value is fitted back into it deterministically (no redraws).
"""

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import numpy as np

from data.seed.catalog import NUM_PRODUCTS, SUPPLIERS, WAREHOUSES, ProductRow, SupplierRow
from data.seed.demand import Demand, ads_of
from data.seed.scenarios import DOC_BANDS, REVIEW_PERIOD_DAYS, Scenario, scenario_at

NUM_WAREHOUSES = len(WAREHOUSES)
HEALTHY_OPEN_ORDERS = 10
CANCELLED_ORDERS = 4
HIGH_SERVICE_TOP_N = 10
DEAD_ON_HAND_RANGE = (40, 400)  # inclusive
HEALTHY_COMMIT_DIVISOR = 9.5  # committed <= available / 9.5  =>  committed < 10% of on_hand

# (sku number, warehouse code) -> (safety_stock_override, lead_time_override_days)
POLICY_OVERRIDES: dict[tuple[int, str], tuple[int | None, int | None]] = {
    (31, "WH-MUM"): (25, None),
    (32, "WH-BLR"): (0, None),
    (33, "WH-DEL"): (None, 3),
}


@dataclass(frozen=True)
class LevelRow:
    sku: str
    warehouse_code: str
    on_hand: int
    committed: int
    as_of: datetime


@dataclass(frozen=True)
class IncomingRow:
    sku: str
    warehouse_code: str
    supplier_code: str
    quantity: int
    order_date: date
    expected_arrival_date: date
    status: str


@dataclass(frozen=True)
class PolicyRow:
    sku: str
    warehouse_code: str
    service_level: Decimal
    review_period_days: int
    safety_stock_override: int | None
    lead_time_override_days: int | None


@dataclass(frozen=True)
class StockPlan:
    levels: tuple[LevelRow, ...]
    incoming: tuple[IncomingRow, ...]
    policies: tuple[PolicyRow, ...]


def as_of_timestamp(as_of: date) -> datetime:
    return datetime.combine(as_of, time(23, 59, 59), tzinfo=UTC)


def order_quantity(target: float, product: ProductRow, supplier: SupplierRow) -> int:
    """Smallest multiple of case_pack that is >= max(target, MOQ)."""
    wanted = max(math.ceil(target), supplier.min_order_qty)
    return -(-wanted // product.case_pack) * product.case_pack


def _supplier(code: str) -> SupplierRow:
    return next(s for s in SUPPLIERS if s.code == code)


def _fit_available(doc: float, ads: float, lo: float, hi: float) -> int:
    """available = ceil(doc x ads), clamped so that available / ads lies in [lo, hi]."""
    return max(math.ceil(lo * ads), min(math.ceil(doc * ads), math.floor(hi * ads)))


def build_stock(
    rng: np.random.Generator, products: tuple[ProductRow, ...], demand: Demand, as_of: date
) -> StockPlan:
    shape = (NUM_PRODUCTS, NUM_WAREHOUSES)
    # --- all random draws, fixed order and fixed size ---
    doc_u = rng.uniform(size=shape)
    commit_u = rng.uniform(size=shape)
    dead_on_hand = rng.integers(DEAD_ON_HAND_RANGE[0], DEAD_ON_HAND_RANGE[1] + 1, size=shape)
    recv_count = rng.integers(1, 4, size=NUM_PRODUCTS)
    recv_wh = rng.integers(0, NUM_WAREHOUSES, size=(NUM_PRODUCTS, 3))
    recv_day = rng.integers(0, len(demand.days), size=(NUM_PRODUCTS, 3))
    recv_mult = rng.integers(1, 4, size=(NUM_PRODUCTS, 3))
    cancel_prod = rng.integers(0, NUM_PRODUCTS, size=CANCELLED_ORDERS)
    cancel_wh = rng.integers(0, NUM_WAREHOUSES, size=CANCELLED_ORDERS)
    cancel_day = rng.integers(0, len(demand.days), size=CANCELLED_ORDERS)
    cancel_mult = rng.integers(1, 4, size=CANCELLED_ORDERS)
    eligible = [
        i * NUM_WAREHOUSES + j
        for i in range(NUM_PRODUCTS)
        for j, wh in enumerate(WAREHOUSES)
        if scenario_at(i + 1, wh.code) is Scenario.HEALTHY
    ]
    healthy_pick = rng.choice(np.array(eligible), size=HEALTHY_OPEN_ORDERS, replace=False)
    healthy_extra = rng.integers(1, 8, size=HEALTHY_OPEN_ORDERS)
    healthy_mult = rng.integers(1, 4, size=HEALTHY_OPEN_ORDERS)
    healthy_ordered = rng.integers(0, 6, size=HEALTHY_OPEN_ORDERS)

    levels: list[LevelRow] = []
    incoming: list[IncomingRow] = []
    stamp = as_of_timestamp(as_of)
    ads_grid: dict[tuple[int, int], float] = {}

    for i, product in enumerate(products):
        supplier = _supplier(product.supplier_code)
        lead = supplier.lead_time_days
        for j, warehouse in enumerate(WAREHOUSES):
            scenario = scenario_at(product.number, warehouse.code)
            ads = ads_of(demand.units[i, j], 30)
            ads_grid[(i, j)] = ads
            u, cu = float(doc_u[i, j]), float(commit_u[i, j])
            if scenario is Scenario.DEAD_STOCK or ads <= 0:
                # zero-demand case (or a degenerate zero-ADS draw): no DoC band exists
                on_hand, committed = int(dead_on_hand[i, j]), 0
            elif scenario is Scenario.STOCKOUT:
                on_hand = int(u * 3 * ads)
                committed = on_hand + 1 + int(cu * 5 * ads)
            else:
                band = DOC_BANDS[scenario](lead, REVIEW_PERIOD_DAYS)
                doc = band.draw_lo + u * (band.draw_hi - band.draw_lo)
                available = _fit_available(doc, ads, band.fit_lo, band.fit_hi)
                if scenario is Scenario.COMMITTED_MASKING:
                    # large committed quantity; on_hand >= 2 x ADS30 x L by construction
                    committed = max(math.ceil(2 * ads * lead) - available, 0) + math.ceil(
                        cu * ads * lead
                    )
                else:
                    committed = int(cu * available / HEALTHY_COMMIT_DIVISOR)
                on_hand = available + committed
                if scenario is Scenario.COVERED_BY_INCOMING:
                    actual_doc = available / ads
                    arrive = max(1, math.floor(actual_doc) - 1)
                    arrival = as_of + timedelta(days=arrive)
                    incoming.append(
                        IncomingRow(
                            sku=product.sku,
                            warehouse_code=warehouse.code,
                            supplier_code=supplier.code,
                            quantity=order_quantity(
                                ads * (lead + REVIEW_PERIOD_DAYS), product, supplier
                            ),
                            order_date=arrival - timedelta(days=lead),
                            expected_arrival_date=arrival,
                            status="OPEN",
                        )
                    )
            levels.append(LevelRow(product.sku, warehouse.code, on_hand, committed, stamp))

    # OPEN orders for ~10 HEALTHY product-warehouses, arriving AFTER t0 + L (must not be counted)
    for k in range(HEALTHY_OPEN_ORDERS):
        i, j = divmod(int(healthy_pick[k]), NUM_WAREHOUSES)
        product = products[i]
        supplier = _supplier(product.supplier_code)
        arrival = as_of + timedelta(days=supplier.lead_time_days + int(healthy_extra[k]))
        target = int(healthy_mult[k]) * max(ads_grid[(i, j)] * REVIEW_PERIOD_DAYS, 1.0)
        incoming.append(
            IncomingRow(
                sku=product.sku,
                warehouse_code=WAREHOUSES[j].code,
                supplier_code=supplier.code,
                quantity=order_quantity(target, product, supplier),
                order_date=as_of - timedelta(days=int(healthy_ordered[k])),
                expected_arrival_date=arrival,
                status="OPEN",
            )
        )

    # RECEIVED: 1-3 historical orders per product, arrived inside the sales window
    for i, product in enumerate(products):
        supplier = _supplier(product.supplier_code)
        for slot in range(int(recv_count[i])):
            j = int(recv_wh[i, slot])
            arrival = demand.days[int(recv_day[i, slot])]
            target = int(recv_mult[i, slot]) * max(ads_grid[(i, j)] * REVIEW_PERIOD_DAYS, 1.0)
            incoming.append(
                IncomingRow(
                    sku=product.sku,
                    warehouse_code=WAREHOUSES[j].code,
                    supplier_code=supplier.code,
                    quantity=order_quantity(target, product, supplier),
                    order_date=arrival - timedelta(days=supplier.lead_time_days),
                    expected_arrival_date=arrival,
                    status="RECEIVED",
                )
            )

    # CANCELLED: exactly 4 orders
    for k in range(CANCELLED_ORDERS):
        i, j = int(cancel_prod[k]), int(cancel_wh[k])
        product = products[i]
        supplier = _supplier(product.supplier_code)
        ordered = demand.days[int(cancel_day[k])]
        target = int(cancel_mult[k]) * max(ads_grid[(i, j)] * REVIEW_PERIOD_DAYS, 1.0)
        incoming.append(
            IncomingRow(
                sku=product.sku,
                warehouse_code=WAREHOUSES[j].code,
                supplier_code=supplier.code,
                quantity=order_quantity(target, product, supplier),
                order_date=ordered,
                expected_arrival_date=ordered + timedelta(days=supplier.lead_time_days),
                status="CANCELLED",
            )
        )

    return StockPlan(
        levels=tuple(levels), incoming=tuple(incoming), policies=_policies(products, demand)
    )


def _policies(products: tuple[ProductRow, ...], demand: Demand) -> tuple[PolicyRow, ...]:
    """150 policies. service_level 0.99 for the 10 highest-lambda products (ties by SKU)."""
    ranked = sorted(range(NUM_PRODUCTS), key=lambda idx: (-float(demand.lam[idx]), idx))
    high = {products[idx].number for idx in ranked[:HIGH_SERVICE_TOP_N]}
    rows: list[PolicyRow] = []
    for product in products:
        for warehouse in WAREHOUSES:
            safety, lead = POLICY_OVERRIDES.get((product.number, warehouse.code), (None, None))
            rows.append(
                PolicyRow(
                    sku=product.sku,
                    warehouse_code=warehouse.code,
                    service_level=Decimal("0.990") if product.number in high else Decimal("0.950"),
                    review_period_days=REVIEW_PERIOD_DAYS,
                    safety_stock_override=safety,
                    lead_time_override_days=lead,
                )
            )
    return tuple(rows)
