import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import {
  EfficiencyValue,
  SpeedupValue,
} from '../src/components/common/PerformanceMetricValue';
import {
  PERFORMANCE_UNAVAILABLE_MESSAGE,
  formatEfficiency,
  formatSpeedup,
} from '../src/utils/performanceMetrics';

afterEach(() => {
  cleanup();
});

describe('métricas HPC no disponibles', () => {
  it('representa null y cero como no disponibles', () => {
    expect(formatSpeedup(null)).toBe(PERFORMANCE_UNAVAILABLE_MESSAGE);
    expect(formatSpeedup(0)).toBe(PERFORMANCE_UNAVAILABLE_MESSAGE);
    expect(formatEfficiency(null, null)).toBe(PERFORMANCE_UNAVAILABLE_MESSAGE);
    expect(formatEfficiency(0, 0)).toBe(PERFORMANCE_UNAVAILABLE_MESSAGE);
  });

  it('conserva mediciones reales de speedup y eficiencia', () => {
    expect(formatSpeedup(3.85)).toBe('3.85×');
    expect(formatSpeedup(1)).toBe('1.00×');
    expect(formatEfficiency(0.9624, 3.85)).toBe('96.2%');
    expect(formatEfficiency(100, 1)).toBe('100.0%');
  });

  it('muestra el mensaje de no disponible en React cuando llegaron null', () => {
    const { container } = render(
      <div>
        <SpeedupValue value={null} />
        {' / '}
        <EfficiencyValue efficiency={null} speedup={null} />
      </div>
    );

    const texto = container.textContent ?? '';
    expect(texto).toContain(PERFORMANCE_UNAVAILABLE_MESSAGE);
    expect(texto.split(PERFORMANCE_UNAVAILABLE_MESSAGE)).toHaveLength(3);
    expect(texto).not.toContain('0.00×');
  });

  it('no muestra 0× como resultado medido en React', () => {
    const { container } = render(<SpeedupValue value={0} />);

    expect(container.textContent).toBe(PERFORMANCE_UNAVAILABLE_MESSAGE);
    expect(container.textContent).not.toMatch(/0×|0\.00×/);
  });

  it('muestra speedup y eficiencia medidos en React', () => {
    const { container } = render(
      <div>
        <SpeedupValue value={3.85} />
        {' / '}
        <EfficiencyValue efficiency={0.9624} speedup={3.85} />
      </div>
    );

    expect(container.textContent).toBe('3.85× / 96.2%');
  });
});
