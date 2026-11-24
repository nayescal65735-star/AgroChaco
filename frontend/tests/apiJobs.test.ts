import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  post: vi.fn(),
  get: vi.fn(),
  delete: vi.fn(),
}));

vi.mock('axios', () => ({
  default: {
    create: () => ({
      post: mocks.post,
      get: mocks.get,
      delete: mocks.delete,
    }),
  },
}));

import { simulationService } from '../src/services/api';

const aceptado = {
  job_id: 'job-123',
  simulation_id: 'SIM-1',
  estado: 'queued',
  status: 'queued',
  progressPercent: 0,
  currentDay: null,
  createdAt: '2026-11-24T12:00:00Z',
};

const trabajo = {
  ...aceptado,
  startedAt: null,
  updatedAt: '2026-11-24T12:00:00Z',
  finishedAt: null,
  pid: null,
  cancelRequested: false,
  error: null,
  error_message: null,
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('servicio de trabajos asíncronos', () => {
  it('interpreta HTTP 202 y conserva el job_id', async () => {
    mocks.post.mockResolvedValue({ status: 202, data: aceptado });

    const respuesta = await simulationService.execute('SIM-1');

    expect(respuesta).toEqual(aceptado);
    expect(mocks.post).toHaveBeenCalledWith(
      '/api/simulations/SIM-1/execute',
      {},
      expect.objectContaining({ timeout: expect.any(Number) })
    );
  });

  it('rechaza respuestas que no sean HTTP 202', async () => {
    mocks.post.mockResolvedValue({ status: 200, data: aceptado });

    await expect(simulationService.execute('SIM-1')).rejects.toThrow(
      'El backend no aceptó la solicitud de ejecución asíncrona.'
    );
  });

  it('consulta el estado del trabajo por job_id', async () => {
    mocks.get.mockResolvedValue({ status: 200, data: trabajo });

    await expect(simulationService.getJob('job-123')).resolves.toEqual(trabajo);
    expect(mocks.get).toHaveBeenCalledWith('/api/jobs/job-123');
  });

  it('solicita la cancelación por job_id', async () => {
    mocks.post.mockResolvedValue({
      status: 200,
      data: { ...trabajo, cancelRequested: true },
    });

    const respuesta = await simulationService.cancelJob('job-123');

    expect(respuesta.cancelRequested).toBe(true);
    expect(mocks.post).toHaveBeenCalledWith(
      '/api/jobs/job-123/cancel',
      {},
      expect.objectContaining({ timeout: expect.any(Number) })
    );
  });
});
