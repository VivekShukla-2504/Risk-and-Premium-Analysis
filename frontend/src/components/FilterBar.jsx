import { useFilterOptions, useFilters } from '../hooks/useFilters.jsx';

function Field({ id, label, children }) {
  return (
    <div className="min-w-0">
      <label htmlFor={id} className="mb-1 block text-xs text-muted">{label}</label>
      {children}
    </div>
  );
}

function Select({ id, value, onChange, options = [], allLabel = 'All' }) {
  return (
    <select id={id} className="control" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{allLabel}</option>
      {options.map((o) => (
        <option key={o} value={o}>{o}</option>
      ))}
    </select>
  );
}

const BASIS_LABELS = { policy_start: 'Policy start date', claim_date: 'Claim date' };

export default function FilterBar() {
  const { filters, error, activeCount, setFilter, reset } = useFilters();
  const { options, error: optionsError, reload: reloadOptions } = useFilterOptions();
  const range = options && (filters.date_basis === 'claim_date' ? options.claim_date_range : options.policy_start_date_range);

  return (
    <form className="border-b border-rule bg-panel" aria-label="Portfolio filters" onSubmit={(e) => e.preventDefault()}>
      <div className="grid grid-cols-2 gap-x-3 gap-y-2.5 px-4 py-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-[repeat(7,minmax(0,1fr))_auto] xl:items-end sm:px-6">
        <Field id="f-type" label="Policy type">
          <Select id="f-type" value={filters.policy_type} onChange={(v) => setFilter('policy_type', v)} options={options?.policy_type} />
        </Field>
        <Field id="f-gender" label="Gender">
          <Select id="f-gender" value={filters.gender} onChange={(v) => setFilter('gender', v)} options={options?.gender} />
        </Field>
        <Field id="f-age" label="Age band">
          <Select id="f-age" value={filters.age_band} onChange={(v) => setFilter('age_band', v)} options={options?.age_band} />
        </Field>
        <Field id="f-status" label="Claim status">
          <Select id="f-status" value={filters.claim_status} onChange={(v) => setFilter('claim_status', v)} options={options?.claim_status} />
        </Field>
        <Field id="f-basis" label="Date range applies to">
          <select id="f-basis" className="control" value={filters.date_basis} onChange={(e) => setFilter('date_basis', e.target.value)}>
            {(options?.date_basis || Object.keys(BASIS_LABELS)).map((b) => (
              <option key={b} value={b}>{BASIS_LABELS[b] || b}</option>
            ))}
          </select>
        </Field>
        <Field id="f-start" label="From">
          <input id="f-start" type="date" className="control" value={filters.start_date} min={range?.[0]} max={range?.[1]} onChange={(e) => setFilter('start_date', e.target.value)} />
        </Field>
        <Field id="f-end" label="To">
          <input id="f-end" type="date" className="control" value={filters.end_date} min={range?.[0]} max={range?.[1]} onChange={(e) => setFilter('end_date', e.target.value)} />
        </Field>
        <div className="col-span-2 flex items-center gap-3 sm:col-span-3 lg:col-span-4 xl:col-span-1">
          <button type="button" className="btn" onClick={reset} disabled={activeCount === 0 && !filters.start_date && !filters.end_date}>
            Reset filters
          </button>
          {activeCount > 0 && <span className="text-xs text-muted">{activeCount} active</span>}
        </div>
      </div>
      {(error || optionsError) && (
        <p role="alert" className="border-t border-rule bg-brick-tint px-4 py-1.5 text-[13px] text-brick sm:px-6">
          {error || `Filter choices could not be loaded: ${optionsError.message}`}
          {optionsError && (
            <button type="button" className="ml-2 underline" onClick={reloadOptions}>
              Retry filter choices
            </button>
          )}
        </p>
      )}
    </form>
  );
}
