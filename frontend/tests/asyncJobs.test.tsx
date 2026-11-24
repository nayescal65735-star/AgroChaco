import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  simulationService: {
    create: vi.fn(),
    list: vi.fn(),
    getById: vi.fn(),
    delete: vi.fn(),
    execute: vi.fn(),
    getJob: vi.fn(),
    cancelJob: vi.fn(),
  },
  systemService: {
    getFullSystemStatus: vi.fn(),
  },
}));

vi.mock('../src/services/api', () => ({
  simulationService: mocks.simulationService,
  systemService: mocks.systemService,
  JOB_POLL_INTERVAL_MS: 10,
  mensajeErrorApi: (error: unknown, fallback: string) =>
    error instanceof Error && error.message ? error.message : fallback,
}));

import { SimulationProvider } from '../src/context/SimulationContext';
import { useSimulations } from '../src/context/useSimulations';

function backendSimulacion(cambios: Record<string, unknown> = {}) {
  return {
    id: 'SIM-1',
    config: {
      name: 'Simulación asíncrona',
      zone: 'yacuiba',
      zoneName: 'Yacuiba',
      department: 'Tarija',
      soilType: 'franco_arenoso',
      cornVariety: 'iniaf_h1',
      plantingDate: '2026-11-20',
      simulationDays: 30,
      gridConfig: { rows: 50, cols: 50, cellSizeMeters: 50 },
      initialMoisturePercent: 18.5,
      droughtScenario: 'moderado_ssp245',
      engine: 'secuencial',
      openmpThreads: null,
      mpiProcesses: null,
      nodesCount: null,
    },
    status: 'pending',
    progressPercent: 0,
    createdAt: '2026-11-24T12:00:00Z',
    completedAt: null,
    timelineData: [],
    spatialGrid: [],
    logs: [],
    ...cambios,
  };
}

function trabajo(
  estado: string,
  progressPercent: number,
  currentDay: number | null,
  cambios: Record<string, unknown> = {}
) {
  return {
    job_id: 'job-123',
    simulation_id: 'SIM-1',
    estado,
    status: estado,
    progressPercent,
    currentDay,
    pid: null,
    cancelRequested: false,
    createdAt: '2026-11-24T12:00:00Z',
    startedAt: '2026-11-24T12:00:01Z',
    updatedAt: '2026-11-24T12:00:02Z',
    finishedAt: estado === 'completed' ? '2026-11-24T12:00:10Z' : null,
    error: null,
    error_message: null,
    ...cambios,
  };
}

const aceptado = {
  job_id: 'job-123',
  simulation_id: 'SIM-1',
  estado: 'queued',
  status: 'queued',
  progressPercent: 0,
  currentDay: null,
  createdAt: '2026-11-24T12:00:00Z',
};

function envoltorio({ children }: { children: React.ReactNode }) {
  return <SimulationProvider>{children}</SimulationProvider>;
}

beforeEach(() => {
  window.localStorage.clear();
  vi.clearAllMocks();
  mocks.systemService.getFullSystemStatus.mockResolvedValue({
    backend: 'online',
    database: 'connected',
    clusterNodes: 0,
    activeJobs: 0,
  });
  mocks.simulationService.list.mockResolvedValue({
    total: 1,
    simulations: [backendSimulacion()],
  });
  mocks.simulationService.getById.mockResolvedValue(backendSimulacion());
  mocks.simulationService.getJob.mockResolvedValue(trabajo('queued', 0, null));
});

afterEach(() => {
  cleanup();
});

