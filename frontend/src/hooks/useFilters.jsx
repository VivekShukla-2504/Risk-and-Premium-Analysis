import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { api } from '../services/api.js';
import { EMPTY_FILTERS, countActiveFilters, validateFilters } from '../utils/params.js';

const FilterContext = createContext(null);

export function FilterProvider({ children }) {
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS });
  const [applied, setApplied] = useState({ ...EMPTY_FILTERS });
  const error = validateFilters(filters);

  // Only valid filter sets reach the API; an invalid draft keeps the last valid one on screen.
  useEffect(() => {
    if (!error) setApplied(filters);
  }, [filters, error]);

  const value = useMemo(
    () => ({
      filters,
      applied,
      error,
      activeCount: countActiveFilters(applied),
      setFilter: (key, val) => setFilters((f) => ({ ...f, [key]: val })),
      reset: () => setFilters({ ...EMPTY_FILTERS }),
    }),
    [filters, applied, error],
  );
  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useFilters() {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error('useFilters must be used inside <FilterProvider>');
  return ctx;
}

// Filter choices come from the API (computed on the unfiltered data) and are fetched once.
let optionsPromise = null;
export function useFilterOptions() {
  const [state, setState] = useState({ options: null, error: null });
  const [reloadCount, setReloadCount] = useState(0);
  useEffect(() => {
    optionsPromise ??= api.summary({}).then((r) => r.data.filter_options);
    let live = true;
    optionsPromise
      .then((options) => live && setState({ options, error: null }))
      .catch((error) => {
        optionsPromise = null;
        if (live) setState({ options: null, error });
      });
    return () => {
      live = false;
    };
  }, [reloadCount]);
  const reload = useCallback(() => setReloadCount((count) => count + 1), []);
  return { ...state, reload };
}
