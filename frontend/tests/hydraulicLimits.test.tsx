import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  ajustarHumedadInicial,
  humedadDentroDeLimites,
  limitesHumedadInicial,
} from '../src/services/mockData';
import type { SoilType } from '../src/types';

const mocks = vi.hoisted(() => ({
  createSimulation: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock('../src/context', () => ({
  useSimulations: () => ({
    createSimulation: mocks.createSimulation,
    simulations: [],
  }),
}));

vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<typeof import('react-router-dom')>(
    'react-router-dom'
  );
  return { ...real, useNavigate: () => mocks.navigate };
});

import { NewSimulation } from '../src/pages/NewSimulation';

const SUELOS: Array<[SoilType, number, number]> = [
  ['franco_arenoso', 8.2, 18.5],
  ['franco_arcilloso', 17.5, 31],
  ['arenoso', 4.8, 12],
  ['franco', 11, 24],
];

describe('límites físicos de humedad inicial', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('define los cuatro rangos y valida los extremos', () => {
    for (const [suelo, min, max] of SUELOS) {
      expect(limitesHumedadInicial(suelo)).toMatchObject({ min, max });
      expect(humedadDentroDeLimites(suelo, min)).toBe(true);
      expect(humedadDentroDeLimites(suelo, max)).toBe(true);
      expect(humedadDentroDeLimites(suelo, min - 0.01)).toBe(false);
      expect(humedadDentroDeLimites(suelo, max + 0.01)).toBe(false);
    }
  });

  it('ajusta la humedad al cambiar de suelo', () => {
    expect(ajustarHumedadInicial('arenoso', 16)).toBe(12);
    expect(ajustarHumedadInicial('franco_arcilloso', 5)).toBe(17.5);
    expect(ajustarHumedadInicial('franco', Number.NaN)).toBe(17.5);
  });

  it('el formulario aplica el rango del suelo y rechaza valores inválidos', () => {
    const { container } = render(<NewSimulation />);
    const humedad = screen.getByLabelText('Humedad Inicial del Suelo (%)');
    const suelo = screen.getByLabelText('Tipo de Suelo');

    expect(humedad.getAttribute('min')).toBe('8.2');
    expect(humedad.getAttribute('max')).toBe('18.5');

    fireEvent.change(suelo, { target: { value: 'arenoso' } });
    expect(humedad.getAttribute('min')).toBe('4.8');
    expect(humedad.getAttribute('max')).toBe('12');
    expect((humedad as HTMLInputElement).value).toBe('12');

    fireEvent.change(humedad, { target: { value: '20' } });
    fireEvent.submit(container.querySelector('form')!);

    expect(screen.getByText(/debe estar entre 4.8% y 12%/)).toBeTruthy();
    expect(mocks.createSimulation).not.toHaveBeenCalled();
  });
});
