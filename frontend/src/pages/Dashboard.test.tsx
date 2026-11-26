import { ThemeProvider } from '@mui/material/styles';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';

import { ApiError } from '../api/client';
import * as endpoints from '../api/endpoints';
import { AuthContext } from '../auth/AuthContext';
import ApiErrorSnackbarProvider from '../components/ApiErrorSnackbar';
import { ChartWidthContext } from '../components/ChartFrame';
import {
  DISTRIBUTION,
  mockDashboardApi,
  riskRow,
  STOCKOUT_PAGE,
  SUMMARY,
  TREND,
} from '../test/dashboardFixtures';
import { fakeAuth, fakeSession } from '../test/utils';
import { RISK_CLASSES, theme } from '../theme/theme';
import Dashboard from './Dashboard';
import { ASK_ADMIN, NO_SNAPSHOT } from './dashboard/EmptySnapshotState';
import { UNKNOWN_CATEGORY, UNKNOWN_WAREHOUSE } from './dashboard/FiltersBar';
import { TILES } from './dashboard/KpiRow';
import { CONFIRM_TEXT, LOCK_HELD } from './dashboard/RecalculateButton';
import { SUM_LABEL } from './dashboard/SalesTrendChart';
import { CAPTION, STALE_NOTICE } from './dashboard/TopRiskTable';

vi.mock('../api/endpoints');

const api = vi.mocked(endpoints);

function Location() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname + location.search}</output>;
}

function renderDashboard(path = '/dashboard', role: 'ADMIN' | 'ANALYST' = 'ADMIN') {
  return render(
    <ThemeProvider theme={theme}>
      <ApiErrorSnackbarProvider>
        <AuthContext.Provider value={fakeAuth(fakeSession(role))}>
          <ChartWidthContext.Provider value={640}>
            <MemoryRouter initialEntries={[path]}>
              <Routes>
                <Route
                  path="/dashboard"
                  element={
                    <>
                      <Dashboard />
                      <Location />
                    </>
                  }
                />
              </Routes>
            </MemoryRouter>
          </ChartWidthContext.Provider>
        </AuthContext.Provider>
      </ApiErrorSnackbarProvider>
    </ThemeProvider>,
  );
}

const panel = (name: string) => screen.getByRole('region', { name });
const conflict = (message: string, details: unknown = null, requestId = 'r-409') =>
  new ApiError({ status: 409, code: 'CONFLICT', message, details, requestId });
const location = () => screen.getByTestId('location').textContent;

async function chooseOption(label: string, option: string) {
  fireEvent.mouseDown(screen.getByRole('combobox', { name: label }));
  fireEvent.click(within(await screen.findByRole('listbox')).getByText(option));
}

beforeEach(() => {
  vi.clearAllMocks();
  mockDashboardApi(endpoints);
});

describe('KPI row (FR-A1, FR-A5)', () => {
  it('shows the canonical seed-42 values with the right formatting', async () => {
    renderDashboard();
    const kpis = await screen.findByRole('region', { name: 'Key figures' });
    const expected: Record<string, string> = {
      'Total products': '50',
      'Total units': '73,484',
      'Inventory value': '₹8,99,44,367.37',
      'Low-stock products': '7',
      'Stockout-risk products': '15',
      'Slow-moving products': '11',
    };
    for (const [label, value] of Object.entries(expected)) {
      await waitFor(() =>
        expect(within(kpis).getByRole('region', { name: label })).toHaveTextContent(value),
      );
    }
    expect(TILES.map((tile) => tile.label)).toEqual(Object.keys(expected));
  });

  it('carries the definitions as tooltips', async () => {
    renderDashboard();
    const info = await screen.findByRole('img', { name: 'About Stockout-risk products' });
    fireEvent.mouseOver(info);
    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      'Stockout risk = Stockout + Critical + High',
    );
    fireEvent.mouseOut(info);
    fireEvent.mouseOver(screen.getByRole('img', { name: 'About Low-stock products' }));
    await waitFor(() =>
      expect(screen.getByRole('tooltip')).toHaveTextContent('Low stock = High + Medium'),
    );
  });

  it('shows the snapshot line and Verified badges with the time zone and data-as-of date', async () => {
    renderDashboard();
    const line = await screen.findByTestId('snapshot-line');
    expect(line.textContent).toMatch(
      /^Verified · calculated 25 Nov 2026, \d\d:\d\d \S+ · data as of 30 Sept 2026$/,
    );
    for (const name of ['Key figures', 'Sales trend', 'Risk distribution', 'Top 10 at risk']) {
      expect(await within(panel(name)).findByTestId('verified-badge')).toHaveTextContent(
        /^Verified · /,
      );
    }
    expect(within(panel('Sales trend')).getByTestId('verified-badge')).toHaveTextContent(
      'Verified · sales to 30 Sept 2026',
    );
  });
});

