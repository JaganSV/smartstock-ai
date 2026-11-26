/** Product-page API fixtures shaped like the seed-42 responses (BOB-P4-03 section 10). */
import { vi } from 'vitest';

import type * as Endpoints from '../api/endpoints';
import type {
  Explanation,
  ProductDetail,
  ProductPage,
  ProductSales,
  RiskDetail,
  SlowMovingPage,
  SlowMovingRow,
  Supplier,
  WarehouseMetric,
} from '../api/types';
import { SNAPSHOT } from './dashboardFixtures';

const POLICY = {
  service_level: 0.99,
  review_period_days: 14,
  safety_stock_override: null,
  lead_time_override_days: null,
};

function warehouseRow(
  id: number,
  code: string,
  overrides: Partial<WarehouseMetric> = {},
): WarehouseMetric {
  return {
    product_id: 154,
    sku: 'SKU-004',
    name: 'Yoga Mat 6mm',
    warehouse_id: id,
    warehouse_code: code,
    on_hand: 1461,
    committed: 118,
    available: 1343,
    incoming_in_lt: 0,
    ads_30: 17.7,
    ads_90: 17.3889,
    days_of_cover: 75.8757,
    safety_stock: 33,
    reorder_point: 281,
    reorder_qty: 0,
    risk_class: 'LOW',
    risk_reason_code: 'R6_HEALTHY',
    is_slow_moving: false,
    inventory_value: '4185954.93',
    policy: POLICY,
    is_high_demand: false,
    ...overrides,
  };
}

export const MUM_ROW = warehouseRow(10, 'WH-MUM', {
  on_hand: 242,
  committed: 19,
  available: 223,
  ads_30: 21.5333,
  ads_90: 22.6111,
  days_of_cover: 10.356,
  safety_stock: 47,
  reorder_point: 349,
  reorder_qty: 432,
  risk_class: 'CRITICAL',
  risk_reason_code: 'R2_STOCKOUT_BEFORE_REPLENISHMENT',
  inventory_value: '693361.46',
});

/** SKU-004: tabs in warehouse-code order; the roll-up (CRITICAL) is driven by WH-MUM. */
export const SKU004_DETAIL: ProductDetail = {
  product: {
    id: 154,
    sku: 'SKU-004',
    name: 'Yoga Mat 6mm',
    category: { id: 19, code: 'SPORT', name: 'Sports & Fitness' },
    supplier: {
      id: 19,
      code: 'SUP-D',
      name: 'Delta Trade Partners (fictional)',
      default_lead_time_days: 14,
      min_order_qty: 36,
    },
    unit_cost: '2865.13',
    unit_price: '4629.10',
    case_pack: 12,
    is_active: true,
  },
  warehouses: [
    warehouseRow(11, 'WH-BLR'),
    warehouseRow(12, 'WH-DEL', { risk_class: 'LOW' }),
    MUM_ROW,
  ],
  rollup: {
    product_id: 154,
    sku: 'SKU-004',
    name: 'Yoga Mat 6mm',
    category_code: 'SPORT',
    supplier_code: 'SUP-D',
    on_hand: 2432,
    available: 2281,
    incoming_in_lt: 0,
    ads_30: 49.1,
    days_of_cover: 46.4562,
    inventory_value: '6967996.16',
    risk_class: 'CRITICAL',
    risk_warehouse_code: 'WH-MUM',
    is_slow_moving: false,
    is_dead_stock: false,
    is_high_demand: false,
  },
  snapshot: SNAPSHOT,
};

const SKU004_UNITS = [
  223.0, 201.4667, 179.9333, 158.4, 136.8667, 115.3333, 93.8, 72.2667, 50.7333, 29.2, 7.6667,
  -13.8667, -35.4, -56.9333, -78.4667,
];

function day(k: number): string {
  return `2026-10-${String(k).padStart(2, '0')}`;
}

/** SKU-004 @ WH-MUM: CRITICAL by R2, stockout projected on day 11 (11 Oct 2026). */
export const SKU004_RISK: RiskDetail = {
  ...MUM_ROW,
  lead_time_days: 14,
  rule_trace: {
    class: 'CRITICAL',
    reason_code: 'R2_STOCKOUT_BEFORE_REPLENISHMENT',
    rule_fired: 'R2',
    rules_checked: [
      { rule: 'R1', class: 'STOCKOUT', matched: false },
      { rule: 'R2', class: 'CRITICAL', matched: true },
    ],
  },
  projection: {
    horizon_days: 14,
    points: SKU004_UNITS.map((units, k) => ({
      day: k,
      date: k === 0 ? '2026-09-30' : day(k),
      projected_units: units,
    })),
    projected_stockout_day: 11,
    open_incoming: [],
  },
  snapshot: SNAPSHOT,
};

