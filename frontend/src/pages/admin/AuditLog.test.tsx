import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../api/client';
import * as endpoints from '../../api/endpoints';
import type { AuditLogItem } from '../../api/types';
import { fakeAuth, fakeSession, preloadPages, renderRoutes } from '../../test/utils';
import { toQuery } from './AuditLog';

vi.mock('../../api/endpoints', () => ({
  login: vi.fn(),
  getMe: vi.fn(),
  getHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  getAuditLog: vi.fn(),
}));

// Warm the lazily loaded pages so a cold module graph never eats the findBy window.
beforeAll(() => preloadPages(), 60_000);

const getAuditLog = vi.mocked(endpoints.getAuditLog);

function item(id: number, overrides: Partial<AuditLogItem> = {}): AuditLogItem {
  return {
    id,
    occurred_at: '2026-11-25T16:10:00Z',
    user_id: 1,
    username: 'admin',
    action: 'ANALYTICS_RECALCULATED',
    entity_type: 'metrics_snapshot',
    entity_id: String(id),
    details: { row_count: 150, triggered_by: 'api:admin' },
    request_id: `req-${id}`,
    ip_address: '127.0.0.1',
    ...overrides,
  };
}

function page(items: AuditLogItem[], pageNo = 1, pageSize = 25, total = 60) {
  return { items, page: pageNo, page_size: pageSize, total };
}

function render() {
  return renderRoutes('/admin/audit-log', fakeAuth(fakeSession('ADMIN')));
}

describe('Admin › Audit log', () => {
  beforeEach(() => {
    getAuditLog
      .mockReset()
      .mockImplementation(async (query) =>
        page(
          [
            item(query.page === 2 ? 26 : 1),
            item(2, { username: null, entity_type: null, request_id: null, ip_address: null }),
          ],
          query.page,
          query.page_size,
        ),
      );
  });

  it('renders the rows with time, user, action, entity, request id and IP', async () => {
    render();
    expect(await screen.findByText('req-1')).toBeInTheDocument();
    const row = screen.getByText('req-1').closest('tr') as HTMLElement;
    expect(within(row).getByText('admin')).toBeInTheDocument();
    expect(within(row).getByText('ANALYTICS_RECALCULATED')).toBeInTheDocument();
    expect(within(row).getByText('metrics_snapshot · 1')).toBeInTheDocument();
    expect(within(row).getByText('127.0.0.1')).toBeInTheDocument();
    expect(screen.getByText('system')).toBeInTheDocument();
    expect(getAuditLog).toHaveBeenCalledWith({ page: 1, page_size: 25 });
  });

  it('paginates on the server and changes page size', async () => {
    render();
    await screen.findByText('req-1');
    fireEvent.click(screen.getByRole('button', { name: /next page/i }));
    expect(await screen.findByText('req-26')).toBeInTheDocument();
    expect(getAuditLog).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 2, page_size: 25 }),
    );
    fireEvent.mouseDown(screen.getByRole('combobox'));
    fireEvent.click(within(screen.getByRole('listbox')).getByText('100'));
    await waitFor(() =>
      expect(getAuditLog).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 1, page_size: 100 }),
      ),
    );
  });

  it('expands a row to show details as JSON text', async () => {
    getAuditLog.mockResolvedValue(
      page([item(1, { details: { note: '<script>alert(1)</script>' } })], 1, 25, 1),
    );
    render();
    await screen.findByText('req-1');
    fireEvent.click(screen.getByRole('button', { name: 'Expand row' }));
    const details = screen.getByLabelText('Details of audit entry 1');
    expect(details.textContent).toBe(
      JSON.stringify({ note: '<script>alert(1)</script>' }, null, 2),
    );
    expect(details.querySelector('script')).toBeNull();
  });

  it('applies and resets filters', async () => {
    render();
    await screen.findByText('req-1');
    fireEvent.change(screen.getByLabelText('Action (exact)'), {
      target: { value: ' LOGIN_FAILED ' },
    });
    fireEvent.change(screen.getByLabelText('Entity type'), { target: { value: 'user' } });
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-11-20' } });
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-11-25' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply filters' }));
    await waitFor(() =>
      expect(getAuditLog).toHaveBeenLastCalledWith(
        expect.objectContaining({ action: 'LOGIN_FAILED', entity_type: 'user', page: 1 }),
      ),
    );
    const last = getAuditLog.mock.calls.at(-1)?.[0];
    expect(last?.from).toBe(new Date('2026-11-20T00:00:00').toISOString());
    expect(last?.to).toBe(new Date('2026-11-25T23:59:59.999').toISOString());
    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
    await waitFor(() => expect(getAuditLog).toHaveBeenLastCalledWith({ page: 1, page_size: 25 }));
    expect(screen.getByLabelText('Action (exact)')).toHaveValue('');
  });

  it('shows an inline error with the reference', async () => {
    getAuditLog.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'VALIDATION_ERROR',
        message: 'Invalid request.',
        requestId: 'r-422',
      }),
    );
    render();
    expect(await screen.findByText('Invalid request.')).toBeInTheDocument();
    expect(screen.getByText('Reference: r-422')).toBeInTheDocument();
  });

  it('shows the empty state', async () => {
    getAuditLog.mockResolvedValue(page([], 1, 25, 0));
    render();
    expect(await screen.findByText('No audit entries match these filters.')).toBeInTheDocument();
  });

  it('builds the query without empty filters', () => {
    expect(toQuery({ action: '', entityType: ' ', from: '', to: '' }, 3, 50)).toEqual({
      page: 3,
      page_size: 50,
      action: undefined,
      entity_type: undefined,
      from: undefined,
      to: undefined,
    });
  });
});