describe('filters (FR-A4)', () => {
  it('selecting a warehouse updates the URL and refetches with warehouse_id', async () => {
    renderDashboard();
    await screen.findByText('₹8,99,44,367.37');
    await chooseOption('Warehouse', 'WH-MUM – Mumbai DC');
    await waitFor(() => expect(location()).toBe('/dashboard?warehouse_id=10'));
    await waitFor(() =>
      expect(api.getDashboardSummary).toHaveBeenLastCalledWith(
        { warehouse_id: 10, category_id: undefined },
        expect.any(AbortSignal),
      ),
    );
    expect(api.getSalesTrend).toHaveBeenLastCalledWith(
      expect.objectContaining({ warehouse_id: 10, days: 90 }),
      expect.any(AbortSignal),
    );
    expect(api.getRiskDistribution).toHaveBeenLastCalledWith(
      expect.objectContaining({ warehouse_id: 10 }),
      expect.any(AbortSignal),
    );
    expect(api.getStockoutRisk).toHaveBeenLastCalledWith(
      expect.objectContaining({ warehouse_id: 10, page_size: 10 }),
      expect.any(AbortSignal),
    );
    expect(screen.getByText('Warehouse: WH-MUM')).toBeInTheDocument();
  });

  it('pre-selects filters from the URL', async () => {
    renderDashboard('/dashboard?warehouse_id=10&category_id=1');
    expect(await screen.findByText('Warehouse: WH-MUM')).toBeInTheDocument();
    expect(screen.getByText('Category: Sports')).toBeInTheDocument();
    await waitFor(() =>
      expect(api.getDashboardSummary).toHaveBeenCalledWith(
        { warehouse_id: 10, category_id: 1 },
        expect.any(AbortSignal),
      ),
    );
    // Never fetched with unvalidated filters first.
    expect(api.getDashboardSummary).toHaveBeenCalledTimes(1);
  });

  it('an unknown or malformed id falls back to All with a notice', async () => {
    renderDashboard('/dashboard?warehouse_id=999&category_id=abc');
    expect(await screen.findByText(UNKNOWN_WAREHOUSE)).toBeInTheDocument();
    expect(screen.getByText(UNKNOWN_CATEGORY)).toBeInTheDocument();
    await waitFor(() => expect(location()).toBe('/dashboard'));
    await waitFor(() =>
      expect(api.getDashboardSummary).toHaveBeenCalledWith(
        { warehouse_id: undefined, category_id: undefined },
        expect.any(AbortSignal),
      ),
    );
    expect(api.getDashboardSummary).not.toHaveBeenCalledWith(
      expect.objectContaining({ warehouse_id: 999 }),
      expect.anything(),
    );
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(screen.queryByText(UNKNOWN_WAREHOUSE, { exact: false })).not.toBeInTheDocument();
  });

  it('Clear filters and chip delete remove the filters', async () => {
    renderDashboard('/dashboard?warehouse_id=10&category_id=2');
    fireEvent.click(await screen.findByRole('button', { name: 'Clear filters' }));
    await waitFor(() => expect(location()).toBe('/dashboard'));
    expect(screen.queryByRole('button', { name: 'Clear filters' })).not.toBeInTheDocument();
    await chooseOption('Category', 'Home');
    await waitFor(() => expect(location()).toBe('/dashboard?category_id=2'));
    const chip = screen.getByText('Category: Home').closest('.MuiChip-root') as HTMLElement;
    fireEvent.click(within(chip).getByTestId('CancelIcon'));
    await waitFor(() => expect(location()).toBe('/dashboard'));
    await chooseOption('Warehouse', 'WH-DEL – Delhi DC');
    await chooseOption('Warehouse', 'All warehouses');
    await waitFor(() => expect(location()).toBe('/dashboard'));
  });

  it('still works if the reference lists fail (filters pass through)', async () => {
    api.getWarehouses.mockRejectedValue(
      new ApiError({ status: 0, code: 'NETWORK_ERROR', message: 'x' }),
    );
    renderDashboard('/dashboard?warehouse_id=10');
    await waitFor(() =>
      expect(api.getDashboardSummary).toHaveBeenCalledWith(
        expect.objectContaining({ warehouse_id: 10 }),
        expect.any(AbortSignal),
      ),
    );
  });
});

