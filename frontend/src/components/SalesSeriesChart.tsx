import Box from '@mui/material/Box';
import { useTheme } from '@mui/material/styles';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis, type TooltipProps } from 'recharts';

import type { SalesPoint } from '../api/types';
import { formatDate, formatMoney, formatNumber, formatShortDate, sumMoney } from '../lib/format';
import ChartFrame from './ChartFrame';
import { visuallyHidden } from './visuallyHidden';

export const WINDOWS = [30, 60, 90] as const;
export type SalesWindow = (typeof WINDOWS)[number];
export const CHART_HEIGHT = 280;
export const SUM_LABEL = 'Sum of the series shown';

function SalesTooltip({ active, payload }: TooltipProps<number, string>) {
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

/** The 30/60/90-day window toggle used by every sales chart. */
export function WindowToggle({
  value,
  onChange,
}: {
  value: SalesWindow;
  onChange: (value: SalesWindow) => void;
}) {
  return (
    <ToggleButtonGroup
      size="small"
      exclusive
      value={value}
      onChange={(_, next: SalesWindow | null) => next && onChange(next)}
      aria-label="Sales window"
    >
      {WINDOWS.map((window) => (
        <ToggleButton key={window} value={window} aria-label={`${window} days`}>
          {window}d
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
}

interface Props {
  series: SalesPoint[];
  startDate: string;
  endDate: string;
}

/**
 * Daily units as a line (Recharts), with the labelled presentation sum ("Sum of the series
 * shown": units, and revenue summed exactly in paise) and a screen-reader table of the series.
 * "No data" for an empty series.
 */
export default function SalesSeriesChart({ series, startDate, endDate }: Props) {
  const theme = useTheme();
  if (series.length === 0) {
    return (
      <Box sx={{ height: CHART_HEIGHT + 28, display: 'grid', placeItems: 'center' }}>
        <Typography color="text.secondary">No data</Typography>
      </Box>
    );
  }
  const totalUnits = series.reduce((sum, point) => sum + point.units, 0);
  const totalRevenue = sumMoney(series.map((point) => point.revenue));
  const summary =
    `Daily units sold from ${formatDate(startDate)} to ${formatDate(endDate)}: ` +
    `${formatNumber(totalUnits)} units in total.`;

  return (
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
            <Tooltip content={SalesTooltip} />
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
      <Box sx={visuallyHidden}>
        <table>
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
        </table>
      </Box>
    </>
  );
}
