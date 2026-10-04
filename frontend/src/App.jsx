import { Navigate, Route, Routes } from 'react-router-dom';

import AppShell from './components/layout/AppShell.jsx';
import { FilterProvider } from './hooks/useFilters.jsx';
import ClaimsAnalytics from './pages/ClaimsAnalytics.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Methodology from './pages/Methodology.jsx';
import PortfolioAnalytics from './pages/PortfolioAnalytics.jsx';
import RateIndication from './pages/RateIndication.jsx';
import RiskSegmentation from './pages/RiskSegmentation.jsx';
import ScenarioAnalysis from './pages/ScenarioAnalysis.jsx';

export default function App() {
  return (
    <FilterProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="portfolio" element={<PortfolioAnalytics />} />
          <Route path="claims" element={<ClaimsAnalytics />} />
          <Route path="risk" element={<RiskSegmentation />} />
          <Route path="scenario" element={<ScenarioAnalysis />} />
          <Route path="rate-indication" element={<RateIndication />} />
          <Route path="methodology" element={<Methodology />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </FilterProvider>
  );
}
