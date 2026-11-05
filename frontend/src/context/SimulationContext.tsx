import { useState, useEffect, useCallback, type ReactNode } from 'react';
import type {
  SimulationResult,
  SimulationConfig,
  SystemHealthStatus,
  SimulationLog,
} from '../types';
import {
  INITIAL_SIMULATIONS,
  generateMockTimeline,
  generateMockSpatialGrid,
  CORN_VARIETIES,
} from '../services/mockData';
import { systemService } from '../services/api';
import { SimulationContext } from './simulationContextDef';

const SIM_STORAGE_KEY = 'agrochaco_simulations_v1';

export function SimulationProvider({ children }: { children: ReactNode }) {
  const [simulations, setSimulations] = useState<SimulationResult[]>(() => {
    try {
      const stored = localStorage.getItem(SIM_STORAGE_KEY);
      if (stored) {
        return JSON.parse(stored) as SimulationResult[];
      }
    } catch {
      // fallback
    }
    return INITIAL_SIMULATIONS;
  });

  const [activeSimulationId, setActiveSimulationId] = useState<string | null>(() => {
    return INITIAL_SIMULATIONS[0]?.id || null;
  });

  const [systemHealth, setSystemHealth] = useState<SystemHealthStatus>({
    backend: 'checking',
    database: 'checking',
    clusterNodes: 4,
    activeJobs: 1,
  });

  const isExecutionActive = simulations.some((s) => s.status === 'running');

  const refreshSystemHealth = useCallback(async () => {
    try {
      const status = await systemService.getFullSystemStatus();
      setSystemHealth(status);
    } catch {
      setSystemHealth({
        backend: 'offline',
        database: 'disconnected',
        clusterNodes: 4,
        activeJobs: 0,
      });
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    systemService.getFullSystemStatus().then((status) => {
      if (isMounted) setSystemHealth(status);
    }).catch(() => {
      if (isMounted) {
        setSystemHealth({
          backend: 'offline',
          database: 'disconnected',
          clusterNodes: 4,
          activeJobs: 0,
        });
      }
    });

    const interval = setInterval(refreshSystemHealth, 30000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [refreshSystemHealth]);

  useEffect(() => {
    try {
      localStorage.setItem(SIM_STORAGE_KEY, JSON.stringify(simulations));
    } catch {
      // ignore
    }
  }, [simulations]);

  const activeSimulation = simulations.find((s) => s.id === activeSimulationId) || null;

  const createSimulation = (configData: Omit<SimulationConfig, 'id' | 'createdAt'>): string => {
    const id = `SIM-GC-${new Date().getFullYear()}-${String(simulations.length + 1).padStart(3, '0')}`;
    const createdAt = new Date().toISOString().replace('T', ' ').substring(0, 16);

    const fullConfig: SimulationConfig = {
      ...configData,
      id,
      createdAt,
    };

    const variety = CORN_VARIETIES.find((v) => v.id === configData.cornVariety);
    const nominalYield = variety ? variety.potentialYieldTnHa : 4.5;

    let speedup = 1.0;
    let efficiency = 100.0;
    let timeEst = 340.0;
    const initialLogs: SimulationLog[] = [
      { timestamp: new Date().toLocaleTimeString(), level: 'INFO', message: `Job ${id} encolado en partición Slurm/MPI.` },
    ];

    if (configData.engine === 'openmp') {
      const threads = configData.openmpThreads || 4;
      speedup = Number((threads * 0.92).toFixed(2));
      efficiency = Number(((speedup / threads) * 100).toFixed(1));
      timeEst = Number((340.0 / speedup).toFixed(1));
      initialLogs.push({
        timestamp: new Date().toLocaleTimeString(),
        level: 'OMP',
        message: `Asignados ${threads} hilos OpenMP en nodo maestro.`,
      });
    } else if (configData.engine === 'mpi') {
      const procs = configData.mpiProcesses || 8;
      const nodes = configData.nodesCount || 2;
      speedup = Number((procs * 0.86).toFixed(2));
      efficiency = Number(((speedup / procs) * 100).toFixed(1));
      timeEst = Number((340.0 / speedup).toFixed(1));
      initialLogs.push({
        timestamp: new Date().toLocaleTimeString(),
        level: 'MPI',
        message: `Comunicador MPI_COMM_WORLD configurado con ${procs} procesos en ${nodes} nodos.`,
      });
    } else if (configData.engine === 'hibrido') {
      const procs = configData.mpiProcesses || 4;
      const threads = configData.openmpThreads || 4;
      const totalCores = procs * threads;
      speedup = Number((totalCores * 0.91).toFixed(2));
      efficiency = Number(((speedup / totalCores) * 100).toFixed(1));
      timeEst = Number((340.0 / speedup).toFixed(1));
      initialLogs.push({
        timestamp: new Date().toLocaleTimeString(),
        level: 'MPI',
        message: `Híbrido: ${procs} procesos MPI con ${threads} hilos OMP cada uno (${totalCores} núcleos paralelos).`,
      });
    }

    const newSim: SimulationResult = {
      id,
      config: fullConfig,
      status: 'pending',
      progressPercent: 0,
      currentDay: 0,
      createdAt,
      executionTimeSeconds: timeEst,
      speedup,
      efficiency,
      averageCWSI: 0.52,
      soilMoistureFinalPercent: 12.4,
      yieldLossPercent: 28.5,
      estimatedYieldTnHa: Number((nominalYield * 0.715).toFixed(2)),
      nominalYieldTnHa: nominalYield,
      waterDeficitMm: 165.0,
      memoryUsageMb: 850,
      timelineData: generateMockTimeline(configData.simulationDays, 1.0),
      spatialGrid: generateMockSpatialGrid(8, 8, 0.52),
      logs: initialLogs,
    };

    setSimulations((prev) => [newSim, ...prev]);
    setActiveSimulationId(id);
    return id;
  };

  const startExecution = (id: string) => {
    setSimulations((prev) =>
      prev.map((s) => {
        if (s.id === id) {
          return {
            ...s,
            status: 'running',
            progressPercent: s.progressPercent === 100 ? 5 : s.progressPercent || 5,
            logs: [
              ...s.logs,
              {
                timestamp: new Date().toLocaleTimeString(),
                level: 'INFO',
                message: 'Iniciando bucle temporal de simulación y cálculo de evapotranspiración.',
              },
            ],
          };
        }
        return s;
      })
    );
  };

  const stopExecution = (id: string) => {
    setSimulations((prev) =>
      prev.map((s) => {
        if (s.id === id) {
          return {
            ...s,
            status: 'paused',
            logs: [
              ...s.logs,
              {
                timestamp: new Date().toLocaleTimeString(),
                level: 'WARN',
                message: 'Ejecución pausada por el operador.',
              },
            ],
          };
        }
        return s;
      })
    );
  };

  const deleteSimulation = (id: string) => {
    setSimulations((prev) => prev.filter((s) => s.id !== id));
    if (activeSimulationId === id) {
      setActiveSimulationId(simulations[0]?.id || null);
    }
  };

  useEffect(() => {
    const runningSim = simulations.find((s) => s.status === 'running');
    if (!runningSim) {
      return;
    }

    const interval = setInterval(() => {
      setSimulations((prev) =>
        prev.map((sim) => {
          if (sim.status !== 'running') return sim;
          const nextProgress = Math.min(100, sim.progressPercent + 8);
          const totalDays = sim.config.simulationDays || 120;
          const nextDay = Math.min(totalDays, Math.floor((nextProgress / 100) * totalDays));

          if (nextProgress >= 100) {
            return {
              ...sim,
              status: 'completed',
              progressPercent: 100,
              currentDay: totalDays,
              completedAt: new Date().toISOString().replace('T', ' ').substring(0, 16),
              logs: [
                ...sim.logs,
                {
                  timestamp: new Date().toLocaleTimeString(),
                  level: 'INFO',
                  message: `Convergencia alcanzada para ${totalDays} días. Simulación exitosa.`,
                },
              ],
            };
          }

          const newLogs = [...sim.logs];
          if (nextProgress % 24 < 8) {
            newLogs.push({
              timestamp: new Date().toLocaleTimeString(),
              level: sim.config.engine === 'mpi' ? 'MPI' : sim.config.engine === 'openmp' ? 'OMP' : 'INFO',
              message: `Paso ${nextDay}/${totalDays}: balance hídrico calculado. Difusión en grilla ${sim.config.gridConfig.rows}x${sim.config.gridConfig.cols}.`,
            });
          }

          return {
            ...sim,
            progressPercent: nextProgress,
            currentDay: nextDay,
            logs: newLogs,
          };
        })
      );
    }, 1500);

    return () => clearInterval(interval);
  }, [simulations]);

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
