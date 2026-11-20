import { useState } from 'react';
import { useSimulations } from '../context';
import { Card } from '../components/common/Card';
import { StatCard } from '../components/common/StatCard';
import { EngineBadge } from '../components/common/EngineBadge';
import {
  Zap,
  Server,
  Layers,
  Cpu,
  TrendingUp,
  Clock,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';

export interface ExperimentalBenchmarkRecord {
  engine: 'secuencial' | 'openmp' | 'mpi' | 'hibrido';
  motor: string;
  label: string;
  recursos: string;
  promedioSegundos: number;
  medianaSegundos: number;
  speedup: number;
  eficienciaPorcentaje: number;
  hardware: string;
}

interface ExperimentalMeasurementRecord {
  engine: 'secuencial' | 'openmp' | 'mpi' | 'hibrido';
  motor: string;
  ejecucion: number;
  trabajadores: number;
  tiempoSegundos: number;
}

const EXPERIMENTAL_CPLUSPLUS_BENCHMARKS: ExperimentalBenchmarkRecord[] = [
  {
    engine: 'secuencial',
    motor: 'Secuencial',
    label: 'Secuencial C++17 (línea base T1)',
    recursos: '1 trabajador',
    promedioSegundos: 0.245,
    medianaSegundos: 0.244,
    speedup: 1.0,
    eficienciaPorcentaje: 100.0,
    hardware: 'Intel Core i7-13700 (Ubuntu 24.04)',
  },
  {
    engine: 'openmp',
    motor: 'OpenMP',
    label: 'OpenMP memoria compartida',
    recursos: '16 trabajadores',
    promedioSegundos: 0.0408,
    medianaSegundos: 0.04,
    speedup: 6.0049,
    eficienciaPorcentaje: 37.53,
    hardware: 'Intel Core i7-13700 (Ubuntu 24.04)',
  },
  {
    engine: 'mpi',
    motor: 'MPI',
    label: 'MPI memoria distribuida',
    recursos: '4 trabajadores',
    promedioSegundos: 0.0682,
    medianaSegundos: 0.067,
    speedup: 3.5924,
    eficienciaPorcentaje: 89.81,
    hardware: 'Intel Core i7-13700 (Ubuntu 24.04)',
  },
  {
    engine: 'hibrido',
    motor: 'Híbrido',
    label: 'Híbrido MPI + OpenMP',
    recursos: '16 trabajadores',
    promedioSegundos: 0.1194,
    medianaSegundos: 0.121,
    speedup: 2.0519,
    eficienciaPorcentaje: 12.82,
    hardware: 'Intel Core i7-13700 (Ubuntu 24.04)',
  },
];

const EXPERIMENTAL_RAW_MEASUREMENTS: ExperimentalMeasurementRecord[] = [
  { engine: 'secuencial', motor: 'Secuencial', ejecucion: 1, trabajadores: 1, tiempoSegundos: 0.252 },
  { engine: 'secuencial', motor: 'Secuencial', ejecucion: 2, trabajadores: 1, tiempoSegundos: 0.246 },
  { engine: 'secuencial', motor: 'Secuencial', ejecucion: 3, trabajadores: 1, tiempoSegundos: 0.244 },
  { engine: 'secuencial', motor: 'Secuencial', ejecucion: 4, trabajadores: 1, tiempoSegundos: 0.243 },
  { engine: 'secuencial', motor: 'Secuencial', ejecucion: 5, trabajadores: 1, tiempoSegundos: 0.24 },
  { engine: 'openmp', motor: 'OpenMP', ejecucion: 1, trabajadores: 16, tiempoSegundos: 0.046 },
  { engine: 'openmp', motor: 'OpenMP', ejecucion: 2, trabajadores: 16, tiempoSegundos: 0.043 },
  { engine: 'openmp', motor: 'OpenMP', ejecucion: 3, trabajadores: 16, tiempoSegundos: 0.04 },
  { engine: 'openmp', motor: 'OpenMP', ejecucion: 4, trabajadores: 16, tiempoSegundos: 0.037 },
  { engine: 'openmp', motor: 'OpenMP', ejecucion: 5, trabajadores: 16, tiempoSegundos: 0.038 },
  { engine: 'mpi', motor: 'MPI', ejecucion: 1, trabajadores: 4, tiempoSegundos: 0.067 },
  { engine: 'mpi', motor: 'MPI', ejecucion: 2, trabajadores: 4, tiempoSegundos: 0.068 },
  { engine: 'mpi', motor: 'MPI', ejecucion: 3, trabajadores: 4, tiempoSegundos: 0.066 },
  { engine: 'mpi', motor: 'MPI', ejecucion: 4, trabajadores: 4, tiempoSegundos: 0.067 },
  { engine: 'mpi', motor: 'MPI', ejecucion: 5, trabajadores: 4, tiempoSegundos: 0.073 },
  { engine: 'hibrido', motor: 'Híbrido', ejecucion: 1, trabajadores: 16, tiempoSegundos: 0.112 },
  { engine: 'hibrido', motor: 'Híbrido', ejecucion: 2, trabajadores: 16, tiempoSegundos: 0.121 },
  { engine: 'hibrido', motor: 'Híbrido', ejecucion: 3, trabajadores: 16, tiempoSegundos: 0.121 },
  { engine: 'hibrido', motor: 'Híbrido', ejecucion: 4, trabajadores: 16, tiempoSegundos: 0.121 },
  { engine: 'hibrido', motor: 'Híbrido', ejecucion: 5, trabajadores: 16, tiempoSegundos: 0.122 },
];

export function PerformanceComparison() {
  const { simulations } = useSimulations();
  const [selectedParadigm, setSelectedParadigm] = useState<'all' | 'secuencial' | 'openmp' | 'mpi' | 'hibrido'>('all');

  const matchesParadigm = (engine: ExperimentalBenchmarkRecord['engine']) =>
    selectedParadigm === 'all' || engine === selectedParadigm;

  const realCompletedSimulations = simulations.filter(
    (s) => s.status === 'completed' && s.executionTimeSeconds != null
  );

  const filteredSummary = EXPERIMENTAL_CPLUSPLUS_BENCHMARKS.filter((item) => matchesParadigm(item.engine));
  const filteredMeasurements = EXPERIMENTAL_RAW_MEASUREMENTS.filter((item) => matchesParadigm(item.engine));
  const filteredRealSimulations = realCompletedSimulations.filter(
    (s) => selectedParadigm === 'all' || s.config.engine === selectedParadigm
  );

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Comparación de Rendimiento HPC</h1>
          <p className="page-description">
            Resultados experimentales históricos respaldados por archivos y ejecuciones reales registradas en PostgreSQL, presentados por separado.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`btn btn-sm ${selectedParadigm === 'all' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setSelectedParadigm('all')}
          >
            Todos los Motores
          </button>
          <button
            type="button"
            className={`btn btn-sm ${selectedParadigm === 'secuencial' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setSelectedParadigm('secuencial')}
          >
            Secuencial (T1)
          </button>
          <button
            type="button"
            className={`btn btn-sm ${selectedParadigm === 'openmp' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setSelectedParadigm('openmp')}
          >
            OpenMP
          </button>
          <button
            type="button"
            className={`btn btn-sm ${selectedParadigm === 'mpi' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setSelectedParadigm('mpi')}
          >
            MPI
          </button>
          <button
            type="button"
            className={`btn btn-sm ${selectedParadigm === 'hibrido' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setSelectedParadigm('hibrido')}
          >
            Híbrido
          </button>
        </div>
      </div>

      <div className="stats-grid">
        <StatCard
          label="Tiempo Línea Base (T1)"
          value="0.2450 s"
          subtext="Secuencial · 1 trabajador (resumen.csv)"
          icon={<Clock size={24} />}
          variant="default"
        />
        <StatCard
          label="Menor Tiempo Medido"
          value="0.0408 s"
          subtext="OpenMP · 16 trabajadores (resumen.csv)"
          icon={<Zap size={24} />}
          variant="gold"
          badge="Menor promedio registrado"
        />
        <StatCard
          label="Speedup Máximo Registrado"
          value="6.0049×"
          subtext="OpenMP frente a la línea base T1"
          icon={<TrendingUp size={24} />}
          variant="agri"
        />
        <StatCard
          label="Eficiencia MPI Registrada"
          value="89.81%"
          subtext="MPI · 4 trabajadores (resumen.csv)"
          icon={<Server size={24} />}
          variant="info"
        />
      </div>

      <div style={{ marginTop: '1.75rem', marginBottom: '1rem' }}>
        <span className="system-tag">FUENTE 1 · ARCHIVOS</span>
        <h2 style={{ margin: '0.5rem 0 0.25rem', fontSize: '1.15rem', color: 'var(--navy)' }}>
          Resultados experimentales históricos
        </h2>
        <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-muted)' }}>
          Fuente: <code>results/benchmark_final/resumen.csv</code>, <code>mediciones.csv</code> y los JSON de cada ejecución. Malla 500×500, 120 días.
        </p>
      </div>

      <Card
        className="mb-6"
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Server size={20} color="var(--navy)" />
            <span>Resumen Experimental de Motores C++17 (results/benchmark_final/resumen.csv)</span>
          </div>
        }
        subtitle="Cuatro modalidades experimentales; los valores mostrados corresponden al archivo de resumen sin estimaciones adicionales"
      >
        <div className="table-container">
          <table className="agro-table">
            <thead>
              <tr>
                <th>Modalidad</th>
                <th>Recursos / Trabajadores</th>
                <th>Tiempo Promedio ($T_p$)</th>
                <th>Tiempo Mediana</th>
                <th>Speedup ($S_p$)</th>
                <th>Eficiencia ($E_p$)</th>
                <th>Entorno de Prueba</th>
              </tr>
            </thead>
            <tbody>
              {filteredSummary.map((item) => (
                <tr key={item.engine}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <EngineBadge engine={item.engine} />
                      <span style={{ fontWeight: 600, color: 'var(--navy)' }}>{item.label}</span>
                    </div>
                  </td>
                  <td>
                    <strong>{item.recursos}</strong>
                  </td>
                  <td>
                    <strong style={{ color: 'var(--navy)' }}>{item.promedioSegundos.toFixed(4)} s</strong>
                  </td>
                  <td>{item.medianaSegundos.toFixed(4)} s</td>
                  <td>
                    <span
                      style={{
                        fontWeight: 700,
                        color: item.speedup > 3 ? 'var(--gold-dark)' : item.speedup > 1 ? 'var(--agri-green)' : 'inherit',
                      }}
                    >
                      {item.speedup.toFixed(4)}×
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span>{item.eficienciaPorcentaje.toFixed(2)}%</span>
                      <div
                        style={{
                          width: '45px',
                          height: '6px',
                          background: '#e2e8f0',
                          borderRadius: '3px',
                          overflow: 'hidden',
                        }}
                      >
                        <div
                          style={{
                            width: `${Math.min(100, item.eficienciaPorcentaje)}%`,
                            height: '100%',
                            background: item.eficienciaPorcentaje >= 80 ? 'var(--agri-green)' : 'var(--status-warning)',
                          }}
                        />
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className="system-tag">{item.hardware}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card
        className="mb-6"
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <TrendingUp size={20} color="var(--navy)" />
            <span>Tiempos promedios medidos por modalidad</span>
          </div>
        }
        subtitle="Solo puntos experimentales disponibles; no representa una curva de escalabilidad"
      >
        <div style={{ height: '320px', width: '100%', marginTop: '0.5rem' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={filteredSummary} margin={{ top: 15, right: 15, left: -10, bottom: 25 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis dataKey="motor" tick={{ fontSize: 12 }} />
              <YAxis label={{ value: 'Tiempo promedio (s)', angle: -90, position: 'insideLeft', fontSize: 12 }} />
              <Tooltip
                formatter={(val, name) => [`${Number(val).toFixed(4)} s`, name]}
                contentStyle={{
                  borderRadius: '8px',
                  borderColor: '#cbd5e1',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                }}
              />
              <Legend verticalAlign="top" height={36} />
              <Bar dataKey="promedioSegundos" name="Tiempo promedio" fill="var(--agri-green)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card
        className="mb-6"
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Layers size={20} color="var(--navy)" />
            <span>Mediciones individuales (results/benchmark_final/mediciones.csv)</span>
          </div>
        }
        subtitle="20 ejecuciones registradas: 5 repeticiones por modalidad"
      >
        <div className="table-container">
          <table className="agro-table">
            <thead>
              <tr>
                <th>Modalidad</th>
                <th>Ejecución</th>
                <th>Trabajadores</th>
                <th>Tiempo medido ($T_p$)</th>
              </tr>
            </thead>
            <tbody>
              {filteredMeasurements.map((item) => (
                <tr key={`${item.engine}-${item.ejecucion}`}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <EngineBadge engine={item.engine} />
                      <span style={{ fontWeight: 600, color: 'var(--navy)' }}>{item.motor}</span>
                    </div>
                  </td>
                  <td>{item.ejecucion}</td>
                  <td>{item.trabajadores}</td>
                  <td>
                    <strong style={{ color: 'var(--navy)' }}>{item.tiempoSegundos.toFixed(3)} s</strong>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: '1.5rem',
          marginBottom: '1.75rem',
        }}
      >
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Cpu size={18} color="var(--agri-green)" />
              <span>Alcance de la comparación</span>
            </div>
          }
        >
          <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Solo se dispone de una configuración paralela por modalidad: OpenMP con 16 trabajadores, MPI con 4 y
            Híbrido con 16. Los datos permiten comparar esos puntos experimentales, pero no construir curvas de
            escalabilidad ni inferir resultados para otros números de trabajadores.
          </p>
        </Card>

        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Zap size={18} color="var(--gold-dark)" />
              <span>Observaciones sobre los promedios registrados</span>
            </div>
          }
        >
          <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            El menor promedio del resumen corresponde a OpenMP (0.0408 s, 6.0049×). MPI registró 0.0682 s
            (3.5924×) con 4 trabajadores y el modo híbrido 0.1194 s (2.0519×) con 16. Estos valores describen
            únicamente las configuraciones ejecutadas.
          </p>
        </Card>

        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Server size={18} color="var(--engine-mpi)" />
              <span>Datos no disponibles</span>
            </div>
          }
        >
          <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Los archivos no incluyen desglose de comunicación, consumo de RAM ni estimaciones de GFLOPs, por lo que
            no se muestran. MPI se ejecutó en una única máquina física: no hay evidencia para atribuir diferencias a
            nodos físicos ni a red inter-nodo.
          </p>
        </Card>
      </div>

      <div style={{ marginTop: '1.75rem', marginBottom: '1rem' }}>
        <span className="system-tag">FUENTE 2 · POSTGRESQL</span>
        <h2 style={{ margin: '0.5rem 0 0.25rem', fontSize: '1.15rem', color: 'var(--navy)' }}>
          Ejecuciones reales registradas en PostgreSQL
        </h2>
        <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-muted)' }}>
          Registros completados obtenidos por FastAPI; se mantienen separados de los resultados experimentales de archivos.
        </p>
      </div>

      <Card
        className="mb-6"
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Zap size={20} color="var(--agri-green)" />
            <span>Corridas reales registradas en Base de Datos (PostgreSQL / FastAPI)</span>
          </div>
        }
        subtitle={`Simulaciones completadas con tiempo de ejecución (${realCompletedSimulations.length} registros disponibles)`}
      >
        {filteredRealSimulations.length > 0 ? (
          <div className="table-container">
            <table className="agro-table">
              <thead>
                <tr>
                  <th>ID Simulación</th>
                  <th>Nombre</th>
                  <th>Modalidad</th>
                  <th>Recursos HPC</th>
                  <th>Malla / Días</th>
                  <th>Tiempo ($T_p$)</th>
                  <th>Speedup ($S_p$)</th>
                  <th>Eficiencia ($E_p$)</th>
                  <th>Estrés CWSI</th>
                </tr>
              </thead>
              <tbody>
                {filteredRealSimulations.map((sim) => {
                  const threads = sim.config.openmpThreads || 1;
                  const procs = sim.config.mpiProcesses || 1;
                  const resourcesLabel =
                    sim.config.engine === 'secuencial'
                      ? '1 hilo (mono-núcleo)'
                      : sim.config.engine === 'openmp'
                      ? `${threads} hilos OpenMP`
                      : sim.config.engine === 'mpi'
                      ? `${procs} procesos MPI`
                      : `${procs} procs × ${threads} hilos (${procs * threads} trabajadores)`;

                  const effVal =
                    sim.efficiency != null
                      ? sim.efficiency <= 1
                        ? sim.efficiency * 100
                        : sim.efficiency
                      : null;

                  return (
                    <tr key={sim.id}>
                      <td>
                        <code style={{ fontWeight: 700 }}>{sim.id}</code>
                      </td>
                      <td>
                        <span style={{ fontWeight: 600, color: 'var(--navy)' }}>{sim.config.name}</span>
                      </td>
                      <td>
                        <EngineBadge
                          engine={sim.config.engine}
                          threads={sim.config.openmpThreads}
                          processes={sim.config.mpiProcesses}
                        />
                      </td>
                      <td>{resourcesLabel}</td>
                      <td>
                        {sim.config.gridConfig.rows}x{sim.config.gridConfig.cols} ({sim.config.simulationDays}d)
                      </td>
                      <td>
                        <strong style={{ color: 'var(--navy)' }}>
                          {sim.executionTimeSeconds != null ? `${sim.executionTimeSeconds.toFixed(4)} s` : '-'}
                        </strong>
                      </td>
                      <td>
                        <span style={{ fontWeight: 700, color: 'var(--agri-green)' }}>
                          {sim.speedup != null ? `${sim.speedup.toFixed(2)}×` : '-'}
                        </span>
                      </td>
                      <td>{effVal != null ? `${effVal.toFixed(1)}%` : '-'}</td>
                      <td>{sim.averageCWSI != null ? sim.averageCWSI.toFixed(3) : '-'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>
            {selectedParadigm === 'all'
              ? 'No hay simulaciones completadas registradas actualmente.'
              : 'No hay simulaciones completadas registradas para la modalidad seleccionada.'}
          </p>
        )}
      </Card>
    </div>
  );
}
