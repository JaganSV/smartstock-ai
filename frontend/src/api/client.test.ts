import {
  AxiosError,
  AxiosHeaders,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  ApiError,
  apiClient,
  isApiError,
  newRequestId,
  requestInterceptor,
  responseErrorInterceptor,
  SERVICE_UNAVAILABLE,
  setAuthHandlers,
  setForbiddenHandler,
  toApiError,
} from './client';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function config(url = '/products'): InternalAxiosRequestConfig {
  return { url, headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
}

function httpError(
  status: number,
  data: unknown,
  headers: Record<string, string> = {},
  url = '/products',
): AxiosError {
  const cfg = config(url);
  const response = {
    status,
    statusText: '',
    data,
    headers: new AxiosHeaders(headers),
    config: cfg,
  } as AxiosResponse;
  return new AxiosError('Request failed', 'ERR_BAD_RESPONSE', cfg, null, response);
}

const envelope = (
  code: string,
  message: string,
  requestId = 'req-123',
  details: unknown = null,
) => ({
  error: { code, message, request_id: requestId, details },
});

let cleanups: (() => void)[] = [];
afterEach(() => {
  cleanups.forEach((cleanup) => cleanup());
  cleanups = [];
});

describe('request interceptor', () => {
  it('adds the Bearer token and a UUID X-Request-ID', () => {
    cleanups.push(setAuthHandlers({ getToken: () => 'abc.def.ghi', onUnauthorized: vi.fn() }));
    const out = requestInterceptor(config());
    expect(out.headers.get('Authorization')).toBe('Bearer abc.def.ghi');
    expect(String(out.headers.get('X-Request-ID'))).toMatch(UUID);
  });

  it('uses a new request id per request and no Authorization when signed out', () => {
    const first = requestInterceptor(config());
    const second = requestInterceptor(config());
    expect(first.headers.has('Authorization')).toBe(false);
    expect(first.headers.get('X-Request-ID')).not.toBe(second.headers.get('X-Request-ID'));
  });

  it('keeps an explicit Authorization header (used right after login)', () => {
    cleanups.push(setAuthHandlers({ getToken: () => 'stored', onUnauthorized: vi.fn() }));
    const cfg = config();
    cfg.headers.set('Authorization', 'Bearer fresh');
    expect(requestInterceptor(cfg).headers.get('Authorization')).toBe('Bearer fresh');
  });

  it('makes a v4 UUID without crypto.randomUUID', () => {
    const original = crypto.randomUUID;
    Object.defineProperty(crypto, 'randomUUID', { value: undefined, configurable: true });
    try {
      expect(newRequestId()).toMatch(UUID);
    } finally {
      Object.defineProperty(crypto, 'randomUUID', { value: original, configurable: true });
    }
  });

  it('is wired into the shared client', async () => {
    cleanups.push(setAuthHandlers({ getToken: () => 'wired', onUnauthorized: vi.fn() }));
    let seen: InternalAxiosRequestConfig | undefined;
    await apiClient.get('/x', {
      adapter: async (cfg) => {
        seen = cfg;
        return { data: {}, status: 200, statusText: 'OK', headers: {}, config: cfg };
      },
    });
    expect(seen?.headers.get('Authorization')).toBe('Bearer wired');
    expect(String(seen?.headers.get('X-Request-ID'))).toMatch(UUID);
  });
});

describe('toApiError', () => {
  it('parses the BP 6.1 envelope', () => {
    const error = toApiError(
      httpError(
        409,
        envelope('CONFLICT', 'Underlying data has changed.', 'r-9', { fields: ['a'] }),
      ),
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 409,
      code: 'CONFLICT',
      message: 'Underlying data has changed.',
      requestId: 'r-9',
      details: { fields: ['a'] },
      retryAfter: null,
    });
  });

  it('turns 5xx into "Service unavailable" and keeps the request id', () => {
    const error = toApiError(
      httpError(500, envelope('INTERNAL_ERROR', 'Internal error.', 'r-500')),
    );
    expect(error.message).toBe(SERVICE_UNAVAILABLE);
    expect(error.requestId).toBe('r-500');
  });

  it('falls back to the response header for the request id and reads Retry-After', () => {
    const error = toApiError(
      httpError(429, 'not json', { 'X-Request-ID': 'hdr-1', 'Retry-After': '540' }),
    );
    expect(error).toMatchObject({
      status: 429,
      requestId: 'hdr-1',
      retryAfter: 540,
      code: 'HTTP_ERROR',
    });
    expect(error.message).toBe('Request failed (429).');
  });

  it('reads headers from a plain object too', () => {
    const cfg = config();
    const plain = new AxiosError('x', 'E', cfg, null, {
      status: 502,
      statusText: '',
      data: null,
      headers: { 'x-request-id': 'plain-1' },
      config: cfg,
    } as unknown as AxiosResponse);
    expect(toApiError(plain)).toMatchObject({
      status: 502,
      requestId: 'plain-1',
      code: 'INTERNAL_ERROR',
    });
  });

  it('maps network failures and unknown throws to status 0', () => {
    const network = new AxiosError('Network Error', 'ERR_NETWORK', config());
    expect(toApiError(network)).toMatchObject({
      status: 0,
      code: 'NETWORK_ERROR',
      message: SERVICE_UNAVAILABLE,
    });
    expect(toApiError(new Error('boom'))).toMatchObject({
      status: 0,
      message: SERVICE_UNAVAILABLE,
    });
    const same = new ApiError({ status: 404, code: 'NOT_FOUND', message: 'x' });
    expect(toApiError(same)).toBe(same);
    expect(isApiError(same)).toBe(true);
    expect(isApiError(new Error('x'))).toBe(false);
  });
});

describe('response error interceptor', () => {
  it('signs out on a 401 from a normal call', async () => {
    const onUnauthorized = vi.fn();
    cleanups.push(setAuthHandlers({ getToken: () => 't', onUnauthorized }));
    await expect(
      responseErrorInterceptor(httpError(401, envelope('UNAUTHORIZED', 'x'))),
    ).rejects.toBeInstanceOf(ApiError);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('does not sign out on a 401 from login itself', async () => {
    const onUnauthorized = vi.fn();
    cleanups.push(setAuthHandlers({ getToken: () => null, onUnauthorized }));
    await expect(
      responseErrorInterceptor(httpError(401, envelope('UNAUTHORIZED', 'x'), {}, '/auth/login')),
    ).rejects.toMatchObject({ status: 401 });
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('shows the permission snackbar on a 403', async () => {
    const onForbidden = vi.fn();
    cleanups.push(setForbiddenHandler(onForbidden));
    await expect(
      responseErrorInterceptor(httpError(403, envelope('FORBIDDEN', 'x'))),
    ).rejects.toMatchObject({
      status: 403,
      code: 'FORBIDDEN',
    });
    expect(onForbidden).toHaveBeenCalledTimes(1);
  });

  it('restores no-op handlers on cleanup', async () => {
    const onForbidden = vi.fn();
    setForbiddenHandler(onForbidden)();
    const onUnauthorized = vi.fn();
    setAuthHandlers({ getToken: () => 'x', onUnauthorized })();
    await expect(responseErrorInterceptor(httpError(403, {}))).rejects.toBeDefined();
    await expect(responseErrorInterceptor(httpError(401, {}))).rejects.toBeDefined();
    expect(onForbidden).not.toHaveBeenCalled();
    expect(onUnauthorized).not.toHaveBeenCalled();
    expect(requestInterceptor(config()).headers.has('Authorization')).toBe(false);
  });
});
