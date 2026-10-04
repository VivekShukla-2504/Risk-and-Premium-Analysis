import KpiBand from '../components/KpiBand.jsx';
import Panel from '../components/Panel.jsx';
import ScopeBanner from '../components/ScopeBanner.jsx';
import Notice from '../components/Notice.jsx';
import { Async, EmptyState } from '../components/StateViews.jsx';
import { CategoryBar } from '../components/charts/BarCharts.jsx';
import Donut from '../components/charts/Donut.jsx';
import MonthlyChart from '../components/charts/MonthlyChart.jsx';
import { ClaimScatter, CoverageLine } from '../components/charts/ScatterCharts.jsx';
import { useApi } from '../hooks/useApi.js';
import { useFilters } from '../hooks/useFilters.jsx';
import { api } from '../services/api.js';
import { coverageBandRows, monthlyRows, scatterRows, segmentRows, statusRows, tierRows } from '../utils/chartData.js';
import { STATUS_COLORS, TIER_COLORS } from '../utils/chartTheme.js';
import { correlationText, testSentence } from '../utils/describe.js';

const typeTable = (cols) => (d) => ({
  columns: [{ key: 'name', label: 'Policy type', type: 'text' }, ...cols],
  rows: segmentRows(d.data.segments),
});

export default function Dashboard() {
  const { applied, reset } = useFilters();
  const summary = useApi((s) => api.summary(applied, s), [applied]);
  const types = useApi((s) => api.policyTypes(applied, s), [applied]);
  const ages = useApi((s) => api.ageBands(applied, s), [applied]);
  const claims = useApi((s) => api.claims(applied, s, { includePoints: true, maxPoints: 500 }), [applied]);
  const monthly = useApi((s) => api.monthlyTrends(applied, s), [applied]);
  const risk = useApi((s) => api.riskSegments(applied, s), [applied]);

  return (
    <>
      <ScopeBanner state={summary} />

      <Async state={summary} minHeight={180}>
        {(r) => (r.meta.policies_in_scope === 0
          ? <EmptyState onReset={reset}>No records match the current filters. Reset filters to restore the portfolio.</EmptyState>
          : <KpiBand data={r.data} meta={r.meta} />)}
      </Async>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel
          title="Premium by policy type"
          subtitle="Written premium (full-term)"
          state={types}
          tableOf={typeTable([{ key: 'premium', label: 'Premium', type: 'amount' }, { key: 'policies', label: 'Policies', type: 'integer' }])}
        >
          {(d) => <CategoryBar data={segmentRows(d.data.segments)} bars={[{ key: 'premium', name: 'Premium' }]} ariaLabel="Premium by policy type" />}
        </Panel>

        <Panel
          title="Claim amount by policy type"
          subtitle="Incurred: settled plus pending"
          state={types}
          tableOf={typeTable([{ key: 'claimAmount', label: 'Claim amount', type: 'amount' }, { key: 'claims', label: 'Claims', type: 'integer' }])}
        >
          {(d) => <CategoryBar data={segmentRows(d.data.segments)} bars={[{ key: 'claimAmount', name: 'Claim amount', color: '#B98320' }]} ariaLabel="Claim amount by policy type" />}
        </Panel>

        <Panel
          title="Loss ratio by policy type"
          subtitle="Incurred claims divided by earned premium"
          state={types}
          rateMetric
          tableOf={typeTable([{ key: 'lossRatio', label: 'Loss ratio', type: 'percent', rateMetric: true }])}
          footnote="The dashed line marks 100%, where claims equal premium. Ratios this far above it are a feature of the synthetic data."
        >
          {(d) => (
            <CategoryBar
              data={segmentRows(d.data.segments)}
              bars={[{ key: 'lossRatio', name: 'Loss ratio', color: '#A24A42' }]}
              format="percent"
              refLine={{ value: 1, label: '100%' }}
              ariaLabel="Loss ratio by policy type"
            />
          )}
        </Panel>

        <Panel
          title="Claim severity by policy type"
          subtitle={(d) => `Average claim size. Differences between types: ${testSentence(d.data.statistical_tests.claim_severity)}`}
          state={types}
          tableOf={typeTable([{ key: 'severity', label: 'Average claim', type: 'amount2' }, { key: 'claims', label: 'Claims', type: 'integer' }])}
        >
          {(d) => <CategoryBar data={segmentRows(d.data.segments)} bars={[{ key: 'severity', name: 'Average claim', color: '#58688A' }]} format="amount" ariaLabel="Claim severity by policy type" />}
        </Panel>

        <Panel
          title="Claims by age band"
          subtitle="Number of policies with a payable claim"
          state={ages}
          tableOf={(d) => ({
            columns: [
              { key: 'name', label: 'Age band', type: 'text' },
              { key: 'claims', label: 'Claims', type: 'integer' },
              { key: 'policies', label: 'Policies', type: 'integer' },
              { key: 'frequency', label: 'Frequency', type: 'percent', rateMetric: true },
            ],
            rows: segmentRows(d.data.segments),
          })}
        >
          {(d) => <CategoryBar data={segmentRows(d.data.segments)} bars={[{ key: 'claims', name: 'Claims' }]} format="integer" ariaLabel="Claims by age band" />}
        </Panel>

        <Panel
          title="Claim status distribution"
          subtitle="Policies by claim status"
          state={claims}
          tableOf={(d) => ({
            columns: [
              { key: 'name', label: 'Status', type: 'text' },
              { key: 'value', label: 'Policies', type: 'integer' },
              { key: 'share', label: 'Share', type: 'percent' },
              { key: 'amount', label: 'Incurred amount', type: 'amount' },
            ],
            rows: statusRows(d.data.claim_status.statuses),
          })}
          footnote={(d) => d.data.claim_status.notes[1]}
        >
          {(d) => <Donut rows={statusRows(d.data.claim_status.statuses)} colors={STATUS_COLORS} ariaLabel="Claim status distribution" />}
        </Panel>

        <Panel
          title="Premium vs coverage"
          subtitle={(d) => correlationText(d.data.correlations.premium_vs_coverage, 'Average premium by coverage band')}
          state={claims}
          tableOf={(d) => ({
            columns: [
              { key: 'name', label: 'Coverage band', type: 'text' },
              { key: 'coverage', label: 'Avg coverage', type: 'amount' },
              { key: 'premium', label: 'Avg premium', type: 'amount2' },
              { key: 'policies', label: 'Policies', type: 'integer' },
            ],
            rows: coverageBandRows(d.data.coverage_bands.bands),
          })}
        >
          {(d) => <CoverageLine data={coverageBandRows(d.data.coverage_bands.bands)} lines={[{ key: 'premium', name: 'Average premium' }]} />}
        </Panel>

        <Panel
          title="Claim amount vs coverage"
          subtitle={(d) => correlationText(d.data.correlations.claim_amount_vs_coverage, 'Sample of claims')}
          state={claims}
          footnote={(d) => d.data.points?.note}
        >
          {(d) => <ClaimScatter data={scatterRows(d.data.points?.claims)} />}
        </Panel>

        <Panel
          title="Monthly claims"
          subtitle="Claim counts by month and claims per 100 policy-months in force"
          state={monthly}
          className="xl:col-span-2"
          height={300}
          tableOf={(d) => ({
            columns: [
              { key: 'name', label: 'Month', type: 'text' },
              { key: 'claims', label: 'Claims', type: 'integer' },
              { key: 'exposure', label: 'Policy-months in force', type: 'amount' },
              { key: 'rate', label: 'Claims per 100 policy-months', type: 'number', rateMetric: true },
              { key: 'incurred', label: 'Incurred amount', type: 'amount' },
            ],
            rows: monthlyRows(d.data.months),
          })}
          footnote={(d) => `${d.data.notes[0]} Faded bars mark months with under 10% of peak exposure.`}
        >
          {(d) => <MonthlyChart data={monthlyRows(d.data.months)} rateMetricsValid={d.meta.rate_metrics_valid} />}
        </Panel>

        <Panel
          title="Risk segment distribution"
          subtitle="Policies by rule-based risk tier (age and coverage rules)"
          state={risk}
          tableOf={(d) => ({
            columns: [
              { key: 'name', label: 'Tier', type: 'text' },
              { key: 'value', label: 'Policies', type: 'integer' },
              { key: 'share', label: 'Share', type: 'percent' },
              { key: 'frequency', label: 'Claim frequency', type: 'percent', rateMetric: true },
              { key: 'lossRatio', label: 'Loss ratio', type: 'percent', rateMetric: true },
            ],
            rows: tierRows(d.data.a_priori_tiers),
          })}
          footnote={(d) => d.meta.rate_metrics_valid
            ? d.data.conclusion
            : 'Claim-frequency comparisons are unavailable for an outcome-selected scope.'}
        >
          {(d) => <Donut rows={tierRows(d.data.a_priori_tiers)} colors={TIER_COLORS} ariaLabel="Risk segment distribution" />}
        </Panel>

        <Panel title="Basis of these figures" state={summary} height={200}>
          {(r) => (
            <div className="space-y-3 px-2 text-[13.5px]">
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
                <dt className="text-muted">Valuation date</dt>
                <dd>{r.data.basis.valuation_date || 'n/a'}</dd>
                <dt className="text-muted">Incurred claims</dt>
                <dd>{r.data.basis.incurred_definition}</dd>
                <dt className="text-muted">Premium for loss ratio</dt>
                <dd>{r.data.basis.premium_basis_for_loss_ratio}</dd>
              </dl>
              {r.meta.warnings.length === 0 && (
                <Notice tone="info">{r.meta.disclaimer}</Notice>
              )}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
