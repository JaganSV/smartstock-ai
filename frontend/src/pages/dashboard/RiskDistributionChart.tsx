import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import { useTheme } from '@mui/material/styles';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import { useEffect, useState } from 'react';
import { Bar, BarChart, Cell, LabelList, XAxis, YAxis } from 'recharts';

import { getRiskDistribution } from '../../api/endpoints';
import type { DashboardFilters } from '../../api/types';
import ChartFrame from '../../components/ChartFrame';
import ErrorState from '../../components/ErrorState';
import RiskBadge from '../../components/RiskBadge';
import VerifiedDataPanel from '../../components/VerifiedDataPanel';
import { useApi } from '../../hooks/useApi';
import { formatNumber } from '../../lib/format';
import { RISK_CLASSES } from '../../theme/theme';
import { isNoSnapshot } from './snapshotErrors';

export type DistributionMode = 'rows' | 'products';
export const MODE_LABEL: Record<DistributionMode, string> = {
  rows: 'Locations',
  products: 'Products',
};
const AXIS_LABEL: Record<DistributionMode, string> = {
  rows: 'Locations (product × warehouse)',
  products: 'Products (most severe warehouse)',
};
export const BAR_HEIGHT = 260;

interface Props {
  filters: DashboardFilters;
  ready: boolean;
  reloadSignal: number;
  /** Called when the API says there is no snapshot yet (page-level empty state). */
  onNoSnapshot: () => void;
}

/** FR-A3: count per risk class, severity order, colour and label on every bar. */
export default function RiskDistributionChart({
  filters,
  ready,
  reloadSignal,
  onNoSnapshot,
}: Props) {
  const theme = useTheme();
  const [mode, setMode] = useState<DistributionMode>('rows');
  const key = ready ? JSON.stringify({ ...filters, reloadSignal }) : null;
  const { data, error, loading, reload } = useApi(
    (signal) => getRiskDistribution(filters, signal),
    key,
  );
  const noSnapshot = isNoSnapshot(error);

  useEffect(() => {
    if (noSnapshot) onNoSnapshot();
  }, [noSnapshot, onNoSnapshot]);

  const counts = data ? data[mode] : null;
  const bars = RISK_CLASSES.map((risk) => {
    const count = counts?.[risk] ?? 0;
    return { risk, count, label: `${risk}: ${formatNumber(count)}` };
  });
  const total = bars.reduce((sum, bar) => sum + bar.count, 0);

  let body;
  if (error && !noSnapshot) {
    body = (
      <ErrorState error={error} title="Could not load the risk distribution" onRetry={reload} />
    );
  } else if (loading || !data) {
    body = (
      <Skeleton
        variant="rounded"
        height={BAR_HEIGHT + 56}
        aria-label="Loading risk distribution"
        role="progressbar"
      />
    );
  } else if (total === 0) {
    body = (
      <Box sx={{ height: BAR_HEIGHT, display: 'grid', placeItems: 'center' }}>
        <Typography color="text.secondary">No data</Typography>
      </Box>
    );
  } else {
    body = (
      <>
        <Box
          role="img"
          aria-label={`${MODE_LABEL[mode]} per risk class: ${bars.map((b) => b.label).join(', ')}.`}
        >
          <ChartFrame height={BAR_HEIGHT}>
            <BarChart
              data={bars}
              layout="vertical"
              margin={{ top: 4, right: 24, bottom: 24, left: 8 }}
              barCategoryGap={6}
            >
              <XAxis
                type="number"
                allowDecimals={false}
                domain={[0, (max: number) => Math.max(1, Math.ceil(max * 1.45))]}
                tickFormatter={(value: number) => formatNumber(value)}
                tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
                label={{
                  value: AXIS_LABEL[mode],
                  position: 'insideBottom',
                  offset: -16,
                  fill: theme.palette.text.secondary,
                }}
              />
              <YAxis type="category" dataKey="risk" hide />
              <Bar dataKey="count" isAnimationActive={false} minPointSize={2}>
                {bars.map((bar) => (
                  <Cell key={bar.risk} fill={theme.risk[bar.risk].background} />
                ))}
                <LabelList
                  dataKey="label"
                  content={(props) => {
                    const x = Number(props.x ?? 0) + Number(props.width ?? 0) + 6;
                    const y = Number(props.y ?? 0) + Number(props.height ?? 0) / 2;
                    return (
                      <text
                        x={x}
                        y={y}
                        dominantBaseline="central"
                        fill={theme.palette.text.primary}
                        fontSize={12}
                      >
                        {props.value}
                      </text>
                    );
                  }}
                />
              </Bar>
            </BarChart>
          </ChartFrame>
        </Box>
        <Box
          component="ul"
          aria-label="Risk legend"
          sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, listStyle: 'none', p: 0, m: 0, mt: 1 }}
        >
          {bars.map((bar) => (
            <Box
              component="li"
              key={bar.risk}
              sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
            >
              <RiskBadge risk={bar.risk} />
              <Typography variant="body2">{formatNumber(bar.count)}</Typography>
            </Box>
          ))}
        </Box>
      </>
    );
  }

  return (
    <VerifiedDataPanel
      title="Risk distribution"
      snapshot={data?.snapshot ?? null}
      actions={
        <ToggleButtonGroup
          size="small"
          exclusive
          value={mode}
          onChange={(_, value: DistributionMode | null) => value && setMode(value)}
          aria-label="Count by"
        >
          <ToggleButton value="rows">{MODE_LABEL.rows}</ToggleButton>
          <ToggleButton value="products">{MODE_LABEL.products}</ToggleButton>
        </ToggleButtonGroup>
      }
    >
      {body}
    </VerifiedDataPanel>
  );
}
