import { useEffect, useState } from 'react';

import DataTable from '../components/DataTable.jsx';
import Notice from '../components/Notice.jsx';
import Panel from '../components/Panel.jsx';
import ScopeBanner from '../components/ScopeBanner.jsx';
import CalculationSteps from '../components/CalculationSteps.jsx';
import ScenarioComparison from '../components/ScenarioComparison.jsx';
import { ErrorState, Loading } from '../components/StateViews.jsx';
import { CategoryBar } from '../components/charts/BarCharts.jsx';
import { useApi } from '../hooks/useApi.js';
import { useFilters } from '../hooks/useFilters.jsx';
import { api } from '../services/api.js';
import { tornadoRows } from '../utils/chartData.js';
import { formatByType, formatSignedPercent } from '../utils/format.js';

const FIELDS = {
  frequency_change_pct: { label: 'Claim frequency change', hint: 'Change in the share of policies with a claim' },
  severity_change_pct: { label: 'Claim severity change', hint: 'Change in the average claim size' },
  inflation_pct: { label: 'Claim cost inflation', hint: 'Applied on top of the severity change' },
  premium_adjustment_pct: { label: 'Premium adjustment', hint: 'Change in earned premium, such as a rate change' },
  expense_ratio_pct: { label: 'Expense ratio (assumption)', hint: 'Expenses as a share of premium' },
  target_loss_ratio_pct: { label: 'Target loss ratio (assumption)', hint: 'Used for the premium-needed estimate' },
};
const GROUPS = [
  { title: 'Claims experience', keys: ['frequency_change_pct', 'severity_change_pct', 'inflation_pct'] },
  { title: 'Pricing', keys: ['premium_adjustment_pct'] },
  { title: 'Assumptions', keys: ['expense_ratio_pct', 'target_loss_ratio_pct'] },
];

function SliderField({ id, spec, limit, value, onChange }) {
  const set = (raw) => {
    const n = Number.parseFloat(raw);
    if (Number.isFinite(n)) onChange(Math.min(limit.max, Math.max(limit.min, n)));
  };
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-sm font-medium">{spec.label}</label>
        <span className="flex items-center gap-1">
          <input
            aria-label={`${spec.label} value`}
            type="number"
            className="w-16 rounded-panel border border-rule bg-white px-1.5 py-0.5 text-right text-sm tabular-nums"
            min={limit.min}
            max={limit.max}
            step="0.5"
            value={value}
            onChange={(e) => set(e.target.value)}
          />
          <span className="text-sm text-muted">%</span>
        </span>
      </div>
      <input
        id={id}
        type="range"
        className="mt-1 w-full accent-brand"
        min={limit.min}
        max={limit.max}
        step="0.5"
        value={value}
        onChange={(e) => set(e.target.value)}
      />
      <div className="flex justify-between text-[11px] text-muted tabular-nums">
        <span>{limit.min}%</span>
        <span>{spec.hint}</span>
        <span>{limit.max}%</span>
      </div>
    </div>
  );
}

function cellStyle(value, pivot, maxDeviation, higherIsWorse) {
  if (value == null || !maxDeviation) return undefined;
  const bad = higherIsWorse ? value > pivot : value < pivot;
  const alpha = 0.1 + 0.5 * Math.min(1, Math.abs(value - pivot) / maxDeviation);
  return { background: bad ? `rgba(162,74,66,${alpha.toFixed(2)})` : `rgba(79,127,94,${alpha.toFixed(2)})` };
}

