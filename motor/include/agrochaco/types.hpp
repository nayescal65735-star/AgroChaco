#ifndef AGROCHACO_TYPES_HPP
#define AGROCHACO_TYPES_HPP

#include <string>
#include <vector>
#include <optional>
#include <stdexcept>

namespace agrochaco {

enum class GranChacoZoneId {
    YACUIBA,
    VILLAMONTES,
    CARAPARI,
    CHARAGUA,
    MACHARETI,
    BOYUIBE
};

enum class SoilType {
    FRANCO_ARENOSO,
    FRANCO_ARCILLOSO,
    ARENOSO,
    FRANCO
};

enum class CornVarietyId {
    CHACO_01_CRIOLLO,
    DEKALB_7088,
    INIAF_H1,
    PIONEER_30F35
};

enum class DroughtScenario {
    HISTORICO,
    MODERADO_SSP245,
    EXTREMO_SSP585,
    SEQUIA_RECENTE_2023
};

enum class SimulationEngine {
    SECUENCIAL,
    OPENMP,
    MPI,
    HIBRIDO
};

enum class RiskLevel {
    BAJO,
    MODERADO,
    SEVERO,
    CRITICO
};

enum class LogLevel {
    INFO,
    MPI,
    OMP,
    WARN,
    ERROR
};

// Funciones de conversión a cadena y viceversa
std::string zoneToString(GranChacoZoneId zone);
GranChacoZoneId stringToZone(const std::string& str);

std::string soilToString(SoilType soil);
SoilType stringToSoil(const std::string& str);

std::string varietyToString(CornVarietyId variety);
CornVarietyId stringToVariety(const std::string& str);

std::string scenarioToString(DroughtScenario scenario);
DroughtScenario stringToScenario(const std::string& str);

std::string engineToString(SimulationEngine engine);
SimulationEngine stringToEngine(const std::string& str);

std::string riskLevelToString(RiskLevel risk);
RiskLevel calculateRiskLevel(double cwsi);

std::string logLevelToString(LogLevel level);

// Estructuras de datos astronómicas y edafológicas de referencia
struct GranChacoZoneInfo {
    GranChacoZoneId id;
    std::string name;
    std::string department;
    double latitude;
    double longitude;
    double annualRainfallMm;
    std::string soilDefault;
    std::string currentRisk;
    double activeHectares;
    double averageTempC;
};

struct SoilInfo {
    SoilType id;
    std::string label;
    double fieldCapacity;       // Capacidad de campo (%)
    double wiltingPoint;        // Punto de marchitez permanente (%)
    double availableWaterMmPerM;// Agua útil (mm/m)
};

struct CornVarietyInfo {
    CornVarietyId id;
    std::string name;
    int cycleDays;
    double potentialYieldTnHa;
    std::string droughtResistance;
    std::string criticalStage;
};

// Configuración de la malla espacial
struct GridConfig {
    int rows{10};
    int cols{10};
    double cellSizeMeters{50.0};
};

// Configuración completa de la simulación recibida
struct SimulationConfig {
    std::string id{"SIM-GC-DEFAULT"};
    std::string name{"Simulación AgroChaco"};
    std::string description{""};
    GranChacoZoneId zone{GranChacoZoneId::VILLAMONTES};
    std::string zoneName{"Villa Montes"};
    std::string department{"Tarija"};
    SoilType soilType{SoilType::ARENOSO};
    CornVarietyId cornVariety{CornVarietyId::CHACO_01_CRIOLLO};
    std::string plantingDate{"2026-11-15"};
    int simulationDays{120};
    GridConfig gridConfig;
    double initialMoisturePercent{14.5};
    DroughtScenario droughtScenario{DroughtScenario::EXTREMO_SSP585};
    SimulationEngine engine{SimulationEngine::SECUENCIAL};
    std::optional<int> openmpThreads;
    std::optional<int> mpiProcesses;
    std::optional<int> nodesCount;
    std::string createdAt{""};
};

// Punto de la serie temporal (resultado diario agregado)
struct TimelineDataPoint {
    int day{0};
    std::string date{""};
    std::string phenologicalStage{""};
    double etActual{0.0};       // mm/día
    double etPotential{0.0};    // mm/día
    double cwsi{0.0};           // Crop Water Stress Index [0, 1]
    double soilMoisture{0.0};   // % volumétrico
    double precipitation{0.0};  // mm/día
};

// Celda espacial resultante para el mapa de calor
struct SpatialCell {
    int x{0};
    int y{0};
    double moisture{0.0};
    double cwsi{0.0};
    RiskLevel riskLevel{RiskLevel::BAJO};
};

// Registro de log emitido durante la simulación
struct SimulationLog {
    std::string timestamp{""};
    LogLevel level{LogLevel::INFO};
    std::string message{""};
};

// Métricas de desempeño HPC
struct HPCMetrics {
    double executionTimeSeconds{0.0};
    double computationTimeSeconds{0.0};
    double communicationTimeSeconds{0.0};
    double speedup{1.0};
    double efficiencyPercent{100.0};
    double memoryUsageMb{0.0};
    double gflopsEstimate{0.0};
};

// Resultado integral estructurado
struct SimulationResult {
    std::string id{""};
    SimulationConfig config;
    std::string status{"completed"};
    int progressPercent{100};
    int currentDay{120};
    std::string createdAt{""};
    std::string completedAt{""};
    double executionTimeSeconds{0.0};
    double speedup{1.0};
    double efficiency{100.0};
    double averageCWSI{0.0};
    double soilMoistureFinalPercent{0.0};
    double yieldLossPercent{0.0};
    double estimatedYieldTnHa{0.0};
    double nominalYieldTnHa{0.0};
    double waterDeficitMm{0.0};
    double memoryUsageMb{0.0};
    std::vector<TimelineDataPoint> timelineData;
    std::vector<SpatialCell> spatialGrid;
    std::vector<SimulationLog> logs;
};

} // namespace agrochaco

#endif // AGROCHACO_TYPES_HPP