describe('sales trend (FR-A2)', () => {
  it('toggles 30/60/90 days and refetches', async () => {
    renderDashboard();
    await waitFor(() =>
      expect(api.getSalesTrend).toHaveBeenCalledWith(
        expect.objectContaining({ days: 90 }),
        expect.any(AbortSignal),
      ),
    );
    fireEvent.click(screen.getByRole('button', { name: '30 days' }));
    await waitFor(() =>
      expect(api.getSalesTrend).toHaveBeenLastCalledWith(
        expect.objectContaining({ days: 30 }),
        expect.any(AbortSignal),
      ),
    );
    fireEvent.click(screen.getByRole('button', { name: '60 days' }));
    await waitFor(() =>
      expect(api.getSalesTrend).toHaveBeenLastCalledWith(
        expect.objectContaining({ days: 60 }),
        expect.any(AbortSignal),
      ),
    );
    expect(screen.getByRole('button', { name: '60 days' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('labels the presentation sum, which equals the sum of the series', async () => {
    renderDashboard();
    const sum = await screen.findByTestId('trend-sum');
    // 10 + 20 + 1234 units; 100.10 + 200.20 + 0.05 revenue.
    expect(sum).toHaveTextContent(`${SUM_LABEL}: 1,264 units · ₹300.35 revenue`);
    const trend = panel('Sales trend');
    expect(within(trend).getByRole('img').getAttribute('aria-label')).toContain(
      '1,264 units in total',
    );
    expect(within(trend).getByText('Units sold')).toBeInTheDocument();
    expect(within(trend).getAllByRole('row')).toHaveLength(TREND.series.length + 1);
  });

  it('shows "No data" for an empty series', async () => {
    api.getSalesTrend.mockResolvedValue({ ...TREND, series: [] });
    renderDashboard();
    expect(
      await within(await screen.findByRole('region', { name: 'Sales trend' })).findByText(
        'No data',
      ),
    ).toBeInTheDocument();
  });
});

describe('risk distribution (FR-A3)', () => {
  it('draws six bars in severity order, each with class and count', async () => {
    renderDashboard();
    const chart = await screen.findByRole('region', { name: 'Risk distribution' });
    await within(chart).findByText('STOCKOUT: 3');
    const labels = [...chart.querySelectorAll('.recharts-label-list text')].map(
      (t) => t.textContent,
    );
    expect(labels).toEqual([
      'STOCKOUT: 3',
      'CRITICAL: 8',
      'HIGH: 4',
      'MEDIUM: 3',
      'OVERSTOCK: 11',
      'LOW: 121',
    ]);
    const fills = [...chart.querySelectorAll('.recharts-bar-rectangle path')].map((p) =>
      p.getAttribute('fill'),
    );
    expect(fills).toEqual(RISK_CLASSES.map((risk) => theme.risk[risk].background));
    const legend = within(chart).getByRole('list', { name: 'Risk legend' });
    for (const risk of RISK_CLASSES) {
      expect(within(legend).getByRole('img', { name: `Risk: ${risk}` })).toBeInTheDocument();
    }
  });

  it('switches between Locations and Products', async () => {
    renderDashboard();
    const chart = await screen.findByRole('region', { name: 'Risk distribution' });
    await within(chart).findByText('LOW: 121');
    fireEvent.click(within(chart).getByRole('button', { name: 'Products' }));
    expect(await within(chart).findByText('LOW: 25')).toBeInTheDocument();
    expect(within(chart).getByText('CRITICAL: 6')).toBeInTheDocument();
    expect(within(chart).getByText('Products (most severe warehouse)')).toBeInTheDocument();
    fireEvent.click(within(chart).getByRole('button', { name: 'Locations' }));
    expect(await within(chart).findByText('LOW: 121')).toBeInTheDocument();
  });

  it('shows "No data" when every count is zero', async () => {
    const zero = Object.fromEntries(RISK_CLASSES.map((risk) => [risk, 0]));
    api.getRiskDistribution.mockResolvedValue({ ...DISTRIBUTION, rows: zero, products: zero });
    renderDashboard();
    const chart = await screen.findByRole('region', { name: 'Risk distribution' });
    expect(await within(chart).findByText('No data')).toBeInTheDocument();
  });
});

describe('top 10 at risk (FR-A3)', () => {
  it('shows at most 10 rows with a RiskBadge each and "—" for no stockout day', async () => {
    api.getStockoutRisk.mockResolvedValue({
      ...STOCKOUT_PAGE,
      items: [...STOCKOUT_PAGE.items, riskRow(11)],
    });
    renderDashboard();
    const table = await screen.findByRole('region', { name: 'Top 10 at risk' });
    await within(table).findByText('SKU-001');
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(10);
    expect(within(rows[0]).getByRole('img', { name: 'Risk: STOCKOUT' })).toBeInTheDocument();
    expect(within(rows[0]).getByText('Day 0')).toBeInTheDocument();
    expect(within(rows[9]).getByRole('img', { name: 'Risk: HIGH' })).toBeInTheDocument();
    expect(within(rows[9]).getByText('—')).toBeInTheDocument();
    expect(within(table).getByText(CAPTION)).toBeInTheDocument();
    expect(within(table).queryByRole('button', { name: /next page/i })).not.toBeInTheDocument();
    // P4-03: the SKU opens the product page on the row's warehouse.
    expect(within(rows[0]).getByRole('link', { name: 'SKU-001' })).toHaveAttribute(
      'href',
      '/products/151?warehouse_id=10',
    );
  });
});

describe('recalculate (FR-B5)', () => {
  it('is hidden without recalculate_analytics', async () => {
    renderDashboard('/dashboard', 'ANALYST');
    await screen.findByText('₹8,99,44,367.37');
    expect(screen.queryByRole('button', { name: /recalculate/i })).not.toBeInTheDocument();
  });

  it('confirm -> POST -> snackbar -> every section reloads', async () => {
    let finish: (value: Awaited<ReturnType<typeof endpoints.recalculate>>) => void = () => {};
    api.recalculate.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    renderDashboard();
    await screen.findByText('₹8,99,44,367.37');
    const counts = () =>
      [
        api.getDashboardSummary,
        api.getSalesTrend,
        api.getRiskDistribution,
        api.getStockoutRisk,
      ].map((fn) => fn.mock.calls.length);
    const before = counts();
    fireEvent.click(screen.getByRole('button', { name: 'Recalculate' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent(CONFIRM_TEXT);
    fireEvent.click(within(dialog).getByRole('button', { name: 'Recalculate' }));
    expect(await screen.findByRole('button', { name: 'Recalculating…' })).toBeDisabled();
    await act(async () =>
      finish({
        snapshot_id: 9,
        data_as_of_date: '2026-09-30',
        row_count: 150,
        risk_distribution: DISTRIBUTION.rows,
        duration_ms: 92,
      }),
    );
    expect(await screen.findByText('Snapshot 9 created (150 rows, 92 ms)')).toBeInTheDocument();
    await waitFor(() => counts().forEach((n, i) => expect(n).toBe(before[i] + 1)));
    expect(api.recalculate).toHaveBeenCalledTimes(1);
  });

  it('cancel does nothing', async () => {
    renderDashboard();
    fireEvent.click(await screen.findByRole('button', { name: 'Recalculate' }));
    fireEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Cancel' }),
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(api.recalculate).not.toHaveBeenCalled();
  });

  it('a held lock (409) shows the message', async () => {
    api.recalculate.mockRejectedValue(conflict(LOCK_HELD));
    renderDashboard();
    fireEvent.click(await screen.findByRole('button', { name: 'Recalculate' }));
    fireEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Recalculate' }),
    );
    expect(await screen.findByText(LOCK_HELD)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Recalculate' })).toBeEnabled();
  });

  it('other failures show the error snackbar with the reference; 403 is left to the interceptor', async () => {
    api.recalculate.mockRejectedValueOnce(
      new ApiError({
        status: 409,
        code: 'CONFLICT',
        message: 'No sales data available.',
        requestId: 'r-1',
      }),
    );
    renderDashboard();
    fireEvent.click(await screen.findByRole('button', { name: 'Recalculate' }));
    fireEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Recalculate' }),
    );
    expect(await screen.findByText('No sales data available.')).toBeInTheDocument();
    expect(screen.getByText('Reference: r-1')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    api.recalculate.mockRejectedValueOnce(
      new ApiError({ status: 403, code: 'FORBIDDEN', message: 'Forbidden.' }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Recalculate' }));
    fireEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Recalculate' }),
    );
    await waitFor(() => expect(api.recalculate).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('Forbidden.')).not.toBeInTheDocument();
  });
});

describe('empty, stale and error states (7.5)', () => {
  it('no snapshot: admin sees "Run first calculation", which recalculates', async () => {
    api.getDashboardSummary.mockRejectedValueOnce(
      conflict('No analytics snapshot available. Run a recalculation.'),
    );
    api.recalculate.mockResolvedValue({
      snapshot_id: 1,
      data_as_of_date: '2026-09-30',
      row_count: 150,
      risk_distribution: DISTRIBUTION.rows,
      duration_ms: 90,
    });
    renderDashboard();
    expect(await screen.findByText(NO_SNAPSHOT)).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Key figures' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Run first calculation' }));
    fireEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Recalculate' }),
    );
    expect(await screen.findByText('₹8,99,44,367.37')).toBeInTheDocument();
    expect(screen.queryByText(NO_SNAPSHOT)).not.toBeInTheDocument();
  });

  it('no snapshot from the distribution also shows the page-level state; analyst is told to ask', async () => {
    api.getRiskDistribution.mockRejectedValue(
      conflict('No analytics snapshot available. Run a recalculation.'),
    );
    renderDashboard('/dashboard', 'ANALYST');
    expect(await screen.findByText(NO_SNAPSHOT)).toBeInTheDocument();
    expect(screen.getByText(ASK_ADMIN)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /calculation/i })).not.toBeInTheDocument();
  });

  it('stale top 10 shows the section notice while the other sections render', async () => {
    api.getStockoutRisk.mockRejectedValue(
      conflict('Underlying data has changed since this snapshot. Run a recalculation.', {
        fields: ['available'],
      }),
    );
    renderDashboard();
    const table = await screen.findByRole('region', { name: 'Top 10 at risk' });
    expect(await within(table).findByText(STALE_NOTICE)).toBeInTheDocument();
    expect(within(table).getByRole('button', { name: 'Recalculate' })).toBeInTheDocument();
    expect(await screen.findByText('₹8,99,44,367.37')).toBeInTheDocument();
    expect(await screen.findByText('STOCKOUT: 3')).toBeInTheDocument();
  });

  it('stale top 10 for an analyst has no Recalculate action', async () => {
    api.getStockoutRisk.mockRejectedValue(conflict('changed', { fields: ['available'] }));
    renderDashboard('/dashboard', 'ANALYST');
    const table = await screen.findByRole('region', { name: 'Top 10 at risk' });
    expect(await within(table).findByText(STALE_NOTICE)).toBeInTheDocument();
    expect(within(table).queryByRole('button')).not.toBeInTheDocument();
  });

  it('a section error shows its request id and Retry works; other sections are unaffected', async () => {
    api.getSalesTrend.mockRejectedValueOnce(
      new ApiError({
        status: 500,
        code: 'INTERNAL_ERROR',
        message: 'Service unavailable. Try again later.',
        requestId: 'r-500',
      }),
    );
    renderDashboard();
    const trend = await screen.findByRole('region', { name: 'Sales trend' });
    expect(await within(trend).findByText('Reference: r-500')).toBeInTheDocument();
    expect(await screen.findByText('₹8,99,44,367.37')).toBeInTheDocument();
    expect(await screen.findByText('SKU-001')).toBeInTheDocument();
    fireEvent.click(within(trend).getByRole('button', { name: 'Retry' }));
    expect(await within(trend).findByTestId('trend-sum')).toBeInTheDocument();
  });

  it('errors in the KPI, distribution and top-10 sections each stay inside their section', async () => {
    const fail = (id: string) =>
      new ApiError({
        status: 404,
        code: 'NOT_FOUND',
        message: 'Unknown warehouse_id.',
        requestId: id,
      });
    api.getDashboardSummary.mockRejectedValue(fail('r-kpi'));
    api.getRiskDistribution.mockRejectedValue(fail('r-dist'));
    api.getStockoutRisk.mockRejectedValue(fail('r-top'));
    renderDashboard();
    expect(await within(panel('Key figures')).findByText('Reference: r-kpi')).toBeInTheDocument();
    expect(
      await within(panel('Risk distribution')).findByText('Reference: r-dist'),
    ).toBeInTheDocument();
    expect(
      await within(panel('Top 10 at risk')).findByText('Reference: r-top'),
    ).toBeInTheDocument();
    expect(await within(panel('Sales trend')).findByTestId('trend-sum')).toBeInTheDocument();
  });

  it('shows skeletons while loading', () => {
    api.getDashboardSummary.mockReturnValue(new Promise(() => {}));
    renderDashboard();
    expect(screen.getAllByTestId('kpi-skeleton')).toHaveLength(6);
    expect(SUMMARY.total_products).toBe(50);
  });
});
