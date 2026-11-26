import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import { useTheme } from '@mui/material/styles';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import { useState } from 'react';
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis, type TooltipProps } from 'recharts';

import { getSalesTrend } from '../../api/endpoints';
import type { DashboardFilters, SalesPoint } from '../../api/types';
import ChartFrame from '../../components/ChartFrame';
import ErrorState from '../../components/ErrorState';
import VerifiedDataPanel from '../../components/VerifiedDataPanel';
import { visuallyHidden } from '../../components/visuallyHidden';
import { useApi } from '../../hooks/useApi';
import { formatDate, formatMoney, formatNumber, formatShortDate, sumMoney } from '../../lib/format';

export const WINDOWS = [30, 60, 90] as const;
export type TrendWindow = (typeof WINDOWS)[number];
export const CHART_HEIGHT = 280;
export const SUM_LABEL = 'Sum of the series shown';

function TrendTooltip({ active, payload }: TooltipProps<number, string>) {
  const point = payload?.[0]?.payload as SalesPoint | undefined;
  if (!active || !point) return null;
  return (
    <Box
      sx={{ bgcolor: 'background.paper', border: 1, borderColor: 'divider', p: 1, fontSize: 13 }}
    >
      <strong>{formatDate(point.date)}</strong>
      <div>Units: {formatNumber(point.units)}</div>
      <div>Revenue: {formatMoney(point.revenue)}</div>
    </Box>
  );
}

interface Props {
  filters: DashboardFilters;
  ready: boolean;
  /** Changes after a recalculation so the section fetches again. */
  reloadSignal: number;
}

/** FR-A2: daily units over the last 30/60/90 days ending at t0, from the sales ledger. */
export default function SalesTrendChart({ filters, ready, reloadSignal }: Props) {
  const theme = useTheme();
  const [days, setDays] = useState<TrendWindow>(90);
  const key = ready ? JSON.stringify({ ...filters, days, reloadSignal }) : null;
  const { data, error, loading, reload } = useApi(
    (signal) => getSalesTrend({ ...filters, days }, signal),
    key,
  );

  const series = data?.series ?? [];
  const totalUnits = series.reduce((sum, point) => sum + point.units, 0);
  const totalRevenue = series.length ? sumMoney(series.map((point) => point.revenue)) : '0.00';
  const summary = data
    ? `Daily units sold from ${formatDate(data.start_date)} to ${formatDate(data.end_date)}: ` +
      `${formatNumber(totalUnits)} units in total.`
    : '';

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
  } else if (series.length === 0) {
    body = (
      <Box sx={{ height: CHART_HEIGHT + 28, display: 'grid', placeItems: 'center' }}>
        <Typography color="text.secondary">No data</Typography>
      </Box>
    );
  } else {
    body = (
      <>
        <Box role="img" aria-label={summary}>
          <ChartFrame height={CHART_HEIGHT}>
            <LineChart data={series} margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
              <CartesianGrid stroke={theme.palette.divider} vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={(value: string) => formatShortDate(value)}
                minTickGap={28}
                tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
                label={{
                  value: 'Date',
                  position: 'insideBottom',
                  offset: -16,
                  fill: theme.palette.text.secondary,
                }}
              />
              <YAxis
                allowDecimals={false}
                tickFormatter={(value: number) => formatNumber(value)}
                tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
                width={64}
                label={{
                  value: 'Units sold',
                  angle: -90,
                  position: 'insideLeft',
                  fill: theme.palette.text.secondary,
                }}
              />
              <Tooltip content={TrendTooltip} />
              <Line
                type="monotone"
                dataKey="units"
                name="Units sold"
                stroke={theme.palette.primary.main}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ChartFrame>
        </Box>
        <Typography variant="body2" sx={{ mt: 1 }} data-testid="trend-sum">
          {SUM_LABEL}: {formatNumber(totalUnits)} units · {formatMoney(totalRevenue)} revenue
        </Typography>
        <Box component="table" sx={visuallyHidden}>
          <caption>Daily sales, {summary}</caption>
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Units</th>
              <th scope="col">Revenue</th>
            </tr>
          </thead>
          <tbody>
            {series.map((point) => (
              <tr key={point.date}>
                <td>{formatDate(point.date)}</td>
                <td>{formatNumber(point.units)}</td>
                <td>{formatMoney(point.revenue)}</td>
              </tr>
            ))}
          </tbody>
        </Box>
      </>
    );
  }

  return (
    <VerifiedDataPanel
      title="Sales trend"
      snapshot={null}
      badgeLabel={data ? `Verified · sales to ${formatDate(data.end_date)}` : undefined}
      actions={
        <ToggleButtonGroup
          size="small"
          exclusive
          value={days}
          onChange={(_, value: TrendWindow | null) => value && setDays(value)}
          aria-label="Trend window"
        >
          {WINDOWS.map((window) => (
            <ToggleButton key={window} value={window} aria-label={`${window} days`}>
              {window}d
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      }
    >
      {body}
    </VerifiedDataPanel>
  );
}
