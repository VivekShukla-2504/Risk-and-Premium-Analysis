import { useEffect, useRef, useState } from 'react';

import { downloadReport } from '../../services/api.js';
import { useFilters } from '../../hooks/useFilters.jsx';

const ITEMS = [
  { label: 'Summary metrics', section: 'summary', format: 'csv' },
  { label: 'Policy types', section: 'policy-types', format: 'csv' },
  { label: 'Age bands', section: 'age-bands', format: 'csv' },
  { label: 'Gender', section: 'gender', format: 'csv' },
  { label: 'Claim status', section: 'claim-status', format: 'csv' },
  { label: 'Monthly trend', section: 'monthly', format: 'csv' },
  { label: 'Risk tiers', section: 'risk-segments', format: 'csv' },
  { label: 'Policy-level data', section: 'policies', format: 'csv' },
  { label: 'Full report with assumptions', section: 'full', format: 'json' },
];

export default function ExportMenu() {
  const { applied } = useFilters();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(null);
  const [message, setMessage] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  async function run(item) {
    setBusy(item.section);
    setMessage(null);
    try {
      const name = await downloadReport({ section: item.section, format: item.format, filters: applied });
      setMessage({ ok: true, text: `Saved ${name}` });
      setOpen(false);
    } catch (e) {
      setMessage({ ok: false, text: e.message });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button type="button" className="btn" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        Export report
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-30 mt-1 w-72 rounded-panel border border-rule bg-white py-1 text-sm shadow-sm">
          <p className="px-3 pb-1 pt-1.5 text-xs text-muted">Exports respect the current filters.</p>
          {ITEMS.map((item) => (
            <button
              key={item.section}
              type="button"
              role="menuitem"
              disabled={busy !== null}
              onClick={() => run(item)}
              className="flex w-full items-center justify-between px-3 py-1.5 text-left hover:bg-paper disabled:opacity-50"
            >
              <span>{item.label}</span>
              <span className="text-xs text-muted">{busy === item.section ? 'Preparing' : item.format.toUpperCase()}</span>
            </button>
          ))}
        </div>
      )}
      {message && (
        <p role="status" className={`absolute right-0 mt-1 w-72 text-xs ${message.ok ? 'text-sage' : 'text-brick'}`}>{message.text}</p>
      )}
    </div>
  );
}
