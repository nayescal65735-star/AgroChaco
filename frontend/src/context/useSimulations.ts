import { useContext } from 'react';
import { SimulationContext } from './simulationContextDef';

export function useSimulations() {
  const context = useContext(SimulationContext);
  if (!context) {
    throw new Error('useSimulations must be used within a SimulationProvider');
  }
  return context;
}
