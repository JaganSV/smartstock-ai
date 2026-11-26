import Alert from '@mui/material/Alert';
import Skeleton from '@mui/material/Skeleton';

import { getStockoutRisk } from '../../api/endpoints';
import type { DashboardFilters, StockoutRiskRow } from '../../api/types';
import DataTable, { type Column } from '../../components/DataTable';
import ErrorState from '../../components/ErrorState';
import RiskBadge from '../../components/RiskBadge';
import VerifiedDataPanel from '../../components/VerifiedDataPanel';
import { useApi } from '../../hooks/useApi';
import { EMPTY, formatDays, formatNumber } from '../../lib/format';
import RecalculateButton from './RecalculateButton';
import { isNoSnapshot, isStale } from './snapshotErrors';

export const TOP_N = 10;
export const STALE_NOTICE = 'Data changed since the last snapshot. Figures may be out of date.';
export const CAPTION = 'Sorted by severity, then days of cover';

export const COLUMNS: Column<StockoutRiskRow>[] = [
  // Plain text until P4-03 adds the product page.
  { id: 'sku', header: 'SKU', render: (row) => row.sku },
  { id: 'name', header: 'Product', render: (row) => row.name },
  { id: 'warehouse', header: 'Warehouse', render: (row) => row.warehouse_code },
  { id: 'risk', header: 'Risk', render: (row) => <RiskBadge risk={row.risk_class} /> },
  {
    id: 'available',
    header: 'Available',
    render: (row) => formatNumber(row.available),
    align: 'right',
  },
  {
    id: 'cover',
    header: 'Days of cover',
    render: (row) => formatDays(row.days_of_cover),
    align: 'right',
  },
  {
    id: 'stockout',
    header: 'Projected stockout',
    render: (row) =>
      row.projected_stockout_day === null ? EMPTY : `Day ${row.projected_stockout_day}`,
    align: 'right',
  },
  {
    id: 'rop',
    header: 'Reorder point',
    render: (row) => formatNumber(row.reorder_point),
    align: 'right',
  },
];

interface Props {
  filters: DashboardFilters;
  ready: boolean;
  reloadSignal: number;
  onRecalculated: () => void;
}

/** FR-A3: the ten most severe stockout-risk rows (``/risk/stockout?page_size=10``). */
export default function TopRiskTable({ filters, ready, reloadSignal, onRecalculated }: Props) {
  const key = ready ? JSON.stringify({ ...filters, reloadSignal }) : null;
  const { data, error, loading, reload } = useApi(
    (signal) => getStockoutRisk({ ...filters, page: 1, page_size: TOP_N }, signal),
    key,
  );

  let body;
  if (isStale(error)) {
    body = (
      <Alert
        severity="warning"
        action={<RecalculateButton onDone={onRecalculated} variant="text" />}
      >
        {STALE_NOTICE}
      </Alert>
    );
  } else if (error && !isNoSnapshot(error)) {
    body = <ErrorState error={error} title="Could not load the top 10" onRetry={reload} />;
  } else if ((loading || !data) && !error) {
    body = (
      <Skeleton variant="rounded" height={420} aria-label="Loading top 10" role="progressbar" />
    );
  } else {
    // No snapshot is handled at page level; render an empty table meanwhile.
    const rows = (data?.items ?? []).slice(0, TOP_N);
    body = (
      <DataTable
        caption={CAPTION}
        columns={COLUMNS}
        rows={rows}
        getRowId={(row) => `${row.product_id}-${row.warehouse_id}`}
        page={1}
        pageSize={TOP_N}
        total={rows.length}
        onPageChange={() => {}}
        hidePagination
        emptyMessage="No products at stockout risk for these filters."
      />
    );
  }

  return (
    <VerifiedDataPanel title="Top 10 at risk" snapshot={data?.snapshot ?? null}>
      {body}
    </VerifiedDataPanel>
  );
}
