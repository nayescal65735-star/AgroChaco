import type {
  GranChacoZone,
  SoilInfo,
  CornVariety,
  SimulationResult,
  HPCBenchmarkRecord,
  StrongScalingPoint,
  User,
} from '../types';

export const DEMO_USERS: User[] = [
  {
    id: 'u-1',
    name: 'Dra. Elena Vargas Morón',
    email: 'elena.vargas@agrochaco.edu.bo',
    role: 'investigador',
    institution: 'Centro de Modelado Ambiental y Agrícola - UAGRM / UAJMS',
    avatarUrl: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80',
  },
  {
    id: 'u-2',
    name: 'Ing. Carlos Céspedes Tarija',
    email: 'carlos.cespedes@agrochaco.edu.bo',
    role: 'operador_hpc',
    institution: 'Laboratorio de Cómputo Distribuido Chaco HPC',
    avatarUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80',
  },
  {
    id: 'u-3',
    name: 'Ing. Agr. Mateo Soliz',
    email: 'mateo.soliz@agrochaco.edu.bo',
    role: 'agronomo',
    institution: 'Estación Experimental Gran Chaco - INIAF',
    avatarUrl: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80',
  },
];

export const GRAN_CHACO_ZONES: GranChacoZone[] = [
  {
    id: 'yacuiba',
    name: 'Yacuiba',
    department: 'Tarija',
    latitude: -22.0167,
    longitude: -63.6833,
    annualRainfallMm: 780,
    soilDefault: 'Franco-arenoso',
    currentRisk: 'severo',
    activeHectares: 24500,
    averageTempC: 31.4,
  },
  {
    id: 'villamontes',
    name: 'Villa Montes',
    department: 'Tarija',
    latitude: -21.2592,
    longitude: -63.4694,
    annualRainfallMm: 620,
    soilDefault: 'Arenoso',
    currentRisk: 'critico',
    activeHectares: 18200,
    averageTempC: 34.8,
  },
  {
    id: 'charagua',
    name: 'Charagua Iyambae',
    department: 'Santa Cruz',
    latitude: -19.7892,
    longitude: -63.2083,
    annualRainfallMm: 590,
    soilDefault: 'Franco-arcilloso',
    currentRisk: 'severo',
    activeHectares: 32000,
    averageTempC: 33.1,
  },
  {
    id: 'machareti',
    name: 'Macharetí',
    department: 'Chuquisaca',
    latitude: -20.8033,
    longitude: -63.3644,
    annualRainfallMm: 540,
    soilDefault: 'Franco-arenoso',
    currentRisk: 'critico',
    activeHectares: 14800,
    averageTempC: 33.9,
  },
  {
    id: 'carapari',
    name: 'Caraparí',
    department: 'Tarija',
    latitude: -21.8267,
    longitude: -63.7433,
    annualRainfallMm: 890,
    soilDefault: 'Franco',
    currentRisk: 'moderado',
    activeHectares: 11500,
    averageTempC: 28.5,
  },
  {
    id: 'boyuibe',
    name: 'Boyuibe',
    department: 'Santa Cruz',
    latitude: -20.4317,
    longitude: -63.2831,
    annualRainfallMm: 610,
    soilDefault: 'Arenoso',
    currentRisk: 'moderado',
    activeHectares: 9400,
    averageTempC: 32.2,
  },
];

export const SOIL_INFOS: SoilInfo[] = [
  {
    id: 'franco_arenoso',
    label: 'Franco-Arenoso (Típico Chaco Central)',
    fieldCapacity: 18.5,
    wiltingPoint: 8.2,
    availableWaterMmPerM: 103,
  },
  {
    id: 'franco_arcilloso',
    label: 'Franco-Arcilloso (Aluvial Pilcomayo)',
    fieldCapacity: 31.0,
    wiltingPoint: 17.5,
    availableWaterMmPerM: 135,
  },
  {
    id: 'arenoso',
    label: 'Arenoso (Dunas paleo eólicas de Charagua)',
    fieldCapacity: 12.0,
    wiltingPoint: 4.8,
    availableWaterMmPerM: 72,
  },
  {
    id: 'franco',
    label: 'Franco Equilibrado (Pie de Monte)',
    fieldCapacity: 24.0,
    wiltingPoint: 11.0,
    availableWaterMmPerM: 130,
  },
];

