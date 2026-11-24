import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSimulations } from '../context';
import { simulationService } from '../services/api';
import { SOIL_INFOS } from '../services/mockData';
import { Card } from '../components/common/Card';
import { StatCard } from '../components/common/StatCard';
import {
  formatEfficiency,
  formatSpeedup,
} from '../utils/performanceMetrics';
import type { SpatialCell, TimelineDataPoint } from '../types';
import {
  Droplets,
  Wheat,
  Activity,
  Layers,
  FileSpreadsheet,
  FileCode,
} from 'lucide-react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from 'recharts';

function descargarArchivo(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = filename;
  document.body.appendChild(enlace);

  try {
    enlace.click();
  } finally {
    document.body.removeChild(enlace);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

function mensajeErrorExportacion(error: unknown, formato: string): string {
  const detalle = error instanceof Error && error.message ? ` ${error.message}` : '';
  return `No se pudo exportar ${formato}. Verifique que la simulación exista y que el backend esté disponible.${detalle}`;
}

export function Results() {
  const { simulations, activeSimulation, setActiveSimulationId } = useSimulations();
  const navigate = useNavigate();
  const [selectedCell, setSelectedCell] = useState<SpatialCell | null>(null);
  const [exportando, setExportando] = useState<'json' | 'csv' | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const exportandoRef = useRef(false);

  const currentSim = activeSimulation || simulations[0];

  const soilInfo = currentSim
    ? SOIL_INFOS.find((soil) => soil.id === currentSim.config.soilType)
    : undefined;

  const peakStressPoint = currentSim?.timelineData.reduce<TimelineDataPoint | null>(
    (peak, point) => (!peak || point.cwsi > peak.cwsi ? point : peak),
    null
  );

  if (!currentSim) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
        <h2>No hay resultados disponibles</h2>
        <p style={{ color: 'var(--text-muted)' }}>Ejecute una simulación para visualizar resultados científicos.</p>
      </div>
    );
  }

  const performanceSubtext =
    currentSim.speedup === undefined
      ? 'Pendiente de ejecución'
      : currentSim.efficiency === undefined
        ? `Speedup: ${formatSpeedup(currentSim.speedup)} · eficiencia pendiente`
        : `Speedup: ${formatSpeedup(currentSim.speedup)} · Eficiencia: ${formatEfficiency(
            currentSim.efficiency,
            currentSim.speedup
          )}`;

  const handleExport = async (formato: 'json' | 'csv') => {
    if (exportandoRef.current || !currentSim) return;

    exportandoRef.current = true;
    setExportando(formato);
    setExportError(null);

    try {
      const resultado =
        formato === 'json'
          ? await simulationService.exportJson(currentSim.id)
          : await simulationService.exportCsv(currentSim.id);
      descargarArchivo(resultado.blob, resultado.filename);
    } catch (error) {
      setExportError(
        mensajeErrorExportacion(error, formato === 'json' ? 'el JSON' : 'el CSV')
      );
    } finally {
      exportandoRef.current = false;
      setExportando(null);
    }
  };

  const getCellColor = (cwsi: number) => {
    if (cwsi >= 0.7) return '#dc2626'; // Crítico
    if (cwsi >= 0.5) return '#ea580c'; // Severo
    if (cwsi >= 0.3) return '#d97706'; // Moderado
    return '#16a34a'; // Óptimo
  };

  return (
    <div>
      {/* Page Header & Selector */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Resultados &amp; Análisis Hidrológico</h1>
          <p className="page-description">
            Evaluación agronómica del déficit hídrico, impacto en rendimiento y balance hídrico temporal en el Chaco.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <select
            className="form-select"
            value={currentSim.id}
            onChange={(e) => setActiveSimulationId(e.target.value)}
            style={{ width: 'auto', fontWeight: 600 }}
          >
            {simulations.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id}: {s.config.name}
              </option>
            ))}
          </select>

          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={() => void handleExport('csv')}
            disabled={exportando !== null}
          >
            {exportando === 'csv' ? (
              'Exportando CSV...'
            ) : (
              <>
                <FileSpreadsheet size={16} />
                Exportar CSV
              </>
            )}
          </button>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={() => void handleExport('json')}
            disabled={exportando !== null}
          >
            {exportando === 'json' ? (
              'Exportando JSON...'
            ) : (
              <>
                <FileCode size={16} />
                Exportar JSON
              </>
            )}
          </button>
        </div>

        {exportError && (
          <div
            role="alert"
            style={{
              flexBasis: '100%',
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-sm)',
              background: '#fee2e2',
              color: '#991b1b',
              fontSize: '0.85rem',
            }}
          >
            {exportError}
          </div>
        )}
      </div>

      {/* KPI Cards of the Simulation */}
      <div className="stats-grid">
        <StatCard
          label="Rendimiento Estimado"
          value={currentSim.estimatedYieldTnHa != null ? `${currentSim.estimatedYieldTnHa.toFixed(2)} tn/ha` : 'Pendiente'}
          subtext={
            currentSim.yieldLossPercent != null
              ? `Pérdida del ${currentSim.yieldLossPercent.toFixed(1)}% vs potencial${
                  currentSim.nominalYieldTnHa != null
                    ? ` (${currentSim.nominalYieldTnHa} tn/ha)`
                    : ''
                }`
              : 'Requiere ejecutar el motor C++'
          }
          icon={<Wheat size={24} />}
          variant="danger"
        />
        <StatCard
          label="Déficit Hídrico Acumulado"
          value={currentSim.waterDeficitMm != null ? `${currentSim.waterDeficitMm.toFixed(1)} mm` : 'Pendiente'}
          subtext="Lámina de agua no satisfecha en ciclo"
          icon={<Droplets size={24} />}
          variant="agri"
        />
        <StatCard
          label="Estrés Hídrico Medio (CWSI)"
          value={currentSim.averageCWSI != null ? currentSim.averageCWSI.toFixed(3) : 'Pendiente'}
          subtext="Crop Water Stress Index promedio"
          icon={<Activity size={24} />}
          variant="gold"
        />
        <StatCard
          label="Tiempo de Cómputo HPC"
          value={currentSim.executionTimeSeconds != null ? `${currentSim.executionTimeSeconds.toFixed(3)}s` : 'Pendiente'}
          subtext={performanceSubtext}
          icon={<Layers size={24} />}
          variant="default"
        />
      </div>

      {/* Main Hydrological Timeline Chart */}
      <Card
        className="mb-6"
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Activity size={20} color="var(--agri-green)" />
            <span>Balance Hídrico Temporal FAO-56 (ETa vs ETc y Precipitación)</span>
          </div>
        }
        subtitle={`Evolución de evapotranspiración potencial vs real, humedad del suelo y lluvias durante los ${currentSim.config.simulationDays} días de cultivo`}
      >
        {currentSim.timelineData.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem 1rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-md)', margin: '1rem 0' }}>
            <Activity size={36} color="var(--text-muted)" style={{ marginBottom: '0.75rem' }} />
            <h3 style={{ fontSize: '1.05rem', color: 'var(--navy)', marginBottom: '0.5rem' }}>
              Sin datos temporales registrados
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', maxWidth: '500px', margin: '0 auto 1.25rem' }}>
              {currentSim.status === 'completed'
                ? 'Esta corrida no contiene puntos temporales detallados en su archivo de resultados.'
                : `Esta simulación se encuentra en estado "${currentSim.status}". Para visualizar la curva hidrológica diaria, inicie la ejecución con el motor C++.`}
            </p>
            {currentSim.status !== 'completed' && (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => {
                  setActiveSimulationId(currentSim.id);
                  navigate('/ejecucion');
                }}
              >
                Ir a Ejecutar Simulación
              </button>
            )}
          </div>
        ) : (
          <div style={{ height: '360px', width: '100%', marginTop: '0.5rem' }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={currentSim.timelineData} margin={{ top: 15, right: 20, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  dataKey="day"
                  label={{ value: 'Día desde la Siembra', position: 'insideBottom', offset: -10, fontSize: 12 }}
                />
                <YAxis
                  yAxisId="left"
                  label={{ value: 'Lámina (mm/día)', angle: -90, position: 'insideLeft', fontSize: 12 }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  domain={[0, 30]}
                  label={{ value: 'Humedad Suelo (%)', angle: 90, position: 'insideRight', fontSize: 12 }}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: '8px',
                    borderColor: '#cbd5e1',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                  }}
                />
                <Legend verticalAlign="top" height={36} />

                {/* Rain bars */}
                <Bar
                  yAxisId="left"
                  dataKey="precipitation"
                  name="Precipitación (mm)"
                  fill="#38bdf8"
                  barSize={8}
                  radius={[4, 4, 0, 0]}
                />

                {/* Potential ET line */}
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="etPotential"
                  name="ET Potencial ETc (mm)"
                  stroke="#d97706"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  dot={false}
                />

                {/* Actual ET area */}
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="etActual"
                  name="ET Real ETa (mm)"
                  stroke="var(--agri-green)"
                  fill="var(--agri-green-subtle)"
                  strokeWidth={2.5}
                />

                {/* Soil moisture line */}
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="soilMoisture"
                  name="Humedad del Suelo (%)"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={false}
                />

                {/* Reference line for Wilting Point */}
                {soilInfo && (
                  <ReferenceLine
                    yAxisId="right"
                    y={soilInfo.wiltingPoint}
                    label={{
                      value: `Punto de Marchitez (${soilInfo.wiltingPoint}%)`,
                      fill: '#dc2626',
                      fontSize: 11,
                    }}
                    stroke="#dc2626"
                    strokeDasharray="3 3"
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Phenological stages explanation bar */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '0.75rem',
            marginTop: '1.25rem',
            paddingTop: '1rem',
            borderTop: '1px solid var(--border-light)',
          }}
        >
          <div style={{ padding: '0.6rem 0.8rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-sm)' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700 }}>DÍAS 1 - 15</span>
            <div style={{ fontWeight: 700, fontSize: '0.82rem', color: 'var(--navy)' }}>Emergencia (VE-V2)</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Kc: 0.40 • Demanda baja</div>
          </div>
          <div style={{ padding: '0.6rem 0.8rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-sm)' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700 }}>DÍAS 16 - 45</span>
            <div style={{ fontWeight: 700, fontSize: '0.82rem', color: 'var(--navy)' }}>Vegetativo (V6-V12)</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Kc: 0.75 • Desarrollo radicular</div>
          </div>
          <div style={{ padding: '0.6rem 0.8rem', background: '#fee2e2', borderRadius: 'var(--radius-sm)' }}>
            <span style={{ fontSize: '0.72rem', color: '#991b1b', fontWeight: 700 }}>DÍAS 46 - 68 (CRÍTICO)</span>
            <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#991b1b' }}>Floración / Polinización (R1)</div>
            <div style={{ fontSize: '0.75rem', color: '#7f1d1d' }}>Kc: 1.20 • Máximo déficit</div>
          </div>
          <div style={{ padding: '0.6rem 0.8rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-sm)' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700 }}>DÍAS 69 - 95</span>
            <div style={{ fontWeight: 700, fontSize: '0.82rem', color: 'var(--navy)' }}>Llenado Grano (R2-R4)</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Kc: 1.05 • Peso de grano</div>
          </div>
          <div style={{ padding: '0.6rem 0.8rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-sm)' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700 }}>DÍAS 96 - 120</span>
            <div style={{ fontWeight: 700, fontSize: '0.82rem', color: 'var(--navy)' }}>Maduración (R6)</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Kc: 0.60 • Senescencia</div>
          </div>
        </div>

        <div style={{ marginTop: '0.85rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          Etapas y Kc de referencia del modelo; la serie mostrada arriba corresponde a la corrida seleccionada.
        </div>
      </Card>

      {/* Two Column Layout: Spatial Grid Heatmap & Agronomic Details */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))',
          gap: '1.5rem',
          marginTop: '1.5rem',
        }}
      >
        {/* Spatial Grid Heatmap of Parcel */}
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Layers size={20} color="var(--navy)" />
              <span>Distribución Espacial del Estrés en la Parcela</span>
            </div>
          }
          subtitle={`Malla de simulación bidimensional (${currentSim.spatialGrid.length} celdas en ${currentSim.config.zoneName})`}
        >
          <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Pase el cursor sobre las celdas para inspeccionar el punto espacial:
            </span>
            <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.72rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: 8, height: 8, background: '#16a34a', borderRadius: 2 }} /> Óptimo
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: 8, height: 8, background: '#d97706', borderRadius: 2 }} /> Moderado
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: 8, height: 8, background: '#dc2626', borderRadius: 2 }} /> Crítico
              </span>
            </div>
          </div>

          {currentSim.spatialGrid.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2.5rem 1rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-md)' }}>
              <Layers size={32} color="var(--text-muted)" style={{ marginBottom: '0.5rem' }} />
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                {currentSim.status === 'completed'
                  ? 'No hay matriz espacial 2D registrada para esta corrida.'
                  : 'La distribución espacial del estrés se calculará al ejecutar la simulación con el motor C++.'}
              </p>
            </div>
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(8, 1fr)',
                gap: '6px',
                padding: '12px',
                background: 'var(--bg-main)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-color)',
              }}
            >
              {currentSim.spatialGrid.map((cell, idx) => (
                <div
                  key={idx}
                  className="grid-cell"
                  style={{
                    backgroundColor: getCellColor(cell.cwsi),
                    height: '42px',
                  }}
                  onMouseEnter={() => setSelectedCell(cell)}
                >
                  {cell.cwsi.toFixed(2)}
                </div>
              ))}
            </div>
          )}

          {/* Cell inspector box */}
          <div
            style={{
              marginTop: '1rem',
              padding: '0.85rem',
              background: 'var(--soft-green)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.84rem',
              color: 'var(--agri-green-dark)',
            }}
          >
            {selectedCell ? (
              <div>
                <strong>Coordenadas Celda:</strong> X: {selectedCell.x}, Y: {selectedCell.y} •{' '}
                <strong>CWSI:</strong> {selectedCell.cwsi} •{' '}
                <strong>Humedad:</strong> {selectedCell.moisture}% •{' '}
                <strong>Riesgo:</strong> {selectedCell.riskLevel.toUpperCase()}
              </div>
            ) : (
              <div>Posicione el cursor sobre cualquier cuadrante para ver métricas micrometeorológicas.</div>
            )}
          </div>
        </Card>

        {/* Agronomic Technical Summary */}
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Wheat size={20} color="var(--agri-green)" />
              <span>Diagnóstico Agronómico del Chaco</span>
            </div>
          }
          subtitle="Indicadores calculados a partir de la corrida seleccionada; sin conclusiones prefijadas"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ padding: '0.85rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontWeight: 700, color: 'var(--navy)', fontSize: '0.9rem' }}>
                Período de mayor estrés
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
                {peakStressPoint
                  ? `Día ${peakStressPoint.day} (${peakStressPoint.phenologicalStage}): CWSI ${peakStressPoint.cwsi.toFixed(3)}, humedad del suelo ${peakStressPoint.soilMoisture.toFixed(1)}%.`
                  : 'No hay serie temporal registrada para identificar el pico de estrés.'}
              </p>
            </div>

            <div style={{ padding: '0.85rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontWeight: 700, color: 'var(--navy)', fontSize: '0.9rem' }}>
                Configuración evaluada ({currentSim.config.cornVariety})
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
                Suelo: {currentSim.config.soilType} · Escenario: {currentSim.config.droughtScenario} · Duración:{' '}
                {currentSim.config.simulationDays} días. Rendimiento estimado:{' '}
                {currentSim.estimatedYieldTnHa != null
                  ? `${currentSim.estimatedYieldTnHa.toFixed(2)} tn/ha`
                  : 'sin datos'}; pérdida:{' '}
                {currentSim.yieldLossPercent != null
                  ? `${currentSim.yieldLossPercent.toFixed(1)}%`
                  : 'sin datos'}.
              </p>
            </div>

            <div style={{ padding: '0.85rem', background: 'var(--bg-main)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontWeight: 700, color: 'var(--navy)', fontSize: '0.9rem' }}>
                Déficit registrado
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
                {currentSim.waterDeficitMm != null
                  ? `Déficit acumulado: ${currentSim.waterDeficitMm.toFixed(1)} mm. Cualquier recomendación de riego requiere validación agronómica adicional.`
                  : 'No hay déficit acumulado registrado; no se emiten recomendaciones de riego.'}
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
