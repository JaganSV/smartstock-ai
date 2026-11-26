import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../api/client';
import * as endpoints from '../../api/endpoints';
import { mockDashboardApi } from '../../test/dashboardFixtures';
import {
  MUM_ROW,
  mockProductApi,
  SKU004_DETAIL,
  SKU004_EXPLAIN,
  SKU004_RISK,
  SKU024_RISK,
} from '../../test/productFixtures';
import { renderPage } from '../../test/utils';
import { STALE_NOTICE } from '../dashboard/StaleNotice';
import { NO_STOCKOUT } from './detail/ProjectionChart';
import { DETERMINISTIC_LABEL, RULE_DESCRIPTIONS } from './detail/RuleTrace';
import ProductDetail, { UNKNOWN_WAREHOUSE_NOTICE } from './ProductDetail';

vi.mock('../../api/endpoints');
const api = vi.mocked(endpoints);
const location = () => screen.getByTestId('location').textContent;
const region = (name: string) => screen.getByRole('region', { name });

beforeEach(() => {
  vi.clearAllMocks();
  mockDashboardApi(endpoints);
  mockProductApi(endpoints);
});

function render(path = '/products/154', role: 'ADMIN' | 'ANALYST' = 'ADMIN') {
  return renderPage(path, '/products/:productId', <ProductDetail />, role);
}

const staleError = () =>
  new ApiError({
    status: 409,
    code: 'CONFLICT',
    message: 'Underlying data has changed since this snapshot. Run a recalculation.',
    details: { fields: ['available'] },
  });

describe('header and warehouse selection', () => {
  it('shows the product facts and the roll-up driven by its warehouse', async () => {
    render();
    expect(
      await screen.findByRole('heading', { name: 'SKU-004 · Yoga Mat 6mm' }),
    ).toBeInTheDocument();
    const facts = region('Product');
    expect(within(facts).getByText('Delta Trade Partners (fictional) (SUP-D)')).toBeInTheDocument();
    expect(within(facts).getByText('₹2,865.13')).toBeInTheDocument();
    expect(within(facts).getByText('₹4,629.10')).toBeInTheDocument();
    expect(within(facts).getByTestId('rollup')).toHaveTextContent('CRITICALdriven by WH-MUM');
    expect(screen.getByTestId('snapshot-line')).toHaveTextContent('data as of 30 Sept 2026');
  });

  it('defaults to the roll-up warehouse and fetches its risk and explanation', async () => {
    render();
    const tabs = await screen.findByRole('tablist', { name: 'Warehouse' });
    expect(
      within(tabs)
        .getAllByRole('tab')
        .map((tab) => tab.textContent),
    ).toEqual(['WH-BLRLOW', 'WH-DELLOW', 'WH-MUMCRITICAL']);
    expect(within(tabs).getByRole('tab', { selected: true })).toHaveAccessibleName(
      'WH-MUM, risk CRITICAL',
    );
    await waitFor(() =>
      expect(api.getRiskDetail).toHaveBeenCalledWith(154, 10, expect.any(AbortSignal)),
    );
    expect(api.getExplanation).toHaveBeenCalledWith(154, 10, expect.any(AbortSignal));
  });

  it('the URL warehouse_id overrides the default; switching tabs updates the URL and refetches', async () => {
    render('/products/154?warehouse_id=11');
    const tabs = await screen.findByRole('tablist', { name: 'Warehouse' });
    expect(within(tabs).getByRole('tab', { selected: true })).toHaveAccessibleName(
      'WH-BLR, risk LOW',
    );
    await waitFor(() =>
      expect(api.getRiskDetail).toHaveBeenCalledWith(154, 11, expect.any(AbortSignal)),
    );
    fireEvent.click(within(tabs).getByRole('tab', { name: 'WH-DEL, risk LOW' }));
    await waitFor(() => expect(location()).toBe('/products/154?warehouse_id=12'));
    await waitFor(() =>
      expect(api.getRiskDetail).toHaveBeenLastCalledWith(154, 12, expect.any(AbortSignal)),
    );
    expect(api.getExplanation).toHaveBeenLastCalledWith(154, 12, expect.any(AbortSignal));
    expect(screen.getByRole('region', { name: 'Metrics at WH-DEL' })).toBeInTheDocument();
  });

  it('an invalid warehouse_id falls back to the default with a notice', async () => {
    render('/products/154?warehouse_id=999');
    expect(await screen.findByText(UNKNOWN_WAREHOUSE_NOTICE)).toBeInTheDocument();
    await waitFor(() => expect(location()).toBe('/products/154'));
    await waitFor(() =>
      expect(api.getRiskDetail).toHaveBeenCalledWith(154, 10, expect.any(AbortSignal)),
    );
    expect(api.getRiskDetail).not.toHaveBeenCalledWith(154, 999, expect.anything());
  });

  it('an unknown product (404) or a malformed id shows the NotFound page', async () => {
    api.getProductDetail.mockRejectedValue(
      new ApiError({ status: 404, code: 'NOT_FOUND', message: 'Unknown product_id.' }),
    );
    const { unmount } = render('/products/99999');
    expect(
      await screen.findByRole('heading', { name: '404 – Page not found' }),
    ).toBeInTheDocument();
    unmount();
    render('/products/abc');
    expect(
      await screen.findByRole('heading', { name: '404 – Page not found' }),
    ).toBeInTheDocument();
  });
});

