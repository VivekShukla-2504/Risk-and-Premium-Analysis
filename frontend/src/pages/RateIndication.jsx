import { useState } from 'react';

import DataTable from '../components/DataTable.jsx';
import Notice from '../components/Notice.jsx';
import Panel from '../components/Panel.jsx';
import ScopeBanner from '../components/ScopeBanner.jsx';
import { EmptyState, ErrorState, Loading } from '../components/StateViews.jsx';
import { useApi } from '../hooks/useApi.js';
import { useFilters } from '../hooks/useFilters.jsx';
import { api, downloadReport } from '../services/api.js';
import { formatByType, formatSignedPercent } from '../utils/format.js';

const DEFAULT_TARGET_LOSS_RATIO_PCT = 65;
const MIN_TARGET_LOSS_RATIO_PCT = 30;
const MAX_TARGET_LOSS_RATIO_PCT = 100;

const DIMENSIONS = [
  { key: 'by_policy_type', label: 'By policy type' },
  { key: 'by_age_band', label: 'By age band' },
  { key: 'by_gender', label: 'By gender' },
];

const COLUMNS = [
  { key: 'segment', label: 'Segment', type: 'text' },
  { key: 'policies', label: 'Policies', type: 'integer' },
  { key: 'claiming_policies', label: 'Claims', type: 'integer' },
  { key: 'observed_loss_ratio', label: 'Observed loss ratio', type: 'percent' },
  { key: 'credibility_factor', label: 'Credibility Z', type: 'number3' },
  { key: 'observed_pure_premium_per_policy', label: 'Observed pure premium', type: 'amount2' },
  { key: 'indicated_pure_premium_per_policy', label: 'Credibility-weighted pure premium', type: 'amount2' },
  { key: 'current_earned_premium_per_policy', label: 'Current earned premium / policy', type: 'amount2' },
  { key: 'indicated_earned_premium_per_policy', label: 'Indicated earned premium / policy', type: 'amount2' },
  {
    key: 'indicated_rate_change_pct',
    label: 'Indicated rate change',
    type: 'text',
    render: (value, row) => row.indication_available ? formatSignedPercent(value) : row.unavailable_reason || 'Unavailable',
  },
];

