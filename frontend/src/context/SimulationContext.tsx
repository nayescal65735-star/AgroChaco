import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type {
  SimulationResult,
  SimulationConfig,
  SystemHealthStatus,
  SimulationJob,
  SimulationJobStatus,
  SimulationStatus,
} from '../types';
import {
  JOB_POLL_INTERVAL_MS,
  mensajeErrorApi,
  simulationService,
  systemService,
  type BackendSimulation,
} from '../services/api';
import { SimulationContext } from './simulationContextDef';

const STORAGE_KEY = 'agrochaco.activeJobs';

const ESTADO_SIMULACION_POR_TRABAJO: Record<
  SimulationJobStatus,
  SimulationStatus
> = {
  queued: 'queued',
  running: 'running',
  completed: 'completed',
  failed: 'failed',
  canceled: 'canceled',
};

function esTerminal(estado: SimulationJobStatus): boolean {
  return estado === 'completed' || estado === 'failed' || estado === 'canceled';
}

function leerTrabajosActivos(): Record<string, string> {
  if (typeof window === 'undefined') {
    return {};
  }
  try {
    const contenido = window.localStorage.getItem(STORAGE_KEY);
    if (!contenido) {
      return {};
    }
    const datos: unknown = JSON.parse(contenido);
    if (!datos || typeof datos !== 'object' || Array.isArray(datos)) {
      return {};
    }
    return Object.fromEntries(
      Object.entries(datos).filter(
        (entrada): entrada is [string, string] =>
          typeof entrada[0] === 'string' && typeof entrada[1] === 'string'
      )
    );
  } catch {
    return {};
  }
}

function normalizarTrabajo(trabajo: SimulationJob): SimulationJob {
  const estado = trabajo.status ?? trabajo.estado;
  return { ...trabajo, estado, status: estado };
}

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
    currentDay: data.currentDay,
    averageCWSI: data.averageCWSI,
    soilMoistureFinalPercent: data.soilMoistureFinalPercent,
    yieldLossPercent: data.yieldLossPercent,
    estimatedYieldTnHa: data.estimatedYieldTnHa,
    nominalYieldTnHa: data.nominalYieldTnHa,
    waterDeficitMm: data.waterDeficitMm,
    executionTimeSeconds: data.executionTimeSeconds,
    speedup: data.speedup,
    efficiency: data.efficiency,
    memoryUsageMb: data.memoryUsageMb,
    timelineData: data.timelineData ?? [],
    spatialGrid: data.spatialGrid ?? [],
    logs: data.logs ?? [],
  };
}

function simulacionSinResultados(
  simulacion: SimulationResult,
  trabajo: SimulationJob
): SimulationResult {
  return {
    ...simulacion,
    status: ESTADO_SIMULACION_POR_TRABAJO[trabajo.status],
    progressPercent: trabajo.progressPercent,
    currentDay: trabajo.currentDay ?? undefined,
    completedAt: undefined,
    executionTimeSeconds: undefined,
    speedup: undefined,
    efficiency: undefined,
    averageCWSI: undefined,
    soilMoistureFinalPercent: undefined,
    yieldLossPercent: undefined,
    estimatedYieldTnHa: undefined,
    nominalYieldTnHa: undefined,
    waterDeficitMm: undefined,
    memoryUsageMb: undefined,
    timelineData: [],
    spatialGrid: [],
    logs: [],
  };
}

function esNoEncontrado(error: unknown): boolean {
  return Boolean(
    error &&
      typeof error === 'object' &&
      (error as { response?: { status?: number } }).response?.status === 404
  );
}

