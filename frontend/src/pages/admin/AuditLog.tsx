import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useEffect, useState, type FormEvent } from 'react';

import { toApiError, type ApiError } from '../../api/client';
import { getAuditLog } from '../../api/endpoints';
import type { AuditLogItem, AuditLogPage, AuditLogQuery } from '../../api/types';
import DataTable, { type Column } from '../../components/DataTable';
import { EMPTY, formatDateTime } from '../../lib/format';

export const PAGE_SIZES = [25, 50, 100];

interface Filters {
  action: string;
  entityType: string;
  /** yyyy-mm-dd from a date input, in the user's local calendar. */
  from: string;
  to: string;
}

const NO_FILTERS: Filters = { action: '', entityType: '', from: '', to: '' };

/** Local calendar days to the API's timestamps: ``from`` at 00:00, ``to`` through 23:59:59.999. */
export function toQuery(filters: Filters, page: number, pageSize: number): AuditLogQuery {
  return {
    page,
    page_size: pageSize,
    action: filters.action.trim() || undefined,
    entity_type: filters.entityType.trim() || undefined,
    from: filters.from ? new Date(`${filters.from}T00:00:00`).toISOString() : undefined,
    to: filters.to ? new Date(`${filters.to}T23:59:59.999`).toISOString() : undefined,
  };
}

const COLUMNS: Column<AuditLogItem>[] = [
  { id: 'time', header: 'Time', render: (row) => formatDateTime(row.occurred_at), width: 190 },
  { id: 'user', header: 'User', render: (row) => row.username ?? 'system' },
  { id: 'action', header: 'Action', render: (row) => row.action },
  {
    id: 'entity',
    header: 'Entity',
    render: (row) =>
      row.entity_type ? `${row.entity_type}${row.entity_id ? ` · ${row.entity_id}` : ''}` : EMPTY,
  },
  {
    id: 'request',
    header: 'Request ID',
    render: (row) => (
      <Box
        component="span"
        sx={{ fontFamily: 'monospace', fontSize: '0.75rem', wordBreak: 'break-all' }}
      >
        {row.request_id ?? EMPTY}
      </Box>
    ),
  },
  { id: 'ip', header: 'IP', render: (row) => row.ip_address ?? EMPTY },
];

/** ``details`` as indented JSON text. React escapes it: it is never parsed as HTML. */
function Details({ row }: { row: AuditLogItem }) {
  return (
    <Box
      component="pre"
      aria-label={`Details of audit entry ${row.id}`}
      sx={{
        m: 0,
        p: 1.5,
        bgcolor: 'grey.100',
        borderRadius: 1,
        fontSize: '0.8rem',
        overflowX: 'auto',
      }}
    >
      {JSON.stringify(row.details, null, 2)}
    </Box>
  );
}

/** Admin › Audit log (``view_governance``): server-paginated, filterable, rows expand to details. */
export default function AuditLog() {
  const [draft, setDraft] = useState<Filters>(NO_FILTERS);
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZES[0]);
  const [data, setData] = useState<AuditLogPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getAuditLog(toQuery(filters, page, pageSize))
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setData(null);
        setError(toApiError(caught));
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [filters, page, pageSize]);

  const apply = (event: FormEvent) => {
    event.preventDefault();
    setFilters(draft);
    setPage(1);
  };

  const reset = () => {
    setDraft(NO_FILTERS);
    setFilters(NO_FILTERS);
    setPage(1);
  };

  return (
    <>
      <Typography variant="h1" gutterBottom>
        Audit log
      </Typography>
      <Box
        component="form"
        role="search"
        aria-label="Audit log filters"
        onSubmit={apply}
        sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center', mb: 2 }}
      >
        <TextField
          label="Action (exact)"
          size="small"
          value={draft.action}
          onChange={(event) => setDraft({ ...draft, action: event.target.value })}
          slotProps={{ htmlInput: { maxLength: 64 } }}
        />
        <TextField
          label="Entity type"
          size="small"
          value={draft.entityType}
          onChange={(event) => setDraft({ ...draft, entityType: event.target.value })}
          slotProps={{ htmlInput: { maxLength: 64 } }}
        />
        <TextField
          label="From"
          type="date"
          size="small"
          value={draft.from}
          onChange={(event) => setDraft({ ...draft, from: event.target.value })}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          label="To"
          type="date"
          size="small"
          value={draft.to}
          onChange={(event) => setDraft({ ...draft, to: event.target.value })}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <Button type="submit" variant="contained">
          Apply filters
        </Button>
        <Button onClick={reset}>Reset</Button>
      </Box>
      <DataTable
        caption="Audit log entries, newest first"
        columns={COLUMNS}
        rows={data?.items ?? []}
        getRowId={(row) => row.id}
        page={page}
        pageSize={pageSize}
        total={data?.total ?? 0}
        pageSizeOptions={PAGE_SIZES}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
        loading={loading}
        error={error}
        emptyMessage="No audit entries match these filters."
        renderExpanded={(row) => <Details row={row} />}
      />
    </>
  );
}
