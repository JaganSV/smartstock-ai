import Skeleton from '@mui/material/Skeleton';
import { useState } from 'react';

import { getSalesTrend } from '../../api/endpoints';
import type { DashboardFilters } from '../../api/types';
import ErrorState from '../../components/ErrorState';
import SalesSeriesChart, {
  CHART_HEIGHT,
  WindowToggle,
  type SalesWindow,
} from '../../components/SalesSeriesChart';
import VerifiedDataPanel from '../../components/VerifiedDataPanel';
import { useApi } from '../../hooks/useApi';
import { formatDate } from '../../lib/format';

export { SUM_LABEL, WINDOWS } from '../../components/SalesSeriesChart';

interface Props {
  filters: DashboardFilters;
  ready: boolean;
  /** Changes after a recalculation so the section fetches again. */
  reloadSignal: number;
}

/** FR-A2: daily units over the last 30/60/90 days ending at t0, from the sales ledger. */
export default function SalesTrendChart({ filters, ready, reloadSignal }: Props) {
  const [days, setDays] = useState<SalesWindow>(90);
  const key = ready ? JSON.stringify({ ...filters, days, reloadSignal }) : null;
  const { data, error, loading, reload } = useApi(
    (signal) => getSalesTrend({ ...filters, days }, signal),
    key,
  );

  let body;
  if (error) {
    body = <ErrorState error={error} title="Could not load the sales trend" onRetry={reload} />;
  } else if (loading || !data) {
    body = (
      <Skeleton
        variant="rounded"
        height={CHART_HEIGHT + 28}
        aria-label="Loading sales trend"
        role="progressbar"
      />
    );
  } else {
    body = (
      <SalesSeriesChart series={data.series} startDate={data.start_date} endDate={data.end_date} />
    );
  }

  return (
    <VerifiedDataPanel
      title="Sales trend"
      snapshot={null}
      badgeLabel={data ? `Verified · sales to ${formatDate(data.end_date)}` : undefined}
      actions={<WindowToggle value={days} onChange={setDays} />}
    >
      {body}
    </VerifiedDataPanel>
  );
}
