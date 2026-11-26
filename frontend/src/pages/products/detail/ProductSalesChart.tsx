import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import { useState } from 'react';

import { getProductSales } from '../../../api/endpoints';
import ErrorState from '../../../components/ErrorState';
import SalesSeriesChart, {
  CHART_HEIGHT,
  WindowToggle,
  type SalesWindow,
} from '../../../components/SalesSeriesChart';
import VerifiedDataPanel from '../../../components/VerifiedDataPanel';
import { useApi } from '../../../hooks/useApi';
import { formatDate } from '../../../lib/format';

type Scope = 'warehouse' | 'all';

interface Props {
  productId: number;
  warehouseId: number;
  warehouseCode: string;
}

/** Section 7: the product's daily units (``/products/{id}/sales``), one warehouse or all. */
export default function ProductSalesChart({ productId, warehouseId, warehouseCode }: Props) {
  const [days, setDays] = useState<SalesWindow>(90);
  const [scope, setScope] = useState<Scope>('warehouse');
  const query = { days, warehouse_id: scope === 'warehouse' ? warehouseId : undefined };
  const { data, error, loading, reload } = useApi(
    (signal) => getProductSales(productId, query, signal),
    JSON.stringify({ productId, ...query }),
  );

  let body;
  if (error) {
    body = <ErrorState error={error} title="Could not load sales" onRetry={reload} />;
  } else if (loading || !data) {
    body = (
      <Skeleton
        variant="rounded"
        height={CHART_HEIGHT + 28}
        aria-label="Loading sales"
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
      title={`Sales (last ${days} days)`}
      snapshot={null}
      badgeLabel={data ? `Verified · sales to ${formatDate(data.end_date)}` : undefined}
      actions={
        <Stack direction="row" spacing={1}>
          <ToggleButtonGroup
            size="small"
            exclusive
            value={scope}
            onChange={(_, value: Scope | null) => value && setScope(value)}
            aria-label="Sales scope"
          >
            <ToggleButton value="warehouse">{warehouseCode}</ToggleButton>
            <ToggleButton value="all">All warehouses</ToggleButton>
          </ToggleButtonGroup>
          <WindowToggle value={days} onChange={setDays} />
        </Stack>
      }
    >
      {body}
    </VerifiedDataPanel>
  );
}
