import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../api/client';
import * as endpoints from '../../api/endpoints';
import { mockDashboardApi } from '../../test/dashboardFixtures';
import { mockProductApi, PRODUCT_PAGE } from '../../test/productFixtures';
import { renderPage } from '../../test/utils';
import ProductList, { UNKNOWN_SUPPLIER } from './ProductList';

vi.mock('../../api/endpoints');
const api = vi.mocked(endpoints);
const location = () => screen.getByTestId('location').textContent;
const lastQuery = () => api.getProducts.mock.calls.at(-1)?.[0];

beforeEach(() => {
  vi.clearAllMocks();
  mockDashboardApi(endpoints);
  mockProductApi(endpoints);
});

function render(path = '/products') {
  return renderPage(path, '/products', <ProductList />);
}

describe('Product catalogue', () => {
  it('lists products with links, roll-up risk, money and flag chips', async () => {
    render();
    const panel = await screen.findByRole('region', { name: 'Product catalogue' });
    const link = await within(panel).findByRole('link', { name: 'SKU-004' });
    expect(link).toHaveAttribute('href', '/products/154');
    const row = link.closest('tr') as HTMLElement;
    expect(within(row).getByRole('img', { name: 'Risk: CRITICAL' })).toBeInTheDocument();
    expect(within(row).getByText('WH-MUM')).toBeInTheDocument();
    expect(within(row).getByText('₹69,67,996.16')).toBeInTheDocument();
    expect(within(row).getByText('High demand')).toBeInTheDocument();
    const old = within(panel).getByText('SKU-022').closest('tr') as HTMLElement;
    expect(within(old).getByText('Dead stock')).toBeInTheDocument();
    expect(within(old).queryByText('Slow-moving')).not.toBeInTheDocument();
    expect(within(old).getByText('No recent demand')).toBeInTheDocument();
    expect(within(panel).getByText('1–25 of 50')).toBeInTheDocument();
    expect(lastQuery()).toMatchObject({ sort: 'sku', order: 'asc', page: 1, page_size: 25 });
  });

  it('debounces the search: one request after typing stops, and q in the URL', async () => {
    render();
    await screen.findByText('SKU-004');
    const before = api.getProducts.mock.calls.length;
    const box = screen.getByRole('textbox', { name: 'Search SKU or name' });
    for (const text of ['s', 'sk', 'sku', 'sku-', 'sku-0', 'sku-00']) {
      fireEvent.change(box, { target: { value: text } });
    }
    await waitFor(() => expect(location()).toBe('/products?q=sku-00'), { timeout: 2000 });
    await waitFor(() => expect(lastQuery()).toMatchObject({ q: 'sku-00', page: 1 }));
    const searches = api.getProducts.mock.calls.slice(before).map(([query]) => query.q);
    expect(searches).toEqual(['sku-00']);
  });

  it('the clear button removes the search', async () => {
    render('/products?q=yoga');
    const box = await screen.findByRole('textbox', { name: 'Search SKU or name' });
    expect(box).toHaveValue('yoga');
    await waitFor(() => expect(lastQuery()).toMatchObject({ q: 'yoga' }));
    fireEvent.click(screen.getByRole('button', { name: 'Clear search' }));
    await waitFor(() => expect(location()).toBe('/products'));
    expect(box).toHaveValue('');
    await waitFor(() => expect(lastQuery()?.q).toBeUndefined());
    // The pending debounce must not bring the old query back.
    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(location()).toBe('/products');
  });

  it('risk chips build repeated risk_class params in severity order', async () => {
    render();
    await screen.findByText('SKU-004');
    const group = screen.getByRole('group', { name: 'Risk class filter' });
    fireEvent.click(within(group).getByRole('button', { name: 'CRITICAL' }));
    fireEvent.click(within(group).getByRole('button', { name: 'STOCKOUT' }));
    await waitFor(() =>
      expect(location()).toBe('/products?risk_class=STOCKOUT&risk_class=CRITICAL'),
    );
    await waitFor(() => expect(lastQuery()?.risk_class).toEqual(['STOCKOUT', 'CRITICAL']));
    expect(within(group).getByRole('button', { name: 'CRITICAL' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    fireEvent.click(within(group).getByRole('button', { name: 'STOCKOUT' }));
    await waitFor(() => expect(location()).toBe('/products?risk_class=CRITICAL'));
  });

  it('sortable headers send sort and order', async () => {
    render();
    await screen.findByText('SKU-004');
    fireEvent.click(screen.getByRole('button', { name: 'Name' }));
    await waitFor(() => expect(location()).toBe('/products?sort=name&order=asc'));
    await waitFor(() => expect(lastQuery()).toMatchObject({ sort: 'name', order: 'asc' }));
    fireEvent.click(screen.getByRole('button', { name: 'Name' }));
    await waitFor(() => expect(lastQuery()).toMatchObject({ sort: 'name', order: 'desc' }));
    fireEvent.click(screen.getByRole('button', { name: 'Risk' }));
    await waitFor(() => expect(lastQuery()).toMatchObject({ sort: 'risk', order: 'asc' }));
  });

  it('supplier, slow-moving and warehouse filters go into the request', async () => {
    render('/products?supplier_id=19&slow_moving=true&warehouse_id=10');
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ supplier_id: 19, slow_moving: true, warehouse_id: 10 }),
    );
    fireEvent.click(screen.getByRole('switch', { name: 'Slow-moving only' }));
    await waitFor(() => expect(lastQuery()?.slow_moving).toBeUndefined());
    fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Supplier' }));
    fireEvent.click(within(await screen.findByRole('listbox')).getByText('All suppliers'));
    await waitFor(() => expect(lastQuery()?.supplier_id).toBeUndefined());
  });

  it('an unknown supplier id falls back to all suppliers with a notice', async () => {
    render('/products?supplier_id=999');
    expect(await screen.findByText(UNKNOWN_SUPPLIER)).toBeInTheDocument();
    await waitFor(() => expect(location()).toBe('/products'));
    expect(api.getProducts).not.toHaveBeenCalledWith(
      expect.objectContaining({ supplier_id: 999 }),
      expect.anything(),
    );
  });

  it('shows the empty-result state and keeps sort/page from the URL', async () => {
    api.getProducts.mockResolvedValue({ ...PRODUCT_PAGE, items: [], total: 0 });
    render('/products?q=zzz&sort=days_of_cover&order=desc&page=1');
    expect(await screen.findByText('No products match these filters.')).toBeInTheDocument();
    expect(lastQuery()).toMatchObject({ q: 'zzz', sort: 'days_of_cover', order: 'desc' });
  });

  it('shows errors with the reference and the no-snapshot state', async () => {
    api.getProducts.mockRejectedValueOnce(
      new ApiError({
        status: 500,
        code: 'INTERNAL_ERROR',
        message: 'Service unavailable. Try again later.',
        requestId: 'r-p',
      }),
    );
    const { unmount } = render();
    expect(await screen.findByText('Reference: r-p')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('SKU-004')).toBeInTheDocument();
    unmount();
    api.getProducts.mockRejectedValue(
      new ApiError({ status: 409, code: 'CONFLICT', message: 'No analytics snapshot available.' }),
    );
    render();
    expect(await screen.findByText('No verified analytics snapshot yet.')).toBeInTheDocument();
  });
});
