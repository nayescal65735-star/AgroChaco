import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSimulations } from '../context';
import { Card } from '../components/common/Card';
import { StatusBadge } from '../components/common/StatusBadge';
import { EngineBadge } from '../components/common/EngineBadge';
import type { SimulationResult } from '../types';
import {
  History as HistoryIcon,
  Search,
  Eye,
  Trash2,
  RotateCcw,
  MapPin,
  ArrowRight,
  X,
} from 'lucide-react';

export function History() {
  const { simulations, setActiveSimulationId, deleteSimulation, startExecution } = useSimulations();
  const navigate = useNavigate();

  const [searchTerm, setSearchTerm] = useState('');
  const [selectedZone, setSelectedZone] = useState<string>('all');
  const [selectedEngine, setSelectedEngine] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [inspectSim, setInspectSim] = useState<SimulationResult | null>(null);

  const filteredSimulations = simulations.filter((sim) => {
    const matchesSearch =
      sim.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      sim.config.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      sim.config.zoneName.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesZone = selectedZone === 'all' || sim.config.zone === selectedZone;
    const matchesEngine = selectedEngine === 'all' || sim.config.engine === selectedEngine;
    const matchesStatus = selectedStatus === 'all' || sim.status === selectedStatus;

    return matchesSearch && matchesZone && matchesEngine && matchesStatus;
  });

  const handleInspect = (sim: SimulationResult) => {
    setInspectSim(sim);
  };

  const handleOpenResults = (id: string) => {
    setActiveSimulationId(id);
    navigate('/resultados');
  };

  const handleRerun = (id: string) => {
    startExecution(id);
    setActiveSimulationId(id);
    navigate('/ejecucion');
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Historial de Corridas Científicas</h1>
          <p className="page-description">
            Registro auditable de simulaciones numéricas, parámetros de configuración y registros de ejecución HPC.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={() => navigate('/nueva-simulacion')}
        >
          Nueva Simulación
        </button>
      </div>

      {/* Filter and Search Bar */}
      <Card className="mb-6">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '1rem',
          }}
        >
          {/* Search box */}
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" htmlFor="hist-search">Buscar por ID, nombre o municipio</label>
            <div style={{ position: 'relative' }}>
              <input
                id="hist-search"
                type="text"
                className="form-input"
                placeholder="Ej. SIM-GC, Villa Montes, Criollo..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ paddingLeft: '2.4rem' }}
              />
              <Search
                size={16}
                color="var(--text-muted)"
                style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)' }}
              />
            </div>
          </div>

          {/* Zone filter */}
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" htmlFor="hist-zone">Zona Chaqueña</label>
            <select
              id="hist-zone"
              className="form-select"
              value={selectedZone}
              onChange={(e) => setSelectedZone(e.target.value)}
            >
              <option value="all">Todas las zonas</option>
              <option value="yacuiba">Yacuiba (Tarija)</option>
              <option value="villamontes">Villa Montes (Tarija)</option>
              <option value="carapari">Caraparí (Tarija)</option>
              <option value="charagua">Charagua (Santa Cruz)</option>
              <option value="machareti">Macharetí (Chuquisaca)</option>
              <option value="boyuibe">Boyuibe (Santa Cruz)</option>
            </select>
          </div>

          {/* Engine filter */}
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" htmlFor="hist-engine">Motor Paralelo</label>
            <select
              id="hist-engine"
              className="form-select"
              value={selectedEngine}
              onChange={(e) => setSelectedEngine(e.target.value)}
            >
              <option value="all">Todos los motores</option>
              <option value="secuencial">Secuencial</option>
              <option value="openmp">OpenMP</option>
              <option value="mpi">MPI Distribuido</option>
              <option value="hibrido">Híbrido (MPI + OMP)</option>
            </select>
          </div>

          {/* Status filter */}
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" htmlFor="hist-status">Estado de Corrida</label>
            <select
              id="hist-status"
              className="form-select"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
            >
              <option value="all">Todos los estados</option>
              <option value="completed">Completadas</option>
              <option value="running">En ejecución</option>
              <option value="pending">En cola</option>
              <option value="paused">Pausadas</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Simulations Table */}
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <HistoryIcon size={20} color="var(--navy)" />
            <span>Registro de Simulaciones ({filteredSimulations.length})</span>
          </div>
        }
      >
        {filteredSimulations.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
            No se encontraron simulaciones que coincidan con los filtros aplicados.
          </div>
        ) : (
          <div className="table-container">
            <table className="agro-table">
              <thead>
                <tr>
                  <th>Código / Identificador</th>
                  <th>Municipio</th>
                  <th>Variedad &amp; Suelo</th>
                  <th>Motor HPC</th>
                  <th>Estado</th>
                  <th>Tiempo</th>
                  <th>Speedup</th>
                  <th>Fecha</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {filteredSimulations.map((sim) => (
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
                        <span style={{ fontWeight: 600 }}>{sim.config.zoneName}</span>
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        {sim.config.department}
                      </div>
                    </td>
                    <td>
                      <div style={{ fontSize: '0.82rem', fontWeight: 600 }}>{sim.config.cornVariety}</div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        {sim.config.soilType}
                      </div>
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
                      <div style={{ fontWeight: 700 }}>{sim.executionTimeSeconds}s</div>
                    </td>
                    <td>
                      <span style={{ fontWeight: 700, color: 'var(--agri-green)' }}>
                        {sim.speedup}×
                      </span>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                        {sim.createdAt}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <button
                          type="button"
                          className="btn btn-outline btn-sm"
                          onClick={() => handleInspect(sim)}
                          title="Inspeccionar configuración y logs"
                        >
                          <Eye size={14} />
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleOpenResults(sim.id)}
                          title="Ver resultados y gráficos"
                        >
                          <ArrowRight size={14} />
                        </button>
                        <button
                          type="button"
                          className="btn btn-outline btn-sm"
                          onClick={() => handleRerun(sim.id)}
                          title="Re-ejecutar corrida"
                        >
                          <RotateCcw size={14} />
                        </button>
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          onClick={() => deleteSimulation(sim.id)}
                          title="Eliminar registro"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Inspect Simulation Modal / Drawer */}
      {inspectSim && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(19, 36, 28, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1.5rem',
            backdropFilter: 'blur(3px)',
          }}
          onClick={() => setInspectSim(null)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '750px',
              maxHeight: '85vh',
              overflowY: 'auto',
              background: '#ffffff',
              borderRadius: 'var(--radius-lg)',
              boxShadow: 'var(--shadow-lg)',
              padding: '1.75rem',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <div>
                <h2 style={{ fontSize: '1.3rem', color: 'var(--navy)' }}>
                  Detalle de Corrida: {inspectSim.id}
                </h2>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  {inspectSim.config.name}
                </p>
              </div>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => setInspectSim(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '1rem',
                marginBottom: '1.5rem',
                padding: '1rem',
                background: 'var(--bg-main)',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <div>
                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>MUNICIPIO / ZONA</span>
                <div style={{ fontWeight: 700 }}>{inspectSim.config.zoneName} ({inspectSim.config.department})</div>
              </div>
              <div>
                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>GRILLA COMPUTACIONAL</span>
                <div style={{ fontWeight: 700 }}>
                  {inspectSim.config.gridConfig.rows} × {inspectSim.config.gridConfig.cols} celdas ({inspectSim.config.gridConfig.cellSizeMeters}m)
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>ARQUITECTURA PARALELA</span>
                <div>
                  <EngineBadge engine={inspectSim.config.engine} threads={inspectSim.config.openmpThreads} processes={inspectSim.config.mpiProcesses} />
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>ESCENARIO CLIMÁTICO</span>
                <div style={{ fontWeight: 700 }}>{inspectSim.config.droughtScenario}</div>
              </div>
            </div>

            <h3 style={{ fontSize: '1rem', color: 'var(--navy)', marginBottom: '0.65rem' }}>
              Logs de Ejecución &amp; Paso de Mensajes
            </h3>
            <div className="terminal-window" style={{ maxHeight: '220px', marginBottom: '1.5rem' }}>
              {inspectSim.logs.map((l, i) => (
                <div key={i} className="terminal-line">
                  <span className="terminal-time">[{l.timestamp}]</span>
                  <span className={`terminal-tag ${l.level}`}>[{l.level}]</span>
                  <span className="terminal-msg">{l.message}</span>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setInspectSim(null)}
              >
                Cerrar
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  setActiveSimulationId(inspectSim.id);
                  navigate('/resultados');
                }}
              >
                Abrir en Resultados
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