function IndicationTable({ row }) {
  if (!row) return null;
  const values = [
    ['Policies', formatByType(row.policies, 'integer')],
    ['Claiming policies', formatByType(row.claiming_policies, 'integer')],
    ['Observed loss ratio', formatByType(row.observed_loss_ratio, 'percent')],
    ['Observed pure premium / policy', formatByType(row.observed_pure_premium_per_policy, 'amount2')],
    ['Credibility-weighted pure premium / policy', formatByType(row.indicated_pure_premium_per_policy, 'amount2')],
    ['Current earned premium / policy', formatByType(row.current_earned_premium_per_policy, 'amount2')],
    ['Indicated earned premium / policy', formatByType(row.indicated_earned_premium_per_policy, 'amount2')],
    ['Indicated rate change', row.indication_available ? formatSignedPercent(row.indicated_rate_change_pct) : row.unavailable_reason],
  ];
  return (
    <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-panel border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-4">
      {values.map(([label, value]) => (
        <div key={label} className="bg-panel px-3 py-3">
          <dt className="text-xs text-muted">{label}</dt>
          <dd className="mt-1 break-words font-medium tabular-nums">{value ?? 'n/a'}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function RateIndication() {
  const { applied, reset } = useFilters();
  const [targetLossRatioPct, setTargetLossRatioPct] = useState(DEFAULT_TARGET_LOSS_RATIO_PCT);
  const [exportState, setExportState] = useState({ busy: null, error: null, message: null });
  const invalidRateScope = Boolean(
    applied.claim_status ||
    ((applied.start_date || applied.end_date) && applied.date_basis === 'claim_date'),
  );
  const request = useApi(
    (signal) => invalidRateScope ? Promise.resolve(null) : api.rateIndication(applied, targetLossRatioPct, signal),
    [applied, targetLossRatioPct, invalidRateScope],
  );
  const response = request.data;
  const report = response?.data;

  async function exportIndication(format) {
    setExportState({ busy: format, error: null, message: null });
    try {
      const name = await downloadReport({
        section: 'rate-indication',
        format,
        filters: applied,
        extraParams: { target_loss_ratio_pct: targetLossRatioPct },
      });
      setExportState({ busy: null, error: null, message: `Saved ${name}` });
    } catch (error) {
      setExportState({ busy: null, error: error.message, message: null });
    }
  }

  function setTarget(value) {
    if (value === '') return;
    const parsed = Number(value);
    if (Number.isFinite(parsed) && parsed >= MIN_TARGET_LOSS_RATIO_PCT && parsed <= MAX_TARGET_LOSS_RATIO_PCT) {
      setTargetLossRatioPct(parsed);
    }
  }

  return (
    <div className="space-y-5">
      <Notice tone="warning" title="Experience indication, not a rate recommendation">
        This tool estimates an earned-premium indication from baseline synthetic experience. It does not create a forecast,
        filed rate, or production pricing recommendation.
      </Notice>

      <section aria-label="Rate indication assumptions" className="rounded-panel border border-rule bg-panel p-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0 flex-1">
            <label htmlFor="target-loss-ratio" className="text-sm font-medium">Target loss ratio</label>
            <input
              id="target-loss-ratio"
              aria-label="Target loss ratio"
              type="range"
              className="mt-2 block w-full accent-brand"
              min={MIN_TARGET_LOSS_RATIO_PCT}
              max={MAX_TARGET_LOSS_RATIO_PCT}
              step="0.5"
              value={targetLossRatioPct}
              onChange={(event) => setTarget(event.target.value)}
            />
            <p className="text-xs text-muted">Choose a target from 30% to 100%. The target loss ratio is the selected claims-to-earned-premium basis.</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              aria-label="Target loss ratio percentage"
              type="number"
              className="w-24 rounded-panel border border-rule bg-white px-2 py-1.5 text-right tabular-nums"
              min={MIN_TARGET_LOSS_RATIO_PCT}
              max={MAX_TARGET_LOSS_RATIO_PCT}
              step="0.5"
              value={targetLossRatioPct}
              onChange={(event) => setTarget(event.target.value)}
            />
            <span className="text-sm text-muted">%</span>
          </div>
        </div>
      </section>

      <ScopeBanner state={request} />

      {invalidRateScope ? (
        <Notice tone="warning" title="Rate indication unavailable for this filter scope">
          Claim-status and claim-date filters select on claim outcomes and exclude policies without claims. Remove those filters
          to restore a cohort-based indication.
          <button type="button" className="ml-2 underline" onClick={reset}>Reset filters</button>
        </Notice>
      ) : request.error ? (
        <ErrorState error={request.error} onRetry={request.reload} />
      ) : !response ? (
        <Loading />
      ) : response.meta.policies_in_scope === 0 ? (
        <EmptyState onReset={reset}>No policies match the current filters. Reset filters to restore the portfolio.</EmptyState>
      ) : (
        <>
          <Panel title="Filtered portfolio indication" subtitle="Overall baseline experience at the selected target loss ratio." state={request} height={170}>
            {(envelope) => (
              <>
                {!envelope.data.available && <Notice tone="warning" title="No indication available">{envelope.data.unavailable_reason}</Notice>}
                <IndicationTable row={envelope.data.overall} />
              </>
            )}
          </Panel>

          {DIMENSIONS.map((dimension) => (
            <Panel
              key={dimension.key}
              title={dimension.label}
              subtitle="Separate indications versus each segment's current earned premium per policy."
              state={request}
              height={150}
            >
              {(envelope) => (
                <DataTable
                  caption={`Credibility-weighted rate indication ${dimension.label.toLowerCase()}`}
                  columns={COLUMNS}
                  rows={envelope.data[dimension.key]}
                  rowKey="segment"
                  dense
                />
              )}
            </Panel>
          ))}

          <Panel title="Method and assumptions" state={request} height={140}>
            {(envelope) => (
              <div className="space-y-3 px-2 text-[13.5px]">
                <ol className="list-decimal space-y-1 pl-5">
                  {Object.entries(envelope.data.formulas).map(([name, formula]) => (
                    <li key={name}><span className="font-medium">{name.replaceAll('_', ' ')}:</span> {formula}</li>
                  ))}
                </ol>
                <p className="text-muted">
                  Segment credibility Z uses {envelope.data.assumptions.credibility_standard_basis.toLowerCase()} The (1 − Z) weight uses the
                  filtered portfolio's observed pure premium as its reference, not an external prior. The overall row is unblended and has no
                  applicable credibility factor. Severity-specific credibility, trend, expenses, profit, tax, reinsurance, capital and IBNR are not modelled.
                </p>
                <ul className="list-disc space-y-1 pl-5 text-muted">
                  {envelope.data.notes.map((note) => <li key={note}>{note}</li>)}
                </ul>
              </div>
            )}
          </Panel>
        </>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="btn" disabled={invalidRateScope || exportState.busy !== null} onClick={() => exportIndication('csv')}>
          {exportState.busy === 'csv' ? 'Preparing CSV…' : 'Export indication CSV'}
        </button>
        <button type="button" className="btn" disabled={invalidRateScope || exportState.busy !== null} onClick={() => exportIndication('json')}>
          {exportState.busy === 'json' ? 'Preparing JSON…' : 'Export indication JSON'}
        </button>
        {exportState.message && <p role="status" className="text-sm text-sage">{exportState.message}</p>}
        {exportState.error && <p role="alert" className="text-sm text-brick">{exportState.error}</p>}
      </div>
    </div>
  );
}
