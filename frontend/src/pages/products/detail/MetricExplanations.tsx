import Box from '@mui/material/Box';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';

import type { Explanation } from '../../../api/types';

/** An input or result value exactly as the API returned it (null as "null"). */
export function showValue(value: unknown): string {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

/**
 * Section 6 body (FR-B6): one row per metric with its BP 7 formula, inputs and result as the
 * API returned them (``/explain`` verifies them against the stored snapshot row).
 */
export default function MetricExplanations({ explanation }: { explanation: Explanation }) {
  return (
    <TableContainer sx={{ maxWidth: '100%', overflowX: 'auto' }}>
      <Table size="small" aria-label="Formula, inputs and result per metric">
        <TableHead>
          <TableRow>
            <TableCell sx={{ fontWeight: 600 }}>Metric</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Formula</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Inputs</TableCell>
            <TableCell sx={{ fontWeight: 600 }} align="right">
              Result
            </TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Source</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {explanation.metrics.map((item) => (
            <TableRow key={item.metric}>
              <TableCell sx={{ fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                {item.metric}
              </TableCell>
              <TableCell>
                <Box component="code" sx={{ fontSize: '0.8rem', whiteSpace: 'pre-wrap' }}>
                  {item.formula}
                </Box>
              </TableCell>
              <TableCell>
                <Box component="ul" sx={{ m: 0, pl: 2, fontSize: '0.8rem' }}>
                  {Object.entries(item.inputs).map(([name, value]) => (
                    <li key={name}>
                      <code>
                        {name} = {showValue(value)}
                      </code>
                    </li>
                  ))}
                </Box>
              </TableCell>
              <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                {showValue(item.result)}
              </TableCell>
              <TableCell sx={{ whiteSpace: 'nowrap' }}>{item.source}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
