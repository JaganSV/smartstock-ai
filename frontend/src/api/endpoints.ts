/** Typed wrappers, one per backend endpoint the UI calls. Shapes come from ``schema.d.ts``. */
import { apiClient, LOGIN_PATH } from './client';
import type {
  AuditLogPage,
  AuditLogQuery,
  HealthResponse,
  LoginRequest,
  LoginResponse,
  MeResponse,
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
