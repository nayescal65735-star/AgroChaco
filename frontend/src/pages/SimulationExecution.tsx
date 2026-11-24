import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useSimulations } from '../context';
import { Card } from '../components/common/Card';
import { StatusBadge } from '../components/common/StatusBadge';
import { EngineBadge } from '../components/common/EngineBadge';
import {
  EfficiencyValue,
  SpeedupValue,
} from '../components/common/PerformanceMetricValue';
import { mensajeErrorApi } from '../services/api';
import {
  Terminal,
  Activity,
  CheckCircle2,
  ArrowRight,
  Play,
  RefreshCw,
  AlertCircle,
  Ban,
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

const ESTADOS_TERMINALES = new Set(['completed', 'failed', 'canceled']);

export function SimulationExecution() {
  const {
    simulations,
    activeSimulation,
    setActiveSimulationId,
    startExecution,
    cancelExecution,
    activeJob,
    jobErrorsBySimulation,
    clearJobError,
  } = useSimulations();
  const navigate = useNavigate();
  const location = useLocation();

  const autoExecutionStarted = useRef<string | null>(null);

  const autoExecuteId = (
    location.state as { autoExecuteId?: string } | null
  )?.autoExecuteId;
  const [isExecuting, setIsExecuting] = useState(false);
  const [isCanceling, setIsCanceling] = useState(false);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [executionSuccess, setExecutionSuccess] = useState<string | null>(null);

  const runningSim =
    activeSimulation ||
    simulations.find((simulation) => simulation.status === 'running') ||
    simulations[0];

  const trabajoEnCurso =
    activeJob !== null && !ESTADOS_TERMINALES.has(activeJob.status);
  const flujoEnCurso =
    trabajoEnCurso ||
    runningSim?.status === 'running' ||
    runningSim?.status === 'queued';
  const errorDelTrabajo = runningSim
    ? jobErrorsBySimulation[runningSim.id]
    : undefined;
  const errorVisible = executionError ?? errorDelTrabajo ?? null;

  const handleExecute = async () => {
    if (!runningSim || typeof runningSim.id !== 'string') {
      setExecutionError('Identificador de simulación inválido o inexistente.');
      return;
    }
    if (flujoEnCurso || isExecuting) {
      return;
    }

    setExecutionError(null);
    clearJobError(runningSim.id);
    setExecutionSuccess(null);
    setIsExecuting(true);

    try {
      await startExecution(runningSim.id);
      setExecutionSuccess(
        `Trabajo encolado para '${runningSim.config.name}'. El progreso se actualizará desde el worker.`
      );
    } catch (error: unknown) {
      setExecutionError(
        mensajeErrorApi(error, 'No se pudo encolar la ejecución de la simulación.')
      );
    } finally {
      setIsExecuting(false);
    }
  };

  const handleCancel = async () => {
    if (!runningSim || !trabajoEnCurso || isCanceling) {
      return;
    }
    setIsCanceling(true);
    setExecutionError(null);
    setExecutionSuccess(null);
    try {
      await cancelExecution(runningSim.id);
      setExecutionSuccess(
        'Cancelación solicitada. El worker confirmará el estado final del trabajo.'
      );
    } catch (error: unknown) {
      setExecutionError(
        mensajeErrorApi(error, 'No se pudo solicitar la cancelación del trabajo.')
      );
    } finally {
      setIsCanceling(false);
    }
  };

  const handleExecuteRef = useRef(handleExecute);

  useEffect(() => {
    handleExecuteRef.current = handleExecute;
  });

  useEffect(() => {
    if (!autoExecuteId) return;
    if (autoExecutionStarted.current === autoExecuteId) return;
    if (!runningSim || runningSim.id !== autoExecuteId) return;

    autoExecutionStarted.current = autoExecuteId;
    if (window.history.state?.usr) {
      window.history.replaceState(
        { ...window.history.state, usr: null },
        ''
      );
    }
    void handleExecuteRef.current();
  }, [autoExecuteId, runningSim]);

  if (!runningSim) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
        <h2>No hay simulaciones en cola ni activas</h2>
        <p style={{ color: 'var(--text-secondary)', margin: '1rem 0' }}>
          Configure una nueva simulación para ejecutarla con el motor C++ del backend.
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

  const currentDay = runningSim.currentDay;
  let currentStage = 'Sin día confirmado por el motor';
  if (currentDay !== undefined) {
    currentStage = 'Emergencia (VE - V2)';
    if (currentDay > 15 && currentDay <= 45) {
      currentStage = 'Desarrollo Vegetativo (V6 - V12)';
    } else if (currentDay > 45 && currentDay <= 68) {
      currentStage = 'Floración y Polinización (R1)';
    } else if (currentDay > 68 && currentDay <= 95) {
      currentStage = 'Llenado de Grano (R2 - R4)';
    } else if (currentDay > 95) {
      currentStage = 'Madurez Fisiológica (R6)';
    }
  }

  const visibleTimeline =
    currentDay === undefined
      ? runningSim.timelineData
      : runningSim.timelineData.filter((punto) => punto.day <= currentDay);
  const resultadosCompletos =
    runningSim.status === 'completed' && runningSim.timelineData.length > 0;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Ejecución &amp; Resultados (HPC)</h1>
          <p className="page-description">
            Ejecución asíncrona del motor C++ y consulta de los resultados y logs devueltos por FastAPI.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <select
            className="form-select"
            value={runningSim.id}
            onChange={(event) => {
              setActiveSimulationId(event.target.value);
              setExecutionError(null);
              setExecutionSuccess(null);
            }}
            style={{ width: 'auto', fontWeight: 600 }}
          >
            {simulations.map((simulation) => (
              <option key={simulation.id} value={simulation.id}>
                {simulation.id}: {simulation.config.name.substring(0, 32)}... ({simulation.status})
              </option>
            ))}
          </select>

          <button
            type="button"
            className={`btn ${flujoEnCurso ? 'btn-outline' : 'btn-primary'}`}
            disabled={flujoEnCurso || isExecuting}
            onClick={handleExecute}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            title={
              flujoEnCurso
                ? 'La simulación tiene un trabajo en curso'
                : 'Encolar ejecución en el worker del backend'
            }
          >
            {flujoEnCurso || isExecuting ? (
              <>
                <RefreshCw size={16} className="animate-spin" />
                <span>Trabajo en curso...</span>
              </>
            ) : (
              <>
                <Play size={16} />
                <span>Ejecutar Simulación HPC</span>
              </>
            )}
          </button>

          {trabajoEnCurso && activeJob && (
            <button
              type="button"
              className="btn btn-outline"
              disabled={isCanceling || activeJob.cancelRequested}
              onClick={handleCancel}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
              title="Solicitar cancelación del trabajo"
            >
              <Ban size={16} />
              <span>
                {activeJob.cancelRequested
                  ? 'Cancelación solicitada'
                  : isCanceling
                  ? 'Cancelando...'
                  : 'Cancelar trabajo'}
              </span>
            </button>
          )}
        </div>
      </div>

      {errorVisible && (
        <div
          style={{
            padding: '1rem',
            marginBottom: '1.25rem',
            borderRadius: 'var(--radius-md)',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#991b1b',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <AlertCircle size={20} />
          <div style={{ flex: 1, fontSize: '0.9rem' }}>
            <strong>Estado de la ejecución:</strong> {errorVisible}
          </div>
          <button
            type="button"
            className="btn btn-sm btn-outline"
            onClick={() => {
              setExecutionError(null);
              clearJobError(runningSim.id);
            }}
            style={{ borderColor: '#fca5a5', color: '#991b1b' }}
          >
            Cerrar
          </button>
        </div>
      )}

      {executionSuccess && (
        <div
          style={{
            padding: '1rem',
            marginBottom: '1.25rem',
            borderRadius: 'var(--radius-md)',
            background: '#f0fdf4',
            border: '1px solid #bbf7d0',
            color: '#166534',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <CheckCircle2 size={20} />
          <div style={{ flex: 1, fontSize: '0.9rem' }}>{executionSuccess}</div>
          <button
            type="button"
            className="btn btn-sm btn-outline"
            onClick={() => setExecutionSuccess(null)}
            style={{ borderColor: '#86efac', color: '#166534' }}
          >
            Cerrar
          </button>
        </div>
      )}

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
        <div style={{ margin: '1rem 0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.88rem' }}>
            <span style={{ fontWeight: 700, color: 'var(--navy)' }}>
              {currentDay === undefined
                ? 'Día de ciclo: pendiente de datos del motor'
                : `Progreso del Ciclo Agrícola: Día ${currentDay} de ${runningSim.config.simulationDays} días`}
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
                    : runningSim.status === 'canceled' || runningSim.status === 'failed'
                    ? 'var(--status-danger)'
                    : runningSim.status === 'paused'
                    ? 'var(--status-warning)'
                    : 'linear-gradient(90deg, var(--agri-green) 0%, var(--gold) 100%)',
                borderRadius: '9999px',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
        </div>

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
              Humedad del Suelo Final
            </div>
            <div style={{ fontSize: '0.98rem', fontWeight: 700, color: '#0284c7', marginTop: '0.2rem' }}>
              {runningSim.soilMoistureFinalPercent != null
                ? `${runningSim.soilMoistureFinalPercent}%`
                : 'Pendiente de resultados reales'}
            </div>
          </div>

          <div style={{ padding: '0.75rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              Estrés CWSI
            </div>
            <div style={{ fontSize: '0.98rem', fontWeight: 700, color: '#dc2626', marginTop: '0.2rem' }}>
              {runningSim.averageCWSI !== undefined
                ? runningSim.averageCWSI.toFixed(3)
                : 'Pendiente de resultados reales'}
            </div>
          </div>

          <div style={{ padding: '0.75rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              Aceleración / Speedup
            </div>
            <div style={{ fontSize: '0.98rem', fontWeight: 700, color: 'var(--gold-dark)', marginTop: '0.2rem' }}>
              <SpeedupValue value={runningSim.speedup} />
              {' · '}
              <EfficiencyValue
                efficiency={runningSim.efficiency}
                speedup={runningSim.speedup}
              />
            </div>
          </div>
        </div>

        {resultadosCompletos && (
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
                Simulación completada
                {runningSim.executionTimeSeconds !== undefined
                  ? ` en ${runningSim.executionTimeSeconds} segundos`
                  : ''}
                . Resultados cargados desde el backend.
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

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
          gap: '1.5rem',
          marginTop: '1.5rem',
        }}
      >
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

        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Terminal size={18} color="var(--navy)" />
              <span>Terminal &amp; Logs de Paralelización</span>
            </div>
          }
          subtitle="Logs del motor C++ devueltos por FastAPI (sin Slurm)"
        >
          <div className="terminal-window">
            {runningSim.logs.length === 0 ? (
              <div className="terminal-line">
                <span className="terminal-tag INFO">[INFO]</span>
                <span className="terminal-msg">
                  {resultadosCompletos
                    ? 'Simulación completada con éxito. Trazas archivadas en results/simulations/.'
                    : 'No hay registros de ejecución en curso. El worker actualizará el estado del trabajo.'}
                </span>
              </div>
            ) : (
              runningSim.logs.map((log, indice) => (
                <div key={indice} className="terminal-line">
                  <span className="terminal-time">[{log.timestamp}]</span>
                  <span className={`terminal-tag ${log.level}`}>[{log.level}]</span>
                  <span className="terminal-msg">{log.message}</span>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
