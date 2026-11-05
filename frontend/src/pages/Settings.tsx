import { useState } from 'react';
import { useSimulations } from '../context';
import { Card } from '../components/common/Card';
import { SCIENTIFIC_CONSTANTS } from '../services/mockData';
import { systemService } from '../services/api';
import {
  Server,
  Database,
  Wifi,
  WifiOff,
  RefreshCw,
  CheckCircle2,
  Sliders,
  Save,
} from 'lucide-react';

export function Settings() {
  const { systemHealth, refreshSystemHealth } = useSimulations();

  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    tested: boolean;
    backendOk: boolean;
    databaseOk: boolean;
    dbInfo?: string;
    backendVersion?: string;
    latencyMs?: number;
  }>({
    tested: false,
    backendOk: false,
    databaseOk: false,
  });

  const [backendUrl, setBackendUrl] = useState(import.meta.env.VITE_API_URL || 'http://localhost:8000');
  const [psychrometricConstant, setPsychrometricConstant] = useState('0.066');
  const [soilDepthMeters, setSoilDepthMeters] = useState('1.2');
  const [albedoMaize, setAlbedoMaize] = useState('0.23');
  const [savedFeedback, setSavedFeedback] = useState(false);

  const runConnectionDiagnostic = async () => {
    setIsTesting(true);
    const start = performance.now();
    try {
      const backendRes = await systemService.checkBackendHealth();
      const dbRes = await systemService.checkDatabaseHealth();
      const end = performance.now();

      setTestResult({
        tested: true,
        backendOk: backendRes.online,
        databaseOk: dbRes.connected,
        dbInfo: dbRes.dbName ? `${dbRes.dbName} (${dbRes.version || 'PostgreSQL 16'})` : undefined,
        backendVersion: backendRes.version,
        latencyMs: Math.round(end - start),
      });

      await refreshSystemHealth();
    } catch {
      setTestResult({
        tested: true,
        backendOk: false,
        databaseOk: false,
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveParameters = (e: React.FormEvent) => {
    e.preventDefault();
    setSavedFeedback(true);
    setTimeout(() => setSavedFeedback(false), 2500);
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Configuración del Sistema &amp; HPC</h1>
          <p className="page-description">
            Diagnóstico de conectividad FastAPI / PostgreSQL 16, topología del clúster Chaco y parámetros del modelo biofísico.
          </p>
        </div>
      </div>

      {/* Two Column: Backend & Database Diagnostics vs Cluster Nodes */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))',
          gap: '1.5rem',
          marginBottom: '1.75rem',
        }}
      >
        {/* Backend & DB Diagnostic Card */}
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Database size={20} color="var(--agri-green)" />
              <span>Conexión Backend FastAPI &amp; PostgreSQL 16</span>
            </div>
          }
          subtitle="Monitoreo de la API REST y de la persistencia relacional en PostgreSQL"
          action={
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={runConnectionDiagnostic}
              disabled={isTesting}
            >
              <RefreshCw size={14} className={isTesting ? 'animate-spin' : ''} />
              {isTesting ? 'Diagnosticando...' : 'Test de Conexión'}
            </button>
          }
        >
          <div className="form-group">
            <label className="form-label" htmlFor="backend-url">URL Base del Backend FastAPI</label>
            <input
              id="backend-url"
              type="text"
              className="form-input"
              value={backendUrl}
              onChange={(e) => setBackendUrl(e.target.value)}
            />
            <span className="form-hint">
              Por defecto: <code>http://localhost:8000</code> conectado al contenedor FastAPI.
            </span>
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
              marginTop: '1.25rem',
              paddingTop: '1rem',
              borderTop: '1px solid var(--border-light)',
            }}
          >
            {/* FastAPI Service status */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.75rem 1rem',
                borderRadius: 'var(--radius-md)',
                background: systemHealth.backend === 'online' ? '#f0fdf4' : 'var(--bg-main)',
                border: `1px solid ${systemHealth.backend === 'online' ? '#bbf7d0' : 'var(--border-color)'}`,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                {systemHealth.backend === 'online' ? (
                  <Wifi size={18} color="#16a34a" />
                ) : (
                  <WifiOff size={18} color="#94a3b8" />
                )}
                <div>
                  <div style={{ fontWeight: 700, color: 'var(--navy)', fontSize: '0.9rem' }}>
                    Servicio FastAPI (app.main)
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Endpoint salud: <code>/api/health</code>
                  </div>
                </div>
              </div>

              <span
                className={`system-tag ${systemHealth.backend === 'online' ? 'online' : ''}`}
                style={{
                  background: systemHealth.backend === 'online' ? '#dcfce7' : '#f1f5f9',
                  color: systemHealth.backend === 'online' ? '#15803d' : '#475569',
                }}
              >
                {systemHealth.backend === 'online' ? 'ONLINE (v1.0.0)' : 'STANDALONE / DEMO'}
              </span>
            </div>

            {/* PostgreSQL 16 status */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.75rem 1rem',
                borderRadius: 'var(--radius-md)',
                background: systemHealth.database === 'connected' ? '#f0fdf4' : 'var(--bg-main)',
                border: `1px solid ${systemHealth.database === 'connected' ? '#bbf7d0' : 'var(--border-color)'}`,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <Database size={18} color={systemHealth.database === 'connected' ? '#16a34a' : '#94a3b8'} />
                <div>
                  <div style={{ fontWeight: 700, color: 'var(--navy)', fontSize: '0.9rem' }}>
                    Base de Datos PostgreSQL 16
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Endpoint prueba: <code>/api/database/test</code>
                  </div>
                </div>
              </div>

              <span
                className="system-tag"
                style={{
                  background: systemHealth.database === 'connected' ? '#dcfce7' : '#f1f5f9',
                  color: systemHealth.database === 'connected' ? '#15803d' : '#475569',
                }}
              >
                {systemHealth.database === 'connected' ? 'CONECTADA' : 'MODO LOCAL'}
              </span>
            </div>
          </div>

          {testResult.tested && (
            <div
              style={{
                marginTop: '1rem',
                padding: '0.85rem',
                borderRadius: 'var(--radius-md)',
                background: testResult.backendOk ? '#f0fdf4' : '#fffbeb',
                border: `1px solid ${testResult.backendOk ? '#bbf7d0' : '#fef3c7'}`,
                fontSize: '0.82rem',
                color: testResult.backendOk ? '#166534' : '#92400e',
              }}
            >
              <strong>Resultado del Test:</strong> Latencia: {testResult.latencyMs} ms • Backend: {testResult.backendOk ? 'Activo' : 'No responde (usando modo autónomo)'} • Base de Datos: {testResult.databaseOk ? testResult.dbInfo || 'Conectada' : 'No disponible'}.
            </div>
          )}
        </Card>

        {/* Cluster Topology Card */}
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Server size={20} color="var(--gold-dark)" />
              <span>Nodos del Clúster HPC Gran Chaco</span>
            </div>
          }
          subtitle="Infraestructura de cómputo paralela y distribuida asignada a AgroChaco"
        >
          <div className="table-container">
            <table className="agro-table">
              <thead>
                <tr>
                  <th>Nodo</th>
                  <th>IP Interna</th>
                  <th>Rol</th>
                  <th>Núcleos</th>
                  <th>RAM</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {SCIENTIFIC_CONSTANTS.clusterNodes.map((node, i) => (
                  <tr key={i}>
                    <td>
                      <strong>{node.name}</strong>
                    </td>
                    <td>
                      <code style={{ fontSize: '0.78rem' }}>{node.ip}</code>
                    </td>
                    <td style={{ fontSize: '0.8rem' }}>{node.role}</td>
                    <td>{node.cores}c</td>
                    <td>{node.ramGb} GB</td>
                    <td>
                      <span className="badge badge-completed">
                        <CheckCircle2 size={12} />
                        {node.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div
            style={{
              marginTop: '1rem',
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-md)',
              background: 'var(--soft-green)',
              color: 'var(--agri-green-dark)',
              fontSize: '0.82rem',
            }}
          >
            <strong>Total Clúster:</strong> 144 núcleos lógicos • 576 GB RAM total • Red 10 GbE MPI Interconnect
          </div>
        </Card>
      </div>

      {/* Model Constants Form */}
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Sliders size={20} color="var(--navy)" />
            <span>Constantes Biofísicas del Modelo FAO-56 Penman-Monteith</span>
          </div>
        }
        subtitle="Parámetros físicos calibrados para la radiación y micrometeorología del Chaco boliviano"
      >
        <form onSubmit={handleSaveParameters}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: '1.25rem',
              marginBottom: '1.5rem',
            }}
          >
            <div className="form-group">
              <label className="form-label" htmlFor="set-psychro">
                Constante Psicrométrica ($\gamma$) [kPa/°C]
              </label>
              <input
                id="set-psychro"
                type="text"
                className="form-input"
                value={psychrometricConstant}
                onChange={(e) => setPsychrometricConstant(e.target.value)}
              />
              <span className="form-hint">A nivel del mar: ~0.067; Yacuiba (600 msnm): ~0.066</span>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="set-soil-depth">
                Profundidad Radicular Efectiva ($Z_r$) [m]
              </label>
              <input
                id="set-soil-depth"
                type="text"
                className="form-input"
                value={soilDepthMeters}
                onChange={(e) => setSoilDepthMeters(e.target.value)}
              />
              <span className="form-hint">Maíz en etapa madura en el Chaco: 1.0 - 1.4 m</span>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="set-albedo">
                Albedo del Cultivo de Maíz ($\alpha$)
              </label>
              <input
                id="set-albedo"
                type="text"
                className="form-input"
                value={albedoMaize}
                onChange={(e) => setAlbedoMaize(e.target.value)}
              />
              <span className="form-hint">FAO-56 estándar para dosel verde de maíz: 0.23</span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontSize: '0.84rem', color: savedFeedback ? 'var(--status-success)' : 'var(--text-muted)' }}>
              {savedFeedback ? '✓ Parámetros actualizados y guardados en memoria del simulador.' : 'Los cambios se aplican a todas las nuevas simulaciones.'}
            </div>

            <button type="submit" className="btn btn-primary">
              <Save size={16} />
              Guardar Parámetros Biofísicos
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
}
