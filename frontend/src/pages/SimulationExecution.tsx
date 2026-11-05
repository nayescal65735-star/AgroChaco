import { useNavigate } from 'react-router-dom';
import { useSimulations } from '../context';
import { Card } from '../components/common/Card';
import { StatusBadge } from '../components/common/StatusBadge';
import { EngineBadge } from '../components/common/EngineBadge';
import {
  Play,
  Pause,
  Terminal,
  Activity,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

export function SimulationExecution() {
  const {
    simulations,
    activeSimulation,
    setActiveSimulationId,
    startExecution,
    stopExecution,
  } = useSimulations();
  const navigate = useNavigate();

  // If there's no active simulation selected, pick running or latest
  const runningSim = simulations.find((s) => s.status === 'running') || activeSimulation || simulations[0];

  const handleToggleExecution = () => {
    if (!runningSim) return;
    if (runningSim.status === 'running') {
      stopExecution(runningSim.id);
    } else {
      startExecution(runningSim.id);
    }
  };

  if (!runningSim) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
        <h2>No hay simulaciones en cola ni activas</h2>
        <p style={{ color: 'var(--text-secondary)', margin: '1rem 0' }}>
          Configure una nueva simulación para ver la ejecución en tiempo real en los nodos del clúster.
        </p>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => navigate('/nueva-simulacion')}
        >
          Crear Simulación
        </button>
      </div>
    );
  }

  // Calculate current phenological stage based on progress / days
  const currentDay = runningSim.currentDay || Math.floor((runningSim.progressPercent / 100) * (runningSim.config.simulationDays || 120));
  let currentStage = 'Emergencia (VE - V2)';
  if (currentDay > 15 && currentDay <= 45) currentStage = 'Desarrollo Vegetativo (V6 - V12)';
  else if (currentDay > 45 && currentDay <= 68) currentStage = 'Floración y Polinización (R1)';
  else if (currentDay > 68 && currentDay <= 95) currentStage = 'Llenado de Grano (R2 - R4)';
  else if (currentDay > 95) currentStage = 'Madurez Fisiológica (R6)';

  // Real-time timeline slice up to current day
  const visibleTimeline = runningSim.timelineData.slice(0, Math.max(5, currentDay));

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Ejecución &amp; Monitoreo en Vivo (HPC)</h1>
          <p className="page-description">
            Supervisión continua de procesos MPI, distribución de hilos OpenMP y convergencia de balance hídrico.
          </p>
        </div>

        {/* Quick selector of active simulation */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <select
            className="form-select"
            value={runningSim.id}
            onChange={(e) => setActiveSimulationId(e.target.value)}
            style={{ width: 'auto', fontWeight: 600 }}
          >
            {simulations.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id}: {s.config.name.substring(0, 32)}... ({s.status})
              </option>
            ))}
          </select>

          <button
            type="button"
            className={`btn ${runningSim.status === 'running' ? 'btn-danger' : 'btn-primary'}`}
            onClick={handleToggleExecution}
          >
            {runningSim.status === 'running' ? (
              <>
                <Pause size={16} />
                Pausar Ejecución
              </>
            ) : (
              <>
                <Play size={16} fill="#ffffff" />
                {runningSim.status === 'completed' ? 'Re-ejecutar' : 'Iniciar / Continuar'}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Execution Banner / Status Card */}
      <Card
        className="mb-6"
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <Activity size={22} color="var(--agri-green)" />
            <span>{runningSim.config.name}</span>
          </div>
        }
        subtitle={`${runningSim.config.zoneName} (${runningSim.config.department}) • Grilla ${runningSim.config.gridConfig.rows}x${runningSim.config.gridConfig.cols} (${runningSim.config.gridConfig.cellSizeMeters}m por celda)`}
        action={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <EngineBadge
              engine={runningSim.config.engine}
              threads={runningSim.config.openmpThreads}
              processes={runningSim.config.mpiProcesses}
            />
            <StatusBadge status={runningSim.status} />
          </div>
        }
      >
        {/* Progress Bar */}
        <div style={{ margin: '1rem 0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.88rem' }}>
            <span style={{ fontWeight: 700, color: 'var(--navy)' }}>
              Progreso del Ciclo Agrícola: Día {currentDay} de {runningSim.config.simulationDays} días
            </span>
            <span style={{ fontWeight: 800, color: 'var(--agri-green)' }}>
              {runningSim.progressPercent}%
            </span>
          </div>

          <div
            style={{
              width: '100%',
              height: '14px',
              backgroundColor: 'var(--soft-green)',
              borderRadius: '9999px',
              overflow: 'hidden',
              border: '1px solid var(--soft-green-border)',
            }}
          >
            <div
              style={{
                width: `${runningSim.progressPercent}%`,
                height: '100%',
                background:
                  runningSim.status === 'completed'
                    ? 'var(--agri-green)'
                    : runningSim.status === 'paused'
                    ? 'var(--status-warning)'
                    : 'linear-gradient(90deg, var(--agri-green) 0%, var(--gold) 100%)',
                borderRadius: '9999px',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
        </div>

        {/* Real-time Submetrics Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
            gap: '1rem',
            marginTop: '1.25rem',
            paddingTop: '1.25rem',
            borderTop: '1px solid var(--border-light)',
          }}
        >
          <div style={{ padding: '0.75rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              Fase Fenológica Actual
            </div>
            <div style={{ fontSize: '0.98rem', fontWeight: 700, color: 'var(--navy)', marginTop: '0.2rem' }}>
              {currentStage}
            </div>
          </div>

          <div style={{ padding: '0.75rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              Humedad del Suelo Actual
            </div>
            <div style={{ fontSize: '0.98rem', fontWeight: 700, color: '#0284c7', marginTop: '0.2rem' }}>
              {runningSim.soilMoistureFinalPercent}%
            </div>
          </div>

          <div style={{ padding: '0.75rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              Estrés CWSI Actual
            </div>
            <div style={{ fontSize: '0.98rem', fontWeight: 700, color: '#dc2626', marginTop: '0.2rem' }}>
              {runningSim.averageCWSI.toFixed(3)} (Alto)
            </div>
          </div>

          <div style={{ padding: '0.75rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              Aceleración / Speedup
            </div>
            <div style={{ fontSize: '0.98rem', fontWeight: 700, color: 'var(--gold-dark)', marginTop: '0.2rem' }}>
              {runningSim.speedup}× ({runningSim.efficiency}% Efic.)
            </div>
          </div>
        </div>

        {runningSim.status === 'completed' && (
          <div
            style={{
              marginTop: '1.25rem',
              padding: '1rem',
              borderRadius: 'var(--radius-md)',
              background: '#f0fdf4',
              border: '1px solid #bbf7d0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', color: '#166534' }}>
              <CheckCircle2 size={20} />
              <span style={{ fontWeight: 700 }}>
                Simulación completada en {runningSim.executionTimeSeconds} segundos. Convergencia numérica alcanzada.
              </span>
            </div>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => {
                setActiveSimulationId(runningSim.id);
                navigate('/resultados');
              }}
            >
              Explorar Resultados &amp; Mapas
              <ArrowRight size={14} />
            </button>
          </div>
        )}
      </Card>

      {/* Two Column Layout: Live Stress Evolution vs HPC Cluster Logs */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
          gap: '1.5rem',
          marginTop: '1.5rem',
        }}
      >
        {/* Dynamic Stress Timeline */}
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Activity size={18} color="var(--agri-green)" />
              <span>Evolución Temporal del Estrés Hídrico (CWSI)</span>
            </div>
          }
          subtitle="Índice CWSI y Evapotranspiración Real diaria calculada"
        >
          <div style={{ height: '280px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={visibleTimeline} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="day" label={{ value: 'Día de Ciclo', position: 'insideBottom', offset: -5, fontSize: 11 }} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(val, name) => [
                    name === 'cwsi' ? Number(val).toFixed(3) : `${val} mm`,
                    name === 'cwsi' ? 'Índice CWSI' : 'ET Real (mm)',
                  ]}
                  labelFormatter={(lbl) => `Día ${lbl}`}
                />
                <Line
                  type="monotone"
                  dataKey="cwsi"
                  stroke="#dc2626"
                  strokeWidth={2.5}
                  dot={false}
                  name="cwsi"
                />
                <Line
                  type="monotone"
                  dataKey="etActual"
                  stroke="var(--agri-green)"
                  strokeWidth={1.8}
                  dot={false}
                  name="etActual"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '0.5rem', fontSize: '0.78rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <div style={{ width: '12px', height: '3px', background: '#dc2626' }} />
              <span>CWSI (0 a 1)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <div style={{ width: '12px', height: '3px', background: 'var(--agri-green)' }} />
              <span>Evapotranspiración Actual ETa</span>
            </div>
          </div>
        </Card>

        {/* HPC Cluster Log Stream */}
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Terminal size={18} color="var(--navy)" />
              <span>Terminal &amp; Logs de Paralelización</span>
            </div>
          }
          subtitle="Salida de consola estándar (stdout/stderr) de Slurm, MPI y OpenMP"
        >
          <div className="terminal-window">
            {runningSim.logs.map((log, idx) => (
              <div key={idx} className="terminal-line">
                <span className="terminal-time">[{log.timestamp}]</span>
                <span className={`terminal-tag ${log.level}`}>[{log.level}]</span>
                <span className="terminal-msg">{log.message}</span>
              </div>
            ))}
            {runningSim.status === 'running' && (
              <div className="terminal-line" style={{ color: '#22c55e' }}>
                <span className="terminal-time">[LIVE]</span>
                <span className="terminal-tag INFO">[RUN]</span>
                <span className="terminal-msg">Calculando celdas en paralelo... paso temporal en curso.</span>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