export const CORN_VARIETIES: CornVariety[] = [
  {
    id: 'chaco_01_criollo',
    name: 'Chaco 01 Criollo Blanco',
    cycleDays: 125,
    potentialYieldTnHa: 3.8,
    droughtResistance: 'Muy Alta',
    criticalStage: 'Floración (R1) - Alta rusticidad radicular',
  },
  {
    id: 'iniaf_h1',
    name: 'INIAF H1 Chaqueño',
    cycleDays: 120,
    potentialYieldTnHa: 5.4,
    droughtResistance: 'Alta',
    criticalStage: 'Espigamiento a llenado de grano (R1-R3)',
  },
  {
    id: 'dekalb_7088',
    name: 'Dekalb DKB 7088',
    cycleDays: 115,
    potentialYieldTnHa: 6.8,
    droughtResistance: 'Media',
    criticalStage: 'Panoja y fecundación',
  },
  {
    id: 'pioneer_30f35',
    name: 'Pioneer 30F35 VyR',
    cycleDays: 118,
    potentialYieldTnHa: 6.1,
    droughtResistance: 'Alta',
    criticalStage: 'Floración femenina (R1)',
  },
];

export function generateMockTimeline(days: number = 120, severityFactor: number = 1.0) {
  const points = [];
  let baseSoil = 22.0;

  for (let d = 1; d <= days; d++) {
    let stage = 'Emergencia (VE-V2)';
    let kc = 0.4;
    if (d > 15 && d <= 45) {
      stage = 'Desarrollo vegetativo (V6-V12)';
      kc = 0.75;
    } else if (d > 45 && d <= 68) {
      stage = 'Floración y Polinización (R1)';
      kc = 1.2;
    } else if (d > 68 && d <= 95) {
      stage = 'Llenado de Grano (R2-R4)';
      kc = 1.05;
    } else if (d > 95) {
      stage = 'Maduración Fisiológica (R6)';
      kc = 0.6;
    }

    const rainDays = [4, 18, 32, 60, 78];
    const rain = rainDays.includes(d) ? Number((Math.random() * 22 + 8).toFixed(1)) : 0;

    const et0 = Number((4.5 + Math.sin(d / 18) * 1.8 + Math.random() * 0.6).toFixed(2));
    const etPotential = Number((et0 * kc).toFixed(2));

    baseSoil = Math.max(6.5, Math.min(26.0, baseSoil + (rain * 0.4) - (etPotential * 0.28 * severityFactor)));
    
    // CWSI: 0 = sin estrés, 1 = estrés hídrico extremo
    const cwsi = Number(Math.min(1.0, Math.max(0.05, (1 - (baseSoil / 22.0)) * severityFactor + (Math.random() * 0.08 - 0.04))).toFixed(3));
    const etActual = Number(Math.max(0.8, etPotential * (1 - cwsi * 0.75)).toFixed(2));

    points.push({
      day: d,
      date: `Día ${d}`,
      phenologicalStage: stage,
      etActual,
      etPotential,
      cwsi,
      soilMoisture: Number(baseSoil.toFixed(1)),
      precipitation: rain,
    });
  }
  return points;
}

export function generateMockSpatialGrid(rows: number = 8, cols: number = 8, averageStress: number = 0.48) {
  const cells = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const gradient = ((r / rows) * 0.25) + ((c / cols) * 0.15);
      const noise = (Math.sin(r * 2.1) + Math.cos(c * 1.7)) * 0.12;
      const cwsi = Math.min(0.96, Math.max(0.08, averageStress + gradient + noise));
      const moisture = Math.max(7.0, Math.min(25.0, 24.0 - (cwsi * 17.0)));

      let riskLevel: 'bajo' | 'moderado' | 'severo' | 'critico' = 'bajo';
      if (cwsi >= 0.7) riskLevel = 'critico';
      else if (cwsi >= 0.5) riskLevel = 'severo';
      else if (cwsi >= 0.3) riskLevel = 'moderado';

      cells.push({
        x: c,
        y: r,
        moisture: Number(moisture.toFixed(1)),
        cwsi: Number(cwsi.toFixed(3)),
        riskLevel,
      });
    }
  }
  return cells;
}

