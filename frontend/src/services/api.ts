
import axios from 'axios';
import type {
  SystemHealthStatus,
  SimulationConfig,
  SimulationStatus,
  TimelineDataPoint,
  WaterBalanceSummary,
  SpatialCell,
  SimulationLog,
  SimulationJob,
  ExecuteSimulationResponse,
} from '../types';

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
const intervaloConfigurado = Number(import.meta.env.VITE_JOB_POLL_INTERVAL_MS);

export const JOB_POLL_INTERVAL_MS =
  Number.isFinite(intervaloConfigurado) && intervaloConfigurado >= 250
    ? intervaloConfigurado
    : 2000;

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Estructura real devuelta por FastAPI
export interface BackendSimulation {
  id: string;
  config: Omit<SimulationConfig, 'id' | 'createdAt'>;
  status: SimulationStatus;
  progressPercent: number;
  createdAt: string;
  completedAt: string | null;

  currentDay?: number;
  executionTimeSeconds?: number;
  speedup?: number | null;
  efficiency?: number | null;
  averageCWSI?: number;
  soilMoistureFinalPercent?: number;
  yieldLossPercent?: number;
  estimatedYieldTnHa?: number;
  nominalYieldTnHa?: number;
  waterDeficitMm?: number;
  memoryUsageMb?: number;
  waterBalanceSummary?: WaterBalanceSummary | null;

  timelineData?: TimelineDataPoint[];
  spatialGrid?: SpatialCell[];
  logs?: SimulationLog[];
}

export interface SimulationListResponse {
  total: number;
  simulations: BackendSimulation[];
}

export interface SimulationExport {
  blob: Blob;
  filename: string;
}

function nombreArchivoSeguro(simulationId: string, extension: string): string {
  const seguro =
    simulationId.replace(/[^A-Za-z0-9_-]/g, '_') || 'simulacion';
  return `${seguro}.${extension}`;
}

function nombreArchivoDesdeHeader(
  contentDisposition: unknown,
  fallback: string
): string {
  const cabecera =
    typeof contentDisposition === 'string' ? contentDisposition : '';
  const coincidencia = cabecera.match(/filename="?([^";]+)"?/i);
  const candidato = coincidencia?.[1]?.trim().split(/[/\\]/).pop();
  return candidato || fallback;
}

export function mensajeErrorApi(error: unknown, fallback: string): string {
  if (error && typeof error === 'object') {
    const datos = error as {
      response?: { data?: { detail?: unknown } };
      message?: unknown;
    };
    const detalle = datos.response?.data?.detail;
    if (typeof detalle === 'string' && detalle.trim()) {
      return detalle;
    }
    if (typeof datos.message === 'string' && datos.message.trim()) {
      return datos.message;
    }
  }
  return fallback;
}

async function obtenerExportacion(
  url: string,
  simulationId: string,
  extension: string
): Promise<SimulationExport> {
  const response = await apiClient.get<Blob>(url, { responseType: 'blob' });
  const fallback = nombreArchivoSeguro(simulationId, extension);

  return {
    blob: response.data,
    filename: nombreArchivoDesdeHeader(
      response.headers['content-disposition'],
      fallback
    ),
  };
}

export const systemService = {
  async checkBackendHealth(): Promise<{ online: boolean; version?: string }> {
    try {
      const response = await apiClient.get('/api/health');

      if (response.data?.estado === 'activo') {
        return { online: true, version: '1.0.0' };
      }

      return { online: false };
    } catch {
      return { online: false };
    }
  },

  async checkDatabaseHealth(): Promise<{
    connected: boolean;
    dbName?: string;
    version?: string;
  }> {
    try {
      const response = await apiClient.get('/api/database/test');

      if (response.data?.estado === 'conectado') {
        return {
          connected: true,
          dbName: response.data.base_datos,
          version: response.data.version,
        };
      }

      return { connected: false };
    } catch {
      return { connected: false };
    }
  },

  async getFullSystemStatus(): Promise<SystemHealthStatus> {
    const backendStatus = await this.checkBackendHealth();
    const dbStatus = await this.checkDatabaseHealth();

    return {
      backend: backendStatus.online ? 'online' : 'offline',
      database: dbStatus.connected ? 'connected' : 'disconnected',
      clusterNodes: 0,
      activeJobs: 0,
      databaseName: dbStatus.dbName || 'agrochaco_db',
      backendVersion: backendStatus.version || '1.0.0',
    };
  },
};

// Operaciones de simulaciones en FastAPI
export const simulationService = {
  async create(
    config: Omit<SimulationConfig, 'id' | 'createdAt'>
  ): Promise<BackendSimulation> {
    const response = await apiClient.post<BackendSimulation>(
      '/api/simulations',
      config
    );

    return response.data;
  },

  async list(): Promise<SimulationListResponse> {
    const response = await apiClient.get<SimulationListResponse>(
      '/api/simulations'
    );

    return response.data;
  },

  async getById(id: string): Promise<BackendSimulation> {
    const response = await apiClient.get<BackendSimulation>(
      `/api/simulations/${id}`
    );

    return response.data;
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(`/api/simulations/${id}`);
  },

  async execute(id: string): Promise<ExecuteSimulationResponse> {
    const response = await apiClient.post<ExecuteSimulationResponse>(
      `/api/simulations/${encodeURIComponent(id)}/execute`,
      {},
      { timeout: 15000 }
    );

    if (response.status !== 202) {
      throw new Error('El backend no aceptó la solicitud de ejecución asíncrona.');
    }
    if (!response.data?.job_id) {
      throw new Error('El backend no devolvió el identificador del trabajo.');
    }

    return response.data;
  },

  async getJob(jobId: string): Promise<SimulationJob> {
    const response = await apiClient.get<SimulationJob>(
      `/api/jobs/${encodeURIComponent(jobId)}`
    );

    if (!response.data?.job_id) {
      throw new Error('El backend devolvió un estado de trabajo inválido.');
    }

    return response.data;
  },

  async cancelJob(jobId: string): Promise<SimulationJob> {
    const response = await apiClient.post<SimulationJob>(
      `/api/jobs/${encodeURIComponent(jobId)}/cancel`,
      {},
      { timeout: 15000 }
    );

    if (!response.data?.job_id) {
      throw new Error('El backend no confirmó la cancelación del trabajo.');
    }

    return response.data;
  },

  async exportJson(id: string): Promise<SimulationExport> {
    return obtenerExportacion(
      `/api/simulations/${encodeURIComponent(id)}/export/json`,
      id,
      'json'
    );
  },

  async exportCsv(id: string): Promise<SimulationExport> {
    return obtenerExportacion(
      `/api/simulations/${encodeURIComponent(id)}/export/csv`,
      id,
      'csv'
    );
  },
};
