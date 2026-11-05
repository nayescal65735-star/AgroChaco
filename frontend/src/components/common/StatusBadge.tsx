import { CheckCircle2, Clock, PlayCircle, XCircle, PauseCircle } from 'lucide-react';
import type { SimulationStatus } from '../../types';

interface StatusBadgeProps {
  status: SimulationStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  switch (status) {
    case 'completed':
      return (
        <span className="badge badge-completed">
          <CheckCircle2 size={12} />
          Completada
        </span>
      );
    case 'running':
      return (
        <span className="badge badge-running">
          <PlayCircle size={12} />
          En ejecución
        </span>
      );
    case 'pending':
      return (
        <span className="badge badge-pending">
          <Clock size={12} />
          En cola
        </span>
      );
    case 'paused':
      return (
        <span className="badge badge-paused">
          <PauseCircle size={12} />
          Pausada
        </span>
      );
    case 'failed':
      return (
        <span className="badge badge-failed">
          <XCircle size={12} />
          Fallida
        </span>
      );
    default:
      return <span className="badge">{status}</span>;
  }
}