describe('metrics (FR-C2)', () => {
  it('shows the stored row, lead time from /risk and sigma and IP from /explain', async () => {
    render();
    const metrics = await screen.findByRole('region', { name: 'Metrics at WH-MUM' });
    const value = (label: string) => within(metrics).getByTestId(`kv-${label}`).textContent;
    expect(value('Available')).toBe('Available223');
    expect(value('On hand')).toBe('On hand242');
    expect(value('Committed')).toBe('Committed19');
    expect(value('ADS 30')).toBe('ADS 3021.5333');
    expect(value('Safety stock')).toBe('Safety stock47');
    expect(value('Reorder point')).toBe('Reorder point349');
    expect(value('Days of cover')).toBe('Days of cover10.4 days');
    expect(value('Reorder quantity')).toBe('Reorder quantity432');
    expect(value('Service level')).toBe('Service level99%');
    await waitFor(() => expect(value('Lead time')).toBe('Lead time14 days'));
    await waitFor(() => expect(value('Demand σ (30 d)')).toBe('Demand σ (30 d)5.2898'));
    expect(value('Inventory position')).toBe('Inventory position223');
  });

  it('labels safety stock and lead time overrides', async () => {
    api.getProductDetail.mockResolvedValue({
      ...SKU004_DETAIL,
      warehouses: [
        {
          ...MUM_ROW,
          safety_stock: 25,
          policy: {
            service_level: 0.95,
            review_period_days: 14,
            safety_stock_override: 25,
            lead_time_override_days: 10,
          },
        },
      ],
    });
    render();
    const metrics = await screen.findByRole('region', { name: 'Metrics at WH-MUM' });
    expect(within(metrics).getByTestId('kv-Safety stock')).toHaveTextContent('25override');
    expect(within(metrics).getByTestId('kv-Lead time')).toHaveTextContent('override');
  });
});

