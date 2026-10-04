import { useState } from 'react';

import DataTable from './DataTable.jsx';
import { Async, EmptyState, RateMetricUnavailable, RateMetricValidityContext } from './StateViews.jsx';
import { useFilters } from '../hooks/useFilters.jsx';

const resolve = (v, data) => (typeof v === 'function' ? v(data) : v);

/**
 * A titled section bound to one useApi() state.
 *  children(data)  -> the chart / content
 *  tableOf(data)   -> { columns, rows } to offer a Chart/Table switch
 */
export default function Panel({ title, subtitle, footnote, state, children, tableOf, height = 280, className = '', rateMetric = false }) {
  const [view, setView] = useState('chart');
  const { reset } = useFilters();
  const data = state?.data;
  const empty = data?.meta?.policies_in_scope === 0;
  const rateMetricsValid = data?.meta?.rate_metrics_valid !== false;
  return (
    <section className={`flex min-w-0 flex-col rounded-panel border border-rule bg-panel shadow-[0_1px_2px_rgba(29,43,38,0.035)] ${className}`}>
      <header className="flex items-start justify-between gap-3 border-b border-rule/80 px-4 py-3.5 sm:px-5">
        <div className="min-w-0">
          <h3 className="font-serif text-[1.075rem] leading-snug tracking-[-0.01em] text-ink">{title}</h3>
          {subtitle && data && <p className="mt-0.5 text-[13px] leading-snug text-muted">{resolve(subtitle, data)}</p>}
        </div>
        {tableOf && (
          <div role="group" aria-label={`${title} view`} className="flex shrink-0 overflow-hidden rounded-panel border border-rule text-xs">
            {['chart', 'table'].map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={`px-2.5 py-1 capitalize ${view === v ? 'bg-ink text-white' : 'bg-white text-muted hover:bg-paper'}`}
              >
                {v}
              </button>
            ))}
          </div>
        )}
      </header>
      <div className="min-w-0 flex-1 px-2 py-3 sm:px-3">
        <Async state={state} minHeight={height}>
          {(d) => {
            if (empty) return <EmptyState onReset={reset}>No records match the current filters.</EmptyState>;
            if (rateMetric && !rateMetricsValid) return <RateMetricUnavailable />;
            return (
              <RateMetricValidityContext.Provider value={rateMetricsValid}>
                {view === 'table' && tableOf
                  ? <DataTable caption={title} {...tableOf(d)} />
                  : children(d)}
              </RateMetricValidityContext.Provider>
            );
          }}
        </Async>
      </div>
      {footnote && data && <footer className="border-t border-rule px-4 py-2 text-xs leading-snug text-muted">{resolve(footnote, data)}</footer>}
    </section>
  );
}
