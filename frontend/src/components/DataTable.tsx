import KeyboardArrowDown from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowRight from '@mui/icons-material/KeyboardArrowRight';
import Box from '@mui/material/Box';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TablePagination from '@mui/material/TablePagination';
import TableRow from '@mui/material/TableRow';
import TableSortLabel from '@mui/material/TableSortLabel';
import Typography from '@mui/material/Typography';
import { Fragment, useState, type ReactNode } from 'react';

import type { ApiError } from '../api/client';
import ErrorState from './ErrorState';

export type SortOrder = 'asc' | 'desc';

export interface Column<T> {
  /** Unique column id. */
  id: string;
  header: string;
  render: (row: T) => ReactNode;
  /** The API's ``sort`` value for this column; omit for an unsortable column. */
  sortKey?: string;
  align?: 'left' | 'right' | 'center';
  width?: number | string;
  /** Keep the cell on one line (short codes such as a SKU). */
  nowrap?: boolean;
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  getRowId: (row: T) => string | number;
  /** 1-based page, as the API counts. */
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  pageSizeOptions?: number[];
  sort?: string;
  order?: SortOrder;
  onSortChange?: (sort: string, order: SortOrder) => void;
  loading?: boolean;
  error?: ApiError | null;
  emptyMessage?: string;
  /** When given, each row gets an expand button that shows this below it. */
  renderExpanded?: (row: T) => ReactNode;
  caption?: string;
  /** A fixed list (e.g. a top 10): no pagination controls. */
  hidePagination?: boolean;
}

/**
 * A typed table over a server-paginated ``Page[T]``: the parent fetches, this renders. Sorting
 * and paging only call back with the API's ``sort``/``order`` and 1-based ``page``/``page_size``.
 */
export default function DataTable<T>({
  columns,
  rows,
  getRowId,
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [25, 50, 100],
  sort,
  order = 'asc',
  onSortChange,
  loading = false,
  error = null,
  emptyMessage = 'No rows to show.',
  renderExpanded,
  caption,
  hidePagination = false,
}: Props<T>) {
  const [expanded, setExpanded] = useState<Set<string | number>>(new Set());
  const columnCount = columns.length + (renderExpanded ? 1 : 0);

  const toggle = (id: string | number) =>
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const sortBy = (key: string) => {
    if (!onSortChange) return;
    const nextOrder: SortOrder = sort === key && order === 'asc' ? 'desc' : 'asc';
    onSortChange(key, nextOrder);
  };

  let body: ReactNode;
  if (error) {
    body = (
      <TableRow>
        <TableCell colSpan={columnCount}>
          <ErrorState error={error} />
        </TableCell>
      </TableRow>
    );
  } else if (!loading && rows.length === 0) {
    body = (
      <TableRow>
        <TableCell colSpan={columnCount}>
          <Typography color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
            {emptyMessage}
          </Typography>
        </TableCell>
      </TableRow>
    );
  } else {
    body = rows.map((row) => {
      const id = getRowId(row);
      const isOpen = expanded.has(id);
      return (
        <Fragment key={id}>
          <TableRow hover>
            {renderExpanded ? (
              <TableCell padding="checkbox">
                <IconButton
                  size="small"
                  aria-label={isOpen ? 'Collapse row' : 'Expand row'}
                  aria-expanded={isOpen}
                  onClick={() => toggle(id)}
                >
                  {isOpen ? <KeyboardArrowDown /> : <KeyboardArrowRight />}
                </IconButton>
              </TableCell>
            ) : null}
            {columns.map((column) => (
              <TableCell
                key={column.id}
                align={column.align}
                sx={column.nowrap ? { whiteSpace: 'nowrap' } : undefined}
              >
                {column.render(row)}
              </TableCell>
            ))}
          </TableRow>
          {renderExpanded && isOpen ? (
            <TableRow>
              <TableCell colSpan={columnCount} sx={{ py: 0 }}>
                <Collapse in={isOpen} timeout="auto" unmountOnExit>
                  <Box sx={{ py: 1.5 }}>{renderExpanded(row)}</Box>
                </Collapse>
              </TableCell>
            </TableRow>
          ) : null}
        </Fragment>
      );
    });
  }

  return (
    <Paper variant="outlined" sx={{ width: '100%', overflow: 'hidden' }}>
      {loading ? <LinearProgress aria-label="Loading rows" /> : <Box sx={{ height: 4 }} />}
      <TableContainer sx={{ maxWidth: '100%', overflowX: 'auto' }}>
        <Table size="small" aria-busy={loading || undefined}>
          {caption ? (
            <caption style={{ captionSide: 'top', textAlign: 'left', padding: '8px 16px' }}>
              {caption}
            </caption>
          ) : null}
          <TableHead>
            <TableRow>
              {renderExpanded ? <TableCell padding="checkbox" aria-label="Details" /> : null}
              {columns.map((column) => (
                <TableCell
                  key={column.id}
                  align={column.align}
                  sx={{ fontWeight: 600, width: column.width }}
                  sortDirection={column.sortKey && sort === column.sortKey ? order : false}
                >
                  {column.sortKey && onSortChange ? (
                    <TableSortLabel
                      active={sort === column.sortKey}
                      direction={sort === column.sortKey ? order : 'asc'}
                      onClick={() => sortBy(column.sortKey as string)}
                    >
                      {column.header}
                    </TableSortLabel>
                  ) : (
                    column.header
                  )}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>{body}</TableBody>
        </Table>
      </TableContainer>
      {hidePagination ? null : (
        <TablePagination
          component="div"
          count={total}
          page={Math.max(0, page - 1)}
          rowsPerPage={pageSize}
          rowsPerPageOptions={pageSizeOptions}
          onPageChange={(_, zeroBased) => onPageChange(zeroBased + 1)}
          onRowsPerPageChange={(event) => onPageSizeChange?.(Number(event.target.value))}
        />
      )}
    </Paper>
  );
}
