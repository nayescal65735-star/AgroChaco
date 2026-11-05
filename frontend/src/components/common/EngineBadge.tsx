import { Cpu, Server, Network, Layers } from 'lucide-react';
import type { SimulationEngine } from '../../types';

interface EngineBadgeProps {
  engine: SimulationEngine;
  threads?: number;
  processes?: number;
}

export function EngineBadge({ engine, threads, processes }: EngineBadgeProps) {
  switch (engine) {
    case 'secuencial':
      return (
        <span className="badge badge-engine badge-engine-secuencial" title="Cálculo monohilo secuencial">
          <Cpu size={12} />
          Secuencial
        </span>
      );
    case 'openmp':
      return (
        <span className="badge badge-engine badge-engine-openmp" title="Memoria compartida OpenMP">
          <Layers size={12} />
          OpenMP {threads ? `(${threads}T)` : ''}
        </span>
      );
    case 'mpi':
      return (
        <span className="badge badge-engine badge-engine-mpi" title="Paso de mensajes distribuido MPI">
          <Network size={12} />
          MPI {processes ? `(${processes}P)` : ''}
        </span>
      );
    case 'hibrido':
      return (
        <span className="badge badge-engine badge-engine-hibrido" title="Híbrido MPI + OpenMP multinodo">
          <Server size={12} />
          Híbrido {processes && threads ? `(${processes}P×${threads}T)` : ''}
        </span>
      );
    default:
      return <span className="badge">{engine}</span>;
  }
}
