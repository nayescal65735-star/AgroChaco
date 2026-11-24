import { createContext } from 'react';
import type {
  SimulationResult,
  SimulationConfig,
  SystemHealthStatus,
  SimulationJob,
} from '../types';

export interface SimulationContextType {
  simulations: SimulationResult[];
  activeSimulation: SimulationResult | null;
  activeSimulationId: string | null;
  setActiveSimulationId: (id: string | null) => void;
  activeJob: SimulationJob | null;
  jobsBySimulation: Record<string, SimulationJob>;
  jobErrorsBySimulation: Record<string, string>;
  jobPollIntervalMs: number;
  clearJobError: (simulationId: string) => void;
  createSimulation: (config: Omit<SimulationConfig, 'id' | 'createdAt'>) => Promise<string>;
  startExecution: (id: string) => Promise<void>;
  cancelExecution: (id: string) => Promise<void>;
  stopExecution: (id: string) => void;
  deleteSimulation: (id: string) => Promise<void>;
  systemHealth: SystemHealthStatus;
  refreshSystemHealth: () => Promise<void>;
  isExecutionActive: boolean;
}

export const SimulationContext = createContext<SimulationContextType | undefined>(undefined);
