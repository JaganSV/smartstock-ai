import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';
import { useCallback, useEffect, useState } from 'react';

import { getDashboardSummary } from '../api/endpoints';
import { useApi } from '../hooks/useApi';
import { formatDate, formatDateTime } from '../lib/format';
import EmptySnapshotState from './dashboard/EmptySnapshotState';
import FiltersBar, { useDashboardFilters } from './dashboard/FiltersBar';
import KpiRow from './dashboard/KpiRow';
import RecalculateButton from './dashboard/RecalculateButton';
import RiskDistributionChart from './dashboard/RiskDistributionChart';
import SalesTrendChart from './dashboard/SalesTrendChart';
import { isNoSnapshot } from './dashboard/snapshotErrors';
import TopRiskTable from './dashboard/TopRiskTable';

/**
 * Inventory Dashboard (Module A, FR-A1–A5). Every number comes from the API and sits in a
 * verified panel; the page formats, it never calculates (the trend's labelled "Sum of the series
 * shown" is the one presentation sum). Each section fetches on its own, so one failure never
 * blanks the page.
 */
export default function Dashboard() {
  const filterState = useDashboardFilters();
  const { filters, ready } = filterState;
  const [reloadSignal, setReloadSignal] = useState(0);
  const [distributionEmpty, setDistributionEmpty] = useState(false);

  const summary = useApi(
    (signal) => getDashboardSummary(filters, signal),
    ready ? JSON.stringify({ ...filters, reloadSignal }) : null,
  );

  const reloadAll = useCallback(() => {
    setDistributionEmpty(false);
    setReloadSignal((value) => value + 1);
  }, []);
  const onNoSnapshot = useCallback(() => setDistributionEmpty(true), []);
  // A new snapshot (or new filters) can end the empty state.
  useEffect(() => setDistributionEmpty(false), [filters]);

  const noSnapshot = isNoSnapshot(summary.error) || distributionEmpty;
  const snapshot = summary.data?.snapshot;

  return (
    <Box sx={{ display: 'grid', gap: 2, minWidth: 0 }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap' }}>
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Typography variant="h1">Inventory Dashboard</Typography>
          {snapshot ? (
            <Typography variant="body2" color="text.secondary" data-testid="snapshot-line">
              Verified · calculated {formatDateTime(snapshot.calculated_at)} · data as of{' '}
              {formatDate(snapshot.data_as_of_date)}
            </Typography>
          ) : summary.loading ? (
            <Skeleton width={360} />
          ) : null}
        </Box>
        {noSnapshot ? null : <RecalculateButton onDone={reloadAll} />}
      </Box>
      <FiltersBar state={filterState} />
      {noSnapshot ? (
        <EmptySnapshotState onDone={reloadAll} />
      ) : (
        <>
          <KpiRow summary={summary} />
          <Box
            sx={{
              display: 'grid',
              gap: 2,
              gridTemplateColumns: { xs: 'minmax(0, 1fr)', lg: 'minmax(0, 3fr) minmax(0, 2fr)' },
            }}
          >
            <SalesTrendChart filters={filters} ready={ready} reloadSignal={reloadSignal} />
            <RiskDistributionChart
              filters={filters}
              ready={ready}
              reloadSignal={reloadSignal}
              onNoSnapshot={onNoSnapshot}
            />
          </Box>
          <TopRiskTable
            filters={filters}
            ready={ready}
            reloadSignal={reloadSignal}
            onRecalculated={reloadAll}
          />
        </>
      )}
    </Box>
  );
}
