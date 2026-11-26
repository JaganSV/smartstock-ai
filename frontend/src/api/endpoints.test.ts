import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './client';
import { getAuditLog, getHealth, getMe, login } from './endpoints';

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
});
