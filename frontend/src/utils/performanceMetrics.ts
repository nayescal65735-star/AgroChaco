export const PERFORMANCE_UNAVAILABLE_MESSAGE =
  'No disponible: falta una medición secuencial comparable';

export function isMeasuredSpeedup(
  value: number | null | undefined
): value is number {
  return (
    typeof value === 'number' && Number.isFinite(value) && value > 0
  );
}

export function isMeasuredEfficiency(
  efficiency: number | null | undefined,
  speedup: number | null | undefined
): efficiency is number {
  return (
    isMeasuredSpeedup(speedup) &&
    typeof efficiency === 'number' &&
    Number.isFinite(efficiency) &&
    efficiency > 0
  );
}

export function formatSpeedup(value: number | null | undefined): string {
  if (value === undefined) {
    return 'Pendiente';
  }
  if (!isMeasuredSpeedup(value)) {
    return PERFORMANCE_UNAVAILABLE_MESSAGE;
  }
  return `${value.toFixed(2)}×`;
}

export function formatSpeedupCompact(value: number | null | undefined): string {
  if (value === undefined) {
    return 'Pendiente';
  }
  if (!isMeasuredSpeedup(value)) {
    return PERFORMANCE_UNAVAILABLE_MESSAGE;
  }
  if (Math.abs(value - 1) < 1e-9) {
    return `Línea base (${value.toFixed(2)}×)`;
  }
  return `${value.toFixed(2)}x acelerado`;
}

export function normalizeEfficiencyPercent(value: number): number {
  return value <= 1 ? value * 100 : value;
}

export function formatEfficiency(
  efficiency: number | null | undefined,
  speedup: number | null | undefined
): string {
  if (efficiency === undefined || speedup === undefined) {
    return 'Pendiente';
  }
  if (!isMeasuredEfficiency(efficiency, speedup)) {
    return PERFORMANCE_UNAVAILABLE_MESSAGE;
  }
  return `${normalizeEfficiencyPercent(efficiency).toFixed(1)}%`;
}