export function SimulationProvider({ children }: { children: ReactNode }) {
  const [simulations, setSimulations] = useState<SimulationResult[]>([]);
  const [activeSimulationId, setActiveSimulationId] = useState<string | null>(
    null
  );
  const [jobsBySimulation, setJobsBySimulation] = useState<
    Record<string, SimulationJob>
  >({});
  const [jobErrorsBySimulation, setJobErrorsBySimulation] = useState<
    Record<string, string>
  >({});
  const [jobIdsActivos, setJobIdsActivos] = useState<Record<string, string>>(
    leerTrabajosActivos
  );
  const [systemHealth, setSystemHealth] = useState<SystemHealthStatus>({
    backend: 'checking',
    database: 'checking',
    clusterNodes: 0,
    activeJobs: 0,
    databaseName: 'agrochaco_db',
    backendVersion: '1.0.0',
  });

  const jobsRef = useRef(jobsBySimulation);
  const jobIdsRef = useRef(jobIdsActivos);
  const enVueloRef = useRef(new Set<string>());
  const iniciandoRef = useRef(new Set<string>());
  const cancelandoRef = useRef(new Set<string>());
  const temporizadoresRef = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const programarPollRef = useRef<
    (simulacionId: string, jobId: string, espera?: number) => void
  >(() => {});

  const activeSimulation = useMemo(
    () =>
      simulations.find((simulation) => simulation.id === activeSimulationId) ??
      null,
    [simulations, activeSimulationId]
  );

  const activeJob = activeSimulationId
    ? jobsBySimulation[activeSimulationId] ?? null
    : null;

  const isExecutionActive = useMemo(
    () =>
      Object.values(jobsBySimulation).some(
        (job) => job.status === 'queued' || job.status === 'running'
      ) ||
      simulations.some(
        (simulation) =>
          simulation.status === 'running' || simulation.status === 'queued'
      ),
    [jobsBySimulation, simulations]
  );

  const limpiarTemporizador = useCallback((simulacionId: string) => {
    const temporizador = temporizadoresRef.current.get(simulacionId);
    if (temporizador !== undefined) {
      clearTimeout(temporizador);
      temporizadoresRef.current.delete(simulacionId);
    }
  }, []);

  const persistirJobId = useCallback(
    (simulacionId: string, jobId: string | null) => {
      const siguiente = { ...jobIdsRef.current };
      if (jobId === null) {
        delete siguiente[simulacionId];
      } else {
        siguiente[simulacionId] = jobId;
      }
      jobIdsRef.current = siguiente;
      setJobIdsActivos(siguiente);
      if (typeof window !== 'undefined') {
        try {
          if (Object.keys(siguiente).length === 0) {
            window.localStorage.removeItem(STORAGE_KEY);
          } else {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(siguiente));
          }
        } catch {
          window.localStorage.removeItem(STORAGE_KEY);
        }
      }
    },
    []
  );

  const establecerErrorJob = useCallback(
    (simulacionId: string, mensaje: string | null) => {
      setJobErrorsBySimulation((anterior) => {
        const siguiente = { ...anterior };
        if (mensaje === null) {
          delete siguiente[simulacionId];
        } else {
          siguiente[simulacionId] = mensaje;
        }
        return siguiente;
      });
    },
    []
  );

  const limpiarErrorJob = useCallback(
    (simulacionId: string) => establecerErrorJob(simulacionId, null),
    [establecerErrorJob]
  );

  const registrarTrabajo = useCallback((trabajo: SimulationJob) => {
    const siguiente = { ...jobsRef.current, [trabajo.simulation_id]: trabajo };
    jobsRef.current = siguiente;
    setJobsBySimulation(siguiente);
  }, []);

  const aplicarTrabajo = useCallback(
    (trabajo: SimulationJob) => {
      registrarTrabajo(trabajo);
      setSimulations((anterior) =>
        anterior.map((simulacion) =>
          simulacion.id === trabajo.simulation_id
            ? {
                ...simulacion,
                status: ESTADO_SIMULACION_POR_TRABAJO[trabajo.status],
                progressPercent: trabajo.progressPercent,
                currentDay: trabajo.currentDay ?? undefined,
                completedAt:
                  trabajo.status === 'completed'
                    ? trabajo.finishedAt ?? simulacion.completedAt
                    : undefined,
              }
            : simulacion
        )
      );
    },
    [registrarTrabajo]
  );

  const actualizarDatosSimulacion = useCallback(
    async (simulacionId: string, estadoTrabajo: SimulationJobStatus) => {
      try {
        const datos = await simulationService.getById(simulacionId);
        if (estadoTrabajo === 'completed' && datos.status !== 'completed') {
          return;
        }
        const actualizada = mapBackendSimulation(datos);
        setSimulations((anterior) =>
          anterior.map((simulacion) =>
            simulacion.id === simulacionId
              ? {
                  ...actualizada,
                  status:
                    estadoTrabajo === 'canceled' ? 'canceled' : actualizada.status,
                }
              : simulacion
          )
        );
      } catch (error) {
        establecerErrorJob(
          simulacionId,
          mensajeErrorApi(error, 'No se pudieron cargar los resultados de la simulación.')
        );
      }
    },
    [establecerErrorJob]
  );

  const consultarTrabajo = useCallback(
    async (jobId: string, simulacionId: string) => {
      if (enVueloRef.current.has(jobId)) {
        return;
      }
      enVueloRef.current.add(jobId);
      try {
        const trabajo = normalizarTrabajo(await simulationService.getJob(jobId));
        aplicarTrabajo(trabajo);
        establecerErrorJob(
          simulacionId,
          esTerminal(trabajo.status) && trabajo.error ? trabajo.error : null
        );
        if (esTerminal(trabajo.status)) {
          limpiarTemporizador(simulacionId);
          persistirJobId(simulacionId, null);
          await actualizarDatosSimulacion(simulacionId, trabajo.status);
        } else {
          programarPollRef.current(simulacionId, jobId);
        }
      } catch (error) {
        if (esNoEncontrado(error)) {
          limpiarTemporizador(simulacionId);
          persistirJobId(simulacionId, null);
        } else {
          programarPollRef.current(simulacionId, jobId);
        }
        establecerErrorJob(
          simulacionId,
          mensajeErrorApi(error, 'No se pudo consultar el estado del trabajo.')
        );
      } finally {
        enVueloRef.current.delete(jobId);
      }
    },
    [
      aplicarTrabajo,
      actualizarDatosSimulacion,
      establecerErrorJob,
      limpiarTemporizador,
      persistirJobId,
    ]
  );

  const programarPoll = useCallback(
    (
      simulacionId: string,
      jobId: string,
      espera: number = JOB_POLL_INTERVAL_MS
    ) => {
      limpiarTemporizador(simulacionId);
      const temporizador = setTimeout(() => {
        void consultarTrabajo(jobId, simulacionId);
      }, espera);
      temporizadoresRef.current.set(simulacionId, temporizador);
    },
    [consultarTrabajo, limpiarTemporizador]
  );

  useEffect(() => {
    programarPollRef.current = programarPoll;
  }, [programarPoll]);

  const loadSimulations = useCallback(async () => {
    try {
      const response = await simulationService.list();
      const registros = response.simulations.map(mapBackendSimulation);
      const trabajos = jobsRef.current;
      const fusionados = registros.map((registro) => {
        const trabajo = trabajos[registro.id];
        if (!trabajo || esTerminal(trabajo.status)) {
          return registro;
        }
        return {
          ...registro,
          status: ESTADO_SIMULACION_POR_TRABAJO[trabajo.status],
          progressPercent: trabajo.progressPercent,
          currentDay: trabajo.currentDay ?? registro.currentDay,
        };
      });

      setSimulations(fusionados);
      setActiveSimulationId((actual) => {
        if (actual && fusionados.some((simulacion) => simulacion.id === actual)) {
          return actual;
        }
        return fusionados[0]?.id ?? null;
      });
    } catch (error) {
      console.error('No se pudieron cargar las simulaciones:', error);
    }
  }, []);

  const refrescarEstadoSistema = useCallback(async () => {
    try {
      const estado = await systemService.getFullSystemStatus();
      const activos = Object.values(jobsRef.current).filter(
        (job) => job.status === 'queued' || job.status === 'running'
      ).length;
      setSystemHealth({ ...estado, activeJobs: activos });
    } catch {
      setSystemHealth({
        backend: 'offline',
        database: 'disconnected',
        clusterNodes: 0,
        activeJobs: 0,
      });
    }
  }, []);

  const recuperarTrabajosActivos = useCallback(async () => {
    await Promise.all(
      Object.entries(jobIdsRef.current).map(async ([simulacionId, jobId]) => {
        try {
          const trabajo = normalizarTrabajo(
            await simulationService.getJob(jobId)
          );
          aplicarTrabajo(trabajo);
          establecerErrorJob(
            simulacionId,
            esTerminal(trabajo.status) && trabajo.error ? trabajo.error : null
          );
          if (esTerminal(trabajo.status)) {
            limpiarTemporizador(simulacionId);
            persistirJobId(simulacionId, null);
            await actualizarDatosSimulacion(simulacionId, trabajo.status);
          } else {
            programarPollRef.current(simulacionId, jobId);
          }
        } catch (error) {
          if (esNoEncontrado(error)) {
            persistirJobId(simulacionId, null);
          } else {
            programarPollRef.current(simulacionId, jobId);
            establecerErrorJob(
              simulacionId,
              mensajeErrorApi(error, 'No se pudo recuperar el trabajo activo.')
            );
          }
        }
      })
    );
  }, [
    aplicarTrabajo,
    actualizarDatosSimulacion,
    establecerErrorJob,
    limpiarTemporizador,
    persistirJobId,
  ]);

  useEffect(() => {
    void loadSimulations();
    void recuperarTrabajosActivos();
    void refrescarEstadoSistema();

    const intervalo = setInterval(refrescarEstadoSistema, 30000);
    const temporizadores = temporizadoresRef.current;
    return () => {
      clearInterval(intervalo);
      temporizadores.forEach((temporizador) => clearTimeout(temporizador));
      temporizadores.clear();
    };
  }, [loadSimulations, recuperarTrabajosActivos, refrescarEstadoSistema]);

  const createSimulation = async (
    config: Omit<SimulationConfig, 'id' | 'createdAt'>
  ): Promise<string> => {
    const response = await simulationService.create(config);
    const nueva = mapBackendSimulation(response);
    setSimulations((anterior) => [
      nueva,
      ...anterior.filter((simulacion) => simulacion.id !== nueva.id),
    ]);
    setActiveSimulationId(nueva.id);
    return nueva.id;
  };

  const startExecution = useCallback(
    async (id: string) => {
      if (iniciandoRef.current.has(id)) {
        return;
      }
      const trabajoActual = jobsRef.current[id];
      if (trabajoActual && !esTerminal(trabajoActual.status)) {
        programarPollRef.current(id, trabajoActual.job_id, 0);
        return;
      }

      iniciandoRef.current.add(id);
      try {
        establecerErrorJob(id, null);
        const aceptada = await simulationService.execute(id);
        if (!aceptada.createdAt) {
          throw new Error('El backend no devolvió la fecha de creación del trabajo.');
        }
        const estado = aceptada.status ?? aceptada.estado;
        const trabajo = normalizarTrabajo({
          job_id: aceptada.job_id,
          simulation_id: aceptada.simulation_id,
          estado: estado,
          status: estado,
          progressPercent: aceptada.progressPercent,
          currentDay: aceptada.currentDay,
          pid: null,
          cancelRequested: false,
          createdAt: aceptada.createdAt,
          startedAt: null,
          updatedAt: null,
          finishedAt: null,
          error: null,
          error_message: null,
        });
        aplicarTrabajo(trabajo);
        persistirJobId(id, trabajo.job_id);
        setSimulations((anterior) =>
          anterior.map((simulacion) =>
            simulacion.id === id
              ? simulacionSinResultados(simulacion, trabajo)
              : simulacion
          )
        );
        programarPollRef.current(id, trabajo.job_id, 0);
      } catch (error) {
        establecerErrorJob(
          id,
          mensajeErrorApi(error, 'No se pudo encolar la ejecución.')
        );
        throw error;
      } finally {
        iniciandoRef.current.delete(id);
      }
    },
    [aplicarTrabajo, establecerErrorJob, persistirJobId]
  );

  const cancelExecution = useCallback(
    async (id: string) => {
      const jobId = jobsRef.current[id]?.job_id ?? jobIdsRef.current[id];
      if (!jobId) {
        const mensaje = 'No hay un trabajo activo que pueda cancelarse.';
        establecerErrorJob(id, mensaje);
        throw new Error(mensaje);
      }
      if (cancelandoRef.current.has(jobId)) {
        return;
      }
      cancelandoRef.current.add(jobId);
      try {
        establecerErrorJob(id, null);
        const trabajo = normalizarTrabajo(
          await simulationService.cancelJob(jobId)
        );
        aplicarTrabajo(trabajo);
        establecerErrorJob(
          id,
          esTerminal(trabajo.status) && trabajo.error ? trabajo.error : null
        );
        if (esTerminal(trabajo.status)) {
          limpiarTemporizador(id);
          persistirJobId(id, null);
          await actualizarDatosSimulacion(id, trabajo.status);
        } else {
          programarPollRef.current(id, jobId, 0);
        }
      } catch (error) {
        establecerErrorJob(
          id,
          mensajeErrorApi(error, 'No se pudo solicitar la cancelación.')
        );
        throw error;
      } finally {
        cancelandoRef.current.delete(jobId);
      }
    },
    [
      aplicarTrabajo,
      actualizarDatosSimulacion,
      establecerErrorJob,
      limpiarTemporizador,
      persistirJobId,
    ]
  );

  const stopExecution = useCallback(
    (id: string) => {
      void cancelExecution(id).catch(() => {});
    },
    [cancelExecution]
  );

  const deleteSimulation = async (id: string) => {
    await simulationService.delete(id);
    limpiarTemporizador(id);
    persistirJobId(id, null);
    const trabajos = { ...jobsRef.current };
    delete trabajos[id];
    jobsRef.current = trabajos;
    setJobsBySimulation(trabajos);
    establecerErrorJob(id, null);
    setSimulations((anterior) =>
      anterior.filter((simulacion) => simulacion.id !== id)
    );
    setActiveSimulationId((actual) => (actual === id ? null : actual));
  };

  return (
    <SimulationContext.Provider
      value={{
        simulations,
        activeSimulation,
        activeSimulationId,
        setActiveSimulationId,
        activeJob,
        jobsBySimulation,
        jobErrorsBySimulation,
        jobPollIntervalMs: JOB_POLL_INTERVAL_MS,
        clearJobError: limpiarErrorJob,
        createSimulation,
        startExecution,
        cancelExecution,
        stopExecution,
        deleteSimulation,
        systemHealth,
        refreshSystemHealth: refrescarEstadoSistema,
        isExecutionActive,
      }}
    >
      {children}
    </SimulationContext.Provider>
  );
}