function SensitivityGrid({ grid }) {
  const [metric, setMetric] = useState('loss_ratio');
  const isLoss = metric === 'loss_ratio';
  const pivot = isLoss ? 1 : 0;
  const values = grid[metric];
  const maxDeviation = Math.max(...values.flat().map((v) => Math.abs(v - pivot)));
  return (
    <div>
      <div role="group" aria-label="Grid measure" className="mb-3 flex w-fit overflow-hidden rounded-panel border border-rule text-xs">
        {[['loss_ratio', 'Loss ratio'], ['underwriting_margin', 'Underwriting margin']].map(([k, label]) => (
          <button key={k} type="button" aria-pressed={metric === k} onClick={() => setMetric(k)} className={`px-3 py-1 ${metric === k ? 'bg-ink text-white' : 'bg-white text-muted hover:bg-paper'}`}>{label}</button>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[460px] border-collapse text-center text-[13.5px] tabular-nums">
          <caption className="sr-only">{isLoss ? 'Loss ratio' : 'Underwriting margin'} by frequency and severity change</caption>
          <thead>
            <tr>
              <th scope="col" className="px-2 py-1.5 text-left text-xs font-normal text-muted">Severity change (down) and frequency change (across)</th>
              {grid.frequency_changes_pct.map((f) => (
                <th key={f} scope="col" className="px-2 py-1.5 font-medium">{formatSignedPercent(f, 0)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grid.severity_changes_pct.map((s, r) => (
              <tr key={s}>
                <th scope="row" className="px-2 py-1.5 text-left font-medium">{formatSignedPercent(s, 0)}</th>
                {grid.frequency_changes_pct.map((f, c) => (
                  <td key={f} style={cellStyle(values[r][c], pivot, maxDeviation, isLoss)} className={`border border-white px-2 py-1.5 ${s === 0 && f === 0 ? 'font-semibold outline outline-1 outline-ink' : ''}`}>
                    {formatByType(values[r][c], 'percent')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-muted">
        Held constant: inflation {formatSignedPercent(grid.held_constant.inflation_pct)}, premium {formatSignedPercent(grid.held_constant.premium_adjustment_pct)}, expense ratio {grid.held_constant.expense_ratio_pct}%.
        Red cells are worse than break-even ({isLoss ? 'loss ratio above 100%' : 'negative margin'}); the outlined cell is the unchanged baseline.
      </p>
    </div>
  );
}

function Results({ r }) {
  const d = r.data;
  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-serif text-lg">Detailed sensitivity for your custom scenario</h2>
        <p className="mt-0.5 text-sm text-muted">Compares the arithmetic effects of individual assumptions around the same baseline; these are not data-estimated rankings.</p>
      </div>

      <Notice tone="info" title="How precise is the starting point?">
        {d.baseline_uncertainty.note} Baseline frequency interval: {formatByType(d.baseline_uncertainty.claim_frequency_ci_95[0], 'percent')} to {formatByType(d.baseline_uncertainty.claim_frequency_ci_95[1], 'percent')}
        {d.baseline_uncertainty.frequency_half_width_pct_of_estimate != null && ` (about plus or minus ${d.baseline_uncertainty.frequency_half_width_pct_of_estimate}% of the estimate)`}.
      </Notice>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel title="Sensitivity grid" subtitle="Frequency and severity adjustments combined" state={{ data: r }} height={200}>
          {() => <div className="px-2"><SensitivityGrid grid={d.sensitivity_grid} /></div>}
        </Panel>
        <Panel
          title="Individual assumption effects"
          subtitle={`Loss ratio after changing one assumption by +/-${d.one_at_a_time_sensitivity[0]?.shock_pct}%`}
          state={{ data: r }}
          tableOf={() => ({
            columns: [
              { key: 'name', label: 'Driver', type: 'text' },
              { key: 'lossRatioAtMinus', label: `Loss ratio at -${d.one_at_a_time_sensitivity[0]?.shock_pct}%`, type: 'percent' },
              { key: 'lossRatioAtPlus', label: `Loss ratio at +${d.one_at_a_time_sensitivity[0]?.shock_pct}%`, type: 'percent' },
              { key: 'swing', label: 'Difference (points)', type: 'number' },
            ],
            rows: tornadoRows(d.one_at_a_time_sensitivity),
          })}
          footnote={(r) => r.data.sensitivity_comparison_note}
        >
          {() => (
            <CategoryBar
              data={tornadoRows(d.one_at_a_time_sensitivity)}
              bars={[
                { key: 'lossRatioAtMinus', name: `- ${d.one_at_a_time_sensitivity[0]?.shock_pct}%` },
                { key: 'lossRatioAtPlus', name: `+ ${d.one_at_a_time_sensitivity[0]?.shock_pct}%`, color: '#B98320' },
              ]}
              format="percent"
              refLine={{ value: d.base.loss_ratio, label: 'Baseline' }}
              ariaLabel="Unranked loss ratio effects for individual assumptions"
            />
          )}
        </Panel>
      </div>

      <Panel title="By policy type" subtitle="The custom assumptions applied to each policy type" state={{ data: r }} height={160}>
        {() => (
          <DataTable
            caption="Custom scenario by policy type"
            rowKey="policy_type"
            rows={d.by_policy_type}
            columns={[
              { key: 'policy_type', label: 'Policy type', type: 'text' },
              { key: 'policies', label: 'Policies', type: 'integer' },
              { key: 'base_loss_ratio', label: 'Base loss ratio', type: 'percent', rateMetric: true },
              { key: 'scenario_loss_ratio', label: 'Scenario loss ratio', type: 'percent', rateMetric: true },
              { key: 'base_expected_claim_cost', label: 'Base claim cost', type: 'amount' },
              { key: 'scenario_expected_claim_cost', label: 'Scenario claim cost', type: 'amount' },
              { key: 'scenario_underwriting_margin', label: 'Scenario margin', type: 'percent', rateMetric: true },
              { key: 'scenario_error', label: 'Scenario validation', type: 'text', align: 'left', render: (v) => v || '—' },
            ]}
          />
        )}
      </Panel>

      <details className="rounded-panel border border-rule bg-panel px-4 py-3 text-[13.5px]">
        <summary className="cursor-pointer font-medium">Formulas used</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
          {Object.values(d.formulas).map((f) => <li key={f}>{f}</li>)}
        </ul>
      </details>
    </div>
  );
}

export default function ScenarioAnalysis() {
  const { applied } = useFilters();
  const meth = useApi((s) => api.methodology(s), []);
  const [inputs, setInputs] = useState(null);
  const [submitted, setSubmitted] = useState(null);

  useEffect(() => {
    if (meth.data && !inputs) setInputs(meth.data.scenario.defaults);
  }, [meth.data, inputs]);

  // Wait briefly after the last slider move before asking the API
  useEffect(() => {
    if (!inputs) return undefined;
    const t = setTimeout(() => setSubmitted(inputs), 350);
    return () => clearTimeout(t);
  }, [inputs]);

  const compare = useApi((s) => (submitted ? api.scenarioCompare(submitted, applied, s) : Promise.resolve(null)), [submitted, applied]);
  const detail = useApi((s) => (submitted ? api.scenario(submitted, applied, s) : Promise.resolve(null)), [submitted, applied]);

  if (meth.error) return <ErrorState error={meth.error} onRetry={meth.reload} />;
  if (!meth.data || !inputs) return <Loading />;
  const { limits, defaults, disclaimer } = meth.data.scenario;
  const loadPreset = (presetInputs) =>
    setInputs((cur) => ({
      ...cur,
      frequency_change_pct: presetInputs.frequency_change_pct,
      severity_change_pct: presetInputs.severity_change_pct,
      inflation_pct: presetInputs.inflation_pct,
      premium_adjustment_pct: presetInputs.premium_adjustment_pct,
    }));

  return (
    <>
      <Notice tone="warning" title="Scenario analysis, not a prediction">{disclaimer}</Notice>
      <ScopeBanner state={compare.data ? compare : null} />

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[22rem_minmax(0,1fr)]">
        <section aria-label="Scenario assumptions" className="rounded-panel border border-rule bg-panel xl:sticky xl:top-4">
          <header className="flex items-center justify-between border-b border-rule px-4 py-3">
            <h2 className="font-serif text-[1.0625rem]">Custom scenario</h2>
            <button type="button" className="btn" onClick={() => setInputs(defaults)}>Reset</button>
          </header>
          <div className="space-y-5 px-4 py-4">
            {GROUPS.map((g) => (
              <fieldset key={g.title} className="space-y-4">
                <legend className="mb-2 text-xs font-medium text-muted">{g.title}</legend>
                {g.keys.map((k) => (
                  <SliderField key={k} id={`s-${k}`} spec={FIELDS[k]} limit={limits[k]} value={inputs[k]} onChange={(v) => setInputs((i) => ({ ...i, [k]: v }))} />
                ))}
              </fieldset>
            ))}
          </div>
        </section>

        <div className="min-w-0 space-y-5">
          {compare.error ? (
            <ErrorState error={compare.error} onRetry={compare.reload} />
          ) : (
            <>
              <ScenarioComparison state={compare} onLoadPreset={loadPreset} />
              <CalculationSteps state={compare} />
              {detail.error ? (
                <ErrorState error={detail.error} onRetry={detail.reload} />
              ) : !detail.data ? (
                <Loading label="Running detailed sensitivity" />
              ) : (
                <div aria-busy={detail.loading} className={detail.loading ? 'opacity-60 transition-opacity' : ''}>
                  <Results r={detail.data} />
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
