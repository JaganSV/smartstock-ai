import { fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as endpoints from './api/endpoints';
import { SIGN_IN_AGAIN } from './auth/AuthContext';
import { NAV_ITEMS, visibleNavItems, type NavItem } from './layout/navConfig';
import { roleLabel } from './layout/AppShell';
import { fakeAuth, fakeSession, renderRoutes } from './test/utils';

vi.mock('./api/endpoints', () => ({
  login: vi.fn(),
  getMe: vi.fn(),
  getHealth: vi.fn(),
  getAuditLog: vi.fn().mockResolvedValue({ items: [], page: 1, page_size: 25, total: 0 }),
}));

const getHealth = vi.mocked(endpoints.getHealth);

describe('route guards', () => {
  beforeEach(() => {
    getHealth
      .mockReset()
      .mockResolvedValue({ status: 'ok', service: 'smartstock-backend', version: '0.1.0' });
  });

  it('RequireAuth sends a signed-out user to /login', () => {
    renderRoutes('/admin/audit-log', fakeAuth(null));
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('shows the auto sign-out notice on the login page', () => {
    renderRoutes('/dashboard', fakeAuth(null, { notice: SIGN_IN_AGAIN }));
    expect(screen.getByText(SIGN_IN_AGAIN)).toBeInTheDocument();
  });

  it('/ redirects to the dashboard', async () => {
    renderRoutes('/', fakeAuth(fakeSession('ANALYST')));
    expect(await screen.findByText('Dashboard – coming in P4-02')).toBeInTheDocument();
  });

  it('RequireCapability shows the 403 page to an analyst on the audit log', () => {
    renderRoutes('/admin/audit-log', fakeAuth(fakeSession('ANALYST')));
    expect(screen.getByRole('heading', { name: '403 – Access denied' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Audit log' })).not.toBeInTheDocument();
  });

  it('a user without view_inventory gets 403 on the dashboard', () => {
    renderRoutes('/dashboard', fakeAuth(fakeSession('ANALYST', ['ask_ai'])));
    expect(screen.getByRole('heading', { name: '403 – Access denied' })).toBeInTheDocument();
  });

  it('an unknown path shows the 404 page', async () => {
    renderRoutes('/no/such/page', fakeAuth(fakeSession('ADMIN')));
    expect(await screen.findByRole('heading', { name: '404 – Page not found' })).toBeInTheDocument();
  });

  it('a signed-in user visiting /login goes to the dashboard', async () => {
    renderRoutes('/login', fakeAuth(fakeSession('ADMIN')));
    expect(await screen.findByText('Dashboard – coming in P4-02')).toBeInTheDocument();
  });
});

describe('navigation', () => {
  beforeEach(() => {
    getHealth
      .mockReset()
      .mockResolvedValue({ status: 'ok', service: 'smartstock-backend', version: '0.1.0' });
  });

  it('shows the Audit log only with view_governance', async () => {
    renderRoutes('/dashboard', fakeAuth(fakeSession('ADMIN')));
    const nav = screen.getByRole('navigation', { name: 'Main navigation' });
    expect(within(nav).getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: 'Admin › Audit log' })).toBeInTheDocument();
    expect(await screen.findByText('Backend: ok')).toBeInTheDocument();
  });

  it('hides the Audit log from an analyst', () => {
    renderRoutes('/dashboard', fakeAuth(fakeSession('ANALYST')));
    const nav = screen.getByRole('navigation', { name: 'Main navigation' });
    expect(within(nav).getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(within(nav).queryByRole('link', { name: /Audit log/ })).not.toBeInTheDocument();
    expect(within(nav).queryByText('Admin')).not.toBeInTheDocument();
  });

  it('decides from capabilities, not the role name', () => {
    // A role string the UI has never heard of, holding view_governance, still sees the item.
    const session = fakeSession('ANALYST', ['view_inventory', 'view_governance']);
    session.user.role = 'SOMETHING_NEW';
    renderRoutes('/admin/audit-log', fakeAuth(session));
    expect(screen.getByRole('link', { name: 'Admin › Audit log' })).toBeInTheDocument();
    expect(screen.getByTestId('user-role')).toHaveTextContent('Something new');
  });

  it('collapses and expands the drawer', () => {
    renderRoutes('/dashboard', fakeAuth(fakeSession('ADMIN')));
    const nav = screen.getByRole('navigation', { name: 'Main navigation' });
    fireEvent.click(screen.getByRole('button', { name: 'Collapse navigation' }));
    expect(within(nav).queryByText('Admin')).not.toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: 'Admin › Audit log' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Expand navigation' }));
    expect(within(nav).getByText('Admin')).toBeInTheDocument();
  });

  it('logs out from the app bar', () => {
    const auth = fakeAuth(fakeSession('ADMIN'));
    renderRoutes('/dashboard', auth);
    fireEvent.click(screen.getByRole('button', { name: 'Log out' }));
    expect(auth.logout).toHaveBeenCalled();
  });

  it('shows "Backend: unavailable" when the health check fails', async () => {
    getHealth.mockReset().mockRejectedValue(new Error('down'));
    renderRoutes('/dashboard', fakeAuth(fakeSession('ADMIN')));
    expect(await screen.findByText('Backend: unavailable')).toBeInTheDocument();
  });

  it('lists only live entries the user may see', () => {
    const planned: NavItem = { ...NAV_ITEMS[0], label: 'Risk', path: '/risk', status: 'planned' };
    const items = visibleNavItems(() => true, [...NAV_ITEMS, planned]);
    expect(items.map((item) => item.label)).toEqual(['Dashboard', 'Audit log']);
    expect(visibleNavItems(() => false)).toEqual([]);
  });

  it('formats role labels for display', () => {
    expect(roleLabel('INVENTORY_MANAGER')).toBe('Inventory manager');
    expect(roleLabel('ADMIN')).toBe('Admin');
  });
});
