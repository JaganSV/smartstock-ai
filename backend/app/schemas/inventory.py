"""Reference, product and sales-series response schemas (BP 6.2 #5-#10, 6.3 ProductMetricOut).

Money is a 2-dp decimal string (``Money``); ADS, days of cover and trend are numbers rounded to
4 dp (``FourDp``); null stays null; counts and quantities are integers.
"""

from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import RiskClass
from app.schemas.common import FourDp, Money, Page, SnapshotMeta

# --- reference lists (#5-#7) ---


class CategoryOut(BaseModel):
    id: int
    code: str
    name: str


class WarehouseOut(BaseModel):
    id: int
    code: str
    name: str
    city: str
    region: str


class SupplierOut(BaseModel):
    """Supplier reference data. ``contact_email`` is deliberately not exposed."""

    id: int
    code: str
    name: str
    default_lead_time_days: int
    min_order_qty: int
    reliability_pct: float = Field(description="On-time delivery reliability, 0-100.")
    is_active: bool


# --- product list (#8) ---


class ProductSummaryOut(BaseModel):
    """One product rolled up across the included warehouses (BP 7.4, ``rollup_by_product``)."""

    product_id: int
    sku: str
    name: str
    category_code: str
    supplier_code: str
    on_hand: int
    available: int
    incoming_in_lt: int
    ads_30: FourDp
    days_of_cover: FourDp | None = Field(description="Null when the summed ADS30 is 0.")
    inventory_value: Money
    risk_class: RiskClass = Field(description="Most severe class across the included warehouses.")
    risk_warehouse_code: str = Field(description="Warehouse that drove risk_class.")
    is_slow_moving: bool
    is_dead_stock: bool
    is_high_demand: bool = Field(
        description="True if any included warehouse row is high-demand (snapshot params_json)."
    )


class ProductPage(Page[ProductSummaryOut]):
    """``Page[ProductSummaryOut]`` plus the snapshot the rows come from."""

    snapshot: SnapshotMeta


# --- product detail (#9) ---


class CategoryRef(BaseModel):
    id: int
    code: str
    name: str


class SupplierRef(BaseModel):
    id: int
    code: str
    name: str
    default_lead_time_days: int
    min_order_qty: int


class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    category: CategoryRef
    supplier: SupplierRef
    unit_cost: Money
    unit_price: Money
    case_pack: int
    is_active: bool


class PolicyOut(BaseModel):
    service_level: float
    review_period_days: int
    safety_stock_override: int | None
    lead_time_override_days: int | None


class ProductMetricOut(BaseModel):
    """BP 6.3 ``ProductMetricOut``: one product x warehouse row of the snapshot."""

    product_id: int
    sku: str
    name: str
    warehouse_id: int
    warehouse_code: str
    on_hand: int
    committed: int
    available: int
    incoming_in_lt: int
    ads_30: FourDp
    ads_90: FourDp
    days_of_cover: FourDp | None = Field(description="Null when ADS30 is 0.")
    safety_stock: int
    reorder_point: int
    reorder_qty: int
    risk_class: RiskClass
    risk_reason_code: str
    is_slow_moving: bool
    inventory_value: Money


class WarehouseMetricOut(ProductMetricOut):
    """``ProductMetricOut`` plus the row's policy and its derived high-demand flag."""

    policy: PolicyOut | None = Field(description="Null when the pair has no policy row.")
    is_high_demand: bool


class ProductDetailOut(BaseModel):
    product: ProductOut
    warehouses: list[WarehouseMetricOut] = Field(description="Sorted by warehouse code.")
    rollup: ProductSummaryOut | None = Field(
        description="Product-level roll-up; null when the snapshot has no row for the product."
    )
    snapshot: SnapshotMeta


# --- sales series (#10, #12) ---


class SalesPoint(BaseModel):
    date: date
    units: int
    revenue: Money


class SalesSeriesOut(BaseModel):
    """Daily series, oldest first, zero-filled; ``end_date`` is t0 (never the wall clock)."""

    start_date: date
    end_date: date
    series: list[SalesPoint]


class ProductSalesOut(BaseModel):
    """One product's daily series (same rules as ``SalesSeriesOut``)."""

    product_id: int
    warehouse_id: int | None = Field(description="Null when summed across all warehouses.")
    start_date: date
    end_date: date
    series: list[SalesPoint]
