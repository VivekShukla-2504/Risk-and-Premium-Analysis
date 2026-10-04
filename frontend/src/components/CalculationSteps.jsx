import { useState } from 'react';

import Panel from './Panel.jsx';
import { SCENARIO_COLORS } from '../utils/chartTheme.js';
import { formatByType } from '../utils/format.js';

/** Walks through one scenario's calculation, step by step, with the actual numbers (all supplied by the API). */
export default function CalculationSteps({ state }) {
  const [key, setKey] = useState('custom');
  return (
    <Panel
      title="How each number is calculated"
      subtitle="Choose a scenario to see its calculation with the actual numbers substituted in."
      state={state}
      height={260}
      footnote={(d) => d.data.assumptions.join(' ')}
    >
      {(d) => {
        const scenario = d.data.scenarios.find((s) => s.key === key) || d.data.scenarios[d.data.scenarios.length - 1];
        return (
          <div className="px-2">
            <div role="group" aria-label="Scenario to explain" className="mb-3 flex flex-wrap gap-1.5">
              {d.data.scenarios.map((s) => (
                <button
                  key={s.key}
                  type="button"
                  aria-pressed={s.key === scenario.key}
                  onClick={() => setKey(s.key)}
                  className={`rounded-panel border px-3 py-1 text-sm ${s.key === scenario.key ? 'border-ink bg-ink text-white' : 'border-rule bg-white text-ink hover:bg-paper'}`}
                >
                  <span className="mr-1.5 inline-block h-2 w-2 rounded-sm align-middle" style={{ background: SCENARIO_COLORS[s.key] }} aria-hidden="true" />
                  {s.label}
                </button>
              ))}
            </div>
            <p className="mb-2 text-[13px] text-muted">{scenario.description}</p>
            <ol className="divide-y divide-rule/70 border-y border-rule/70">
              {scenario.steps.map((step, i) => (
                <li key={step.label} className="grid gap-x-6 gap-y-1 py-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                  <div className="min-w-0">
                    <p className="font-medium"><span className="mr-2 text-muted tabular-nums">{i + 1}.</span>{step.label}</p>
                    <p className="mt-0.5 text-[13px] text-muted">{step.formula}</p>
                    <p className="mt-1 text-[13.5px] tabular-nums">{step.substitution}</p>
                    <p className="mt-1 text-[13px] leading-snug text-muted">{step.explanation}</p>
                  </div>
                  <p className="font-serif text-xl tabular-nums sm:text-right">{formatByType(step.value, step.format, { digits: step.digits })}</p>
                </li>
              ))}
            </ol>
          </div>
        );
      }}
    </Panel>
  );
}
