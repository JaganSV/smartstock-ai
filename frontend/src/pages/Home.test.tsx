import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as client from '../api/client';
import Home from './Home';

vi.mock('../api/client', () => ({ getHealth: vi.fn() }));

const getHealth = vi.mocked(client.getHealth);

describe('Home', () => {
  beforeEach(() => {
    getHealth.mockReset();
  });

  it('renders the title', async () => {
    getHealth.mockResolvedValue({ status: 'ok', service: 'smartstock-backend', version: '0.1.0' });
    render(<Home />);
    expect(screen.getByText('SmartStock AI')).toBeInTheDocument();
    expect(await screen.findByText('Backend: ok')).toBeInTheDocument();
  });

  it('shows "Backend: ok" on success', async () => {
    getHealth.mockResolvedValue({ status: 'ok', service: 'smartstock-backend', version: '0.1.0' });
    render(<Home />);
    expect(await screen.findByText('Backend: ok')).toBeInTheDocument();
  });

  it('shows "Backend: unavailable" on failure', async () => {
    getHealth.mockRejectedValue(new Error('Network Error'));
    render(<Home />);
    expect(await screen.findByText('Backend: unavailable')).toBeInTheDocument();
  });

  it('shows a loading state first', () => {
    getHealth.mockReturnValue(new Promise(() => {}));
    render(<Home />);
    expect(screen.getByText('Checking backend…')).toBeInTheDocument();
  });
});