/** SKU-024 @ WH-MUM: MEDIUM by R4; 115 units arrive on day 6, no stockout within L. */
export const SKU024_RISK: RiskDetail = {
  ...MUM_ROW,
  product_id: 174,
  sku: 'SKU-024',
  name: 'Desk Lamp',
  available: 27,
  incoming_in_lt: 115,
  risk_class: 'MEDIUM',
  risk_reason_code: 'R4_COVER_BELOW_LEAD_PLUS_REVIEW',
  lead_time_days: 14,
  rule_trace: {
    class: 'MEDIUM',
    reason_code: 'R4_COVER_BELOW_LEAD_PLUS_REVIEW',
    rule_fired: 'R4',
    rules_checked: [
      { rule: 'R1', class: 'STOCKOUT', matched: false },
      { rule: 'R2', class: 'CRITICAL', matched: false },
      { rule: 'R3', class: 'HIGH', matched: false },
      { rule: 'R4', class: 'MEDIUM', matched: true },
    ],
  },
  projection: {
    horizon_days: 14,
    points: Array.from({ length: 15 }, (_, k) => ({
      day: k,
      date: k === 0 ? '2026-09-30' : day(k),
      projected_units: k < 6 ? 27 - 4 * k : 27 - 4 * k + 115,
    })),
    projected_stockout_day: null,
    open_incoming: [
      { expected_arrival_date: '2026-10-06', quantity: 115 },
      { expected_arrival_date: '2026-11-20', quantity: 40 },
    ],
  },
  snapshot: SNAPSHOT,
};

export const SKU004_EXPLAIN: Explanation = {
  product_id: 154,
  sku: 'SKU-004',
  warehouse_id: 10,
  warehouse_code: 'WH-MUM',
  snapshot: SNAPSHOT,
  risk: SKU004_RISK.rule_trace,
  metrics: [
    {
      metric: 'available',
      formula: 'available = on_hand - committed',
      inputs: { on_hand: 242, committed: 19 },
      result: 223,
      source: 'BP 7.2',
    },
    {
      metric: 'demand_std_30',
      formula:
        'sigma_d = population standard deviation (ddof = 0) of the daily units, last 30 days',
      inputs: { window_days: 30 },
      result: 5.2898,
      source: 'BP 7.2',
    },
    {
      metric: 'lead_time_days',
      formula: 'L = lead_time_override_days if set, else the supplier default_lead_time_days',
      inputs: { lead_time_override_days: null, supplier_lead_time_days: 14 },
      result: 14,
      source: 'BP 7.2',
    },
    {
      metric: 'inventory_position',
      formula: 'IP = available + incoming_in_LT',
      inputs: { available: 223, incoming_in_lt: 0 },
      result: 223,
      source: 'BP 7.2',
    },
    {
      metric: 'risk_class',
      formula: 'first matching rule of BP 7.4',
      inputs: { rule_fired: 'R2' },
      result: 'CRITICAL',
      source: 'BP 7.4',
    },
  ],
};

export const SALES: ProductSales = {
  product_id: 154,
  warehouse_id: 10,
  start_date: '2026-09-29',
  end_date: '2026-09-30',
  series: [
    { date: '2026-09-29', units: 20, revenue: '92582.00' },
    { date: '2026-09-30', units: 22, revenue: '101840.20' },
  ],
};

export const SUPPLIERS: Supplier[] = [
  {
    id: 19,
    code: 'SUP-D',
    name: 'Delta Trade Partners (fictional)',
    default_lead_time_days: 14,
    min_order_qty: 36,
    reliability_pct: 92.5,
    is_active: true,
  },
];

export function slowRow(index: number, overrides: Partial<SlowMovingRow> = {}): SlowMovingRow {
  return {
    ...MUM_ROW,
    product_id: 170 + index,
    sku: `SKU-0${20 + index}`,
    name: `Slow product ${index}`,
    warehouse_id: 11,
    warehouse_code: 'WH-BLR',
    ads_30: 0.1333,
    ads_90: 0.9,
    risk_class: 'OVERSTOCK',
    is_slow_moving: true,
    inventory_value: '10741403.52',
    is_dead_stock: false,
    ...overrides,
  };
}

export const SLOW_PAGE: SlowMovingPage = {
  items: [slowRow(2, { is_dead_stock: true, ads_30: 0, ads_90: 0 }), slowRow(5)],
  page: 1,
  page_size: 25,
  total: 11,
  snapshot: SNAPSHOT,
};

export const PRODUCT_PAGE: ProductPage = {
  items: [
    { ...SKU004_DETAIL.rollup!, is_high_demand: true },
    {
      ...SKU004_DETAIL.rollup!,
      product_id: 172,
      sku: 'SKU-022',
      name: 'Old Stock',
      risk_class: 'OVERSTOCK',
      risk_warehouse_code: 'WH-BLR',
      is_slow_moving: true,
      is_dead_stock: true,
      days_of_cover: null,
    },
  ],
  page: 1,
  page_size: 25,
  total: 50,
  snapshot: SNAPSHOT,
};

/** Default resolved values for the product pages in an automocked ``api/endpoints``. */
export function mockProductApi(endpoints: typeof Endpoints) {
  vi.mocked(endpoints.getProductDetail).mockResolvedValue(SKU004_DETAIL);
  vi.mocked(endpoints.getRiskDetail).mockResolvedValue(SKU004_RISK);
  vi.mocked(endpoints.getExplanation).mockResolvedValue(SKU004_EXPLAIN);
  vi.mocked(endpoints.getProductSales).mockResolvedValue(SALES);
  vi.mocked(endpoints.getSuppliers).mockResolvedValue(SUPPLIERS);
  vi.mocked(endpoints.getSlowMoving).mockResolvedValue(SLOW_PAGE);
  vi.mocked(endpoints.getProducts).mockResolvedValue(PRODUCT_PAGE);
}
