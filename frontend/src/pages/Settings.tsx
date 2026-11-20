import { useState } from 'react';
import { useSimulations } from '../context';
import { Card } from '../components/common/Card';
import { systemService } from '../services/api';
import {
  Server,
  Database,
  Wifi,
  WifiOff,
  RefreshCw,
  Sliders,
} from 'lucide-react';

export function Settings() {
  const { systemHealth, refreshSystemHealth } = useSimulations();

  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    tested: boolean;
    backendOk: boolean;
    databaseOk: boolean;
    dbInfo?: string;
    latencyMs?: number;
  }>({
    tested: false,
    backendOk: false,
    databaseOk: false,
  });

  const validatedEnvironment = [
    { componente: 'Procesador', valor: 'Intel Core i7-13700' },
    { componente: 'CPU lógicas', valor: '24' },
    { componente: 'Memoria instalada', valor: '32 GiB de RAM' },
    { componente: 'Sistema operativo', valor: 'Ubuntu 24.04' },
    { componente: 'MPI', valor: 'Ejecutado en una única máquina física' },
    { componente: 'OpenMP', valor: 'Memoria compartida' },
  ];

  const configuredBackendUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001';
  const psychrometricConstant = '0.066';
  const soilDepthMeters = '1.2';
  const albedoMaize = '0.23';

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
        dbInfo: dbRes.dbName ? `${dbRes.dbName} (${dbRes.version || 'PostgreSQL'})` : undefined,
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

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Configuración del Sistema &amp; HPC</h1>
          <p className="page-description">
            Diagnóstico de conectividad FastAPI / PostgreSQL, entorno de ejecución validado y constantes de referencia del modelo biofísico.
          </p>
        </div>
      </div>

      {/* Two Column: Backend & Database Diagnostics vs Validated Environment */}
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
              <span>Conexión Backend FastAPI &amp; PostgreSQL</span>
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
              value={configuredBackendUrl}
              readOnly
            />
            <span className="form-hint">
              Configurado mediante <code>VITE_API_URL</code> al compilar; este campo no modifica la conexión en caliente.
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
                {systemHealth.backend === 'online' ? 'ONLINE' : 'SIN CONEXIÓN'}
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
                    Base de Datos PostgreSQL
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
                {systemHealth.database === 'connected' ? 'CONECTADA' : 'NO DISPONIBLE'}
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
              <strong>Resultado del Test:</strong> Latencia: {testResult.latencyMs} ms • Backend: {testResult.backendOk ? 'Activo' : 'No responde'} • Base de Datos: {testResult.databaseOk ? testResult.dbInfo || 'Conectada' : 'No disponible'}.
            </div>
          )}
        </Card>

        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Server size={20} color="var(--gold-dark)" />
              <span>Entorno de ejecución validado</span>
            </div>
          }
          subtitle="Equipo donde se realizaron los experimentos; valores estáticos, no telemetría dinámica"
        >
          <div className="table-container">
            <table className="agro-table">
              <thead>
                <tr>
                  <th>Componente</th>
                  <th>Configuración verificada</th>
                </tr>
              </thead>
              <tbody>
                {validatedEnvironment.map((item) => (
                  <tr key={item.componente}>
                    <td>
                      <strong>{item.componente}</strong>
                    </td>
                    <td style={{ fontSize: '0.85rem' }}>{item.valor}</td>
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
            <strong>Alcance:</strong> describe el entorno de los experimentos disponibles; no se actualiza desde ningún endpoint.
          </div>
        </Card>
      </div>

      {/* Model Constants Reference */}
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Sliders size={20} color="var(--navy)" />
            <span>Constantes Biofísicas del Modelo FAO-56 Penman-Monteith</span>
          </div>
        }
        subtitle="Valores de referencia: no se envían al backend ni se aplican a las simulaciones"
      >
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
              readOnly
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
              readOnly
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
              readOnly
            />
            <span className="form-hint">FAO-56 estándar para dosel verde de maíz: 0.23</span>
          </div>
        </div>

        <div
          style={{
            padding: '0.85rem 1rem',
            borderRadius: 'var(--radius-md)',
            background: '#fffbeb',
            border: '1px solid #fef3c7',
            fontSize: '0.84rem',
            color: '#92400e',
          }}
        >
          No existe un endpoint para persistir estas constantes. La API actual no las aplica a nuevas simulaciones.
        </div>
      </Card>
    </div>
  );
}
