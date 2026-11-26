import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../api/client';
import * as endpoints from '../../api/endpoints';
import { mockDashboardApi, riskRow, STOCKOUT_PAGE } from '../../test/dashboardFixtures';
import { mockProductApi, SLOW_PAGE } from '../../test/productFixtures';
import { renderPage } from '../../test/utils';
import { STALE_NOTICE } from '../dashboard/StaleNotice';
import SlowMoving, { CAPTION as SLOW_CAPTION } from './SlowMoving';
import StockoutRisk, { CAPTION } from './StockoutRisk';

vi.mock('../../api/endpoints');
const api = vi.mocked(endpoints);
const location = () => screen.getByTestId('location').textContent;
const stale = () =>
  new ApiError({
    status: 409,
    code: 'CONFLICT',
    message: 'Underlying data has changed since this snapshot. Run a recalculation.',
    details: { fields: ['available'] },
    requestId: 'r-stale',
  });

beforeEach(() => {
  vi.clearAllMocks();
  mockDashboardApi(endpoints);
  mockProductApi(endpoints);
});

function bodyRows(region: HTMLElement) {
  return within(region).getAllByRole('row').slice(1) as HTMLTableRowElement[];
}

describe('Stockout risk list (FR-C1)', () => {
  it('renders rows in the API order without re-sorting', async () => {
    // Deliberately not in severity order: the page must keep the API's order.
    const items = [riskRow(9, { sku: 'SKU-HIGH', risk_class: 'HIGH' }), riskRow(1), riskRow(4)];
    api.getStockoutRisk.mockResolvedValue({ ...STOCKOUT_PAGE, items, total: 3 });
    renderPage('/risk', '/risk', <StockoutRisk />);
    const panel = await screen.findByRole('region', { name: 'Products at stockout risk' });
    await within(panel).findByText('SKU-HIGH');
    expect(bodyRows(panel).map((row) => row.cells[0].textContent)).toEqual([
      'SKU-HIGH',
      'SKU-001',
      'SKU-004',
    ]);
    expect(within(panel).getByText(CAPTION)).toBeInTheDocument();
  });

  it('links each SKU to its product page on the row warehouse and shows all columns', async () => {
    api.getStockoutRisk.mockResolvedValue({
      ...STOCKOUT_PAGE,
      items: [riskRow(1, { is_high_demand: true, reorder_qty: 1200 })],
      total: 1,
    });
    renderPage('/risk', '/risk', <StockoutRisk />);
    const link = await screen.findByRole('link', { name: 'SKU-001' });
    expect(link).toHaveAttribute('href', '/products/151?warehouse_id=10');
    const row = link.closest('tr') as HTMLElement;
    expect(within(row).getByRole('img', { name: 'Risk: STOCKOUT' })).toBeInTheDocument();
    expect(within(row).getByText('Day 0')).toBeInTheDocument();
    expect(within(row).getByText('1,200')).toBeInTheDocument();
    expect(within(row).getByText('High demand')).toBeInTheDocument();
    fireEvent.click(link);
    expect(location()).toBe('/products/151?warehouse_id=10');
  });

  it('filters and page live in the URL and drive the request', async () => {
    api.getStockoutRisk.mockResolvedValue({ ...STOCKOUT_PAGE, total: 60 });
    renderPage('/risk?page=2&page_size=50', '/risk', <StockoutRisk />);
    await waitFor(() =>
      expect(api.getStockoutRisk).toHaveBeenCalledWith(
        expect.objectContaining({ page: 2, page_size: 50 }),
        expect.any(AbortSignal),
      ),
    );
    fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Warehouse' }));
    fireEvent.click(within(await screen.findByRole('listbox')).getByText('WH-MUM – Mumbai DC'));
    // A new filter starts at page 1.
    await waitFor(() => expect(location()).toBe('/risk?page_size=50&warehouse_id=10'));
    await waitFor(() =>
      expect(api.getStockoutRisk).toHaveBeenLastCalledWith(
        { warehouse_id: 10, category_id: undefined, page: 1, page_size: 50 },
        expect.any(AbortSignal),
      ),
    );
    fireEvent.click(await screen.findByRole('button', { name: /next page/i }));
    await waitFor(() => expect(location()).toBe('/risk?page_size=50&warehouse_id=10&page=2'));
    fireEvent.mouseDown(screen.getByRole('combobox', { name: /rows per page/i }));
    fireEvent.click(within(await screen.findByRole('listbox')).getByText('25'));
    await waitFor(() => expect(location()).toBe('/risk?warehouse_id=10'));
  });

  it('a stale snapshot shows the notice with Recalculate for admins', async () => {
    api.getStockoutRisk.mockRejectedValue(stale());
    renderPage('/risk', '/risk', <StockoutRisk />);
    expect(await screen.findByText(STALE_NOTICE)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Recalculate' })).toBeInTheDocument();
  });

  it('a stale snapshot shows no Recalculate to an analyst', async () => {
    api.getStockoutRisk.mockRejectedValue(stale());
    renderPage('/risk', '/risk', <StockoutRisk />, 'ANALYST');
    expect(await screen.findByText(STALE_NOTICE)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /recalculate/i })).not.toBeInTheDocument();
  });

  it('other errors show the reference with Retry; no snapshot shows the empty state', async () => {
    api.getStockoutRisk.mockRejectedValueOnce(
      new ApiError({
        status: 500,
        code: 'INTERNAL_ERROR',
        message: 'Service unavailable. Try again later.',
        requestId: 'r-500',
      }),
    );
    const { unmount } = renderPage('/risk', '/risk', <StockoutRisk />);
    expect(await screen.findByText('Reference: r-500')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('SKU-001')).toBeInTheDocument();
    unmount();
    api.getStockoutRisk.mockRejectedValue(
      new ApiError({ status: 409, code: 'CONFLICT', message: 'No analytics snapshot available.' }),
    );
    renderPage('/risk', '/risk', <StockoutRisk />);
    expect(await screen.findByText('No verified analytics snapshot yet.')).toBeInTheDocument();
  });
});

