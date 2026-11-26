import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import { useState } from 'react';

import { getSlowMoving } from '../../api/endpoints';
import type { SlowMovingRow } from '../../api/types';
import DataTable, { type Column } from '../../components/DataTable';
import ErrorState from '../../components/ErrorState';
import RiskBadge from '../../components/RiskBadge';
import VerifiedDataPanel from '../../components/VerifiedDataPanel';
import { useApi } from '../../hooks/useApi';
import { usePageParams } from '../../hooks/useUrlParams';
import { formatDays, formatMoney, formatNumber } from '../../lib/format';
import EmptySnapshotState from '../dashboard/EmptySnapshotState';
import FiltersBar, { useDashboardFilters } from '../dashboard/FiltersBar';
import { isNoSnapshot, isStale } from '../dashboard/snapshotErrors';
import StaleNotice from '../dashboard/StaleNotice';
import { SkuLink } from '../dashboard/TopRiskTable';

export const PAGE_SIZES = [25, 50];
export const CAPTION = 'Dead stock first, then highest inventory value';

export const COLUMNS: Column<SlowMovingRow>[] = [
  { id: 'sku', header: 'SKU', render: (row) => <SkuLink row={row} />, nowrap: true },
  { id: 'name', header: 'Product', render: (row) => row.name },
  { id: 'warehouse', header: 'Warehouse', render: (row) => row.warehouse_code, nowrap: true },
  {
    id: 'kind',
    header: 'Status',
    render: (row) =>
      row.is_dead_stock ? (
        <Chip label="Dead stock" size="small" color="error" variant="outlined" />
      ) : (
        <Chip label="Slow-moving" size="small" color="warning" variant="outlined" />
      ),
  },
  { id: 'risk', header: 'Risk', render: (row) => <RiskBadge risk={row.risk_class} /> },
  { id: 'ads30', header: 'ADS 30', render: (row) => formatNumber(row.ads_30, 4), align: 'right' },
  { id: 'ads90', header: 'ADS 90', render: (row) => formatNumber(row.ads_90, 4), align: 'right' },
  {
    id: 'cover',
    header: 'Days of cover',
    render: (row) => formatDays(row.days_of_cover),
    align: 'right',
  },
  { id: 'onhand', header: 'On hand', render: (row) => formatNumber(row.on_hand), align: 'right' },
  {
    id: 'value',
    header: 'Inventory value',
    render: (row) => formatMoney(row.inventory_value),
    align: 'right',
    nowrap: true,
  },
];

/** Slow-moving and dead-stock rows (BP 7.5), in the API's order. Filters and page in the URL. */
export default function SlowMoving() {
  const filterState = useDashboardFilters();
  const { filters, ready } = filterState;
  const { page, pageSize, setPage, setPageSize } = usePageParams(PAGE_SIZES);
  const [reloadSignal, setReloadSignal] = useState(0);
  const reloadAll = () => setReloadSignal((value) => value + 1);
  const { data, error, loading, reload } = useApi(
    (signal) => getSlowMoving({ ...filters, page, page_size: pageSize }, signal),
    ready ? JSON.stringify({ ...filters, page, pageSize, reloadSignal }) : null,
  );

  let body;
  if (isStale(error)) {
    body = <StaleNotice onRecalculated={reloadAll} />;
  } else if (isNoSnapshot(error)) {
    body = <EmptySnapshotState onDone={reloadAll} />;
  } else if (error) {
    body = (
      <ErrorState error={error} title="Could not load the slow-moving list" onRetry={reload} />
    );
  } else {
    body = (
      <DataTable
        caption={CAPTION}
        columns={COLUMNS}
        rows={data?.items ?? []}
        getRowId={(row) => `${row.product_id}-${row.warehouse_id}`}
        page={page}
        pageSize={pageSize}
        total={data?.total ?? 0}
        pageSizeOptions={PAGE_SIZES}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        loading={loading}
        emptyMessage="No slow-moving or dead stock for these filters."
      />
    );
  }

  return (
    <Box sx={{ display: 'grid', gap: 2, minWidth: 0 }}>
      <Typography variant="h1">Slow-moving &amp; dead stock</Typography>
      <FiltersBar state={filterState} />
      <VerifiedDataPanel title="Slow-moving and dead stock" snapshot={data?.snapshot ?? null}>
        {body}
      </VerifiedDataPanel>
    </Box>
  );
}
