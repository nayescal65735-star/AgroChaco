import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSimulations } from '../context';
import {
  GRAN_CHACO_ZONES,
  SOIL_INFOS,
  CORN_VARIETIES,
} from '../services/mockData';
import type {
  GranChacoZoneId,
  SoilType,
  CornVarietyId,
  SimulationEngine,
  DroughtScenario,
} from '../types';
import { Card } from '../components/common/Card';
import {
  Cpu,
  Layers,
  Network,
  Server,
  Sprout,
  Play,
  Grid,
} from 'lucide-react';

export function NewSimulation() {
  const { createSimulation, startExecution } = useSimulations();
  const navigate = useNavigate();

  // Form states
  const [name, setName] = useState('Simulación Sequía Gran Chaco 2026');
  const [zone, setZone] = useState<GranChacoZoneId>('villamontes');
  const [soilType, setSoilType] = useState<SoilType>('franco_arenoso');
  const [cornVariety, setCornVariety] = useState<CornVarietyId>('chaco_01_criollo');
  const [plantingDate, setPlantingDate] = useState('2026-11-15');
  const [simulationDays, setSimulationDays] = useState(120);
  const [initialMoisture, setInitialMoisture] = useState(16.0);
  const [droughtScenario, setDroughtScenario] = useState<DroughtScenario>('extremo_ssp585');
  
  // Grid config
  const [gridRows, setGridRows] = useState(200);
  const [gridCols, setGridCols] = useState(200);
  const [cellSize, setCellSize] = useState(50);

  // HPC config
  const [engine, setEngine] = useState<SimulationEngine>('hibrido');
  const [openmpThreads, setOpenmpThreads] = useState(8);
  const [mpiProcesses, setMpiProcesses] = useState(4);
  const [nodesCount, setNodesCount] = useState(4);

  const selectedZone = GRAN_CHACO_ZONES.find((z) => z.id === zone)!;
  const selectedSoil = SOIL_INFOS.find((s) => s.id === soilType)!;

  // Real-time HPC estimation
  const totalCells = gridRows * gridCols;
  const totalHectaresSimulated = ((totalCells * (cellSize * cellSize)) / 10000).toFixed(0);

  const calculateEstimate = () => {
    const baseSequentialSeconds = Math.max(30, (totalCells / 40000) * (simulationDays / 120) * 320);
    let speedup = 1.0;

    if (engine === 'openmp') {
      speedup = Number((openmpThreads * 0.88).toFixed(2));
    } else if (engine === 'mpi') {
      speedup = Number((mpiProcesses * 0.84).toFixed(2));
    } else if (engine === 'hibrido') {
      speedup = Number((mpiProcesses * openmpThreads * 0.85).toFixed(2));
    }

    const estimatedTime = (baseSequentialSeconds / speedup).toFixed(1);
    const efficiency = ((speedup / (engine === 'secuencial' ? 1 : engine === 'openmp' ? openmpThreads : engine === 'mpi' ? mpiProcesses : mpiProcesses * openmpThreads)) * 100).toFixed(1);

    return { estimatedTime, speedup, efficiency, baseSequentialSeconds: baseSequentialSeconds.toFixed(1) };
  };

  const est = calculateEstimate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const newSimId = createSimulation({
      name,
      zone,
      zoneName: selectedZone.name,
      department: selectedZone.department,
      soilType,
      cornVariety,
      plantingDate,
      simulationDays,
      gridConfig: {
        rows: gridRows,
        cols: gridCols,
        cellSizeMeters: cellSize,
      },
      initialMoisturePercent: initialMoisture,
      droughtScenario,
      engine,
      openmpThreads: engine === 'openmp' || engine === 'hibrido' ? openmpThreads : undefined,
      mpiProcesses: engine === 'mpi' || engine === 'hibrido' ? mpiProcesses : undefined,
      nodesCount: engine === 'mpi' || engine === 'hibrido' ? nodesCount : 1,
    });

    startExecution(newSimId);
    navigate('/ejecucion');
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Configuración de Nueva Simulación HPC</h1>
          <p className="page-description">
            Defina la parametriza hidrológica, el dominio espacial y la arquitectura de paralelización para la
            campaña agrícola.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
            gap: '1.5rem',
            marginBottom: '1.5rem',
          }}
        >
          {/* Section 1: Gran Chaco Agroclimatic Parameters */}
          <Card
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sprout size={20} color="var(--agri-green)" />
                <span>1. Parámetros del Cultivo y Suelo Chaqueño</span>
              </div>
            }
            subtitle="Condiciones edafológicas y fenológicas de Zea mays en el Chaco boliviano"
          >
            <div className="form-group">
              <label className="form-label" htmlFor="sim-name">Nombre de la Corrida Experimental</label>
              <input
                id="sim-name"
                type="text"
                className="form-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="sim-zone">Zona Geográfica (Municipio)</label>
                <select
                  id="sim-zone"
                  className="form-select"
                  value={zone}
                  onChange={(e) => setZone(e.target.value as GranChacoZoneId)}
                >
                  {GRAN_CHACO_ZONES.map((z) => (
                    <option key={z.id} value={z.id}>
                      {z.name} ({z.department}) - Riesgo {z.currentRisk}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="sim-soil">Tipo de Suelo</label>
                <select
                  id="sim-soil"
                  className="form-select"
                  value={soilType}
                  onChange={(e) => setSoilType(e.target.value as SoilType)}
                >
                  {SOIL_INFOS.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Dynamic Soil detail banner */}
            <div
              style={{
                padding: '0.75rem',
                borderRadius: 'var(--radius-md)',
                background: 'var(--bg-main)',
                fontSize: '0.8rem',
                color: 'var(--text-secondary)',
                marginBottom: '1rem',
              }}
            >
              <strong>Propiedades hídricas del suelo:</strong> Capacidad de Campo: {selectedSoil.fieldCapacity}% • Punto de Marchitez: {selectedSoil.wiltingPoint}% • Agua Útil: {selectedSoil.availableWaterMmPerM} mm/m.
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="sim-variety">Variedad de Maíz</label>
                <select
                  id="sim-variety"
                  className="form-select"
                  value={cornVariety}
                  onChange={(e) => setCornVariety(e.target.value as CornVarietyId)}
                >
                  {CORN_VARIETIES.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name} ({v.cycleDays} días, rinde {v.potentialYieldTnHa} tn/ha)
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="sim-initial-moisture">
                  Humedad Inicial del Suelo (%)
                </label>
                <input
                  id="sim-initial-moisture"
                  type="number"
                  step="0.5"
                  min="5"
                  max="35"
                  className="form-input"
                  value={initialMoisture}
                  onChange={(e) => setInitialMoisture(Number(e.target.value))}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="sim-date">Fecha de Siembra</label>
                <input
                  id="sim-date"
                  type="date"
                  className="form-input"
                  value={plantingDate}
                  onChange={(e) => setPlantingDate(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="sim-days">Horizonte Temporal (Días)</label>
                <input
                  id="sim-days"
                  type="number"
                  min="30"
                  max="150"
                  className="form-input"
                  value={simulationDays}
                  onChange={(e) => setSimulationDays(Number(e.target.value))}
                />
              </div>
            </div>
          </Card>

          {/* Section 2: Climate Scenario & Grid Discretization */}
          <Card
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Grid size={20} color="var(--navy)" />
                <span>2. Escenario Climático &amp; Malla Espacial</span>
              </div>
            }
            subtitle="Discretización bidimensional en diferencias finitas y forzamiento meteorológico"
          >
            <div className="form-group">
              <label className="form-label" htmlFor="sim-scenario">Escenario de Sequía y Proyección</label>
              <select
                id="sim-scenario"
                className="form-select"
                value={droughtScenario}
                onChange={(e) => setDroughtScenario(e.target.value as DroughtScenario)}
              >
                <option value="historico">Histórico Normal (Promedios SENAMHI 1991-2020)</option>
                <option value="moderado_ssp245">CMIP6 SSP2-4.5 (Calentamiento moderado +1.5°C)</option>
                <option value="extremo_ssp585">CMIP6 SSP5-8.5 (Sequía severa proyectada +3.0°C)</option>
                <option value="sequia_recente_2023">Sequía Extrema Reciente (Evento histórico 2023)</option>
              </select>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="sim-grid-rows">Filas (Y)</label>
                <input
                  id="sim-grid-rows"
                  type="number"
                  min="50"
                  max="1000"
                  step="50"
                  className="form-input"
                  value={gridRows}
                  onChange={(e) => setGridRows(Number(e.target.value))}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="sim-grid-cols">Columnas (X)</label>
                <input
                  id="sim-grid-cols"
                  type="number"
                  min="50"
                  max="1000"
                  step="50"
                  className="form-input"
                  value={gridCols}
                  onChange={(e) => setGridCols(Number(e.target.value))}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="sim-cell-size">Celda (m)</label>
                <input
                  id="sim-cell-size"
                  type="number"
                  min="10"
                  max="200"
                  step="10"
                  className="form-input"
                  value={cellSize}
                  onChange={(e) => setCellSize(Number(e.target.value))}
                />
              </div>
            </div>

            <div
              style={{
                padding: '0.85rem 1rem',
                borderRadius: 'var(--radius-md)',
                background: 'var(--soft-green)',
                color: 'var(--agri-green-dark)',
                fontSize: '0.85rem',
                marginTop: '1rem',
              }}
            >
              <div style={{ fontWeight: 700 }}>Resumen del Dominio Físico:</div>
              <div>
                • Celdas de cálculo: <strong>{totalCells.toLocaleString()} puntos</strong>
              </div>
              <div>
                • Extensión modelada: <strong>{totalHectaresSimulated} hectáreas</strong> ({gridRows * cellSize / 1000} km × {gridCols * cellSize / 1000} km)
              </div>
            </div>
          </Card>
        </div>

        {/* Section 3: Parallel & Distributed Architecture Selection */}
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Server size={20} color="var(--gold)" />
              <span>3. Motor de Cómputo Paralelo (HPC)</span>
            </div>
          }
          subtitle="Seleccione el paradigma de aceleración: mono-hilo, memoria compartida, memoria distribuida o híbrido"
        >
          {/* Engine Selector Grid */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '1rem',
              marginBottom: '1.5rem',
            }}
          >
            {/* Sequential */}
            <div
              style={{
                border: `2px solid ${engine === 'secuencial' ? 'var(--navy)' : 'var(--border-color)'}`,
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
                background: engine === 'secuencial' ? '#f0f4f8' : 'var(--bg-card)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onClick={() => setEngine('secuencial')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <Cpu size={20} color="var(--engine-sec)" />
                <span style={{ fontWeight: 700, color: 'var(--navy)' }}>Secuencial</span>
              </div>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Mono-núcleo clásico C/C++. Línea base de referencia científica ($T_1$).
              </p>
            </div>

            {/* OpenMP */}
            <div
              style={{
                border: `2px solid ${engine === 'openmp' ? 'var(--agri-green)' : 'var(--border-color)'}`,
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
                background: engine === 'openmp' ? 'var(--soft-green)' : 'var(--bg-card)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onClick={() => setEngine('openmp')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <Layers size={20} color="var(--agri-green)" />
                <span style={{ fontWeight: 700, color: 'var(--agri-green-dark)' }}>OpenMP</span>
              </div>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Memoria compartida multihilo. Paralelización de bucles de balance hídrico.
              </p>
            </div>

            {/* MPI */}
            <div
              style={{
                border: `2px solid ${engine === 'mpi' ? 'var(--engine-mpi)' : 'var(--border-color)'}`,
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
                background: engine === 'mpi' ? '#f5f3ff' : 'var(--bg-card)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onClick={() => setEngine('mpi')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <Network size={20} color="var(--engine-mpi)" />
                <span style={{ fontWeight: 700, color: 'var(--engine-mpi)' }}>MPI Distribuido</span>
              </div>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Paso de mensajes en clúster. Descomposición de dominio 2D con intercambio de halos.
              </p>
            </div>

            {/* Hybrid */}
            <div
              style={{
                border: `2px solid ${engine === 'hibrido' ? 'var(--gold)' : 'var(--border-color)'}`,
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
                background: engine === 'hibrido' ? '#fefce8' : 'var(--bg-card)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onClick={() => setEngine('hibrido')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <Server size={20} color="var(--gold-dark)" />
                <span style={{ fontWeight: 700, color: 'var(--gold-dark)' }}>Híbrido (MPI + OMP)</span>
              </div>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Máximo rendimiento HPC: procesos MPI entre nodos con hilos OpenMP multinúcleo.
              </p>
            </div>
          </div>

          {/* Engine Parameters Controls */}
          {engine !== 'secuencial' && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '1rem',
                padding: '1.25rem',
                background: 'var(--bg-main)',
                borderRadius: 'var(--radius-md)',
                marginBottom: '1.5rem',
              }}
            >
              {(engine === 'openmp' || engine === 'hibrido') && (
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label" htmlFor="sim-threads">
                    Hilos OpenMP por Proceso
                  </label>
                  <select
                    id="sim-threads"
                    className="form-select"
                    value={openmpThreads}
                    onChange={(e) => setOpenmpThreads(Number(e.target.value))}
                  >
                    <option value={2}>2 hilos (dual core)</option>
                    <option value={4}>4 hilos (quad core)</option>
                    <option value={8}>8 hilos (octa core)</option>
                    <option value={16}>16 hilos (high-throughput)</option>
                  </select>
                </div>
              )}

              {(engine === 'mpi' || engine === 'hibrido') && (
                <>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label" htmlFor="sim-procs">
                      Procesos MPI (Ranks)
                    </label>
                    <select
                      id="sim-procs"
                      className="form-select"
                      value={mpiProcesses}
                      onChange={(e) => setMpiProcesses(Number(e.target.value))}
                    >
                      <option value={2}>2 procesos</option>
                      <option value={4}>4 procesos</option>
                      <option value={8}>8 procesos</option>
                      <option value={16}>16 procesos</option>
                    </select>
                  </div>

                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label" htmlFor="sim-nodes">
                      Nodos de Clúster Involucrados
                    </label>
                    <select
                      id="sim-nodes"
                      className="form-select"
                      value={nodesCount}
                      onChange={(e) => setNodesCount(Number(e.target.value))}
                    >
                      <option value={1}>1 nodo (local)</option>
                      <option value={2}>2 nodos (chaco-node-01..02)</option>
                      <option value={4}>4 nodos (chaco-node-01..04)</option>
                    </select>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Performance Projection Box */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '1.25rem 1.5rem',
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, var(--navy) 0%, var(--navy-dark) 100%)',
              color: '#ffffff',
              flexWrap: 'wrap',
              gap: '1rem',
            }}
          >
            <div>
              <div style={{ fontSize: '0.78rem', color: 'var(--gold)', textTransform: 'uppercase', fontWeight: 700 }}>
                Proyección de Rendimiento HPC
              </div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, marginTop: '0.2rem' }}>
                Tiempo Estimado: ~{est.estimatedTime}s{' '}
                <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 400 }}>
                  (vs {est.baseSequentialSeconds}s secuencial)
                </span>
              </div>
              <div style={{ fontSize: '0.8rem', color: '#cbd5e1', marginTop: '0.2rem' }}>
                Aceleración esperada: <strong>{est.speedup}×</strong> • Eficiencia paralela: <strong>{est.efficiency}%</strong>
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-lg"
              style={{
                background: 'var(--agri-green-light)',
                boxShadow: '0 4px 14px rgba(47, 107, 79, 0.4)',
              }}
            >
              <Play size={20} fill="#ffffff" />
              Lanzar Simulación HPC
            </button>
          </div>
        </Card>
      </form>
    </div>
  );
}
