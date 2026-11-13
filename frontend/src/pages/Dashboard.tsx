import { useNavigate } from 'react-router-dom';
import { useSimulations } from '../context';
import { GRAN_CHACO_ZONES } from '../services/mockData';
import { StatCard } from '../components/common/StatCard';
import { Card } from '../components/common/Card';
import { StatusBadge } from '../components/common/StatusBadge';
import { EngineBadge } from '../components/common/EngineBadge';
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

export function Dashboard() {
  const { simulations, setActiveSimulationId } = useSimulations();
  const navigate = useNavigate();

  const totalSimulations = simulations.length;
  const runningSimulations = simulations.filter((s) => s.status === 'running').length;
  const completedSimulations = simulations.filter((s) => s.status === 'completed').length;

  const totalHectares = GRAN_CHACO_ZONES.reduce((acc, z) => acc + z.activeHectares, 0);
  const avgCWSI = Number(
    (simulations.reduce((acc, s) => acc + (s.averageCWSI ?? 0), 0) / (simulations.filter(s => s.averageCWSI !== undefined).length || 1)).toFixed(2)
  );

  // Speedup chart data from benchmark
  const speedupChartData = [
    { name: 'Secuencial (1c)', speedup: 1.0, color: 'var(--engine-sec)' },
    { name: 'OpenMP (8h)', speedup: 6.66, color: 'var(--engine-omp)' },
    { name: 'MPI (16p)', speedup: 12.78, color: 'var(--engine-mpi)' },
    { name: 'Híbrido (32c)', speedup: 25.95, color: 'var(--gold)' },
  ];

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
            Monitoreo en tiempo real de estrés hídrico en maíz y orquestación de cómputo de alto rendimiento (HPC)
            en el Gran Chaco boliviano.
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
          badge="HPC Jobs"
        />
        <StatCard
          label="Superficie Modelada"
          value={`${totalHectares.toLocaleString()} ha`}
          subtext="6 Municipios Chaqueños"
          icon={<MapPin size={24} />}
          variant="default"
        />
        <StatCard
          label="Índice CWSI Promedio"
          value={avgCWSI.toFixed(2)}
          subtext="Estrés Hídrico Moderado a Severo"
          icon={<Droplets size={24} />}
          variant="danger"
        />
        <StatCard
          label="Speedup Máximo"
          value="25.95×"
          subtext="Híbrido MPI+OpenMP (32 cores)"
          icon={<Zap size={24} />}
          variant="gold"
          badge="Aceleración"
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
          subtitle="Monitoreo agroclimático por municipios en Tarija, Santa Cruz y Chuquisaca"
          action={
            <span className="system-tag" style={{ background: '#fef3c7', color: '#b45309' }}>
              Campaña Maicera 2026
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
              <span>Aceleración de Cómputo (Speedup $S_p$)</span>
            </div>
          }
          subtitle="Comparativa de escalabilidad: Secuencial vs OpenMP vs MPI vs Híbrido"
          action={
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={() => navigate('/comparacion-rendimiento')}
            >
              Ver Benchmark Completo
            </button>
          }
        >
          <div style={{ height: '240px', width: '100%', marginTop: '0.5rem' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={speedupChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#4a5c53' }} />
                <YAxis unit="x" tick={{ fontSize: 12, fill: '#4a5c53' }} />
                <Tooltip
                  formatter={(value) => [`${value}x`, 'Aceleración']}
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

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '0.85rem 1rem',
              background: 'var(--soft-green)',
              borderRadius: 'var(--radius-md)',
              marginTop: '1rem',
              fontSize: '0.82rem',
              color: 'var(--agri-green-dark)',
            }}
          >
            <div>
              <strong>Motor Híbrido:</strong> 342.5s mono-hilo reducido a <strong>13.2s</strong> en clúster.
            </div>
            <span style={{ fontWeight: 700 }}>Eficiencia: 81.1%</span>
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
        subtitle="Registro de ejecuciones científicas del modelo de balance de agua"
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
                      {sim.speedup !== undefined ? (sim.speedup > 1 ? `${sim.speedup}x acelerado` : 'Línea base') : 'Pendiente'}
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
