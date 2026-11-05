import { createContext } from 'react';
import type {
  SimulationResult,
  SimulationConfig,
  SystemHealthStatus,
} from '../types';

export interface SimulationContextType {
  simulations: SimulationResult[];
  activeSimulation: SimulationResult | null;
  activeSimulationId: string | null;
  setActiveSimulationId: (id: string | null) => void;
  createSimulation: (config: Omit<SimulationConfig, 'id' | 'createdAt'>) => string;
  startExecution: (id: string) => void;
  stopExecution: (id: string) => void;
  deleteSimulation: (id: string) => void;
  systemHealth: SystemHealthStatus;
  refreshSystemHealth: () => Promise<void>;
  isExecutionActive: boolean;
}

export const SimulationContext = createContext<SimulationContextType | undefined>(undefined);
