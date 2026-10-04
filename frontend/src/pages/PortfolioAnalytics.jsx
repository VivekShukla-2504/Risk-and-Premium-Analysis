import DataTable from '../components/DataTable.jsx';
import Panel from '../components/Panel.jsx';
import ScopeBanner from '../components/ScopeBanner.jsx';
import Verdict from '../components/Verdict.jsx';
import { RateMetricUnavailable } from '../components/StateViews.jsx';
import { FrequencyCI } from '../components/charts/BarCharts.jsx';
import { useApi } from '../hooks/useApi.js';
import { useFilters } from '../hooks/useFilters.jsx';
import { api } from '../services/api.js';
import { frequencyRows } from '../utils/chartData.js';
import { yesNo } from '../utils/describe.js';
import { formatByType } from '../utils/format.js';

const interval = (_, r) => (r.claim_frequency_ci_low == null ? 'n/a' : `${formatByType(r.claim_frequency_ci_low, 'percent')} to ${formatByType(r.claim_frequency_ci_high, 'percent')}`);
const versus = (_, r) => (r.frequency_ci_includes_portfolio == null ? 'n/a' : r.frequency_ci_includes_portfolio ? 'Consistent with portfolio' : 'Differs from portfolio');

const SEGMENT_COLUMNS = (label) => [
  { key: 'segment', label, type: 'text' },
  { key: 'policies', label: 'Policies', type: 'integer' },
  { key: 'share_of_policies', label: 'Share', type: 'percent' },
  { key: 'claiming_policies', label: 'Claims', type: 'integer' },
  { key: 'claim_frequency', label: 'Frequency', type: 'percent', rateMetric: true },
  { key: 'ci', label: '95% interval', render: interval, rateMetric: true },
  { key: 'vs', label: 'Frequency vs portfolio', type: 'text', align: 'left', render: versus, rateMetric: true },
  { key: 'claim_severity', label: 'Severity', type: 'amount2' },
  { key: 'pure_premium', label: 'Pure premium', type: 'amount2', rateMetric: true },
  { key: 'total_premium', label: 'Premium', type: 'amount' },
  { key: 'loss_ratio', label: 'Loss ratio', type: 'percent', rateMetric: true },
  { key: 'credibility_z', label: 'Credibility', type: 'number' },
];

const AE_COLUMNS = (label) => [
  { key: 'segment', label, type: 'text' },
  { key: 'actual_claims', label: 'Actual claims', type: 'integer' },
  { key: 'expected_claims', label: 'Expected claims', type: 'number', rateMetric: true },
  { key: 'actual_to_expected_claims', label: 'Actual / expected', type: 'number3', rateMetric: true },
  { key: 'z_score', label: 'z-score', type: 'number', rateMetric: true },
  { key: 'p_value', label: 'p-value', type: 'p', rateMetric: true },
  { key: 'significant_at_5pct', label: 'Significant at 5%', type: 'text', align: 'left', render: (v) => yesNo(v), rateMetric: true },
  { key: 'actual_to_expected_cost', label: 'Cost actual / expected', type: 'number3', rateMetric: true },
];

function SegmentSection({ title, label, state }) {
  return (
    <Panel
      title={title}
      subtitle="Every measure is calculated by the API from the filtered portfolio."
      state={state}
      height={240}
      footnote={(d) => d.data.notes[0]}
    >
      {(d) => (
        <div className="space-y-5">
          <DataTable caption={title} columns={SEGMENT_COLUMNS(label)} rows={d.data.segments} rowKey="segment" />
          <div className="grid gap-3 px-2 lg:grid-cols-2">
            {d.meta.rate_metrics_valid
              ? <Verdict label="Is claim frequency different between groups?" test={d.data.statistical_tests.claim_frequency} />
              : <RateMetricUnavailable />}
            <Verdict label="Is average claim size different between groups?" test={d.data.statistical_tests.claim_severity} />
          </div>
          <div>
            <h4 className="px-3 pb-1 font-serif text-[0.95rem]">Actual versus expected claims</h4>
            <p className="px-3 pb-2 text-[13px] text-muted">Expected assumes each group claims at the portfolio rate. Rate-based comparisons are unavailable when filters select on claim outcomes.</p>
            <DataTable caption={`${title}: actual versus expected`} columns={AE_COLUMNS(label)} rows={d.data.actual_vs_expected} rowKey="segment" />
          </div>
        </div>
      )}
    </Panel>
  );
}

export default function PortfolioAnalytics() {
  const { applied } = useFilters();
  const types = useApi((s) => api.policyTypes(applied, s), [applied]);
  const ages = useApi((s) => api.ageBands(applied, s), [applied]);
  const freq = useApi((s) => api.frequency(applied, s), [applied]);
  const lossRatio = useApi((s) => api.lossRatio(applied, s), [applied]);

  return (
    <>
      <ScopeBanner state={types} />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel
          title="Claim frequency by policy type"
          subtitle="Whiskers show the 95% interval. The dashed line is the portfolio frequency."
          state={freq}
          rateMetric
          footnote="If every whisker crosses the dashed line, the differences are consistent with chance."
        >
          {(d) => <FrequencyCI data={frequencyRows(d.data.by_policy_type.segments)} portfolio={d.data.overall.claim_frequency} ariaLabel="Claim frequency by policy type with intervals" />}
        </Panel>
        <Panel title="Claim frequency by age band" subtitle="Same layout, by age band." state={freq} rateMetric>
          {(d) => <FrequencyCI data={frequencyRows(d.data.by_age_band.segments)} portfolio={d.data.overall.claim_frequency} ariaLabel="Claim frequency by age band with intervals" />}
        </Panel>
      </div>

      <SegmentSection title="Policy types" label="Policy type" state={types} />
      <SegmentSection title="Age bands" label="Age band" state={ages} />

      <Panel title="Gender" subtitle="Claim frequency and loss ratio by gender." state={freq} height={160}>
        {(f) => (
          <GenderTable freq={f.data.by_gender.segments} test={f.data.by_gender.test} lossState={lossRatio} rateMetricsValid={f.meta.rate_metrics_valid} />
        )}
      </Panel>
    </>
  );
}

function GenderTable({ freq, test, lossState, rateMetricsValid }) {
  const lr = lossState.data?.data.by_gender || [];
  const rows = freq.map((s) => ({ ...s, ...(lr.find((x) => x.segment === s.segment) || {}) , name: s.segment }));
  const columns = [
    { key: 'segment', label: 'Gender', type: 'text' },
    { key: 'policies', label: 'Policies', type: 'integer' },
    { key: 'claiming_policies', label: 'Claims', type: 'integer' },
    { key: 'claim_frequency', label: 'Frequency', type: 'percent', rateMetric: true },
    { key: 'ci', label: '95% interval', render: (_, r) => (r.ci_95_low == null ? 'n/a' : `${formatByType(r.ci_95_low, 'percent')} to ${formatByType(r.ci_95_high, 'percent')}`), rateMetric: true },
    { key: 'loss_ratio', label: 'Loss ratio', type: 'percent', rateMetric: true },
    { key: 'paid_loss_ratio', label: 'Paid loss ratio', type: 'percent', rateMetric: true },
  ];
  return (
    <div className="space-y-4">
      <DataTable caption="Gender" columns={columns} rows={rows} rowKey="segment" rateMetricsValid={rateMetricsValid} />
      <div className="px-2">{rateMetricsValid
        ? <Verdict label="Is claim frequency different between genders?" test={test} />
        : <RateMetricUnavailable />}</div>
    </div>
  );
}
