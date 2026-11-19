"""Column names of the plain DataFrames the analytics engine consumes and produces.

Input frames (one per source table, loaded by P2-02 through repositories). Only the listed
columns are read; extra columns are ignored.
"""

# --- input frames ---
PRODUCTS_COLS = ("id", "sku", "supplier_id", "unit_cost", "case_pack", "is_active")
WAREHOUSES_COLS = ("id", "code")
SUPPLIERS_COLS = ("id", "default_lead_time_days", "min_order_qty")
POLICIES_COLS = (
    "product_id",
    "warehouse_id",
    "service_level",
    "review_period_days",
    "safety_stock_override",
    "lead_time_override_days",
)
LEVELS_COLS = ("product_id", "warehouse_id", "on_hand_qty", "committed_qty")
INCOMING_COLS = ("product_id", "warehouse_id", "quantity", "expected_arrival_date", "status")
SALES_COLS = ("product_id", "warehouse_id", "sale_date", "units_sold")

# --- build_metric_inputs output columns ---
KEY_COLS = ("product_id", "warehouse_id")
IDENTITY_COLS = ("product_id", "warehouse_id", "sku", "warehouse_code")
INPUT_COLS = (
    *IDENTITY_COLS,
    "supplier_id",
    "unit_cost",
    "case_pack",
    "supplier_moq",
    "supplier_lead_time_days",
    "service_level",
    "review_period_days",
    "safety_stock_override",
    "lead_time_override_days",
    "on_hand",
    "committed",
    "units_by_day",
    "open_incoming",
)

# --- compute_metrics output columns (input keys plus the metrics) ---
METRIC_COLS = (
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
    "demand_trend",
    "inventory_value",
    "projected_stockout_day",
)
