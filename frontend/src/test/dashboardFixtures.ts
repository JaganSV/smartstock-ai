/** Dashboard API fixtures shaped like the seed-42 responses (BOB-P4-02 section 10). */
import { vi } from 'vitest';

import type * as Endpoints from '../api/endpoints';
import type {
  Category,
  DashboardSummary,
  RiskDistribution,
  SalesSeries,
  StockoutRiskPage,
  StockoutRiskRow,
  Warehouse,
} from '../api/types';

export const SNAPSHOT = {
  snapshot_id: 8,
  calculated_at: '2026-11-25T16:10:00Z',
  data_as_of_date: '2026-09-30',
  verified: true as const,
};

export const SUMMARY: DashboardSummary = {
  total_products: 50,
  total_units: 73484,
  inventory_value: '89944367.37',
  low_stock_count: 7,
  stockout_risk_count: 15,
  slow_moving_count: 11,
  snapshot: SNAPSHOT,
};

export const DISTRIBUTION: RiskDistribution = {
  rows: { STOCKOUT: 3, CRITICAL: 8, HIGH: 4, MEDIUM: 3, OVERSTOCK: 11, LOW: 121 },
  products: { STOCKOUT: 3, CRITICAL: 6, HIGH: 6, MEDIUM: 1, OVERSTOCK: 9, LOW: 25 },
  snapshot: SNAPSHOT,
};

export const TREND: SalesSeries = {
  start_date: '2026-09-28',
  end_date: '2026-09-30',
  series: [
    { date: '2026-09-28', units: 10, revenue: '100.10' },
    { date: '2026-09-29', units: 20, revenue: '200.20' },
    { date: '2026-09-30', units: 1234, revenue: '0.05' },
  ],
};

export const WAREHOUSES: Warehouse[] = [
  { id: 10, code: 'WH-MUM', name: 'Mumbai DC', city: 'Mumbai', region: 'West' },
  { id: 11, code: 'WH-DEL', name: 'Delhi DC', city: 'Delhi', region: 'North' },
  { id: 12, code: 'WH-BLR', name: 'Bengaluru DC', city: 'Bengaluru', region: 'South' },
];

export const CATEGORIES: Category[] = [
  { id: 1, code: 'SPORT', name: 'Sports' },
  { id: 2, code: 'HOME', name: 'Home' },
];

const RISKS = ['STOCKOUT', 'STOCKOUT', 'STOCKOUT', 'CRITICAL', 'CRITICAL', 'CRITICAL'] as const;

export function riskRow(index: number, overrides: Partial<StockoutRiskRow> = {}): StockoutRiskRow {
  const sku = `SKU-${String(index).padStart(3, '0')}`;
  const risk = (RISKS[index - 1] ?? 'HIGH') as StockoutRiskRow['risk_class'];
  return {
    product_id: 150 + index,
    sku,
    name: `Product ${index}`,
    warehouse_id: 10,
    warehouse_code: 'WH-MUM',
    on_hand: 100,
    committed: 10,
    available: risk === 'STOCKOUT' ? 0 : 90 + index,
    incoming_in_lt: 0,
    ads_30: 5,
    ads_90: 5,
    days_of_cover: risk === 'STOCKOUT' ? 0 : 3 + index,
    safety_stock: 20,
    reorder_point: 120,
    reorder_qty: 200,
    risk_class: risk,
    risk_reason_code: 'R1',
    is_slow_moving: false,
    inventory_value: '1000.00',
    projected_stockout_day: risk === 'HIGH' ? null : index - 1,
    is_high_demand: false,
    ...overrides,
  };
}

export const STOCKOUT_PAGE: StockoutRiskPage = {
  items: Array.from({ length: 10 }, (_, i) => riskRow(i + 1)),
  page: 1,
  page_size: 10,
  total: 15,
  snapshot: SNAPSHOT,
};

/** Loads the default resolved values into an automocked ``api/endpoints`` module. */
export function mockDashboardApi(endpoints: typeof Endpoints) {
  vi.mocked(endpoints.getWarehouses).mockResolvedValue(WAREHOUSES);
  vi.mocked(endpoints.getCategories).mockResolvedValue(CATEGORIES);
  vi.mocked(endpoints.getDashboardSummary).mockResolvedValue(SUMMARY);
  vi.mocked(endpoints.getSalesTrend).mockResolvedValue(TREND);
  vi.mocked(endpoints.getRiskDistribution).mockResolvedValue(DISTRIBUTION);
  vi.mocked(endpoints.getStockoutRisk).mockResolvedValue(STOCKOUT_PAGE);
  vi.mocked(endpoints.getHealth).mockResolvedValue({
    status: 'ok',
    service: 'smartstock-backend',
    version: '0.1.0',
  });
}
