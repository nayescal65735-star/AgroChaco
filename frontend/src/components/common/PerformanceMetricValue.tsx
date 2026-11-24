import {
  formatEfficiency,
  formatSpeedup,
  formatSpeedupCompact,
} from '../../utils/performanceMetrics';

interface SpeedupValueProps {
  value?: number | null;
  compact?: boolean;
}

export function SpeedupValue({ value, compact = false }: SpeedupValueProps) {
  return <>{compact ? formatSpeedupCompact(value) : formatSpeedup(value)}</>;
}

interface EfficiencyValueProps {
  efficiency?: number | null;
  speedup?: number | null;
}

export function EfficiencyValue({
  efficiency,
  speedup,
}: EfficiencyValueProps) {
  return <>{formatEfficiency(efficiency, speedup)}</>;
}
