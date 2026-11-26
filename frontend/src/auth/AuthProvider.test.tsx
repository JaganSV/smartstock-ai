import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { requestInterceptor, responseErrorInterceptor } from '../api/client';
import * as endpoints from '../api/endpoints';
import { me } from '../test/utils';
import { SESSION_EXPIRED, SIGN_IN_AGAIN, useAuth, type AuthContextValue } from './AuthContext';
import AuthProvider from './AuthProvider';
import {
  AxiosError,
  AxiosHeaders,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';

vi.mock('../api/endpoints', () => ({ login: vi.fn(), getMe: vi.fn(), getHealth: vi.fn() }));

const login = vi.mocked(endpoints.login);
const getMe = vi.mocked(endpoints.getMe);

let auth: AuthContextValue;
function Probe() {
  auth = useAuth();
  return (
    <p data-testid="state">
      {auth.session ? auth.session.user.username : `out:${auth.notice ?? ''}`}
    </p>
  );
}

function renderProvider() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

function unauthorized(): AxiosError {
  const config = { url: '/products', headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
  const response = {
    status: 401,
    statusText: '',
    data: {},
    headers: new AxiosHeaders(),
    config,
  } as AxiosResponse;
  return new AxiosError('x', 'ERR', config, null, response);
}

describe('AuthProvider', () => {
  beforeEach(() => {
    login.mockReset().mockResolvedValue({
      access_token: 'jwt-for-test',
      token_type: 'bearer',
      expires_in: 3600,
      user: { id: 1, username: 'admin', role: 'ADMIN' },
    });
    getMe.mockReset().mockResolvedValue(me('ADMIN'));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('logs in with POST /auth/login then GET /auth/me and holds capabilities', async () => {
    renderProvider();
    await act(() => auth.login('admin', 'pw'));
    expect(login).toHaveBeenCalledWith({ username: 'admin', password: 'pw' });
    expect(getMe).toHaveBeenCalledWith('jwt-for-test');
    expect(screen.getByTestId('state')).toHaveTextContent('admin');
    expect(auth.can('view_governance')).toBe(true);
    expect(auth.session?.expiresAt).toBeGreaterThan(Date.now());
    // The API client now sends this token.
    const config = requestInterceptor({
      headers: new AxiosHeaders(),
    } as InternalAxiosRequestConfig);
    expect(config.headers.get('Authorization')).toBe('Bearer jwt-for-test');
  });

  it('logout clears the session and the token used by the client', async () => {
    renderProvider();
    await act(() => auth.login('admin', 'pw'));
    act(() => auth.logout());
    expect(screen.getByTestId('state')).toHaveTextContent('out:');
    expect(auth.can('view_inventory')).toBe(false);
    const config = requestInterceptor({
      headers: new AxiosHeaders(),
    } as InternalAxiosRequestConfig);
    expect(config.headers.has('Authorization')).toBe(false);
  });

  it('signs out automatically at expiry with the expiry message', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    renderProvider();
    await act(() => auth.login('admin', 'pw'));
    act(() => vi.advanceTimersByTime(3_599_000));
    expect(screen.getByTestId('state')).toHaveTextContent('admin');
    act(() => vi.advanceTimersByTime(2_000));
    expect(screen.getByTestId('state')).toHaveTextContent(`out:${SESSION_EXPIRED}`);
  });

  it('a 401 from any call clears the session with "Please sign in again."', async () => {
    renderProvider();
    await act(() => auth.login('admin', 'pw'));
    await act(async () => {
      await responseErrorInterceptor(unauthorized()).catch(() => undefined);
    });
    expect(screen.getByTestId('state')).toHaveTextContent(`out:${SIGN_IN_AGAIN}`);
  });

  it('a failed login leaves no session', async () => {
    login.mockRejectedValueOnce(new Error('nope'));
    renderProvider();
    await expect(act(() => auth.login('admin', 'bad'))).rejects.toThrow('nope');
    expect(auth.session).toBeNull();
  });

  it('never writes localStorage or sessionStorage (ADR-006)', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    renderProvider();
    await act(() => auth.login('admin', 'pw'));
    act(() => auth.logout());
    expect(setItem).not.toHaveBeenCalled();
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(document.cookie).toBe('');
  });

  it('useAuth outside the provider is a programming error', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const quiet = (event: ErrorEvent) => event.preventDefault();
    window.addEventListener('error', quiet);
    expect(() => render(<Probe />)).toThrow('useAuth must be used inside <AuthProvider>');
    window.removeEventListener('error', quiet);
  });
});
