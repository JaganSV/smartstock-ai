import { useCallback } from 'react';
import { useSearchParams } from 'react-router';

export type ParamValue = string | number | boolean | readonly string[] | undefined;

/**
 * Read and write list state in the URL query string, so a view can be shared and survives a
 * reload. ``update`` replaces the given keys (``undefined`` or ``[]`` removes one) and, unless
 * ``keepPage`` is set, drops ``page`` so a new filter starts at page 1.
 */
export function useUrlParams() {
  const [params, setParams] = useSearchParams();
  const update = useCallback(
    (changes: Record<string, ParamValue>, options: { keepPage?: boolean } = {}) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          for (const [name, value] of Object.entries(changes)) {
            next.delete(name);
            if (Array.isArray(value)) value.forEach((item) => next.append(name, item));
            else if (value !== undefined && value !== '' && value !== false) {
              next.set(name, String(value));
            }
          }
          if (!options.keepPage && !('page' in changes)) next.delete('page');
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );
  return { params, update };
}

/** 1-based ``page`` and ``page_size`` from the URL; out-of-range values fall back to defaults. */
export function usePageParams(sizes: readonly number[]) {
  const { params, update } = useUrlParams();
  const rawPage = Number(params.get('page'));
  const rawSize = Number(params.get('page_size'));
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;
  const pageSize = sizes.includes(rawSize) ? rawSize : sizes[0];
  return {
    page,
    pageSize,
    setPage: (next: number) => update({ page: next > 1 ? next : undefined }, { keepPage: true }),
    setPageSize: (next: number) => update({ page_size: next === sizes[0] ? undefined : next }),
  };
}