export const INITIAL_SIMULATIONS: SimulationResult[] = [
  {
    id: 'SIM-GC-2026-001',
    config: {
      id: 'SIM-GC-2026-001',
      name: 'Sequía Extrema SSP585 - Villa Montes (Maíz Criollo)',
      zone: 'villamontes',
      zoneName: 'Villa Montes',
      department: 'Tarija',
      soilType: 'arenoso',
      cornVariety: 'chaco_01_criollo',
      plantingDate: '2026-11-15',
      simulationDays: 120,
      gridConfig: { rows: 250, cols: 250, cellSizeMeters: 50 },
      initialMoisturePercent: 14.5,
      droughtScenario: 'extremo_ssp585',
      engine: 'hibrido',
      nodesCount: 4,
      openmpThreads: 8,
      mpiProcesses: 4,
      createdAt: '2026-11-04 09:15',
    },
    status: 'completed',
    progressPercent: 100,
    currentDay: 120,
    createdAt: '2026-11-04 09:15',
    completedAt: '2026-11-04 09:17',
    executionTimeSeconds: 128.4,
    speedup: 14.64,
    efficiency: 91.5,
    averageCWSI: 0.642,
    soilMoistureFinalPercent: 9.8,
    yieldLossPercent: 38.6,
    estimatedYieldTnHa: 2.33,
    nominalYieldTnHa: 3.8,
    waterDeficitMm: 215.4,
    memoryUsageMb: 1420,
    timelineData: generateMockTimeline(120, 1.25),
    spatialGrid: generateMockSpatialGrid(8, 8, 0.64),
    logs: [
      { timestamp: '09:15:01', level: 'MPI', message: 'MPI_Init iniciado con 4 procesos en nodos chaco-node-[01..04]' },
      { timestamp: '09:15:02', level: 'OMP', message: 'OpenMP thread binding completado: 8 threads por proceso (32 cores totales)' },
      { timestamp: '09:15:04', level: 'INFO', message: 'Malla espacial 250x250 descompuesta en dominios 2D cartesianos' },
      { timestamp: '09:15:45', level: 'INFO', message: 'Iteración Día 60 (R1 Floración): Estrés severo detectado en subcuadrante Este' },
      { timestamp: '09:17:09', level: 'INFO', message: 'Simulación finalizada. Convergencia de balance hídrico exitosa.' },
    ],
  },
  {
    id: 'SIM-GC-2026-002',
    config: {
      id: 'SIM-GC-2026-002',
      name: 'Evaluación Híbrido INIAF H1 en Yacuiba (Transición Hídrica)',
      zone: 'yacuiba',
      zoneName: 'Yacuiba',
      department: 'Tarija',
      soilType: 'franco_arenoso',
      cornVariety: 'iniaf_h1',
      plantingDate: '2026-11-20',
      simulationDays: 120,
      gridConfig: { rows: 200, cols: 200, cellSizeMeters: 50 },
      initialMoisturePercent: 18.2,
      droughtScenario: 'moderado_ssp245',
      engine: 'openmp',
      openmpThreads: 8,
      createdAt: '2026-11-04 14:30',
    },
    status: 'completed',
    progressPercent: 100,
    currentDay: 120,
    createdAt: '2026-11-04 14:30',
    completedAt: '2026-11-04 14:36',
    executionTimeSeconds: 312.8,
    speedup: 6.66,
    efficiency: 83.3,
    averageCWSI: 0.428,
    soilMoistureFinalPercent: 14.2,
    yieldLossPercent: 21.4,
    estimatedYieldTnHa: 4.24,
    nominalYieldTnHa: 5.4,
    waterDeficitMm: 142.1,
    memoryUsageMb: 890,
    timelineData: generateMockTimeline(120, 0.85),
    spatialGrid: generateMockSpatialGrid(8, 8, 0.43),
    logs: [
      { timestamp: '14:30:00', level: 'OMP', message: 'Iniciando OpenMP paralelo con 8 núcleos locales' },
      { timestamp: '14:32:10', level: 'INFO', message: 'Modelo FAO-56 Penman-Monteith calculando evapotranspiración' },
      { timestamp: '14:35:12', level: 'INFO', message: 'Finalizando pasos temporales para 120 días' },
    ],
  },
  {
    id: 'SIM-GC-2026-003',
    config: {
      id: 'SIM-GC-2026-003',
      name: 'Simulación Distribuida MPI - Charagua Iyambae (Sequía 2023)',
      zone: 'charagua',
      zoneName: 'Charagua Iyambae',
      department: 'Santa Cruz',
      soilType: 'franco_arcilloso',
      cornVariety: 'dekalb_7088',
      plantingDate: '2026-12-01',
      simulationDays: 115,
      gridConfig: { rows: 300, cols: 300, cellSizeMeters: 50 },
      initialMoisturePercent: 16.0,
      droughtScenario: 'sequia_recente_2023',
      engine: 'mpi',
      nodesCount: 4,
      mpiProcesses: 16,
      createdAt: '2026-11-05 08:20',
    },
    status: 'running',
    progressPercent: 68,
    currentDay: 78,
    createdAt: '2026-11-05 08:20',
    executionTimeSeconds: 18.5,
    speedup: 12.78,
    efficiency: 79.9,
    averageCWSI: 0.584,
    soilMoistureFinalPercent: 11.4,
    yieldLossPercent: 32.8,
    estimatedYieldTnHa: 4.56,
    nominalYieldTnHa: 6.8,
    waterDeficitMm: 188.5,
    memoryUsageMb: 2150,
    timelineData: generateMockTimeline(78, 1.1),
    spatialGrid: generateMockSpatialGrid(8, 8, 0.58),
    logs: [
      { timestamp: '08:20:00', level: 'MPI', message: 'mpirun -np 16 --hostfile cluster_hosts ./agrochaco_mpi' },
      { timestamp: '08:20:02', level: 'MPI', message: 'Halo exchange bidireccional establecido (Ghost cells = 2)' },
      { timestamp: '08:20:10', level: 'INFO', message: 'Paso 78/115: Etapa R3 (Llenado lechoso). Computando difusión hídrica' },
    ],
  },
  {
    id: 'SIM-GC-2026-004',
    config: {
      id: 'SIM-GC-2026-004',
      name: 'Baseline Secuencial - Calibración Macharetí',
      zone: 'machareti',
      zoneName: 'Macharetí',
      department: 'Chuquisaca',
      soilType: 'franco_arenoso',
      cornVariety: 'chaco_01_criollo',
      plantingDate: '2026-11-10',
      simulationDays: 120,
      gridConfig: { rows: 100, cols: 100, cellSizeMeters: 50 },
      initialMoisturePercent: 12.0,
      droughtScenario: 'historico',
      engine: 'secuencial',
      createdAt: '2026-11-03 16:45',
    },
    status: 'completed',
    progressPercent: 100,
    currentDay: 120,
    createdAt: '2026-11-03 16:45',
    completedAt: '2026-11-03 16:51',
    executionTimeSeconds: 342.5,
    speedup: 1.0,
    efficiency: 100.0,
    averageCWSI: 0.695,
    soilMoistureFinalPercent: 8.6,
    yieldLossPercent: 44.2,
    estimatedYieldTnHa: 2.12,
    nominalYieldTnHa: 3.8,
    waterDeficitMm: 238.0,
    memoryUsageMb: 240,
    timelineData: generateMockTimeline(120, 1.35),
    spatialGrid: generateMockSpatialGrid(8, 8, 0.70),
    logs: [
      { timestamp: '16:45:00', level: 'INFO', message: 'Ejecución mono-hilo secuencial iniciada para línea base' },
      { timestamp: '16:50:42', level: 'INFO', message: 'Tiempo total secuencial de referencia T1 = 342.5 segundos' },
    ],
  },
];

