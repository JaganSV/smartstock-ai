/**
 * Named aliases over the generated OpenAPI types (``schema.d.ts``, from docs/api/openapi-v1.json
 * via ``npm run gen:api``). Never hand-write a response shape: add an alias here instead.
 */
import type { components, operations } from './schema';

type Schemas = components['schemas'];

export type LoginRequest = Schemas['LoginRequest'];
export type LoginResponse = Schemas['LoginResponse'];
export type MeResponse = Schemas['MeResponse'];
export type HealthResponse = Schemas['HealthResponse'];
export type SnapshotMeta = Schemas['SnapshotMeta'];
export type ErrorEnvelope = Schemas['ErrorEnvelope'];
export type AuditLogItem = Schemas['AuditLogItem'];
export type AuditLogPage = Schemas['Page_AuditLogItem_'];
export type AuditLogQuery = NonNullable<
  operations['audit_log_api_v1_admin_audit_log_get']['parameters']['query']
>;

/** Server pagination common to every ``Page[T]`` response. */
export interface PageParams {
  page: number;
  page_size: number;
}

export type DashboardSummary = Schemas['DashboardSummaryOut'];
export type SalesSeries = Schemas['SalesSeriesOut'];
export type SalesPoint = Schemas['SalesPoint'];
export type RiskDistribution = Schemas['RiskDistributionOut'];
export type StockoutRiskPage = Schemas['StockoutRiskPage'];
export type StockoutRiskRow = Schemas['StockoutRiskOut'];
export type Warehouse = Schemas['WarehouseOut'];
export type Category = Schemas['CategoryOut'];
export type RecalculateResult = Schemas['RecalculateOut'];

/** The dashboard's filters (FR-A4); undefined means "All". */
export interface DashboardFilters {
  warehouse_id?: number;
  category_id?: number;
}
