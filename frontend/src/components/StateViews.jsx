import { createContext } from 'react';

import { useFilters } from '../hooks/useFilters.jsx';

export const RateMetricValidityContext = createContext(true);

export function Loading({ minHeight = 200, label = 'Loading data' }) {
  return (
    <div role="status" aria-live="polite" style={{ minHeight }} className="flex items-center justify-center text-sm text-muted">
      <span className="mr-2 inline-block h-3 w-3 animate-spin rounded-full border-2 border-rule border-t-brand" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorState({ error, onRetry, minHeight = 200 }) {
  return (
    <div role="alert" style={{ minHeight }} className="flex flex-col items-start justify-center gap-3 px-4 py-6">
      <p className="text-sm font-medium text-brick">Could not load this section</p>
      <p className="max-w-prose text-sm text-muted">{error?.message || 'Unknown error.'}</p>
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  children = 'No data is available for the current selection.',
  minHeight = 160,
  onReset,
}) {
  const { reset } = useFilters();
  return (
    <div style={{ minHeight }} className="flex flex-col items-center justify-center gap-2 px-4 text-center text-sm text-muted">
      <p>{children}</p>
      {(onReset || reset) && (
        <button type="button" className="btn" onClick={onReset || reset}>
          Reset filters
        </button>
      )}
    </div>
  );
}

export function RateMetricUnavailable({ children = 'This rate is unavailable because the selected filters are based on claim outcomes.' }) {
  return (
    <p role="status" className="rounded-panel bg-paper px-3 py-2 text-sm text-muted">
      {children}
    </p>
  );
}

/** Renders loading / error / content for one useApi() state. `children` is a function of the data. */
export function Async({ state, children, minHeight = 200 }) {
  const { data, error, loading, reload } = state;
  if (error) return <ErrorState error={error} onRetry={reload} minHeight={minHeight} />;
  if (!data) return <Loading minHeight={minHeight} />;
  return (
    <div aria-busy={loading} className={loading ? 'opacity-60 transition-opacity' : ''}>
      {children(data)}
    </div>
  );
}