export const HPC_BENCHMARK_DATA: HPCBenchmarkRecord[] = [
  {
    engine: 'secuencial',
    label: 'Secuencial Mono-núcleo (Baseline)',
    coresOrProcesses: 1,
    nodes: 1,
    executionTimeSeconds: 342.5,
    speedup: 1.0,
    efficiencyPercent: 100.0,
    computationTimeSec: 338.2,
    communicationTimeSec: 0.0,
    memoryMb: 240,
    gflopsEstimate: 2.4,
  },
  {
    engine: 'openmp',
    label: 'OpenMP (2 hilos compartidos)',
    coresOrProcesses: 2,
    nodes: 1,
    executionTimeSeconds: 176.2,
    speedup: 1.94,
    efficiencyPercent: 97.2,
    computationTimeSec: 172.5,
    communicationTimeSec: 3.7,
    memoryMb: 310,
    gflopsEstimate: 4.6,
  },
  {
    engine: 'openmp',
    label: 'OpenMP (4 hilos compartidos)',
    coresOrProcesses: 4,
    nodes: 1,
    executionTimeSeconds: 91.8,
    speedup: 3.73,
    efficiencyPercent: 93.3,
    computationTimeSec: 87.4,
    communicationTimeSec: 4.4,
    memoryMb: 460,
    gflopsEstimate: 8.9,
  },
  {
    engine: 'openmp',
    label: 'OpenMP (8 hilos compartidos)',
    coresOrProcesses: 8,
    nodes: 1,
    executionTimeSeconds: 51.4,
    speedup: 6.66,
    efficiencyPercent: 83.3,
    computationTimeSec: 45.1,
    communicationTimeSec: 6.3,
    memoryMb: 680,
    gflopsEstimate: 15.8,
  },
  {
    engine: 'openmp',
    label: 'OpenMP (16 hilos compartidos)',
    coresOrProcesses: 16,
    nodes: 1,
    executionTimeSeconds: 34.1,
    speedup: 10.04,
    efficiencyPercent: 62.8,
    computationTimeSec: 26.8,
    communicationTimeSec: 7.3,
    memoryMb: 1120,
    gflopsEstimate: 23.9,
  },
  {
    engine: 'mpi',
    label: 'MPI Distribuido (2 procesos)',
    coresOrProcesses: 2,
    nodes: 1,
    executionTimeSeconds: 181.0,
    speedup: 1.89,
    efficiencyPercent: 94.6,
    computationTimeSec: 174.0,
    communicationTimeSec: 7.0,
    memoryMb: 360,
    gflopsEstimate: 4.5,
  },
  {
    engine: 'mpi',
    label: 'MPI Distribuido (4 procesos en 2 nodos)',
    coresOrProcesses: 4,
    nodes: 2,
    executionTimeSeconds: 94.5,
    speedup: 3.62,
    efficiencyPercent: 90.6,
    computationTimeSec: 86.8,
    communicationTimeSec: 7.7,
    memoryMb: 580,
    gflopsEstimate: 8.6,
  },
  {
    engine: 'mpi',
    label: 'MPI Distribuido (8 procesos en 2 nodos)',
    coresOrProcesses: 8,
    nodes: 2,
    executionTimeSeconds: 48.2,
    speedup: 7.11,
    efficiencyPercent: 88.8,
    computationTimeSec: 39.5,
    communicationTimeSec: 8.7,
    memoryMb: 920,
    gflopsEstimate: 16.9,
  },
  {
    engine: 'mpi',
    label: 'MPI Distribuido (16 procesos en 4 nodos)',
    coresOrProcesses: 16,
    nodes: 4,
    executionTimeSeconds: 26.8,
    speedup: 12.78,
    efficiencyPercent: 79.9,
    computationTimeSec: 17.6,
    communicationTimeSec: 9.2,
    memoryMb: 1540,
    gflopsEstimate: 30.4,
  },
  {
    engine: 'hibrido',
    label: 'Híbrido (2 nodos × 4 hilos OMP = 8 cores)',
    coresOrProcesses: 8,
    nodes: 2,
    executionTimeSeconds: 45.1,
    speedup: 7.59,
    efficiencyPercent: 94.9,
    computationTimeSec: 41.2,
    communicationTimeSec: 3.9,
    memoryMb: 850,
    gflopsEstimate: 18.0,
  },
  {
    engine: 'hibrido',
    label: 'Híbrido (4 nodos × 4 hilos OMP = 16 cores)',
    coresOrProcesses: 16,
    nodes: 4,
    executionTimeSeconds: 23.4,
    speedup: 14.64,
    efficiencyPercent: 91.5,
    computationTimeSec: 18.8,
    communicationTimeSec: 4.6,
    memoryMb: 1420,
    gflopsEstimate: 34.8,
  },
  {
    engine: 'hibrido',
    label: 'Híbrido (4 nodos × 8 hilos OMP = 32 cores)',
    coresOrProcesses: 32,
    nodes: 4,
    executionTimeSeconds: 13.2,
    speedup: 25.95,
    efficiencyPercent: 81.1,
    computationTimeSec: 8.9,
    communicationTimeSec: 4.3,
    memoryMb: 2350,
    gflopsEstimate: 61.6,
  },
];