describe('Slow-moving list', () => {
  it('shows dead-stock and slow-moving chips, both ADS values and money', async () => {
    renderPage('/risk/slow-moving', '/risk/slow-moving', <SlowMoving />);
    const panel = await screen.findByRole('region', { name: 'Slow-moving and dead stock' });
    await within(panel).findByText('SKU-022');
    const [dead, slow] = bodyRows(panel);
    expect(within(dead).getByText('Dead stock')).toBeInTheDocument();
    expect(within(dead).queryByText('Slow-moving')).not.toBeInTheDocument();
    expect(within(slow).getByText('Slow-moving')).toBeInTheDocument();
    expect(within(slow).getByText('0.1333')).toBeInTheDocument();
    expect(within(slow).getByText('0.9')).toBeInTheDocument();
    expect(within(slow).getByText('₹1,07,41,403.52')).toBeInTheDocument();
    expect(within(dead).getByRole('link', { name: 'SKU-022' })).toHaveAttribute(
      'href',
      '/products/172?warehouse_id=11',
    );
    expect(within(panel).getByText(SLOW_CAPTION)).toBeInTheDocument();
    expect(within(panel).getByText('1–11 of 11')).toBeInTheDocument();
    expect(SLOW_PAGE.total).toBe(11);
  });

  it('applies filters from the URL and handles stale and errors', async () => {
    renderPage('/risk/slow-moving?category_id=1', '/risk/slow-moving', <SlowMoving />);
    await waitFor(() =>
      expect(api.getSlowMoving).toHaveBeenCalledWith(
        { warehouse_id: undefined, category_id: 1, page: 1, page_size: 25 },
        expect.any(AbortSignal),
      ),
    );
  });

  it('shows the stale notice, an error with reference, and the empty state', async () => {
    api.getSlowMoving.mockRejectedValueOnce(stale());
    const first = renderPage('/risk/slow-moving', '/risk/slow-moving', <SlowMoving />);
    expect(await screen.findByText(STALE_NOTICE)).toBeInTheDocument();
    first.unmount();
    api.getSlowMoving.mockRejectedValueOnce(
      new ApiError({
        status: 404,
        code: 'NOT_FOUND',
        message: 'Unknown warehouse_id.',
        requestId: 'r-404',
      }),
    );
    const second = renderPage('/risk/slow-moving', '/risk/slow-moving', <SlowMoving />);
    expect(await screen.findByText('Reference: r-404')).toBeInTheDocument();
    second.unmount();
    api.getSlowMoving.mockRejectedValueOnce(
      new ApiError({ status: 409, code: 'CONFLICT', message: 'No analytics snapshot available.' }),
    );
    renderPage('/risk/slow-moving', '/risk/slow-moving', <SlowMoving />);
    expect(await screen.findByText('No verified analytics snapshot yet.')).toBeInTheDocument();
  });
});
