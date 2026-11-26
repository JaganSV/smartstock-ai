import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, useLocation } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import { useDebouncedValue } from './useDebouncedValue';
import { usePageParams, useUrlParams } from './useUrlParams';

function wrapperAt(path: string) {
  return ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
  );
}

describe('useDebouncedValue', () => {
  it('returns the value once it stops changing', () => {
    vi.useFakeTimers();
    try {
      const { result, rerender } = renderHook(({ v }) => useDebouncedValue(v, 300), {
        initialProps: { v: 'a' },
      });
      rerender({ v: 'ab' });
      act(() => vi.advanceTimersByTime(200));
      rerender({ v: 'abc' });
      act(() => vi.advanceTimersByTime(200));
      expect(result.current).toBe('a');
      act(() => vi.advanceTimersByTime(100));
      expect(result.current).toBe('abc');
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('useUrlParams / usePageParams', () => {
  it('writes values, arrays and removals, and resets the page unless kept', () => {
    const { result } = renderHook(() => ({ url: useUrlParams(), location: useLocation() }), {
      wrapper: wrapperAt('/x?page=3&q=old'),
    });
    act(() => result.current.url.update({ q: 'new', risk_class: ['A', 'B'], flag: true }));
    expect(result.current.location.search).toBe('?q=new&risk_class=A&risk_class=B&flag=true');
    act(() => result.current.url.update({ page: 4 }, { keepPage: true }));
    act(() =>
      result.current.url.update({ q: undefined, risk_class: [], flag: false }, { keepPage: true }),
    );
    expect(result.current.location.search).toBe('?page=4');
  });

  it('validates page and page_size and writes them back', () => {
    const { result } = renderHook(
      () => ({ paging: usePageParams([25, 50]), location: useLocation() }),
      { wrapper: wrapperAt('/x?page=0&page_size=33') },
    );
    expect(result.current.paging).toMatchObject({ page: 1, pageSize: 25 });
    act(() => result.current.paging.setPage(3));
    expect(result.current.location.search).toBe('?page_size=33&page=3');
    act(() => result.current.paging.setPageSize(50));
    expect(result.current.location.search).toBe('?page_size=50');
    expect(result.current.paging.pageSize).toBe(50);
    act(() => result.current.paging.setPage(1));
    act(() => result.current.paging.setPageSize(25));
    expect(result.current.location.search).toBe('');
  });
});
