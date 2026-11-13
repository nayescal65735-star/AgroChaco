export type Role = 'investigador' | 'agronomo' | 'operador_hpc' | 'admin';

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  institution: string;
  avatarUrl?: string;
}

export type GranChacoZoneId = 'yacuiba' | 'villamontes' | 'carapari' | 'charagua' | 'machareti' | 'boyuibe';

export interface GranChacoZone {
  id: GranChacoZoneId;
  name: string;
  department: 'Tarija' | 'Santa Cruz' | 'Chuquisaca';
  latitude: number;
  longitude: number;
  annualRainfallMm: number;
  soilDefault: string;
  currentRisk: 'bajo' | 'moderado' | 'severo' | 'critico';
  activeHectares: number;
  averageTempC: number;
}

export type SoilType = 'franco_arenoso' | 'franco_arcilloso' | 'arenoso' | 'franco';

export interface SoilInfo {
  id: SoilType;
  label: string;
  fieldCapacity: number; // Capacidad de campo (%)
  wiltingPoint: number;  // Punto de marchitez permanente (%)
  availableWaterMmPerM: number;
}

export type CornVarietyId = 'chaco_01_criollo' | 'dekalb_7088' | 'iniaf_h1' | 'pioneer_30f35';

export interface CornVariety {
  id: CornVarietyId;
  name: string;
  cycleDays: number;
  potentialYieldTnHa: number;
  droughtResistance: 'Media' | 'Alta' | 'Muy Alta';
  criticalStage: string;
}

export type SimulationEngine = 'secuencial' | 'openmp' | 'mpi' | 'hibrido';

export type SimulationStatus = 'pending' | 'running' | 'completed' | 'failed' | 'paused';

export type DroughtScenario = 'historico' | 'moderado_ssp245' | 'extremo_ssp585' | 'sequia_recente_2023';

export interface GridConfig {
  rows: number;
  cols: number;
  cellSizeMeters: number;
}

export interface SimulationConfig {
  id: string;
  name: string;
  description?: string;
  zone: GranChacoZoneId;
  zoneName: string;
  department: string;
  soilType: SoilType;
  cornVariety: CornVarietyId;
  plantingDate: string;
  simulationDays: number;
  gridConfig: GridConfig;
  initialMoisturePercent: number;
  droughtScenario: DroughtScenario;
  engine: SimulationEngine;
  openmpThreads?: number;
  mpiProcesses?: number;
  nodesCount?: number;
  createdAt: string;
}

export interface TimelineDataPoint {
  day: number;
  date: string;
  phenologicalStage: string;
  etActual: number;        // mm/día
  etPotential: number;     // mm/día
  cwsi: number;            // Crop Water Stress Index (0 a 1)
  soilMoisture: number;    // %
  precipitation: number;   // mm
}

export interface SpatialCell {
  x: number;
  y: number;
  moisture: number;
  cwsi: number;
  riskLevel: 'bajo' | 'moderado' | 'severo' | 'critico';
}

export interface SimulationResult {
  id: string;
  config: SimulationConfig;
  status: SimulationStatus;
  progressPercent: number;
  currentDay?: number;
  createdAt: string;
  completedAt?: string;
  executionTimeSeconds?: number;
  speedup?: number;
  efficiency?: number;
  averageCWSI?: number;
  soilMoistureFinalPercent?: number;
  yieldLossPercent?: number;
  estimatedYieldTnHa?: number;
  nominalYieldTnHa?: number;
  waterDeficitMm?: number;
  memoryUsageMb?: number;
  timelineData: TimelineDataPoint[];
  spatialGrid: SpatialCell[];
  logs: SimulationLog[];
}

export interface SimulationLog {
  timestamp: string;
  level: 'INFO' | 'MPI' | 'OMP' | 'WARN' | 'ERROR';
  message: string;
}

export interface HPCBenchmarkRecord {
  engine: SimulationEngine;
  label: string;
  coresOrProcesses: number;
  nodes: number;
  executionTimeSeconds?: number;
  speedup?: number;
  efficiencyPercent: number;
  computationTimeSec: number;
  communicationTimeSec: number;
  memoryMb: number;
  gflopsEstimate: number;
}

export interface StrongScalingPoint {
  workers: number; // threads or procs
  idealSpeedup: number;
  secuencialSpeedup: number;
  openmpSpeedup: number;
  mpiSpeedup: number;
  hibridoSpeedup: number;
}

export interface SystemHealthStatus {
  backend: 'online' | 'offline' | 'checking';
  database: 'connected' | 'disconnected' | 'checking';
  clusterNodes: number;
  activeJobs: number;
  databaseName?: string;
  backendVersion?: string;
}
