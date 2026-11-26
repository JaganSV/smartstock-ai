import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import { useState } from 'react';

import { getStockoutRisk } from '../../api/endpoints';
import type { StockoutRiskRow } from '../../api/types';
import DataTable, { type Column } from '../../components/DataTable';
import ErrorState from '../../components/ErrorState';
import RiskBadge from '../../components/RiskBadge';
import VerifiedDataPanel from '../../components/VerifiedDataPanel';
import { useApi } from '../../hooks/useApi';
import { usePageParams } from '../../hooks/useUrlParams';
import { EMPTY, formatDays, formatNumber } from '../../lib/format';
import EmptySnapshotState from '../dashboard/EmptySnapshotState';
import FiltersBar, { useDashboardFilters } from '../dashboard/FiltersBar';
import { isNoSnapshot, isStale } from '../dashboard/snapshotErrors';
import StaleNotice from '../dashboard/StaleNotice';
import { SkuLink } from '../dashboard/TopRiskTable';

export const PAGE_SIZES = [25, 50];
export const CAPTION = 'Most severe first, then lowest days of cover';

export const COLUMNS: Column<StockoutRiskRow>[] = [
  { id: 'sku', header: 'SKU', render: (row) => <SkuLink row={row} />, nowrap: true },
  { id: 'name', header: 'Product', render: (row) => row.name },
  { id: 'warehouse', header: 'Warehouse', render: (row) => row.warehouse_code, nowrap: true },
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
  {
    id: 'qty',
    header: 'Reorder qty',
    render: (row) => formatNumber(row.reorder_qty),
    align: 'right',
  },
  {
    id: 'flags',
    header: 'Flags',
    render: (row) =>
      row.is_high_demand ? <Chip label="High demand" size="small" color="info" /> : null,
  },
];

/**
 * FR-C1: STOCKOUT, CRITICAL and HIGH rows of the latest snapshot, in the API's order (most
 * severe, then lowest days of cover). Never re-sorted here. Filters and page live in the URL.
 */
export default function StockoutRisk() {
  const filterState = useDashboardFilters();
  const { filters, ready } = filterState;
  const { page, pageSize, setPage, setPageSize } = usePageParams(PAGE_SIZES);
  const [reloadSignal, setReloadSignal] = useState(0);
  const reloadAll = () => setReloadSignal((value) => value + 1);
  const { data, error, loading, reload } = useApi(
    (signal) => getStockoutRisk({ ...filters, page, page_size: pageSize }, signal),
    ready ? JSON.stringify({ ...filters, page, pageSize, reloadSignal }) : null,
  );

  let body;
  if (isStale(error)) {
    body = <StaleNotice onRecalculated={reloadAll} />;
  } else if (isNoSnapshot(error)) {
    body = <EmptySnapshotState onDone={reloadAll} />;
  } else if (error) {
    body = (
      <ErrorState error={error} title="Could not load the stockout risk list" onRetry={reload} />
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
        emptyMessage="No products at stockout risk for these filters."
      />
    );
  }

  return (
    <Box sx={{ display: 'grid', gap: 2, minWidth: 0 }}>
      <Typography variant="h1">Stockout risk</Typography>
      <FiltersBar state={filterState} />
      <VerifiedDataPanel title="Products at stockout risk" snapshot={data?.snapshot ?? null}>
        {body}
      </VerifiedDataPanel>
    </Box>
  );
}