export const STRONG_SCALING_CURVES: StrongScalingPoint[] = [
  { workers: 1, idealSpeedup: 1.0, secuencialSpeedup: 1.0, openmpSpeedup: 1.0, mpiSpeedup: 1.0, hibridoSpeedup: 1.0 },
  { workers: 2, idealSpeedup: 2.0, secuencialSpeedup: 1.0, openmpSpeedup: 1.94, mpiSpeedup: 1.89, hibridoSpeedup: 1.96 },
  { workers: 4, idealSpeedup: 4.0, secuencialSpeedup: 1.0, openmpSpeedup: 3.73, mpiSpeedup: 3.62, hibridoSpeedup: 3.85 },
  { workers: 8, idealSpeedup: 8.0, secuencialSpeedup: 1.0, openmpSpeedup: 6.66, mpiSpeedup: 7.11, hibridoSpeedup: 7.59 },
  { workers: 16, idealSpeedup: 16.0, secuencialSpeedup: 1.0, openmpSpeedup: 10.04, mpiSpeedup: 12.78, hibridoSpeedup: 14.64 },
  { workers: 32, idealSpeedup: 32.0, secuencialSpeedup: 1.0, openmpSpeedup: 13.2, mpiSpeedup: 20.8, hibridoSpeedup: 25.95 },
];

