import { NavLink, Outlet, useLocation } from 'react-router-dom';

import FilterBar from '../FilterBar.jsx';
import ExportMenu from './ExportMenu.jsx';
import { NAV } from './nav.js';
import { useApi } from '../../hooks/useApi.js';
import { api } from '../../services/api.js';
import { formatInteger } from '../../utils/format.js';

const SOURCE_LABELS = { mongodb: 'MongoDB Atlas', cleaned_csv: 'Cleaned CSV', raw_csv_pipeline: 'Raw CSV (cleaned on load)' };

function DataStatus() {
  const { data, error } = useApi((signal) => api.health(signal), []);
  if (error) return <p className="text-xs text-brick">API unreachable</p>;
  if (!data) return <p className="text-xs text-slate-400">Checking data source</p>;
  return (
    <div className="space-y-0.5 text-xs text-slate-300">
      <p className="flex items-center gap-1.5">
        <span className={`inline-block h-2 w-2 rounded-full ${data.data_loaded ? 'bg-sage' : 'bg-brick'}`} aria-hidden="true" />
        {data.data_loaded ? (SOURCE_LABELS[data.data_source] || data.data_source) : 'No data loaded'}
      </p>
      {data.rows != null && <p className="text-slate-400">{formatInteger(data.rows)} policies</p>}
      {data.mongodb_configured && data.mongodb_error && <p className="text-ochre" title={data.mongodb_error}>MongoDB unavailable, using CSV</p>}
    </div>
  );
}

function navClass({ isActive }) {
  return `mx-2 flex items-center gap-3 rounded-panel px-3 py-2.5 text-[13px] transition-colors ${isActive ? 'bg-white/10 font-medium text-white' : 'text-slate-300 hover:bg-white/5 hover:text-white'}`;
}

export default function AppShell() {
  const { pathname } = useLocation();
  const page = NAV.find((n) => (n.to === '/' ? pathname === '/' : pathname.startsWith(n.to))) || NAV[0];
  const pageNumber = String(NAV.indexOf(page) + 1).padStart(2, '0');

  return (
    <div className="min-h-screen lg:pl-[264px]">
      <aside className="fixed inset-y-0 left-0 hidden w-[264px] flex-col border-r border-white/10 bg-sidebar lg:flex">
        <div className="px-5 pb-7 pt-7">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-panel border border-white/15 bg-white/10 font-serif text-sm font-semibold tracking-wide text-white" aria-hidden="true">IR</span>
            <div>
              <p className="font-serif text-[15px] leading-tight text-white">Insurance analytics</p>
              <p className="mt-1 text-[10px] uppercase tracking-[0.15em] text-slate-400">Synthetic portfolio</p>
            </div>
          </div>
        </div>
        <p className="eyebrow px-5 pb-2 text-slate-500">Analysis</p>
        <nav aria-label="Main" className="flex-1 space-y-1">
          {NAV.map((n, index) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} className={navClass}>
              <span className="w-5 font-mono text-[10px] tabular-nums text-slate-500">{String(index + 1).padStart(2, '0')}</span>
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="space-y-3 border-t border-white/10 px-5 py-5">
          <DataStatus />
          <p className="text-[11px] leading-relaxed text-slate-400">Illustrative analysis on synthetic data. Not pricing advice or production software.</p>
        </div>
      </aside>

      <header className="border-b border-white/10 bg-sidebar lg:hidden">
        <div className="flex items-center gap-2.5 px-4 pb-2 pt-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-panel border border-white/15 bg-white/10 font-serif text-xs font-semibold text-white" aria-hidden="true">IR</span>
          <div>
            <p className="font-serif text-sm leading-tight text-white">Insurance analytics</p>
            <p className="text-[10px] text-slate-400">Portfolio study · synthetic data</p>
          </div>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-2 pb-2 pt-1">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} className={({ isActive }) => `whitespace-nowrap rounded-panel px-3 py-2 text-xs transition-colors ${isActive ? 'bg-white/10 font-medium text-white' : 'text-slate-300 hover:bg-white/5'}`}>{n.label}</NavLink>
          ))}
        </nav>
      </header>

      <div className="min-w-0">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-rule/80 bg-panel/70 px-4 pb-5 pt-6 sm:px-6 lg:px-8 lg:pb-6 lg:pt-8">
          <div className="min-w-0 max-w-3xl">
            <p className="eyebrow mb-2">Portfolio review <span className="mx-1.5 text-brand">/</span> {pageNumber}</p>
            <h1 className="font-serif text-[1.8rem] leading-tight tracking-[-0.025em] text-ink sm:text-[2rem]">{page.title}</h1>
            <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-muted sm:text-sm">{page.description}</p>
          </div>
          {page.exportable && <ExportMenu />}
        </div>
        {page.filters && <FilterBar />}
        <main className="mx-auto max-w-[1720px] space-y-5 px-4 py-5 sm:px-6 lg:space-y-6 lg:px-8 lg:py-7" id="main">
          <Outlet />
        </main>
        <footer className="mx-auto max-w-[1720px] border-t border-rule/70 px-4 pb-8 pt-4 text-xs text-muted sm:px-6 lg:px-8">
          Amounts are in the policy currency, which the data does not state. All figures are calculated by the API.
        </footer>
      </div>
    </div>
  );
}
