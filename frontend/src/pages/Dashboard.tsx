import { useNavigate } from 'react-router-dom';
import { useSimulations } from '../context';
import type { SimulationEngine, SimulationResult } from '../types';
import { GRAN_CHACO_ZONES } from '../services/mockData';
import { StatCard } from '../components/common/StatCard';
import { Card } from '../components/common/Card';
import { StatusBadge } from '../components/common/StatusBadge';
import { EngineBadge } from '../components/common/EngineBadge';
import { SpeedupValue } from '../components/common/PerformanceMetricValue';
import {
  formatSpeedup,
  isMeasuredSpeedup,
  PERFORMANCE_UNAVAILABLE_MESSAGE,
} from '../utils/performanceMetrics';
import {
  Activity,
  Layers,
  MapPin,
  PlayCircle,
  PlusCircle,
  Zap,
  ArrowRight,
  Droplets,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from 'recharts';

const ENGINE_LABELS: Record<SimulationEngine, string> = {
  secuencial: 'Secuencial',
  openmp: 'OpenMP',
  mpi: 'MPI',
  hibrido: 'Híbrido',
};

const ENGINE_COLORS: Record<SimulationEngine, string> = {
  secuencial: 'var(--engine-sec)',
  openmp: 'var(--engine-omp)',
  mpi: 'var(--engine-mpi)',
  hibrido: 'var(--gold)',
};

export function Dashboard() {
  const { simulations, setActiveSimulationId } = useSimulations();
  const navigate = useNavigate();

  const totalSimulations = simulations.length;
  const runningSimulations = simulations.filter(
    (simulation) => simulation.status === 'running' || simulation.status === 'queued'
  ).length;
  const completedSimulations = simulations.filter((s) => s.status === 'completed').length;

  const totalHectares = GRAN_CHACO_ZONES.reduce((acc, z) => acc + z.activeHectares, 0);

  const cwsiRecords = simulations.filter((s) => s.averageCWSI !== undefined);
  const avgCWSI = cwsiRecords.length
    ? Number(
        (
          cwsiRecords.reduce((acc, s) => acc + (s.averageCWSI ?? 0), 0) /
          cwsiRecords.length
        ).toFixed(2)
      )
    : null;

  const completedWithPerformance = simulations.filter(
    (s) => s.status === 'completed' && s.executionTimeSeconds != null
  );

  const speedupRecords = completedWithPerformance.filter(
    (sim): sim is SimulationResult & { speedup: number } =>
      isMeasuredSpeedup(sim.speedup)
  );

  const maxSpeedupSimulation = speedupRecords.reduce<SimulationResult | null>(
    (best, sim) => (!best || sim.speedup > (best.speedup ?? -Infinity) ? sim : best),
    null
  );

  const fastestSimulation = completedWithPerformance.reduce<SimulationResult | null>(
    (best, sim) =>
      !best || (sim.executionTimeSeconds ?? Infinity) < (best.executionTimeSeconds ?? Infinity)
        ? sim
        : best,
    null
  );

  const speedupChartData = speedupRecords.map((sim) => ({
    name: ENGINE_LABELS[sim.config.engine],
    speedup: sim.speedup,
    color: ENGINE_COLORS[sim.config.engine],
  }));

  const handleViewSimulation = (id: string) => {
    setActiveSimulationId(id);
    navigate('/resultados');
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'critico':
        return '#dc2626';
      case 'severo':
        return '#ea580c';
      case 'moderado':
        return '#d97706';
      default:
        return '#16a34a';
    }
  };

  return (
    <div>
      {/* Page Title & Quick Actions */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Panel de Control &amp; Modelado AgroChaco</h1>
          <p className="page-description">
            Consulta de ejecuciones, resultados de estrés hídrico y métricas HPC registradas por FastAPI y PostgreSQL
            para el Gran Chaco boliviano.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate('/comparacion-rendimiento')}
          >
            <Zap size={16} />
            Métricas de Rendimiento
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate('/nueva-simulacion')}
          >
            <PlusCircle size={16} />
            Nueva Simulación HPC
          </button>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="stats-grid">
        <StatCard
          label="Simulaciones"
          value={totalSimulations}
          subtext={`${completedSimulations} completadas • ${runningSimulations} en curso`}
          icon={<Activity size={24} />}
          variant="agri"
          badge="BD"
        />
        <StatCard
          label="Superficie de Referencia"
          value={`${totalHectares.toLocaleString()} ha`}
          subtext="6 municipios del catálogo DEMO"
          icon={<MapPin size={24} />}
          variant="default"
          badge="DEMO"
        />
        <StatCard
          label="Índice CWSI Promedio"
          value={avgCWSI !== null ? avgCWSI.toFixed(2) : 'Sin datos'}
          subtext="Promedio de corridas con métricas disponibles"
          icon={<Droplets size={24} />}
          variant="danger"
        />
        <StatCard
          label="Speedup Máximo Registrado"
          value={
            maxSpeedupSimulation
              ? formatSpeedup(maxSpeedupSimulation.speedup)
              : 'Sin datos'
          }
          subtext={
            maxSpeedupSimulation
              ? `${ENGINE_LABELS[maxSpeedupSimulation.config.engine]} · ${maxSpeedupSimulation.id}`
              : PERFORMANCE_UNAVAILABLE_MESSAGE
          }
          icon={<Zap size={24} />}
          variant="gold"
          badge="FastAPI"
        />
      </div>

      {/* Two Column Layout: Regional Drought & Benchmark Summary */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
          gap: '1.5rem',
          marginBottom: '1.75rem',
        }}
      >
        {/* Regional Gran Chaco Vulnerability Card */}
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <MapPin size={20} color="var(--agri-green)" />
              <span>Vulnerabilidad Hídrica en el Gran Chaco</span>
            </div>
          }
          subtitle="Valores de referencia del catálogo local; no son telemetría agroclimática en vivo"
          action={
            <span className="system-tag" style={{ background: '#fef3c7', color: '#b45309' }}>
              Datos DEMO
            </span>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {GRAN_CHACO_ZONES.map((zone) => (
              <div
                key={zone.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--bg-main)',
                  border: '1px solid var(--border-light)',
                  transition: 'transform 0.15s ease',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontWeight: 700, color: 'var(--navy)' }}>{zone.name}</span>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      ({zone.department})
                    </span>
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                    Pp: {zone.annualRainfallMm} mm • T° Media: {zone.averageTempC}°C • {zone.activeHectares.toLocaleString()} ha maíz
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                  <span
                    style={{
                      padding: '0.25rem 0.65rem',
                      borderRadius: '9999px',
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      color: '#ffffff',
                      backgroundColor: getRiskColor(zone.currentRisk),
                    }}
                  >
                    Riesgo {zone.currentRisk}
                  </span>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => navigate('/nueva-simulacion')}
                    title={`Iniciar simulación en ${zone.name}`}
                  >
                    Simular
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* HPC Speedup Comparison Chart */}
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Zap size={20} color="var(--gold)" />
              <span>Speedup observado por motor</span>
            </div>
          }
          subtitle="Ejecuciones completadas devueltas por FastAPI/PostgreSQL; sin curvas ni extrapolaciones"
          action={
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={() => navigate('/comparacion-rendimiento')}
            >
              Ver evidencia
            </button>
          }
        >
          {speedupChartData.length > 0 ? (
            <div style={{ height: '240px', width: '100%', marginTop: '0.5rem' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={speedupChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#4a5c53' }} />
                  <YAxis unit="x" tick={{ fontSize: 12, fill: '#4a5c53' }} />
                  <Tooltip
                    formatter={(value) => [`${value}x`, 'Speedup registrado']}
                    contentStyle={{
                      borderRadius: '8px',
                      borderColor: '#cbd5e1',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                    }}
                  />
                  <Bar dataKey="speedup" radius={[6, 6, 0, 0]}>
                    {speedupChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div
              style={{
                textAlign: 'center',
                padding: '4rem 1rem',
                color: 'var(--text-muted)',
                fontSize: '0.88rem',
              }}
            >
              {PERFORMANCE_UNAVAILABLE_MESSAGE}
            </div>
          )}

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '1rem',
              padding: '0.85rem 1rem',
              background: 'var(--soft-green)',
              borderRadius: 'var(--radius-md)',
              marginTop: '1rem',
              fontSize: '0.82rem',
              color: 'var(--agri-green-dark)',
            }}
          >
            <span>
              <strong>Tiempo mínimo registrado:</strong>{' '}
              {fastestSimulation?.executionTimeSeconds != null
                ? `${fastestSimulation.executionTimeSeconds}s (${ENGINE_LABELS[fastestSimulation.config.engine]})`
                : 'sin datos'}
            </span>
            <span style={{ fontWeight: 700 }}>Fuente: PostgreSQL / FastAPI</span>
          </div>
        </Card>
      </div>

      {/* Recent Simulations Feed */}
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Layers size={20} color="var(--navy)" />
            <span>Simulaciones Recientes de Estrés Hídrico</span>
          </div>
        }
        subtitle="Registros devueltos por FastAPI desde PostgreSQL; sin simulaciones DEMO en esta tabla"
        action={
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={() => navigate('/historial')}
          >
            Ver Todo el Historial
          </button>
        }
      >
        <div className="table-container">
          <table className="agro-table">
            <thead>
              <tr>
                <th>Código / Nombre</th>
                <th>Zona Chaqueña</th>
                <th>Variedad Maíz</th>
                <th>Motor Paralelo</th>
                <th>Estado</th>
                <th>Tiempo / Speedup</th>
                <th>CWSI Prom.</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody>
              {simulations.slice(0, 5).map((sim) => (
                <tr key={sim.id}>
                  <td>
                    <div style={{ fontWeight: 700, color: 'var(--navy)' }}>{sim.id}</div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      {sim.config.name}
                    </div>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <MapPin size={14} color="var(--agri-green)" />
                      <span>{sim.config.zoneName}</span>
                    </div>
                    <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                      {sim.config.department}
                    </span>
                  </td>
                  <td>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                      {sim.config.cornVariety === 'chaco_01_criollo'
                        ? 'Chaco 01 Criollo'
                        : sim.config.cornVariety === 'iniaf_h1'
                        ? 'INIAF H1'
                        : sim.config.cornVariety === 'dekalb_7088'
                        ? 'Dekalb 7088'
                        : 'Pioneer 30F35'}
                    </div>
                    <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                      {sim.config.simulationDays} días ciclo
                    </span>
                  </td>
                  <td>
                    <EngineBadge
                      engine={sim.config.engine}
                      threads={sim.config.openmpThreads}
                      processes={sim.config.mpiProcesses}
                    />
                  </td>
                  <td>
                    <StatusBadge status={sim.status} />
                  </td>
                  <td>
                    <div style={{ fontWeight: 700, color: 'var(--navy)' }}>
                      {sim.executionTimeSeconds !== undefined ? `${sim.executionTimeSeconds}s` : 'Pendiente'}
                    </div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--agri-green)', fontWeight: 600 }}>
                      <SpeedupValue value={sim.speedup} compact />
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Droplets size={14} color="#0284c7" />
                      <span style={{ fontWeight: 700 }}>{sim.averageCWSI !== undefined ? sim.averageCWSI.toFixed(2) : 'Sin datos'}</span>
                    </div>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      Déficit: {sim.waterDeficitMm !== undefined ? `${sim.waterDeficitMm} mm` : 'Sin datos'}
                    </span>
                  </td>
                  <td>
                    {sim.status === 'running' ? (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => navigate('/ejecucion')}
                      >
                        <PlayCircle size={14} />
                        Monitorear
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-outline btn-sm"
                        onClick={() => handleViewSimulation(sim.id)}
                      >
                        Resultados
                        <ArrowRight size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
