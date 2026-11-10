import { useState } from 'react';
import { Card } from '../components/common/Card';
import { StatCard } from '../components/common/StatCard';
import { EngineBadge } from '../components/common/EngineBadge';
import {
  HPC_BENCHMARK_DATA,
  STRONG_SCALING_CURVES,
} from '../services/mockData';
import {
  Zap,
  Server,
  Layers,
  Cpu,
  Network,
  TrendingUp,
  Clock,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';

export function PerformanceComparison() {
  const [selectedParadigm, setSelectedParadigm] = useState<'all' | 'openmp' | 'mpi' | 'hibrido'>('all');

  const filteredData =
    selectedParadigm === 'all'
      ? HPC_BENCHMARK_DATA
      : HPC_BENCHMARK_DATA.filter((d) => d.engine === selectedParadigm || d.engine === 'secuencial');

  // Breakdown data for computation vs communication
  const breakdownData = [
    { name: 'Secuencial (1c)', comp: 338.2, comm: 0.0, total: 342.5 },
    { name: 'OpenMP (4h)', comp: 87.4, comm: 4.4, total: 91.8 },
    { name: 'OpenMP (16h)', comp: 26.8, comm: 7.3, total: 34.1 },
    { name: 'MPI (4p)', comp: 86.8, comm: 7.7, total: 94.5 },
    { name: 'MPI (16p)', comp: 17.6, comm: 9.2, total: 26.8 },
    { name: 'Híbrido (16c)', comp: 18.8, comm: 4.6, total: 23.4 },
    { name: 'Híbrido (32c)', comp: 8.9, comm: 4.3, total: 13.2 },
  ];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Comparación de Rendimiento HPC</h1>
          <p className="page-description">
            Evaluación empírica y teórica de escalabilidad: Secuencial vs OpenMP vs MPI vs Híbrido en el clúster
            Chaco.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            className={`btn btn-sm ${selectedParadigm === 'all' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setSelectedParadigm('all')}
          >
            Todos los Motores
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
            MPI Distribuido
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

      {/* HPC Performance Headline Stats */}
      <div className="stats-grid">
        <StatCard
          label="Tiempo Línea Base (T1)"
          value="342.5 s"
          subtext="Secuencial Mono-núcleo C++"
          icon={<Clock size={24} />}
          variant="default"
        />
        <StatCard
          label="Mejor Tiempo Clúster"
          value="13.2 s"
          subtext="Híbrido 4 Nodos x 8 Hilos (32 cores)"
          icon={<Zap size={24} />}
          variant="gold"
          badge="Máxima Rapidez"
        />
        <StatCard
          label="Speedup Máximo Alcanzado"
          value="25.95×"
          subtext="Aceleración respecto a mono-núcleo"
          icon={<TrendingUp size={24} />}
          variant="agri"
        />
        <StatCard
          label="Eficiencia Paralela Pico"
          value="97.2%"
          subtext="OpenMP con 2 hilos (mínimo overhead)"
          icon={<Server size={24} />}
          variant="info"
        />
      </div>

      {/* Strong Scaling Chart & Communication Breakdown */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
          gap: '1.5rem',
          marginBottom: '1.75rem',
        }}
      >
        {/* Strong Scaling Chart */}
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <TrendingUp size={20} color="var(--navy)" />
              <span>Escalabilidad Fuerte: Speedup ($S_p$) vs Núcleos</span>
            </div>
          }
          subtitle="Tamaño de problema fijo (Grilla 250×250, 120 días). Comparativa frente a la aceleración lineal ideal."
        >
          <div style={{ height: '320px', width: '100%', marginTop: '0.5rem' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={STRONG_SCALING_CURVES} margin={{ top: 15, right: 20, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  dataKey="workers"
                  label={{ value: 'Número de Núcleos / Hilos / Procesos', position: 'insideBottom', offset: -10, fontSize: 12 }}
                />
                <YAxis
                  label={{ value: 'Speedup Sp (veces)', angle: -90, position: 'insideLeft', fontSize: 12 }}
                  domain={[1, 32]}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: '8px',
                    borderColor: '#cbd5e1',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                  }}
                  formatter={(val, name) => [`${val}x`, name]}
                  labelFormatter={(lbl) => `${lbl} núcleos`}
                />
                <Legend verticalAlign="top" height={36} />

                {/* Ideal line */}
                <Line
                  type="monotone"
                  dataKey="idealSpeedup"
                  name="Ideal Lineal"
                  stroke="#94a3b8"
                  strokeDasharray="4 4"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="hibridoSpeedup"
                  name="Híbrido (MPI + OMP)"
                  stroke="var(--gold)"
                  strokeWidth={3}
                  activeDot={{ r: 6 }}
                />
                <Line
                  type="monotone"
                  dataKey="mpiSpeedup"
                  name="MPI Distribuido"
                  stroke="var(--engine-mpi)"
                  strokeWidth={2.5}
                />
                <Line
                  type="monotone"
                  dataKey="openmpSpeedup"
                  name="OpenMP Compartido"
                  stroke="var(--agri-green)"
                  strokeWidth={2.5}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div
            style={{
              fontSize: '0.8rem',
              color: 'var(--text-secondary)',
              marginTop: '0.5rem',
              padding: '0.6rem 0.85rem',
              background: 'var(--bg-main)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <strong>Observación:</strong> El motor Híbrido escala con mayor proximidad a la curva ideal debido a que
            minimiza el número de mensajes MPI utilizando memoria compartida dentro de cada nodo socket.
          </div>
        </Card>

        {/* Computation vs Communication Breakdown */}
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Layers size={20} color="var(--agri-green)" />
              <span>Desglose: Cálculo vs Sobrecarga de Comunicación</span>
            </div>
          }
          subtitle="Tiempo en cómputo hidrológico local frente a sincronización y halo exchange en red (segundos)"
        >
          <div style={{ height: '320px', width: '100%', marginTop: '0.5rem' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={breakdownData} margin={{ top: 15, right: 15, left: -10, bottom: 25 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-15} textAnchor="end" />
                <YAxis label={{ value: 'Tiempo (seg)', angle: -90, position: 'insideLeft', fontSize: 12 }} />
                <Tooltip
                  formatter={(val, name) => [`${val}s`, name === 'comp' ? 'Cálculo Local' : 'Comunicación & Sync']}
                  contentStyle={{
                    borderRadius: '8px',
                    borderColor: '#cbd5e1',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                  }}
                />
                <Legend verticalAlign="top" height={36} />
                <Bar dataKey="comp" name="Cálculo Hidrológico" fill="var(--agri-green)" stackId="a" />
                <Bar dataKey="comm" name="Comunicación / Sincronización" fill="var(--gold)" stackId="a" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div
            style={{
              fontSize: '0.8rem',
              color: 'var(--text-secondary)',
              marginTop: '0.5rem',
              padding: '0.6rem 0.85rem',
              background: 'var(--bg-main)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <strong>Sobrecarga:</strong> En MPI puro a 16 procesos la comunicación representa el 34.3% del tiempo total,
            mientras que en Híbrido 32 cores se reduce al 32.5% gracias al intercambio en bloques locales de memoria compartida.
          </div>
        </Card>
      </div>

      {/* Full Benchmark Data Table */}
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Server size={20} color="var(--navy)" />
            <span>Matriz de Benchmark Detallada del Simulador AgroChaco</span>
          </div>
        }
        subtitle="Mediciones obtenidas en el Clúster HPC Gran Chaco (Nodos chaco-node-[01..04])"
      >
        <div className="table-container">
          <table className="agro-table">
            <thead>
              <tr>
                <th>Arquitectura / Motor</th>
                <th>Cores / Hilos</th>
                <th>Nodos</th>
                <th>Tiempo Ejecución ($T_p$)</th>
                <th>Speedup ($S_p$)</th>
                <th>Eficiencia ($E_p$)</th>
                <th>Cálculo Local</th>
                <th>Comunicación</th>
                <th>RAM</th>
                <th>Rendimiento</th>
              </tr>
            </thead>
            <tbody>
              {filteredData.map((item, idx) => (
                <tr key={idx}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <EngineBadge engine={item.engine} />
                      <span style={{ fontWeight: 600, color: 'var(--navy)' }}>{item.label}</span>
                    </div>
                  </td>
                  <td>
                    <span style={{ fontWeight: 700 }}>{item.coresOrProcesses}</span> núcleos
                  </td>
                  <td>{item.nodes} {item.nodes === 1 ? 'nodo' : 'nodos'}</td>
                  <td>
                    <strong style={{ color: 'var(--navy)' }}>{item.executionTimeSeconds} s</strong>
                  </td>
                  <td>
                    <span
                      style={{
                        fontWeight: 700,
                        color: (item.speedup ?? 0) > 10 ? 'var(--gold-dark)' : (item.speedup ?? 0) > 1 ? 'var(--agri-green)' : 'inherit',
                      }}
                    >
                      {item.speedup}×
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span>{item.efficiencyPercent}%</span>
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
                            width: `${Math.min(100, item.efficiencyPercent)}%`,
                            height: '100%',
                            background: item.efficiencyPercent >= 80 ? 'var(--agri-green)' : 'var(--status-warning)',
                          }}
                        />
                      </div>
                    </div>
                  </td>
                  <td>{item.computationTimeSec} s</td>
                  <td>{item.communicationTimeSec} s</td>
                  <td>{item.memoryMb} MB</td>
                  <td>
                    <span className="system-tag">{item.gflopsEstimate} GFLOPs</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Scientific Analysis & Theoretical Discussion */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: '1.5rem',
          marginTop: '1.75rem',
        }}
      >
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Cpu size={18} color="var(--agri-green)" />
              <span>Análisis de Cuellos de Botella (OpenMP)</span>
            </div>
          }
        >
          <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Al escalar OpenMP más allá de 8 hilos en un único nodo, la eficiencia decae de 83.3% a 62.8% debido al
            <strong> cuello de botella en el ancho de banda del bus de memoria (Memory Bandwidth Saturation)</strong>.
            Las actualizaciones de la matriz bidimensional de suelo requieren lecturas intensivas que saturan los canales DDR4/DDR5.
          </p>
        </Card>

        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Network size={18} color="var(--engine-mpi)" />
              <span>Intercambio de Halos en MPI (Ghost Cells)</span>
            </div>
          }
        >
          <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            En la descomposición 2D en damero con MPI, cada subdominio intercambia 2 celdas de halo en las cuatro fronteras
            cardinales mediante llamadas <code>MPI_Isend</code> y <code>MPI_Irecv</code>. A 16 procesos, el número de mensajes
            aumenta y la latencia de la red Gigabit Ethernet comienza a competir con el tiempo de cálculo local.
          </p>
        </Card>

        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Server size={18} color="var(--gold-dark)" />
              <span>Por qué Triunfa el Modelo Híbrido</span>
            </div>
          }
        >
          <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            La arquitectura híbrida (1 proceso MPI por socket + 8 hilos OpenMP) combina lo mejor de ambos mundos:
            aprovecha la localidad de la caché L3 por CPU y minimiza el tráfico de red inter-nodo, permitiendo alcanzar
            un speedup de <strong>25.95×</strong> con una eficiencia superior al <strong>81%</strong> en 32 núcleos.
          </p>
        </Card>
      </div>
    </div>
  );
}
