import DataTable from '../components/DataTable.jsx';
import Notice from '../components/Notice.jsx';
import Panel from '../components/Panel.jsx';
import ScopeBanner from '../components/ScopeBanner.jsx';
import Verdict from '../components/Verdict.jsx';
import { RateMetricUnavailable } from '../components/StateViews.jsx';
import { CategoryBar, FrequencyCI } from '../components/charts/BarCharts.jsx';
import Donut from '../components/charts/Donut.jsx';
import { useApi } from '../hooks/useApi.js';
import { useFilters } from '../hooks/useFilters.jsx';
import { api } from '../services/api.js';
import { frequencyRows, tierRows } from '../utils/chartData.js';
import { TIER_COLORS } from '../utils/chartTheme.js';
import { yesNo } from '../utils/describe.js';
import { formatByType } from '../utils/format.js';

const TIER_COLUMNS = [
  { key: 'segment', label: 'Tier', type: 'text' },
  { key: 'policies', label: 'Policies', type: 'integer' },
  { key: 'share_of_policies', label: 'Share', type: 'percent' },
  { key: 'claiming_policies', label: 'Claims', type: 'integer' },
  { key: 'claim_frequency', label: 'Frequency', type: 'percent', rateMetric: true },
  { key: 'ci', label: '95% interval', render: (_, r) => (r.claim_frequency_ci_low == null ? 'n/a' : `${formatByType(r.claim_frequency_ci_low, 'percent')} to ${formatByType(r.claim_frequency_ci_high, 'percent')}`), rateMetric: true },
  { key: 'claim_severity', label: 'Severity', type: 'amount2' },
  { key: 'pure_premium', label: 'Pure premium', type: 'amount2', rateMetric: true },
  { key: 'loss_ratio', label: 'Loss ratio', type: 'percent', rateMetric: true },
  { key: 'credibility_z', label: 'Credibility', type: 'number' },
];

const AE_COLUMNS = [
  { key: 'segment', label: 'Tier', type: 'text' },
  { key: 'actual_claims', label: 'Actual claims', type: 'integer' },
  { key: 'expected_claims', label: 'Expected claims', type: 'number', rateMetric: true },
  { key: 'actual_to_expected_claims', label: 'Actual / expected', type: 'number3', rateMetric: true },
  { key: 'z_score', label: 'z-score', type: 'number', rateMetric: true },
  { key: 'p_value', label: 'p-value', type: 'p', rateMetric: true },
  { key: 'significant_at_5pct', label: 'Significant at 5%', type: 'text', align: 'left', render: (v) => yesNo(v), rateMetric: true },
  { key: 'actual_to_expected_cost', label: 'Cost actual / expected', type: 'number3', rateMetric: true },
];

const POINT_COLUMNS = [
  { key: 'factor', label: 'Factor', type: 'text' },
  { key: 'condition', label: 'Condition', type: 'text', align: 'left' },
  { key: 'points', label: 'Points', type: 'integer' },
  { key: 'rationale', label: 'Why', type: 'text', align: 'left' },
];

const CLASS_COLUMNS = [
  { key: 'class', label: 'Claim size class', type: 'text' },
  { key: 'policies', label: 'Policies', type: 'integer' },
  { key: 'share_of_policies', label: 'Share', type: 'percent' },
  { key: 'total_claim_amount', label: 'Claim amount', type: 'amount' },
  { key: 'share_of_claim_amount', label: 'Share of claim amount', type: 'percent' },
  { key: 'average_claim_amount', label: 'Average claim', type: 'amount2' },
  { key: 'settled_claims', label: 'Settled', type: 'integer' },
  { key: 'pending_claims', label: 'Pending', type: 'integer' },
];

