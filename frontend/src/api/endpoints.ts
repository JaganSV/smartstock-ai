/** Typed wrappers, one per backend endpoint the UI calls. Shapes come from ``schema.d.ts``. */
import { apiClient, LOGIN_PATH } from './client';
import type {
  AuditLogPage,
  AuditLogQuery,
  Category,
  DashboardFilters,
  DashboardSummary,
  Explanation,
  HealthResponse,
  LoginRequest,
  LoginResponse,
  MeResponse,
  ProductDetail,
  ProductPage,
  ProductQuery,
  ProductSales,
  RecalculateResult,
  RiskDetail,
  RiskDistribution,
  SalesSeries,
  SlowMovingPage,
  StockoutRiskPage,
  Supplier,
  Warehouse,
} from './types';

export async function getHealth(): Promise<HealthResponse> {
  const response = await apiClient.get<HealthResponse>('/health');
  return response.data;
}

export async function login(body: LoginRequest): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>(LOGIN_PATH, body);
  return response.data;
}

/** ``GET /auth/me``. ``token`` is passed right after login, before it is in the auth state. */
export async function getMe(token?: string): Promise<MeResponse> {
  const response = await apiClient.get<MeResponse>('/auth/me', {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  return response.data;
}

/** Drops empty filters so they are not sent as ``?action=``. */
function compact<T extends object>(query: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(query).filter(
      ([, value]) => value !== undefined && value !== null && value !== '',
    ),
  ) as Partial<T>;
}

export async function getAuditLog(query: AuditLogQuery): Promise<AuditLogPage> {
  const response = await apiClient.get<AuditLogPage>('/admin/audit-log', {
    params: compact(query),
  });
  return response.data;
}

// --- reference data ---

export async function getWarehouses(signal?: AbortSignal): Promise<Warehouse[]> {
  const response = await apiClient.get<Warehouse[]>('/reference/warehouses', { signal });
  return response.data;
}

export async function getCategories(signal?: AbortSignal): Promise<Category[]> {
  const response = await apiClient.get<Category[]>('/reference/categories', { signal });
  return response.data;
}

export async function getSuppliers(signal?: AbortSignal): Promise<Supplier[]> {
  const response = await apiClient.get<Supplier[]>('/reference/suppliers', { signal });
  return response.data;
}

// --- products (#8-#10) ---

export async function getProducts(query: ProductQuery, signal?: AbortSignal): Promise<ProductPage> {
  const response = await apiClient.get<ProductPage>('/products', {
    params: compact(query),
    signal,
  });
  return response.data;
}

export async function getProductDetail(
  productId: number,
  signal?: AbortSignal,
): Promise<ProductDetail> {
  const response = await apiClient.get<ProductDetail>(`/products/${productId}`, { signal });
  return response.data;
}

export async function getProductSales(
  productId: number,
  query: { days: number; warehouse_id?: number },
  signal?: AbortSignal,
): Promise<ProductSales> {
  const response = await apiClient.get<ProductSales>(`/products/${productId}/sales`, {
    params: compact(query),
    signal,
  });
  return response.data;
}

// --- dashboard (#11-#13) and risk (#18) ---

export async function getDashboardSummary(
  filters: DashboardFilters,
  signal?: AbortSignal,
): Promise<DashboardSummary> {
  const response = await apiClient.get<DashboardSummary>('/dashboard/summary', {
    params: compact(filters),
    signal,
  });
  return response.data;
}

export async function getSalesTrend(
  query: DashboardFilters & { days: number },
  signal?: AbortSignal,
): Promise<SalesSeries> {
  const response = await apiClient.get<SalesSeries>('/dashboard/sales-trend', {
    params: compact(query),
    signal,
  });
  return response.data;
}

export async function getRiskDistribution(
  filters: DashboardFilters,
  signal?: AbortSignal,
): Promise<RiskDistribution> {
  const response = await apiClient.get<RiskDistribution>('/dashboard/risk-distribution', {
    params: compact(filters),
    signal,
  });
  return response.data;
}

export async function getStockoutRisk(
  query: DashboardFilters & { page?: number; page_size?: number },
  signal?: AbortSignal,
): Promise<StockoutRiskPage> {
  const response = await apiClient.get<StockoutRiskPage>('/risk/stockout', {
    params: compact(query),
    signal,
  });
  return response.data;
}

export async function getSlowMoving(
  query: DashboardFilters & { page?: number; page_size?: number },
  signal?: AbortSignal,
): Promise<SlowMovingPage> {
  const response = await apiClient.get<SlowMovingPage>('/risk/slow-moving', {
    params: compact(query),
    signal,
  });
  return response.data;
}

/** ``GET /risk/{id}?warehouse_id=`` (#19): stored row, rule trace and BP 7.3 projection. */
export async function getRiskDetail(
  productId: number,
  warehouseId: number,
  signal?: AbortSignal,
): Promise<RiskDetail> {
  const response = await apiClient.get<RiskDetail>(`/risk/${productId}`, {
    params: { warehouse_id: warehouseId },
    signal,
  });
  return response.data;
}

/** ``GET /analytics/metrics/{id}/explain?warehouse_id=`` (#15): formula, inputs, result (FR-B6). */
export async function getExplanation(
  productId: number,
  warehouseId: number,
  signal?: AbortSignal,
): Promise<Explanation> {
  const response = await apiClient.get<Explanation>(`/analytics/metrics/${productId}/explain`, {
    params: { warehouse_id: warehouseId },
    signal,
  });
  return response.data;
}

// --- recalculation (#16, ADMIN) ---

export async function recalculate(): Promise<RecalculateResult> {
  const response = await apiClient.post<RecalculateResult>('/analytics/recalculate');
  return response.data;
}
