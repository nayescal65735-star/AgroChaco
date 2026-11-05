import axios from 'axios';
import type { SystemHealthStatus } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 6000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const systemService = {
  async checkBackendHealth(): Promise<{ online: boolean; version?: string }> {
    try {
      const response = await apiClient.get('/api/health');
      if (response.data && response.data.estado === 'activo') {
        return { online: true, version: '1.0.0' };
      }
      return { online: false };
    } catch {
      // Intentar endpoint raíz si /api/health difiere
      try {
        const rootRes = await apiClient.get('/');
        if (rootRes.data && rootRes.data.proyecto === 'AgroChaco') {
          return { online: true, version: rootRes.data.version };
        }
      } catch {
        // En desarrollo frontend autónomo o sin backend activo
      }
      return { online: false };
    }
  },

  async checkDatabaseHealth(): Promise<{ connected: boolean; dbName?: string; version?: string }> {
    try {
      const response = await apiClient.get('/api/database/test');
      if (response.data && response.data.estado === 'conectado') {
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
      clusterNodes: 4,
      activeJobs: 1,
      databaseName: dbStatus.dbName || 'agrochaco_db',
      backendVersion: backendStatus.version || '1.0.0',
    };
  },
};
