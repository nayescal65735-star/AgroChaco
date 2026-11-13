import {
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';

import type {
  SimulationResult,
  SimulationConfig,
  SystemHealthStatus,
} from '../types';

import {
  systemService,
  simulationService,
  type BackendSimulation,
} from '../services/api';

import { SimulationContext } from './simulationContextDef';

function mapBackendSimulation(data: BackendSimulation): SimulationResult {
  return {
    id: data.id,
    config: {
      ...data.config,
      id: data.id,
      createdAt: data.createdAt,
    },
    status: data.status,
    progressPercent: data.progressPercent,
    createdAt: data.createdAt,
    completedAt: data.completedAt || undefined,

    // Estos datos se completarán cuando se integre el motor.
    timelineData: [],
    spatialGrid: [],
    logs: [],
  };
}

export function SimulationProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [simulations, setSimulations] = useState<SimulationResult[]>([]);
  const [activeSimulationId, setActiveSimulationId] =
    useState<string | null>(null);

  const [systemHealth, setSystemHealth] = useState<SystemHealthStatus>({
    backend: 'checking',
    database: 'checking',
    clusterNodes: 0,
    activeJobs: 0,
  });

  const activeSimulation =
    simulations.find((s) => s.id === activeSimulationId) || null;

  const isExecutionActive = simulations.some(
    (s) => s.status === 'running'
  );

  useEffect(() => {
    if (
      activeSimulationId &&
      !simulations.some((s) => s.id === activeSimulationId)
    ) {
      setActiveSimulationId(simulations[0]?.id || null);
    }
  }, [simulations, activeSimulationId]);

  const loadSimulations = useCallback(async () => {
    try {
      const response = await simulationService.list();

      const records = response.simulations.map(mapBackendSimulation);

      setSimulations(records);

      setActiveSimulationId((currentId) => {
        if (currentId && records.some((s) => s.id === currentId)) {
          return currentId;
        }

        return records[0]?.id || null;
      });
    } catch (error) {
      console.error('No se pudieron cargar las simulaciones:', error);
    }
  }, []);

  const refreshSystemHealth = useCallback(async () => {
    try {
      const status = await systemService.getFullSystemStatus();
      setSystemHealth(status);
    } catch {
      setSystemHealth({
        backend: 'offline',
        database: 'disconnected',
        clusterNodes: 0,
        activeJobs: 0,
      });
    }
  }, []);

  useEffect(() => {
    loadSimulations();
    refreshSystemHealth();

    const interval = setInterval(refreshSystemHealth, 30000);

    return () => clearInterval(interval);
  }, [loadSimulations, refreshSystemHealth]);

  const createSimulation = async (
    config: Omit<SimulationConfig, 'id' | 'createdAt'>
  ): Promise<string> => {
    const response = await simulationService.create(config);
    const newSimulation = mapBackendSimulation(response);

    setSimulations((previous) => [
      newSimulation,
      ...previous.filter((s) => s.id !== newSimulation.id),
    ]);

    setActiveSimulationId(newSimulation.id);

    return newSimulation.id;
  };

  const startExecution = async (id: string): Promise<void> => {
    const response = await simulationService.execute(id);
    const updatedSimulation = mapBackendSimulation(response);

    setSimulations((previous) =>
      previous.map((s) =>
        s.id === id ? updatedSimulation : s
      )
    );
  };

  const stopExecution = (_id: string): void => {
    console.warn(
      'La pausa de simulaciones estará disponible cuando se integre el motor.'
    );
  };

  const deleteSimulation = async (id: string): Promise<void> => {
    await simulationService.delete(id);

    setSimulations((previous) =>
      previous.filter((s) => s.id !== id)
    );
  };

  return (
    <SimulationContext.Provider
      value={{
        simulations,
        activeSimulation,
        activeSimulationId,
        setActiveSimulationId,
        createSimulation,
        startExecution,
        stopExecution,
        deleteSimulation,
        systemHealth,
        refreshSystemHealth,
        isExecutionActive,
      }}
    >
      {children}
    </SimulationContext.Provider>
  );
}
