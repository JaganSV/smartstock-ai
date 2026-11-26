import { fireEvent, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, SERVICE_UNAVAILABLE } from '../api/client';
import * as endpoints from '../api/endpoints';
import { mockDashboardApi } from '../test/dashboardFixtures';
import { me, renderApp } from '../test/utils';
import { INVALID_CREDENTIALS, TOO_MANY_ATTEMPTS_LATER, tooManyAttempts } from './Login';

vi.mock('../api/endpoints');

const login = vi.mocked(endpoints.login);
const getMe = vi.mocked(endpoints.getMe);

function fill(username = 'admin', password = 'pw') {
  fireEvent.change(screen.getByLabelText(/username/i), { target: { value: username } });
  fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: password } });
}

function submit() {
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
}

const ok = {
  access_token: 'jwt-for-test',
  token_type: 'bearer' as const,
  expires_in: 3600,
  user: { id: 1, username: 'admin', role: 'ADMIN' },
};

describe('Login page', () => {
  beforeEach(() => {
    mockDashboardApi(endpoints);
    vi.mocked(endpoints.getAuditLog).mockResolvedValue({
      items: [],
      page: 1,
      page_size: 25,
      total: 0,
    });
    login.mockReset();
    getMe.mockReset().mockResolvedValue(me('ADMIN'));
  });

  it('signs in and lands on the dashboard', async () => {
    login.mockResolvedValue(ok);
    renderApp('/login');
    fill();
    submit();
    expect(
      await screen.findByRole('heading', { name: 'Inventory Dashboard' }, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(screen.getByTestId('user-name')).toHaveTextContent('admin');
    expect(screen.getByTestId('user-role')).toHaveTextContent('Admin');
  });

  it('returns to the page the user asked for', async () => {
    login.mockResolvedValue(ok);
    renderApp('/admin/audit-log');
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument();
    fill();
    submit();
    expect(await screen.findByRole('heading', { name: 'Audit log' })).toBeInTheDocument();
  });

  it('shows the generic message on 401', async () => {
    login.mockRejectedValue(
      new ApiError({ status: 401, code: 'UNAUTHORIZED', message: 'Invalid username or password.' }),
    );
    renderApp('/login');
    fill('admin', 'wrong');
    submit();
    expect(await screen.findByRole('alert')).toHaveTextContent(INVALID_CREDENTIALS);
    expect(screen.getByLabelText(/^password/i)).toHaveValue('');
  });

  it('shows the lockout minutes on 429', async () => {
    login.mockRejectedValue(
      new ApiError({ status: 429, code: 'RATE_LIMITED', message: 'x', retryAfter: 541 }),
    );
    renderApp('/login');
    fill();
    submit();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Too many failed attempts. Try again in 10 minutes.',
    );
  });

  it('formats the lockout message', () => {
    expect(tooManyAttempts(30)).toBe('Too many failed attempts. Try again in 1 minute.');
    expect(tooManyAttempts(900)).toBe('Too many failed attempts. Try again in 15 minutes.');
    expect(tooManyAttempts(null)).toBe(TOO_MANY_ATTEMPTS_LATER);
  });

  it('shows "Service unavailable" on a network error', async () => {
    login.mockRejectedValue(
      new ApiError({ status: 0, code: 'NETWORK_ERROR', message: SERVICE_UNAVAILABLE }),
    );
    renderApp('/login');
    fill();
    submit();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(SERVICE_UNAVAILABLE);
    expect(alert).not.toHaveTextContent('Reference');
  });

  it('shows "Service unavailable" with the reference on 5xx', async () => {
    login.mockRejectedValue(
      new ApiError({
        status: 503,
        code: 'INTERNAL_ERROR',
        message: SERVICE_UNAVAILABLE,
        requestId: 'r-503',
      }),
    );
    renderApp('/login');
    fill();
    submit();
    expect(await screen.findByRole('alert')).toHaveTextContent('Reference: r-503');
  });

  it('shows other API messages as they come', async () => {
    login.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'VALIDATION_ERROR',
        message: 'Invalid request.',
        requestId: 'r-422',
      }),
    );
    renderApp('/login');
    fill('ab', 'pw');
    submit();
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid request.');
  });

  it('disables submit while the request is in flight and when fields are empty', async () => {
    let resolve: (value: typeof ok) => void = () => {};
    login.mockReturnValue(new Promise((r) => (resolve = r)));
    renderApp('/login');
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled();
    fill();
    submit();
    expect(await screen.findByRole('button', { name: 'Signing in…' })).toBeDisabled();
    resolve(ok);
    expect(
      await screen.findByRole('heading', { name: 'Inventory Dashboard' }, { timeout: 5000 }),
    ).toBeInTheDocument();
  });

  it('shows and hides the password', () => {
    renderApp('/login');
    const input = screen.getByLabelText(/^password/i);
    expect(input).toHaveAttribute('type', 'password');
    fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(input).toHaveAttribute('type', 'text');
    fireEvent.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(input).toHaveAttribute('type', 'password');
  });

  it('logging out returns to the login page', async () => {
    login.mockResolvedValue(ok);
    renderApp('/login');
    fill();
    submit();
    fireEvent.click(await screen.findByRole('button', { name: 'Log out' }));
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument();
  });
});