describe('rule trace (FR-C2, BP 7.4)', () => {
  it('shows ✓/✗ per rule, highlights the fired rule with its reason code, hides later rules', async () => {
    render();
    const panel = await screen.findByRole('region', { name: 'Why this risk class' });
    expect(within(panel).getByText(DETERMINISTIC_LABEL)).toBeInTheDocument();
    const items = await within(panel).findAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText('R1')).toBeInTheDocument();
    expect(within(items[0]).getByTitle('not matched')).toBeInTheDocument();
    expect(items[0]).not.toHaveAttribute('data-fired');
    expect(within(items[1]).getByTitle('matched')).toBeInTheDocument();
    expect(items[1]).toHaveAttribute('data-fired', 'true');
    expect(within(items[1]).getByTestId('reason-code')).toHaveTextContent(
      'R2_STOCKOUT_BEFORE_REPLENISHMENT',
    );
    expect(within(items[1]).getByText(RULE_DESCRIPTIONS.R2)).toBeInTheDocument();
    expect(within(panel).queryByText('R3')).not.toBeInTheDocument();
    // Verified panel, not the AI panel.
    expect(within(panel).getByTestId('verified-badge')).toBeInTheDocument();
    expect(screen.queryByText(/AI-generated/)).not.toBeInTheDocument();
  });
});

describe('projection chart (FR-C3)', () => {
  it('SKU-004: zero line and the Day 11 stockout marker', async () => {
    render();
    const panel = await screen.findByRole('region', { name: 'Lead-time projection' });
    expect(await within(panel).findByText('0 units')).toBeInTheDocument();
    const label = 'Projected stockout: Day 11 (11 Oct 2026)';
    expect(within(panel).getAllByText(label)).toHaveLength(2); // chart label + text legend
    expect(within(panel).getAllByText('End of lead time (L = 14 days)').length).toBeGreaterThan(0);
    expect(within(panel).queryByText(NO_STOCKOUT)).not.toBeInTheDocument();
    expect(panel.querySelectorAll('.recharts-reference-line')).toHaveLength(3);
  });

  it('SKU-024: arrival marker, later arrival listed, and the no-stockout note', async () => {
    api.getRiskDetail.mockResolvedValue(SKU024_RISK);
    render();
    const panel = await screen.findByRole('region', { name: 'Lead-time projection' });
    expect(await within(panel).findByText('Arrival +115')).toBeInTheDocument();
    expect(within(panel).getByText('Arrival: 115 units on 6 Oct 2026 (Day 6)')).toBeInTheDocument();
    expect(
      within(panel).getByText('Later arrival (after the lead time): 40 units on 20 Nov 2026'),
    ).toBeInTheDocument();
    expect(within(panel).getByText(NO_STOCKOUT)).toBeInTheDocument();
    expect(within(panel).queryByText(/Projected stockout/)).not.toBeInTheDocument();
  });
});

describe('explanations (FR-B6)', () => {
  it('are collapsed by default, then show formula, inputs and result', async () => {
    render();
    const panel = await screen.findByRole('region', { name: 'How each number is calculated' });
    const toggle = within(panel).getByRole('button', { name: /show calculations/i });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(within(panel).queryByRole('table')).not.toBeInTheDocument();
    fireEvent.click(toggle);
    const table = await within(panel).findByRole('table');
    expect(within(table).getAllByRole('row')).toHaveLength(SKU004_EXPLAIN.metrics.length + 1);
    expect(within(table).getByText('available = on_hand - committed')).toBeInTheDocument();
    expect(within(table).getByText('on_hand = 242')).toBeInTheDocument();
    expect(within(table).getByText('lead_time_override_days = null')).toBeInTheDocument();
    expect(within(table).getByText('CRITICAL')).toBeInTheDocument();
    fireEvent.click(within(panel).getByRole('button', { name: /hide calculations/i }));
    expect(within(panel).queryByRole('table')).not.toBeInTheDocument();
  });
});

