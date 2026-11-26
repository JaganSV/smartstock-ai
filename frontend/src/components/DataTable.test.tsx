import { fireEvent, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/client';
import { renderWithTheme } from '../test/utils';
import DataTable, { type Column } from './DataTable';

interface Row {
  id: number;
  sku: string;
  units: number;
}

const COLUMNS: Column<Row>[] = [
  { id: 'sku', header: 'SKU', render: (row) => row.sku, sortKey: 'sku' },
  { id: 'units', header: 'Units', render: (row) => row.units, sortKey: 'units', align: 'right' },
  { id: 'note', header: 'Note', render: () => 'n/a' },
];

const ROWS: Row[] = [
  { id: 1, sku: 'SKU-001', units: 0 },
  { id: 2, sku: 'SKU-002', units: 12 },
];

function setup(overrides: Partial<Parameters<typeof DataTable<Row>>[0]> = {}) {
  const props = {
    columns: COLUMNS,
    rows: ROWS,
    getRowId: (row: Row) => row.id,
    page: 1,
    pageSize: 25,
    total: 60,
    onPageChange: vi.fn(),
    onPageSizeChange: vi.fn(),
    onSortChange: vi.fn(),
    sort: 'sku',
    order: 'asc' as const,
    ...overrides,
  };
  renderWithTheme(<DataTable {...props} />);
  return props;
}

describe('DataTable', () => {
  it('renders rows and the server total', () => {
    setup();
    expect(screen.getByText('SKU-001')).toBeInTheDocument();
    expect(screen.getByText('1–25 of 60')).toBeInTheDocument();
  });

  it('pages with 1-based page numbers and changes page size', () => {
    const props = setup();
    fireEvent.click(screen.getByRole('button', { name: /next page/i }));
    expect(props.onPageChange).toHaveBeenCalledWith(2);
    fireEvent.mouseDown(screen.getByRole('combobox'));
    fireEvent.click(within(screen.getByRole('listbox')).getByText('50'));
    expect(props.onPageSizeChange).toHaveBeenCalledWith(50);
  });

  it('passes sort and order; clicking the active column flips the order', () => {
    const props = setup();
    fireEvent.click(screen.getByRole('button', { name: 'SKU' }));
    expect(props.onSortChange).toHaveBeenLastCalledWith('sku', 'desc');
    fireEvent.click(screen.getByRole('button', { name: 'Units' }));
    expect(props.onSortChange).toHaveBeenLastCalledWith('units', 'asc');
    expect(screen.queryByRole('button', { name: 'Note' })).not.toBeInTheDocument();
  });

  it('flips desc back to asc', () => {
    const props = setup({ order: 'desc' });
    fireEvent.click(screen.getByRole('button', { name: 'SKU' }));
    expect(props.onSortChange).toHaveBeenLastCalledWith('sku', 'asc');
  });

  it('shows the empty state', () => {
    setup({ rows: [], total: 0, emptyMessage: 'Nothing here.' });
    expect(screen.getByText('Nothing here.')).toBeInTheDocument();
  });

  it('shows the loading state', () => {
    setup({ loading: true });
    expect(screen.getByRole('progressbar', { name: 'Loading rows' })).toBeInTheDocument();
  });

  it('shows the error with its request reference', () => {
    const error = new ApiError({
      status: 404,
      code: 'NOT_FOUND',
      message: 'Unknown snapshot_id.',
      requestId: 'r-77',
    });
    setup({ error });
    expect(screen.getByRole('alert')).toHaveTextContent('Unknown snapshot_id.');
    expect(screen.getByText('Reference: r-77')).toBeInTheDocument();
    expect(screen.queryByText('SKU-001')).not.toBeInTheDocument();
  });

  it('expands and collapses a row', () => {
    setup({ renderExpanded: (row) => <span>details of {row.sku}</span> });
    const [first] = screen.getAllByRole('button', { name: 'Expand row' });
    fireEvent.click(first);
    expect(screen.getByText('details of SKU-001')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Collapse row' }));
    expect(screen.queryByText('details of SKU-001')).not.toBeInTheDocument();
  });

  it('renders plain headers without sort callbacks', () => {
    setup({ onSortChange: undefined, caption: 'Stock' });
    expect(screen.queryByRole('button', { name: 'SKU' })).not.toBeInTheDocument();
    expect(screen.getByText('Stock')).toBeInTheDocument();
  });
});
