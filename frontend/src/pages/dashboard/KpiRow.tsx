import Box from '@mui/material/Box';

import type { DashboardSummary } from '../../api/types';
import ErrorState from '../../components/ErrorState';
import KpiTile from '../../components/KpiTile';
import VerifiedDataPanel from '../../components/VerifiedDataPanel';
import type { ApiState } from '../../hooks/useApi';
import { formatMoney, formatNumber } from '../../lib/format';

interface TileSpec {
  label: string;
  value: (summary: DashboardSummary) => string;
  /** One-line definition (BP §7.4 / FR-A1), shown as the tile's tooltip. */
  description: string;
}

/** FR-A1 tiles in the order the prompt fixes. Values are formatted, never computed. */
export const TILES: TileSpec[] = [
  {
    label: 'Total products',
    value: (s) => formatNumber(s.total_products),
    description: 'Active products matching the filters.',
  },
  {
    label: 'Total units',
    value: (s) => formatNumber(s.total_units),
    description: 'Units on hand across the matching warehouses.',
  },
  {
    label: 'Inventory value',
    value: (s) => formatMoney(s.inventory_value),
    description: 'Sum of on-hand units × unit cost, in INR.',
  },
  {
    label: 'Low-stock products',
    value: (s) => formatNumber(s.low_stock_count),
    description: 'Low stock = High + Medium (products, by their most severe warehouse).',
  },
  {
    label: 'Stockout-risk products',
    value: (s) => formatNumber(s.stockout_risk_count),
    description: 'Stockout risk = Stockout + Critical + High (products).',
  },
  {
    label: 'Slow-moving products',
    value: (s) => formatNumber(s.slow_moving_count),
    description: 'Products with at least one slow-moving warehouse row.',
  },
];

/** Six verified KPI tiles in one panel (FR-A1, FR-A5). 3 × 2 at 1280 px, one row from 1536 px. */
export default function KpiRow({ summary }: { summary: ApiState<DashboardSummary> }) {
  const { data, error, loading, reload } = summary;
  return (
    <VerifiedDataPanel title="Key figures" snapshot={data?.snapshot ?? null}>
      {error ? (
        <ErrorState error={error} title="Could not load the key figures" onRetry={reload} />
      ) : (
        <Box
          sx={{
            display: 'grid',
            gap: 2,
            gridTemplateColumns: {
              xs: 'repeat(2, minmax(0, 1fr))',
              md: 'repeat(3, minmax(0, 1fr))',
              xl: 'repeat(6, minmax(0, 1fr))',
            },
          }}
        >
          {TILES.map((tile) => (
            <KpiTile
              key={tile.label}
              label={tile.label}
              value={data ? tile.value(data) : null}
              description={tile.description}
              loading={loading || !data}
            />
          ))}
        </Box>
      )}
    </VerifiedDataPanel>
  );
}
