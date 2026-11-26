import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './client';
import {
  getAuditLog,
  getCategories,
  getDashboardSummary,
  getHealth,
  getMe,
  getRiskDistribution,
  getSalesTrend,
  getStockoutRisk,
  getWarehouses,
  login,
  recalculate,
} from './endpoints';

vi.mock('./client', () => ({
  LOGIN_PATH: '/auth/login',
  apiClient: { get: vi.fn(), post: vi.fn() },
}));

const get = vi.mocked(apiClient.get);
const post = vi.mocked(apiClient.post);

describe('endpoints', () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue({ data: { ok: true } });
    post.mockReset().mockResolvedValue({ data: { access_token: 't' } });
  });

  it('calls health, login and me on their paths', async () => {
    expect(await getHealth()).toEqual({ ok: true });
    expect(get).toHaveBeenCalledWith('/health');
    await login({ username: 'admin', password: 'pw' });
    expect(post).toHaveBeenCalledWith('/auth/login', { username: 'admin', password: 'pw' });
    await getMe('fresh');
    expect(get).toHaveBeenLastCalledWith('/auth/me', {
      headers: { Authorization: 'Bearer fresh' },
    });
    await getMe();
    expect(get).toHaveBeenLastCalledWith('/auth/me', { headers: undefined });
  });

  it('drops empty audit-log filters', async () => {
    await getAuditLog({
      page: 2,
      page_size: 50,
      action: '',
      entity_type: null,
      from: undefined,
      to: 'x',
    });
    expect(get).toHaveBeenCalledWith('/admin/audit-log', {
      params: { page: 2, page_size: 50, to: 'x' },
    });
  });

  it('calls the dashboard, reference, risk and recalculate endpoints with filters and signal', async () => {
    const signal = new AbortController().signal;
    await getWarehouses(signal);
    expect(get).toHaveBeenLastCalledWith('/reference/warehouses', { signal });
    await getCategories(signal);
    expect(get).toHaveBeenLastCalledWith('/reference/categories', { signal });
    await getDashboardSummary({ warehouse_id: 10, category_id: undefined }, signal);
    expect(get).toHaveBeenLastCalledWith('/dashboard/summary', {
      params: { warehouse_id: 10 },
      signal,
    });
    await getSalesTrend({ days: 30, category_id: 2 }, signal);
    expect(get).toHaveBeenLastCalledWith('/dashboard/sales-trend', {
      params: { days: 30, category_id: 2 },
      signal,
    });
    await getRiskDistribution({}, signal);
    expect(get).toHaveBeenLastCalledWith('/dashboard/risk-distribution', { params: {}, signal });
    await getStockoutRisk({ page: 1, page_size: 10 }, signal);
    expect(get).toHaveBeenLastCalledWith('/risk/stockout', {
      params: { page: 1, page_size: 10 },
      signal,
    });
    await recalculate();
    expect(post).toHaveBeenLastCalledWith('/analytics/recalculate');
  });
});