export default function RiskSegmentation() {
  const { applied } = useFilters();
  const risk = useApi((s) => api.riskSegments(applied, s), [applied]);

  return (
    <>
      <ScopeBanner state={risk} />

      <Panel title="What the data says" state={risk} height={100}>
        {(d) => (
          <div className="px-2">
            <Notice tone={d.meta.rate_metrics_valid && d.data.tiers_supported_by_experience ? 'success' : 'warning'}>
              {d.meta.rate_metrics_valid ? d.data.conclusion : 'Tier comparisons based on claim frequency are unavailable for an outcome-selected scope.'}
            </Notice>
          </div>
        )}
      </Panel>

      <Panel title="How the tiers are assigned" subtitle={(d) => d.data.rules.a_priori_tiers.purpose} state={risk} height={200}>
        {(d) => {
          const r = d.data.rules.a_priori_tiers;
          return (
            <div className="space-y-3">
              <DataTable caption="Risk tier points" columns={POINT_COLUMNS} rows={r.points} rowKey="factor" />
              <ul className="flex flex-wrap gap-x-6 gap-y-1 px-3 text-[13.5px]">
                {Object.entries(r.tiers).map(([tier, rule]) => (
                  <li key={tier}><span className="font-medium">{tier}</span> tier: {rule}</li>
                ))}
              </ul>
              <div className="space-y-2 px-2">
                <Notice tone="info">{r.policy_type}</Notice>
                <Notice tone="warning">{r.caveat}</Notice>
              </div>
            </div>
          );
        }}
      </Panel>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel
          title="Policies by risk tier"
          subtitle="Share of policies falling in each tier"
          state={risk}
          tableOf={(d) => ({
            columns: [
              { key: 'name', label: 'Tier', type: 'text' },
              { key: 'value', label: 'Policies', type: 'integer' },
              { key: 'share', label: 'Share', type: 'percent' },
            ],
            rows: tierRows(d.data.a_priori_tiers),
          })}
        >
          {(d) => <Donut rows={tierRows(d.data.a_priori_tiers)} colors={TIER_COLORS} ariaLabel="Policies by risk tier" />}
        </Panel>

        <Panel
          title="Do claims follow the tiers?"
          subtitle="Claim frequency by tier with 95% intervals. The dashed line is the portfolio frequency."
          state={risk}
          rateMetric
          footnote="A real risk gradient would show frequency rising from Low to High with clearly separated intervals."
        >
          {(d) => <FrequencyCI data={frequencyRows(d.data.a_priori_tiers)} portfolio={d.data.portfolio_claim_frequency} ariaLabel="Claim frequency by risk tier" />}
        </Panel>
      </div>

      <Panel title="Tier results" state={risk} height={200}>
        {(d) => (
          <div className="space-y-4">
            <DataTable caption="Risk tier results" columns={TIER_COLUMNS} rows={d.data.a_priori_tiers} rowKey="segment" />
            <div className="grid gap-3 px-2 lg:grid-cols-2">
              {d.meta.rate_metrics_valid
                ? <Verdict label="Is claim frequency different between tiers?" test={d.data.tier_significance.claim_frequency} />
                : <RateMetricUnavailable />}
              <Verdict label="Is average claim size different between tiers?" test={d.data.tier_significance.claim_severity} />
            </div>
            <div>
              <h4 className="px-3 pb-1 font-serif text-[0.95rem]">Actual versus expected claims</h4>
              <p className="px-3 pb-2 text-[13px] text-muted">Expected assumes each tier claims at the portfolio rate. This is the test of whether the tiers carry information.</p>
              <DataTable caption="Actual versus expected by tier" columns={AE_COLUMNS} rows={d.data.actual_vs_expected} rowKey="segment" />
            </div>
          </div>
        )}
      </Panel>

      <Panel
        title="Claim size classes"
        subtitle={(d) => d.data.rules.claim_experience_classes.purpose}
        state={risk}
        tableOf={(d) => ({ columns: CLASS_COLUMNS, rows: d.data.claim_experience_classes })}
        footnote={(d) => d.data.rules.claim_experience_classes.caveat}
      >
        {(d) => (
          <CategoryBar
            data={d.data.claim_experience_classes.map((c) => ({ name: c.class, policies: c.policies }))}
            bars={[{ key: 'policies', name: 'Policies', color: '#58688A' }]}
            format="integer"
            ariaLabel="Policies by claim size class"
          />
        )}
      </Panel>
    </>
  );
}
