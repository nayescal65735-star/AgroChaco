
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

/**
 * Convierte la respuesta del backend al formato utilizado
 * por el frontend, conservando las métricas y resultados.
 */
function mapBackendSimulation(
  data: BackendSimulation
): SimulationResult {
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

    // Métricas agronómicas
    currentDay: data.currentDay,
    averageCWSI: data.averageCWSI,
    soilMoistureFinalPercent: data.soilMoistureFinalPercent,
    yieldLossPercent: data.yieldLossPercent,
    estimatedYieldTnHa: data.estimatedYieldTnHa,
    nominalYieldTnHa: data.nominalYieldTnHa,
    waterDeficitMm: data.waterDeficitMm,

    // Métricas de rendimiento paralelo
    executionTimeSeconds: data.executionTimeSeconds,
    speedup: data.speedup,
    efficiency: data.efficiency,
    memoryUsageMb: data.memoryUsageMb,

    // Resultados detallados
    timelineData: data.timelineData ?? [],
    spatialGrid: data.spatialGrid ?? [],
    logs: data.logs ?? [],
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

  const [systemHealth, setSystemHealth] =
    useState<SystemHealthStatus>({
      backend: 'checking',
      database: 'checking',
      clusterNodes: 0,
      activeJobs: 0,
    });

  const activeSimulation =
    simulations.find((simulation) => simulation.id === activeSimulationId) ||
    null;

  const isExecutionActive = simulations.some(
    (simulation) => simulation.status === 'running'
  );

  // Mantener una simulación activa válida.
  useEffect(() => {
    if (
      activeSimulationId &&
      !simulations.some(
        (simulation) => simulation.id === activeSimulationId
      )
    ) {
      setActiveSimulationId(simulations[0]?.id || null);
    }
  }, [simulations, activeSimulationId]);

  // Cargar simulaciones desde el backend.
  const loadSimulations = useCallback(async () => {
    try {
      const response = await simulationService.list();

      const records = response.simulations.map(
        mapBackendSimulation
      );

      setSimulations(records);

      setActiveSimulationId((currentId) => {
        if (
          currentId &&
          records.some((simulation) => simulation.id === currentId)
        ) {
          return currentId;
        }

        return records[0]?.id || null;
      });
    } catch (error) {
      console.error(
        'No se pudieron cargar las simulaciones:',
        error
      );
    }
  }, []);

  // Consultar el estado del backend y la base de datos.
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

  // Carga inicial y actualización periódica del estado del sistema.
  useEffect(() => {
    loadSimulations();
    refreshSystemHealth();

    const interval = setInterval(
      refreshSystemHealth,
      30000
    );

    return () => clearInterval(interval);
  }, [loadSimulations, refreshSystemHealth]);

  // Crear una simulación.
  const createSimulation = async (
    config: Omit<SimulationConfig, 'id' | 'createdAt'>
  ): Promise<string> => {
    const response = await simulationService.create(config);

    const newSimulation = mapBackendSimulation(response);

    setSimulations((previous) => [
      newSimulation,
      ...previous.filter(
        (simulation) => simulation.id !== newSimulation.id
      ),
    ]);

    setActiveSimulationId(newSimulation.id);

    return newSimulation.id;
  };

  // Ejecutar una simulación utilizando el motor C++ del backend.
  const startExecution = async (id: string): Promise<void> => {
    try {
      const response = await simulationService.execute(id);

      const updatedSimulation = mapBackendSimulation(response);

      setSimulations((previous) => {
        const exists = previous.some(
          (simulation) => simulation.id === id
        );

        if (!exists) {
          return [updatedSimulation, ...previous];
        }

        return previous.map((simulation) =>
          simulation.id === id
            ? updatedSimulation
            : simulation
        );
      });

      setActiveSimulationId(id);
    } catch (error) {
      console.error(
        `Error al ejecutar la simulación ${id}:`,
        error
      );

      throw error;
    }
  };

  // La pausa todavía no está implementada en el backend.
  const stopExecution = (_id: string): void => {
    console.warn(
      'La pausa de simulaciones estará disponible cuando se integre el motor.'
    );
  };

  // Eliminar una simulación.
  const deleteSimulation = async (id: string): Promise<void> => {
    await simulationService.delete(id);

    setSimulations((previous) =>
      previous.filter((simulation) => simulation.id !== id)
    );

    setActiveSimulationId((currentId) =>
      currentId === id ? null : currentId
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