describe('integración asíncrona del contexto de simulaciones', () => {
  it('hace polling hasta finalizar y carga resultados reales', async () => {
    mocks.simulationService.execute.mockResolvedValue(aceptado);
    mocks.simulationService.getJob
      .mockResolvedValueOnce(trabajo('running', 65, 7))
      .mockResolvedValueOnce(trabajo('completed', 100, 30));
    mocks.simulationService.getById.mockResolvedValue(
      backendSimulacion({
        status: 'completed',
        progressPercent: 100,
        currentDay: 30,
        completedAt: '2026-11-24T12:00:10Z',
        timelineData: [{ day: 1, cwsi: 0.1, soilMoisture: 18, etActual: 2 }],
      })
    );

    const { result } = renderHook(() => useSimulations(), {
      wrapper: envoltorio,
    });

    await waitFor(() => expect(result.current.simulations).toHaveLength(1));
    await act(async () => {
      await result.current.startExecution('SIM-1');
    });

    await waitFor(() =>
      expect(result.current.simulations[0].status).toBe('completed')
    );
    expect(result.current.simulations[0].progressPercent).toBe(100);
    expect(result.current.simulations[0].currentDay).toBe(30);
    expect(result.current.simulations[0].timelineData).toHaveLength(1);
    expect(mocks.simulationService.getJob.mock.calls.length).toBeGreaterThanOrEqual(2);

    const consultas = mocks.simulationService.getJob.mock.calls.length;
    await new Promise((resolver) => setTimeout(resolver, 60));
    expect(mocks.simulationService.getJob.mock.calls.length).toBe(consultas);
  });

  it('evita ejecuciones duplicadas concurrentes', async () => {
    let resolverEjecucion: (valor: typeof aceptado) => void = () => {};
    mocks.simulationService.execute.mockReturnValue(
      new Promise<typeof aceptado>((resolver) => {
        resolverEjecucion = resolver;
      })
    );

    const { result } = renderHook(() => useSimulations(), {
      wrapper: envoltorio,
    });

    await waitFor(() => expect(result.current.simulations).toHaveLength(1));

    let primera: Promise<void> | undefined;
    let segunda: Promise<void> | undefined;
    await act(async () => {
      primera = result.current.startExecution('SIM-1');
      segunda = result.current.startExecution('SIM-1');
      resolverEjecucion(aceptado);
      await Promise.all([primera, segunda]);
    });

    expect(mocks.simulationService.execute).toHaveBeenCalledTimes(1);
  });

  it('cancela un trabajo en curso y deja de consultarlo', async () => {
    mocks.simulationService.execute.mockResolvedValue(aceptado);
    mocks.simulationService.getJob.mockResolvedValue(trabajo('running', 40, 10));
    mocks.simulationService.cancelJob.mockResolvedValue(
      trabajo('canceled', 40, 10, {
        cancelRequested: true,
        error: 'Cancelación solicitada por el usuario.',
      })
    );
    mocks.simulationService.getById.mockResolvedValue(
      backendSimulacion({ status: 'paused', progressPercent: 40, currentDay: 10 })
    );

    const { result } = renderHook(() => useSimulations(), {
      wrapper: envoltorio,
    });

    await waitFor(() => expect(result.current.simulations).toHaveLength(1));
    await act(async () => {
      await result.current.startExecution('SIM-1');
    });
    await waitFor(() => expect(result.current.simulations[0].status).toBe('running'));

    await act(async () => {
      await result.current.cancelExecution('SIM-1');
    });

    await waitFor(() =>
      expect(result.current.simulations[0].status).toBe('canceled')
    );
    expect(mocks.simulationService.cancelJob).toHaveBeenCalledWith('job-123');
    expect(window.localStorage.getItem('agrochaco.activeJobs')).toBeNull();

    const consultas = mocks.simulationService.getJob.mock.calls.length;
    await new Promise((resolver) => setTimeout(resolver, 60));
    expect(mocks.simulationService.getJob.mock.calls.length).toBe(consultas);
  });

  it('informa errores de red sin inventar progreso', async () => {
    mocks.simulationService.execute.mockResolvedValue(aceptado);
    mocks.simulationService.getJob.mockRejectedValue(new Error('Network down'));

    const { result } = renderHook(() => useSimulations(), {
      wrapper: envoltorio,
    });

    await waitFor(() => expect(result.current.simulations).toHaveLength(1));
    await act(async () => {
      await result.current.startExecution('SIM-1');
    });

    await waitFor(() =>
      expect(result.current.jobErrorsBySimulation['SIM-1']).toBe('Network down')
    );
    expect(result.current.simulations[0].progressPercent).toBe(0);
    expect(result.current.simulations[0].currentDay).toBeUndefined();
    expect(result.current.simulations[0].timelineData).toEqual([]);
  });

  it('recupera un trabajo activo después de recargar', async () => {
    window.localStorage.setItem(
      'agrochaco.activeJobs',
      JSON.stringify({ 'SIM-1': 'job-recuperado' })
    );
    mocks.simulationService.list.mockResolvedValue({
      total: 1,
      simulations: [backendSimulacion({ status: 'running' })],
    });
    mocks.simulationService.getJob.mockResolvedValue(
      trabajo('running', 42, 7, { job_id: 'job-recuperado' })
    );

    const { result } = renderHook(() => useSimulations(), {
      wrapper: envoltorio,
    });

    await waitFor(() => expect(result.current.simulations[0]?.progressPercent).toBe(42));
    expect(result.current.simulations[0].status).toBe('running');
    expect(result.current.simulations[0].currentDay).toBe(7);
    expect(mocks.simulationService.execute).not.toHaveBeenCalled();
    expect(mocks.simulationService.getJob).toHaveBeenCalledWith('job-recuperado');
  });
});