export const SCIENTIFIC_CONSTANTS = {
  fao56Description: 'Ecuación de Penman-Monteith (FAO-56) para evapotranspiración de referencia (ET0) diaria calculada con radiación neta, velocidad de viento a 2m, temperatura media y presión de vapor.',
  cwsiFormula: 'CWSI = 1 - (ET_actual / ET_potencial) = (dT - dT_lleno) / (dT_seco - dT_lleno)',
  cornKcStages: [
    { stage: 'Inicial (VE - V2)', durationDays: 20, kc: 0.40 },
    { stage: 'Desarrollo (V3 - V12)', durationDays: 35, kc: 0.80 },
    { stage: 'Media estación / Floración (R1 - R2)', durationDays: 40, kc: 1.20 },
    { stage: 'Fin de estación / Maduración (R3 - R6)', durationDays: 25, kc: 0.60 },
  ],
  clusterNodes: [
    { name: 'chaco-master', ip: '192.168.10.1', role: 'Head Node / Slurm Controller', cores: 16, ramGb: 64, status: 'Online' },
    { name: 'chaco-node-01', ip: '192.168.10.2', role: 'Worker MPI / OMP', cores: 32, ramGb: 128, status: 'Online' },
    { name: 'chaco-node-02', ip: '192.168.10.3', role: 'Worker MPI / OMP', cores: 32, ramGb: 128, status: 'Online' },
    { name: 'chaco-node-03', ip: '192.168.10.4', role: 'Worker MPI / OMP', cores: 32, ramGb: 128, status: 'Online' },
    { name: 'chaco-node-04', ip: '192.168.10.5', role: 'Worker MPI / OMP', cores: 32, ramGb: 128, status: 'Online' },
  ],
};
