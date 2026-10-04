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
  return `block border-l-[3px] px-4 py-2 text-sm ${isActive ? 'border-brand bg-white/5 font-medium text-white' : 'border-transparent text-slate-300 hover:bg-white/5 hover:text-white'}`;
}

export default function AppShell() {
  const { pathname } = useLocation();
  const page = NAV.find((n) => (n.to === '/' ? pathname === '/' : pathname.startsWith(n.to))) || NAV[0];

  return (
    <div className="min-h-screen lg:pl-60">
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col bg-sidebar lg:flex">
        <div className="px-4 pb-5 pt-6">
          <p className="font-serif text-lg leading-tight text-white">Risk and premium analytics</p>
          <p className="mt-1 text-xs text-slate-400">Synthetic insurance portfolio</p>
        </div>
        <nav aria-label="Main" className="flex-1">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} className={navClass}>{n.label}</NavLink>
          ))}
        </nav>
        <div className="space-y-3 border-t border-white/10 px-4 py-4">
          <DataStatus />
          <p className="text-[11px] leading-snug text-slate-500">Educational project on synthetic data. Not actuarial advice or production software.</p>
        </div>
      </aside>

      <header className="bg-sidebar lg:hidden">
        <p className="px-4 pt-3 font-serif text-base text-white">Risk and premium analytics</p>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-2 pb-2 pt-1">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} className={({ isActive }) => `whitespace-nowrap rounded-panel px-3 py-1.5 text-sm ${isActive ? 'bg-white/10 text-white' : 'text-slate-300'}`}>{n.label}</NavLink>
          ))}
        </nav>
      </header>

      <div className="min-w-0">
        <div className="flex flex-wrap items-start justify-between gap-3 px-4 pb-4 pt-6 sm:px-6">
          <div className="min-w-0 max-w-3xl">
            <h1 className="font-serif text-[1.65rem] leading-tight text-ink">{page.title}</h1>
            <p className="mt-1 text-sm text-muted">{page.description}</p>
          </div>
          {page.exportable && <ExportMenu />}
        </div>
        {page.filters && <FilterBar />}
        <main className="space-y-5 px-4 py-5 sm:px-6" id="main">
          <Outlet />
        </main>
        <footer className="px-4 pb-8 pt-2 text-xs text-muted sm:px-6">
          Amounts are in the policy currency, which the data does not state. All figures are calculated by the API.
        </footer>
      </div>
    </div>
  );
}
