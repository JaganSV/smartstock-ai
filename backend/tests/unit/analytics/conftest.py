"""In-memory seed-42 frames for the analytics tests (no database)."""

import pandas as pd
import pytest

from app.analytics.inputs import build_metric_inputs
from app.analytics.metrics import compute_metrics
from app.analytics.params import AnalyticsParams
from data.seed.catalog import SUPPLIERS, WAREHOUSES
from data.seed.demand import sales_rows
from data.seed.generator import DEFAULT_SEED, build_dataset
from data.seed.report import Dataset
from tests.unit.analytics.helpers import T0


@pytest.fixture(scope="session")
def seed_ds() -> Dataset:
    return build_dataset(DEFAULT_SEED, T0)


@pytest.fixture(scope="session")
def seed_params() -> AnalyticsParams:
    return AnalyticsParams(t0=T0)


@pytest.fixture(scope="session")
def seed_inputs(seed_ds: Dataset, seed_params: AnalyticsParams) -> pd.DataFrame:
    """The seed as the raw frames P2-02 will load, run through build_metric_inputs."""
    supplier_id = {s.code: i + 1 for i, s in enumerate(SUPPLIERS)}
    warehouse_id = {w.code: i + 1 for i, w in enumerate(WAREHOUSES)}
    product_id = {p.sku: p.number for p in seed_ds.products}
    products = pd.DataFrame(
        [
            {
                "id": p.number,
                "sku": p.sku,
                "supplier_id": supplier_id[p.supplier_code],
                "unit_cost": p.unit_cost,
                "case_pack": p.case_pack,
                "is_active": True,
            }
            for p in seed_ds.products
        ]
    )
    warehouses = pd.DataFrame([{"id": warehouse_id[w.code], "code": w.code} for w in WAREHOUSES])
    suppliers = pd.DataFrame(
        [
            {
                "id": supplier_id[s.code],
                "default_lead_time_days": s.lead_time_days,
                "min_order_qty": s.min_order_qty,
            }
            for s in SUPPLIERS
        ]
    )
    policies = pd.DataFrame(
        [
            {
                "product_id": product_id[r.sku],
                "warehouse_id": warehouse_id[r.warehouse_code],
                "service_level": r.service_level,
                "review_period_days": r.review_period_days,
                "safety_stock_override": r.safety_stock_override,
                "lead_time_override_days": r.lead_time_override_days,
            }
            for r in seed_ds.stock.policies
        ]
    )
    levels = pd.DataFrame(
        [
            {
                "product_id": product_id[r.sku],
                "warehouse_id": warehouse_id[r.warehouse_code],
                "on_hand_qty": r.on_hand,
                "committed_qty": r.committed,
            }
            for r in seed_ds.stock.levels
        ]
    )
    incoming = pd.DataFrame(
        [
            {
                "product_id": product_id[r.sku],
                "warehouse_id": warehouse_id[r.warehouse_code],
                "quantity": r.quantity,
                "expected_arrival_date": r.expected_arrival_date,
                "status": r.status,
            }
            for r in seed_ds.stock.incoming
        ]
    )
    sales = pd.DataFrame(
        [
            {
                "product_id": product_id[sku],
                "warehouse_id": warehouse_id[wh],
                "sale_date": day,
                "units_sold": units_sold,
            }
            for sku, wh, day, units_sold, _ in sales_rows(seed_ds.products, seed_ds.demand)
        ]
    )
    return build_metric_inputs(
        products, warehouses, suppliers, policies, levels, incoming, sales, seed_params
    )


@pytest.fixture(scope="session")
def seed_metrics(seed_inputs: pd.DataFrame, seed_params: AnalyticsParams) -> pd.DataFrame:
    return compute_metrics(seed_inputs, seed_params)
