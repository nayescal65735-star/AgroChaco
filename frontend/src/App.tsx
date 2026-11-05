import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, SimulationProvider } from './context';
import { AppLayout } from './components/layout/AppLayout';

import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { NewSimulation } from './pages/NewSimulation';
import { SimulationExecution } from './pages/SimulationExecution';
import { Results } from './pages/Results';
import { PerformanceComparison } from './pages/PerformanceComparison';
import { History } from './pages/History';
import { Settings } from './pages/Settings';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <SimulationProvider>
          <Routes>
            <Route path="/login" element={<Login />} />

            <Route
              path="/"
              element={
                <AppLayout>
                  <Dashboard />
                </AppLayout>
              }
            />

            <Route
              path="/nueva-simulacion"
              element={
                <AppLayout>
                  <NewSimulation />
                </AppLayout>
              }
            />

            <Route
              path="/ejecucion"
              element={
                <AppLayout>
                  <SimulationExecution />
                </AppLayout>
              }
            />

            <Route
              path="/resultados"
              element={
                <AppLayout>
                  <Results />
                </AppLayout>
              }
            />

            <Route
              path="/comparacion-rendimiento"
              element={
                <AppLayout>
                  <PerformanceComparison />
                </AppLayout>
              }
            />

            <Route
              path="/historial"
              element={
                <AppLayout>
                  <History />
                </AppLayout>
              }
            />

            <Route
              path="/configuracion"
              element={
                <AppLayout>
                  <Settings />
                </AppLayout>
              }
            />

            {/* Fallback route */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </SimulationProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
