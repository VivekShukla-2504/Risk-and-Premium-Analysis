import { CategoryBar } from './charts/BarCharts.jsx';
import Panel from './Panel.jsx';
import Notice from './Notice.jsx';
import { SCENARIO_COLORS } from '../utils/chartTheme.js';
import { scenarioRows } from '../utils/chartData.js';
import { formatByType, formatPoints, formatSignedPercent } from '../utils/format.js';

const ASSUMPTION_ROWS = [
  ['frequency_change_pct', 'Claim frequency adjustment'],
  ['severity_change_pct', 'Claim severity adjustment'],
  ['inflation_pct', 'Claim inflation'],
  ['premium_adjustment_pct', 'Premium adjustment'],
];

const RESULT_ROWS = [
  { label: 'Baseline claim cost', get: (s) => s.results ? formatByType(s.results.baseline_claim_cost, 'amount') : 'Unavailable' },
  { label: 'Adjusted claim frequency', get: (s) => s.results ? formatByType(s.results.adjusted_claim_frequency, 'percent', { digits: 2 }) : 'Unavailable' },
  { label: 'Adjusted claim severity', get: (s) => s.results ? formatByType(s.results.adjusted_claim_severity, 'amount2') : 'Unavailable' },
  { label: 'Adjusted expected claim cost', get: (s) => s.results ? formatByType(s.results.adjusted_expected_claim_cost, 'amount') : 'Unavailable' },
  { label: 'Adjusted premium', get: (s) => s.results ? formatByType(s.results.adjusted_premium, 'amount') : 'Unavailable' },
  { label: 'Adjusted loss ratio', strong: true, get: (s) => s.results ? formatByType(s.results.adjusted_loss_ratio, 'percent') : 'Unavailable', bad: (s) => s.results?.adjusted_loss_ratio > 1 },
  { label: 'Loss ratio versus baseline', get: (s) => s.change_vs_baseline ? formatPoints(s.change_vs_baseline.loss_ratio_points) : 'Unavailable' },
  { label: 'Illustrative underwriting margin', get: (s) => s.results ? formatByType(s.results.underwriting_margin, 'percent') : 'Unavailable', bad: (s) => s.results?.underwriting_margin < 0 },
  { label: 'Premium change needed to break even', get: (s) => s.premium_change_to_break_even_pct == null ? 'Unavailable' : formatSignedPercent(s.premium_change_to_break_even_pct) },
];

function SectionRow({ children, span }) {
  return (
    <tr>
      <th colSpan={span} scope="colgroup" className="bg-paper/70 px-3 py-1.5 text-left text-xs font-medium text-muted">{children}</th>
    </tr>
  );
}

function ComparisonTable({ scenarios }) {
  const span = scenarios.length + 1;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[620px] border-collapse text-[13.5px] tabular-nums">
        <caption className="sr-only">Scenario comparison</caption>
        <thead>
          <tr className="border-b border-rule">
            <th scope="col" className="px-3 py-2 text-left font-medium text-muted">Measure</th>
            {scenarios.map((s) => (
              <th key={s.key} scope="col" className="px-3 py-2 text-right" title={s.description}>
                <span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: SCENARIO_COLORS[s.key] }} aria-hidden="true" />
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <SectionRow span={span}>Assumptions</SectionRow>
          {ASSUMPTION_ROWS.map(([key, label]) => (
            <tr key={key} className="border-b border-rule/70">
              <th scope="row" className="px-3 py-1.5 text-left font-normal">{label}</th>
              {scenarios.map((s) => (
                <td key={s.key} className="px-3 py-1.5 text-right">{formatSignedPercent(s.inputs[key])}</td>
              ))}
            </tr>
          ))}
          <SectionRow span={span}>Results — invalid-frequency scenarios are unavailable</SectionRow>
          {RESULT_ROWS.map((row) => (
            <tr key={row.label} className="border-b border-rule/70 last:border-0">
              <th scope="row" className={`px-3 py-1.5 text-left ${row.strong ? 'font-semibold' : 'font-normal'}`}>{row.label}</th>
              {scenarios.map((s) => (
                <td key={s.key} className={`px-3 py-1.5 text-right ${row.strong ? 'font-semibold' : ''} ${row.bad?.(s) ? 'text-brick' : ''}`}>{row.get(s)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Baseline / Optimistic / Stress / Custom side by side: assumptions, results and two charts. */
export default function ScenarioComparison({ state, onLoadPreset }) {
  return (
    <>
      <Panel
        title="Scenario comparison"
        subtitle={(d) => d.data.preset_note}
        state={state}
        height={320}
        footnote={(d) => `Shared assumptions: expense ratio ${d.data.shared_assumptions.expense_ratio_pct}% (${d.data.shared_assumptions.expense_ratio_note.toLowerCase()}) and a ${d.data.shared_assumptions.target_loss_ratio_pct}% target loss ratio. Hover a scenario name for its description.`}
      >
        {(d) => (
          <div className="space-y-3">
            <ComparisonTable scenarios={d.data.scenarios} />
            {d.data.scenarios.filter((s) => s.validation_error).map((s) => (
              <Notice key={s.key} tone="warning" title={`${s.label} scenario unavailable`}>{s.validation_error}</Notice>
            ))}
            <div className="flex flex-wrap items-center gap-2 px-3 pb-1">
              <span className="text-[13px] text-muted">Use as a starting point for your custom scenario:</span>
              {d.data.scenarios.filter((s) => s.is_preset && s.key !== 'baseline').map((s) => (
                <button key={s.key} type="button" className="btn" onClick={() => onLoadPreset(s.inputs)}>
                  Load {s.label.toLowerCase()} into sliders
                </button>
              ))}
            </div>
          </div>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel
          title="Expected claim cost versus premium"
          subtitle="Where claims exceed premium, the scenario loses money before expenses."
          state={state}
          tableOf={(d) => ({
            columns: [
              { key: 'name', label: 'Scenario', type: 'text' },
              { key: 'claimCost', label: 'Expected claim cost', type: 'amount' },
              { key: 'premium', label: 'Premium', type: 'amount' },
              { key: 'lossRatio', label: 'Loss ratio', type: 'percent' },
            ],
            rows: scenarioRows(d.data.scenarios),
          })}
        >
          {(d) => (
            <CategoryBar
              data={scenarioRows(d.data.scenarios)}
              bars={[{ key: 'claimCost', name: 'Expected claim cost', color: '#B98320' }, { key: 'premium', name: 'Premium', color: '#16607A' }]}
              format="amount"
              ariaLabel="Expected claim cost and premium by scenario"
            />
          )}
        </Panel>

        <Panel
          title="Loss ratio by scenario"
          subtitle="Expected claim cost divided by adjusted premium"
          state={state}
          footnote="The dashed line marks 100%, where claims equal premium."
          tableOf={(d) => ({
            columns: [
              { key: 'name', label: 'Scenario', type: 'text' },
              { key: 'lossRatio', label: 'Loss ratio', type: 'percent' },
              { key: 'margin', label: 'Underwriting margin', type: 'percent' },
            ],
            rows: scenarioRows(d.data.scenarios),
          })}
        >
          {(d) => (
            <CategoryBar
              data={scenarioRows(d.data.scenarios)}
              bars={[{ key: 'lossRatio', name: 'Loss ratio' }]}
              format="percent"
              refLine={{ value: 1, label: '100%' }}
              cellColors={(row) => SCENARIO_COLORS[row.key]}
              ariaLabel="Loss ratio by scenario"
            />
          )}
        </Panel>
      </div>
    </>
  );
}
