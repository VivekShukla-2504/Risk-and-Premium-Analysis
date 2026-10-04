import DataTable from '../components/DataTable.jsx';
import Notice from '../components/Notice.jsx';
import Panel from '../components/Panel.jsx';
import ScopeBanner from '../components/ScopeBanner.jsx';
import Verdict from '../components/Verdict.jsx';
import { RateMetricUnavailable } from '../components/StateViews.jsx';
import { CategoryBar } from '../components/charts/BarCharts.jsx';
import { CoverageLine } from '../components/charts/ScatterCharts.jsx';
import { useApi } from '../hooks/useApi.js';
import { useFilters } from '../hooks/useFilters.jsx';
import { api } from '../services/api.js';
import { coverageBandRows, histogramRows } from '../utils/chartData.js';
import { correlationText } from '../utils/describe.js';
import { formatByType } from '../utils/format.js';

function StatGrid({ items }) {
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-panel border border-rule bg-rule sm:grid-cols-4">
      {items.map((i) => (
        <div key={i.label} className="bg-panel px-3 py-3">
          <dt className="text-xs text-muted">{i.label}</dt>
          <dd className="mt-1 font-serif text-xl tabular-nums">{i.value}</dd>
        </div>
      ))}
    </dl>
  );
}

const STATUS_COLUMNS = [
  { key: 'status', label: 'Status', type: 'text' },
  { key: 'policies', label: 'Policies', type: 'integer' },
  { key: 'share_of_policies', label: 'Share', type: 'percent' },
  { key: 'claim_records', label: 'Counted as claims', type: 'integer' },
  { key: 'average_claim_amount', label: 'Average amount', type: 'amount2' },
  { key: 'paid_amount', label: 'Paid', type: 'amount' },
  { key: 'outstanding_amount', label: 'Outstanding', type: 'amount' },
  { key: 'incurred_amount', label: 'Incurred', type: 'amount' },
  { key: 'share_of_incurred', label: 'Share of incurred', type: 'percent' },
];

const SEVERITY_COLUMNS = (label) => [
  { key: 'segment', label, type: 'text' },
  { key: 'claims', label: 'Claims', type: 'integer' },
  { key: 'mean', label: 'Mean', type: 'amount2' },
  { key: 'median', label: 'Median', type: 'amount2' },
  { key: 'std', label: 'Std deviation', type: 'amount2' },
  { key: 'ci', label: '95% interval for mean', render: (_, r) => (r.ci_95_low == null ? 'n/a' : `${formatByType(r.ci_95_low, 'amount')} to ${formatByType(r.ci_95_high, 'amount')}`) },
  { key: 'min', label: 'Min', type: 'amount' },
  { key: 'max', label: 'Max', type: 'amount' },
];

