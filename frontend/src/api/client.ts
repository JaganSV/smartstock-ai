/**
 * The one Axios instance for the API, its interceptors and the typed ``ApiError``.
 *
 * - Every request gets ``Authorization: Bearer <token>`` (when signed in) and a fresh
 *   ``X-Request-ID`` (UUID) that the backend echoes and logs.
 * - Every failure becomes an ``ApiError`` parsed from the BP §6.1 envelope.
 * - A 401 from any call except login signs the user out; a 403 shows the permission snackbar.
 *
 * The token is never stored here: ``AuthProvider`` hands in a getter (memory only, ADR-006).
 * Nothing in this module logs a request, a header or a token.
 */
import axios, { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';

import type { ErrorEnvelope } from './types';

export const REQUEST_ID_HEADER = 'X-Request-ID';
export const LOGIN_PATH = '/auth/login';
export const SERVICE_UNAVAILABLE = 'Service unavailable. Try again later.';

/** A failed API call. ``status`` is 0 when the server could not be reached. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly details: unknown;
  /** Seconds from ``Retry-After``, when the browser can read it (429). */
  readonly retryAfter: number | null;

  constructor(init: {
    status: number;
    code: string;
    message: string;
    requestId?: string | null;
    details?: unknown;
    retryAfter?: number | null;
  }) {
    super(init.message);
    this.name = 'ApiError';
    this.status = init.status;
    this.code = init.code;
    this.requestId = init.requestId ?? null;
    this.details = init.details ?? null;
    this.retryAfter = init.retryAfter ?? null;
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

interface AuthHandlers {
  getToken: () => string | null;
  onUnauthorized: () => void;
}

const handlers: { auth: AuthHandlers; onForbidden: () => void } = {
  auth: { getToken: () => null, onUnauthorized: () => {} },
  onForbidden: () => {},
};

/** Called by ``AuthProvider``: where the token comes from and what a 401 does. */
export function setAuthHandlers(auth: AuthHandlers): () => void {
  handlers.auth = auth;
  return () => {
    if (handlers.auth === auth) handlers.auth = { getToken: () => null, onUnauthorized: () => {} };
  };
}

/** Called by the snackbar provider: what a 403 does. */
export function setForbiddenHandler(onForbidden: () => void): () => void {
  handlers.onForbidden = onForbidden;
  return () => {
    if (handlers.onForbidden === onForbidden) handlers.onForbidden = () => {};
  };
}

export function newRequestId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  // RFC 4122 v4 from getRandomValues, for non-secure contexts without randomUUID.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function requestInterceptor(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  const headers = AxiosHeaders.from(config.headers);
  const token = handlers.auth.getToken();
  if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`);
  headers.set(REQUEST_ID_HEADER, newRequestId());
  config.headers = headers;
  return config;
}

function isEnvelope(data: unknown): data is ErrorEnvelope {
  if (typeof data !== 'object' || data === null || !('error' in data)) return false;
  const error = (data as { error: unknown }).error;
  return (
    typeof error === 'object' &&
    error !== null &&
    typeof (error as { message?: unknown }).message === 'string'
  );
}

function headerValue(headers: unknown, name: string): string | null {
  if (headers instanceof AxiosHeaders) {
    const value = headers.get(name);
    return typeof value === 'string' ? value : null;
  }
  if (typeof headers === 'object' && headers !== null) {
    const record = headers as Record<string, unknown>;
    const value = record[name] ?? record[name.toLowerCase()];
    return typeof value === 'string' ? value : null;
  }
  return null;
}

/** Any thrown value from an API call as an ``ApiError`` (never with a stack or raw exception). */
export function toApiError(error: unknown): ApiError {
  if (isApiError(error)) return error;
  if (!(error instanceof AxiosError) || !error.response) {
    return new ApiError({ status: 0, code: 'NETWORK_ERROR', message: SERVICE_UNAVAILABLE });
  }
  const { status, data, headers } = error.response;
  const envelope = isEnvelope(data) ? data.error : null;
  const requestId = envelope?.request_id ?? headerValue(headers, REQUEST_ID_HEADER);
  const retryHeader = headerValue(headers, 'Retry-After');
  const retryAfter = retryHeader !== null && /^\d+$/.test(retryHeader) ? Number(retryHeader) : null;
  return new ApiError({
    status,
    code: envelope?.code ?? (status >= 500 ? 'INTERNAL_ERROR' : 'HTTP_ERROR'),
    message:
      status >= 500 ? SERVICE_UNAVAILABLE : (envelope?.message ?? `Request failed (${status}).`),
    requestId,
    details: envelope?.details ?? null,
    retryAfter,
  });
}

export function responseErrorInterceptor(error: unknown): Promise<never> {
  const apiError = toApiError(error);
  const url = error instanceof AxiosError ? (error.config?.url ?? '') : '';
  if (apiError.status === 401 && !url.endsWith(LOGIN_PATH)) handlers.auth.onUnauthorized();
  if (apiError.status === 403) handlers.onForbidden();
  return Promise.reject(apiError);
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30_000,
});

apiClient.interceptors.request.use(requestInterceptor);
apiClient.interceptors.response.use((response) => response, responseErrorInterceptor);
