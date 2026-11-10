import axios from 'axios';
import type {
  SystemHealthStatus,
  SimulationConfig,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Estructura que devuelve FastAPI
export interface BackendSimulation {
  id: string;
  config: Omit<SimulationConfig, 'id' | 'createdAt'>;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused';
  progressPercent: number;
  createdAt: string;
  completedAt: string | null;
}

export interface SimulationListResponse {
  total: number;
  simulations: BackendSimulation[];
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

// Operaciones reales de simulaciones en FastAPI
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

  async execute(id: string): Promise<BackendSimulation> {
    const response = await apiClient.post<BackendSimulation>(
      `/api/simulations/${id}/execute`
    );

    return response.data;
  },
};