describe('states', () => {
  it('a stale 409 affects only sections 4–6; the header, metrics and sales still render', async () => {
    api.getRiskDetail.mockRejectedValue(staleError());
    api.getExplanation.mockRejectedValue(staleError());
    render();
    for (const name of [
      'Why this risk class',
      'Lead-time projection',
      'How each number is calculated',
    ]) {
      expect(
        await within(await screen.findByRole('region', { name })).findByText(STALE_NOTICE),
      ).toBeInTheDocument();
    }
    expect(screen.getAllByRole('button', { name: 'Recalculate' })).toHaveLength(3);
    expect(region('Metrics at WH-MUM')).toHaveTextContent('Available223');
    expect(within(region('Metrics at WH-MUM')).getByTestId('kv-Demand σ (30 d)')).toHaveTextContent(
      '—',
    );
    expect(screen.getByRole('heading', { name: 'SKU-004 · Yoga Mat 6mm' })).toBeInTheDocument();
    expect(
      await within(region('Sales (last 90 days)')).findByTestId('trend-sum'),
    ).toBeInTheDocument();
  });

  it('stale for an analyst shows no Recalculate', async () => {
    api.getRiskDetail.mockRejectedValue(staleError());
    render('/products/154', 'ANALYST');
    expect(await screen.findAllByText(STALE_NOTICE)).toHaveLength(3);
    expect(screen.queryByRole('button', { name: /recalculate/i })).not.toBeInTheDocument();
  });

  it('a section error shows its reference and Retry, without blanking the page', async () => {
    api.getRiskDetail.mockRejectedValueOnce(
      new ApiError({
        status: 500,
        code: 'INTERNAL_ERROR',
        message: 'Service unavailable. Try again later.',
        requestId: 'r-risk',
      }),
    );
    render();
    const trace = await screen.findByRole('region', { name: 'Why this risk class' });
    expect(await within(trace).findByText('Reference: r-risk')).toBeInTheDocument();
    expect(region('Metrics at WH-MUM')).toBeInTheDocument();
    fireEvent.click(within(trace).getByRole('button', { name: 'Retry' }));
    expect(await within(trace).findByTestId('reason-code')).toBeInTheDocument();
  });

  it('product errors: no snapshot and other errors', async () => {
    api.getProductDetail.mockRejectedValueOnce(
      new ApiError({ status: 409, code: 'CONFLICT', message: 'No analytics snapshot available.' }),
    );
    const { unmount } = render();
    expect(await screen.findByText('No verified analytics snapshot yet.')).toBeInTheDocument();
    unmount();
    api.getProductDetail.mockRejectedValueOnce(
      new ApiError({
        status: 500,
        code: 'INTERNAL_ERROR',
        message: 'Service unavailable. Try again later.',
        requestId: 'r-pd',
      }),
    );
    render();
    expect(await screen.findByText('Reference: r-pd')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(
      await screen.findByRole('heading', { name: 'SKU-004 · Yoga Mat 6mm' }),
    ).toBeInTheDocument();
  });

  it('sales: scope and window toggles refetch', async () => {
    render();
    const sales = await screen.findByRole('region', { name: 'Sales (last 90 days)' });
    await waitFor(() =>
      expect(api.getProductSales).toHaveBeenCalledWith(
        154,
        { days: 90, warehouse_id: 10 },
        expect.any(AbortSignal),
      ),
    );
    fireEvent.click(within(sales).getByRole('button', { name: 'All warehouses' }));
    await waitFor(() =>
      expect(api.getProductSales).toHaveBeenLastCalledWith(
        154,
        { days: 90, warehouse_id: undefined },
        expect.any(AbortSignal),
      ),
    );
    fireEvent.click(within(sales).getByRole('button', { name: '30 days' }));
    await waitFor(() =>
      expect(api.getProductSales).toHaveBeenLastCalledWith(
        154,
        { days: 30, warehouse_id: undefined },
        expect.any(AbortSignal),
      ),
    );
    expect(screen.getByRole('region', { name: 'Sales (last 30 days)' })).toBeInTheDocument();
  });

  it('the AI slot exists but renders nothing visible', async () => {
    const { container } = render();
    await screen.findByRole('heading', { name: 'SKU-004 · Yoga Mat 6mm' });
    const slot = container.querySelector('aside[data-slot="ai-explanation"]') as HTMLElement;
    expect(slot).not.toBeNull();
    expect(slot).not.toBeVisible();
    expect(slot).toBeEmptyDOMElement();
    expect(SKU004_RISK.projection.projected_stockout_day).toBe(11);
  });
});