export default function ClaimsAnalytics() {
  const { applied } = useFilters();
  const claims = useApi((s) => api.claims(applied, s), [applied]);
  const severity = useApi((s) => api.severity(applied, s), [applied]);
  const lossRatio = useApi((s) => api.lossRatio(applied, s), [applied]);

  return (
    <>
      <ScopeBanner state={claims} />

      <Panel title="Claim status" subtitle="How claims break down by status, with paid and outstanding amounts." state={claims} height={180}>
        {(d) => (
          <div className="space-y-3">
            <DataTable caption="Claim status" columns={STATUS_COLUMNS} rows={d.data.claim_status.statuses} rowKey="status" />
            <div className="space-y-2 px-2">
              {d.data.claim_status.notes.map((n) => (
                <Notice key={n} tone="info">{n}</Notice>
              ))}
            </div>
          </div>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel
          title="Coverage versus claim size"
          subtitle={(d) => correlationText(d.data.correlations.claim_amount_vs_coverage, 'Claim amount and coverage')}
          state={claims}
          tableOf={(d) => ({
            columns: [
              { key: 'name', label: 'Coverage band', type: 'text' },
              { key: 'policies', label: 'Policies', type: 'integer' },
              { key: 'coverage', label: 'Avg coverage', type: 'amount' },
              { key: 'premium', label: 'Avg premium', type: 'amount2' },
              { key: 'claimAmount', label: 'Avg claim', type: 'amount2' },
              { key: 'frequency', label: 'Frequency', type: 'percent', rateMetric: true },
            ],
            rows: coverageBandRows(d.data.coverage_bands.bands),
          })}
          footnote={(d) => d.data.correlations.note}
        >
          {(d) => (
            <CoverageLine
              data={coverageBandRows(d.data.coverage_bands.bands)}
              lines={[{ key: 'claimAmount', name: 'Average claim', color: '#B98320' }, { key: 'premium', name: 'Average premium' }]}
            />
          )}
        </Panel>

        <Panel title="Claim-to-coverage ratio" subtitle="Claim amount as a share of the policy's coverage, for policies with a claim." state={claims} height={220}>
          {(d) => {
            const c = d.data.claim_to_coverage;
            return (
              <div className="space-y-3 px-2">
                <StatGrid
                  items={[
                    { label: 'Mean', value: formatByType(c.mean, 'percent') },
                    { label: 'Median', value: formatByType(c.median, 'percent') },
                    { label: 'Largest', value: formatByType(c.max, 'percent') },
                    { label: 'Claims above coverage', value: formatByType(c.claims_exceeding_coverage, 'integer') },
                  ]}
                />
                <details className="text-[13.5px]">
                  <summary className="cursor-pointer text-muted">How this is defined</summary>
                  <p className="mt-2"><span className="font-medium">Formula:</span> {c.definition.formula}</p>
                  <p className="mt-1"><span className="font-medium">Limitations:</span> {c.definition.limitations}</p>
                </details>
              </div>
            );
          }}
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel title="Distribution of claim sizes" subtitle="Number of claims in each size range." state={severity}
          tableOf={(d) => ({ columns: [{ key: 'name', label: 'Claim size range', type: 'text' }, { key: 'claims', label: 'Claims', type: 'integer' }], rows: histogramRows(d.data.histogram) })}
          footnote={(d) => d.data.notes[2]}>
          {(d) => <CategoryBar data={histogramRows(d.data.histogram)} bars={[{ key: 'claims', name: 'Claims' }]} format="integer" ariaLabel="Histogram of claim sizes" />}
        </Panel>

        <Panel title="Severity summary" subtitle="Claim severity = total claim amount / number of claims." state={severity} height={240}>
          {(d) => (
            <div className="space-y-3 px-2">
              <StatGrid
                items={[
                  { label: 'Average claim', value: formatByType(d.data.overall.mean, 'amount2') },
                  { label: 'Median claim', value: formatByType(d.data.overall.median, 'amount2') },
                  { label: 'Std deviation', value: formatByType(d.data.overall.std, 'amount2') },
                  { label: 'Variation (CV)', value: formatByType(d.data.overall.cv, 'number') },
                ]}
              />
              <DataTable
                caption="Severity quantiles"
                columns={Object.keys(d.data.quantiles).map((k) => ({ key: k, label: k.toUpperCase(), type: 'amount' }))}
                rows={[d.data.quantiles]}
                dense
              />
              <p className="text-[13px] text-muted">95% interval for the mean: {formatByType(d.data.overall.ci_95_low, 'amount2')} to {formatByType(d.data.overall.ci_95_high, 'amount2')}.</p>
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Severity by policy type" state={severity} height={200}>
        {(d) => (
          <div className="space-y-3">
            <DataTable caption="Severity by policy type" columns={SEVERITY_COLUMNS('Policy type')} rows={d.data.by_policy_type} rowKey="segment" />
            <div className="px-2"><Verdict label="Is average claim size different between policy types?" test={d.data.statistical_tests.policy_type} /></div>
          </div>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel title="Severity by age band" state={severity} height={200}>
          {(d) => (
            <div className="space-y-3">
              <DataTable caption="Severity by age band" columns={SEVERITY_COLUMNS('Age band').slice(0, 5)} rows={d.data.by_age_band} rowKey="segment" dense />
              <div className="px-2"><Verdict label="Is average claim size different between age bands?" test={d.data.statistical_tests.age_band} /></div>
            </div>
          )}
        </Panel>
        <Panel title="Severity by claim status" subtitle="Pending amounts are estimates." state={severity} height={200}>
          {(d) => <DataTable caption="Severity by claim status" columns={SEVERITY_COLUMNS('Status').slice(0, 5)} rows={d.data.by_claim_status} rowKey="segment" dense />}
        </Panel>
      </div>

      <Panel title="Loss ratio" subtitle="Incurred claims divided by earned premium, and two reference versions." state={lossRatio} height={200}
        footnote={(d) => d.data.notes[0]}>
        {(d) => {
          const p = d.data.portfolio;
          return (
            <div className="space-y-4">
              <div className="px-2">
                <StatGrid
                  items={[
                    { label: 'Loss ratio (incurred)', value: d.meta.rate_metrics_valid ? formatByType(p.loss_ratio, 'percent') : 'Unavailable' },
                    { label: 'Settled claims only', value: d.meta.rate_metrics_valid ? formatByType(p.paid_loss_ratio, 'percent') : 'Unavailable' },
                    { label: 'On written premium (reference)', value: d.meta.rate_metrics_valid ? formatByType(p.loss_ratio_on_written_premium, 'percent') : 'Unavailable' },
                    { label: 'Outstanding (pending) amount', value: formatByType(p.total_outstanding_amount, 'amount') },
                  ]}
                />
              </div>
              <DataTable
                caption="Loss ratio by policy type"
                columns={[
                  { key: 'segment', label: 'Policy type', type: 'text' },
                  { key: 'total_claim_amount', label: 'Incurred claims', type: 'amount' },
                  { key: 'total_earned_premium', label: 'Earned premium', type: 'amount' },
                  { key: 'loss_ratio', label: 'Loss ratio', type: 'percent', rateMetric: true },
                  { key: 'paid_loss_ratio', label: 'Paid loss ratio', type: 'percent', rateMetric: true },
                  { key: 'credibility_z', label: 'Credibility', type: 'number' },
                ]}
                rows={d.data.by_policy_type}
                rowKey="segment"
              />
              {!d.meta.rate_metrics_valid && <RateMetricUnavailable />}
              <details className="px-3 text-[13.5px]">
                <summary className="cursor-pointer text-muted">Definition and limitations</summary>
                <p className="mt-2"><span className="font-medium">Formula:</span> {d.data.definitions.loss_ratio.formula}</p>
                <p className="mt-1"><span className="font-medium">Assumptions:</span> {d.data.definitions.loss_ratio.assumptions}</p>
                <p className="mt-1"><span className="font-medium">Limitations:</span> {d.data.definitions.loss_ratio.limitations}</p>
              </details>
            </div>
          );
        }}
      </Panel>
    </>
  );
}
