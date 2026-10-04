import DataTable from '../components/DataTable.jsx';
import Notice from '../components/Notice.jsx';
import Panel from '../components/Panel.jsx';
import { useApi } from '../hooks/useApi.js';
import { api } from '../services/api.js';
import { formatByType, formatSignedPercent } from '../utils/format.js';
import { yesNo } from '../utils/describe.js';

function DefinitionList({ definitions }) {
  return (
    <div className="divide-y divide-rule/70">
      {Object.entries(definitions).map(([key, d]) => (
        <details key={key} className="group px-4 py-2.5 text-[13.5px]">
          <summary className="flex cursor-pointer flex-wrap items-baseline justify-between gap-x-4">
            <span className="font-medium">{d.name}</span>
            <span className="text-muted">{d.formula}</span>
          </summary>
          <dl className="mt-3 grid gap-x-4 gap-y-2 sm:grid-cols-[9rem_1fr]">
            <dt className="text-muted">Numerator</dt><dd>{d.numerator}</dd>
            <dt className="text-muted">Denominator</dt><dd>{d.denominator}</dd>
            <dt className="text-muted">Assumptions</dt><dd>{d.assumptions}</dd>
            <dt className="text-muted">Limitations</dt><dd>{d.limitations}</dd>
          </dl>
        </details>
      ))}
    </div>
  );
}

const SEVERITY_TONE = { warning: 'warning', info: 'info' };

export default function Methodology() {
  const meth = useApi((s) => api.methodology(s), []);
  const dq = useApi((s) => api.dataQuality(s), []);

  return (
    <>
      <Panel title="Read this first" state={meth} height={80}>
        {(m) => (
          <div className="space-y-2 px-2">
            <Notice tone="warning">{m.disclaimer}</Notice>
            <p className="text-[13.5px] text-muted">
              Every number in this application is calculated by the backend from the policy and claim file. The browser only formats and draws what the API returns.
            </p>
          </div>
        )}
      </Panel>

      <Panel title="Data audit findings" subtitle="What the dataset can and cannot support, and the decision taken for each." state={dq} height={200}>
        {(d) => (
          <div className="space-y-4 px-2">
            <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-panel border border-rule bg-rule sm:grid-cols-4">
              {[
                ['Rows in file', formatByType(d.shape.rows_raw, 'integer')],
                ['Duplicate rows removed', formatByType(d.cleaning.exact_duplicate_rows_removed, 'integer')],
                ['Policies analysed', formatByType(d.shape.rows_after_cleaning, 'integer')],
                ['Premium earned to', d.cleaning.valuation_date],
              ].map(([k, v]) => (
                <div key={k} className="bg-panel px-3 py-3">
                  <dt className="text-xs text-muted">{k}</dt>
                  <dd className="mt-1 font-serif text-xl tabular-nums">{v}</dd>
                </div>
              ))}
            </dl>
            <ul className="space-y-3">
              {d.findings.map((f) => (
                <li key={f.id}>
                  <Notice tone={SEVERITY_TONE[f.severity] || 'info'} title={f.title}>
                    <p>{f.detail}</p>
                    <p className="mt-1.5"><span className="font-medium">Decision:</span> {f.decision}</p>
                  </Notice>
                </li>
              ))}
            </ul>
            <DataTable
              caption="Consistency checks"
              columns={[{ key: 'check', label: 'Consistency check', type: 'text' }, { key: 'count', label: 'Rows affected', type: 'integer' }]}
              rows={Object.entries(d.consistency_checks).map(([check, count]) => ({ check: check.replaceAll('_', ' '), count }))}
              rowKey="check"
              dense
            />
          </div>
        )}
      </Panel>

      <Panel title="Metric definitions" subtitle="Formula, numerator, denominator, assumptions and limitations. Open any row for the detail." state={meth} height={200}>
        {(m) => <DefinitionList definitions={m.metric_definitions} />}
      </Panel>

      <Panel title="Rate indication assumptions" subtitle="Baseline experience indication, separate from what-if scenario analysis." state={meth} height={180}>
        {(m) => {
          const r = m.rate_indication;
          return (
            <div className="space-y-3 px-2 text-[13.5px]">
              <Notice tone="warning">{r.disclaimer}</Notice>
              <p className="text-muted">
                Target loss ratio: {r.default_target_loss_ratio_pct}% by default
                (allowed {r.target_loss_ratio_limits_pct.minimum}% to {r.target_loss_ratio_limits_pct.maximum}%).
                Credibility standard: {formatByType(r.credibility_standard_claims, 'integer')} claims.
              </p>
              <DataTable
                caption="Rate indication formulas"
                columns={[
                  { key: 'formula_name', label: 'Measure', type: 'text' },
                  { key: 'formula', label: 'Formula', type: 'text', align: 'left' },
                ]}
                rows={Object.entries(r.formulas).map(([formula_name, formula]) => ({
                  formula_name: formula_name.replaceAll('_', ' '),
                  formula,
                }))}
                rowKey="formula_name"
                dense
              />
              <ul className="list-disc space-y-1 pl-5 text-muted">
                {r.assumptions.map((assumption) => <li key={assumption}>{assumption}</li>)}
              </ul>
            </div>
          );
        }}
      </Panel>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel title="Claim status treatment" state={meth} height={140}>
          {(m) => (
            <DataTable
              caption="Claim status treatment"
              rowKey="status"
              rows={Object.entries(m.claim_status_treatment).map(([status, t]) => ({ status, ...t }))}
              columns={[
                { key: 'status', label: 'Status', type: 'text' },
                { key: 'counts_as_claim', label: 'Counts as claim', type: 'text', align: 'left', render: yesNo },
                { key: 'paid', label: 'Paid', type: 'text', align: 'left', render: yesNo },
                { key: 'incurred', label: 'In incurred cost', type: 'text', align: 'left', render: yesNo },
              ]}
            />
          )}
        </Panel>

        <Panel title="Scenario limits" subtitle="Allowed range of each assumption." state={meth} height={140}>
          {(m) => (
            <DataTable
              caption="Scenario limits"
              rowKey="name"
              rows={Object.entries(m.scenario.limits).map(([name, l]) => ({ name: name.replaceAll('_', ' '), ...l, default: m.scenario.defaults[name] }))}
              columns={[
                { key: 'name', label: 'Assumption', type: 'text' },
                { key: 'min', label: 'Minimum', render: (v) => formatSignedPercent(v, 0) },
                { key: 'max', label: 'Maximum', render: (v) => formatSignedPercent(v, 0) },
                { key: 'default', label: 'Default', render: (v) => formatSignedPercent(v, 0) },
              ]}
            />
          )}
        </Panel>
      </div>

      <Panel title="Risk tier rules" subtitle={(m) => m.risk_segmentation_rules.a_priori_tiers.purpose} state={meth} height={140}>
        {(m) => {
          const r = m.risk_segmentation_rules.a_priori_tiers;
          return (
            <div className="space-y-3 px-2 text-[13.5px]">
              <ul className="list-disc space-y-1 pl-5">
                {r.points.map((p) => <li key={p.factor}><span className="font-medium">{p.factor}:</span> {p.condition} adds {p.points} point. {p.rationale}</li>)}
              </ul>
              <Notice tone="warning">{r.caveat}</Notice>
              <p className="text-muted">Credibility factor: min(1, square root of claims / {formatByType(m.credibility_standard_claims, 'integer')}), the classical standard for claim counts.</p>
            </div>
          );
        }}
      </Panel>
    </>
  );
}
