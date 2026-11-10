#include "agrochaco/simulation_engine.hpp"
#include <omp.h>
#include "agrochaco/agronomic_data.hpp"
#include "agrochaco/soil_model.hpp"
#include "agrochaco/crop_model.hpp"
#include "agrochaco/grid.hpp"
#include "agrochaco/metrics.hpp"
#include "agrochaco/config.hpp"
#include <cmath>
#include <iomanip>
#include <sstream>
#include <ctime>

namespace agrochaco {

static std::string getCurrentIsoTimestamp() {
    auto now = std::chrono::system_clock::now();
    std::time_t t = std::chrono::system_clock::to_time_t(now);
    std::tm tmNow;
    localtime_r(&t, &tmNow);

    std::ostringstream ss;
    ss << std::put_time(&tmNow, "%Y-%m-%d %H:%M:%S");
    return ss.str();
}

static std::string getTimeOnly() {
    auto now = std::chrono::system_clock::now();
    std::time_t t = std::chrono::system_clock::to_time_t(now);
    std::tm tmNow;
    localtime_r(&t, &tmNow);

    std::ostringstream ss;
    ss << std::put_time(&tmNow, "%H:%M:%S");
    return ss.str();
}

OpenMPEngine::OpenMPEngine(SimulationConfig config)
    : config_(std::move(config)) {}

void OpenMPEngine::log(std::vector<SimulationLog>& logs, LogLevel level, const std::string& message) {
    SimulationLog entry;
    entry.timestamp = getTimeOnly();
    entry.level = level;
    entry.message = message;
    logs.push_back(entry);
}

SimulationResult OpenMPEngine::run() {
    ExecutionTimer timer;
    timer.start();

    omp_set_dynamic(0);
    const int requestedThreads = config_.openmpThreads.value_or(omp_get_max_threads());
    const int threadCount = requestedThreads > 0 ? requestedThreads : 1;
    omp_set_num_threads(threadCount);

    SimulationResult result;
    result.id = config_.id;
    result.config = config_;
    result.config.engine = SimulationEngine::OPENMP;
    result.config.openmpThreads = threadCount;
    result.status = "running";
    result.progressPercent = 0;
    result.currentDay = 0;
    result.createdAt = config_.createdAt.empty() ? getCurrentIsoTimestamp() : config_.createdAt;

    log(result.logs, LogLevel::INFO, "Iniciando motor paralelo AgroChaco con OpenMP");

    // 1. Validación de consistencia de configuración
    std::vector<std::string> errors;
    if (!ConfigValidator::validate(config_, errors)) {
        log(result.logs, LogLevel::ERROR, "Fallo de validación en parámetros de configuración");
        for (const auto& err : errors) {
            log(result.logs, LogLevel::ERROR, err);
        }
        result.status = "failed";
        timer.stop();
        result.executionTimeSeconds = timer.getElapsedSeconds();
        result.completedAt = getCurrentIsoTimestamp();
        return result;
    }

    // 2. Carga de parámetros agronómicos y edáficos de referencia
    const auto& zone = AgronomicData::getZone(config_.zone);
    const auto& soil = AgronomicData::getSoil(config_.soilType);
    const auto& variety = AgronomicData::getCornVariety(config_.cornVariety);

    result.nominalYieldTnHa = variety.potentialYieldTnHa;

    log(result.logs, LogLevel::INFO, "Zona seleccionada: " + zone.name + " (" + zone.department + ") | Temp base: " + std::to_string(zone.averageTempC) + " °C");
    log(result.logs, LogLevel::INFO, "Suelo: " + soil.label + " | CC: " + std::to_string(soil.fieldCapacity) + "% | PMP: " + std::to_string(soil.wiltingPoint) + "%");
    log(result.logs, LogLevel::INFO, "Variedad: " + variety.name + " | Ciclo: " + std::to_string(variety.cycleDays) + " días | Rend. pot: " + std::to_string(variety.potentialYieldTnHa) + " tn/ha");
    log(result.logs, LogLevel::INFO, "Malla espacial 2D: " + std::to_string(config_.gridConfig.rows) + "x" + std::to_string(config_.gridConfig.cols) + " (" + std::to_string(config_.gridConfig.rows * config_.gridConfig.cols) + " celdas)");

    // 3. Inicialización de la malla espacial
    SpatialGrid grid(
        config_.gridConfig.rows,
        config_.gridConfig.cols,
        config_.gridConfig.cellSizeMeters,
        config_.initialMoisturePercent,
        soil
    );

    // 4. Bucle temporal diario
    double totalEtc = 0.0;
    double totalEta = 0.0;
    double totalCwsi = 0.0;
    double totalDeficitMm = 0.0;
    SpatialGrid::StepSummary lastSummary{};

    // Acumuladores de demanda y consumo por etapa fenológica para el modelo aditivo FAO-33
    std::vector<double> stageEtc(5, 0.0);
    std::vector<double> stageEta(5, 0.0);
    std::vector<double> stageKy(5, 0.0);

    result.timelineData.reserve(config_.simulationDays);

    for (int day = 1; day <= config_.simulationDays; ++day) {
        // Fenología y requerimientos
        auto pheno = AgronomicData::getPhenology(day, variety.cycleDays);
        auto climate = AgronomicData::getDailyClimate(day, config_.zone, config_.droughtScenario);
        double rootDepth = CropModel::calculateRootDepth(day, variety.cycleDays);
        double etc = CropModel::calculateEtc(climate.et0, pheno.kc);

        // Actualización espacial celda por celda con precipitación uniforme y conservación de masa
        lastSummary = grid.updateDailyStepOpenMP(soil, etc, climate.precipitation, rootDepth);

        // Acumulación de estadísticas estacionales y por etapa fenológica
        totalEtc += lastSummary.averageEtPotential;
        totalEta += lastSummary.averageEtActual;
        totalCwsi += lastSummary.averageCwsi;
        totalDeficitMm += std::max(0.0, lastSummary.averageEtPotential - lastSummary.averageEtActual);

        int sIdx = std::clamp(pheno.stageIndex, 0, 4);
        stageEtc[sIdx] += lastSummary.averageEtPotential;
        stageEta[sIdx] += lastSummary.averageEtActual;
        stageKy[sIdx] = pheno.ky;

        // Registro en la serie temporal
        TimelineDataPoint point;
        point.day = day;
        point.date = "Día " + std::to_string(day);
        point.phenologicalStage = pheno.stageName;
        point.etActual = std::round(lastSummary.averageEtActual * 100.0) / 100.0;
        point.etPotential = std::round(lastSummary.averageEtPotential * 100.0) / 100.0;
        point.cwsi = std::round(lastSummary.averageCwsi * 1000.0) / 1000.0;
        point.soilMoisture = std::round(lastSummary.averageMoisture * 10.0) / 10.0;
        point.precipitation = std::round(lastSummary.averagePrecipitation * 10.0) / 10.0;

        result.timelineData.push_back(point);

        if (pheno.isCritical && day == (variety.cycleDays / 2)) {
            log(result.logs, LogLevel::INFO, "Paso Día " + std::to_string(day) + " (Etapa Crítica R1 Floración): CWSI promedio = " + std::to_string(point.cwsi));
        }

        if (progressCallback_) {
            progressCallback_(day, config_.simulationDays, lastSummary.averageCwsi);
        }
    }

    timer.stop();

    // 5. Consolidación de resultados (Modelo FAO-33 sin ponderaciones heurísticas)
    double avgCwsi = (config_.simulationDays > 0) ? (totalCwsi / config_.simulationDays) : 0.0;
    double yieldLoss = CropModel::calculateYieldLoss(stageEtc, stageEta, stageKy, variety);
    double estimatedYield = std::max(0.0, variety.potentialYieldTnHa * (1.0 - yieldLoss / 100.0));

    result.status = "completed";
    result.progressPercent = 100;
    result.currentDay = config_.simulationDays;
    result.completedAt = getCurrentIsoTimestamp();
    result.executionTimeSeconds = timer.getElapsedSeconds();
    // Se calcularán al comparar contra la ejecución secuencial T1.
    result.speedup = 0.0;
    result.efficiency = 0.0;
    result.averageCWSI = std::round(avgCwsi * 1000.0) / 1000.0;
    result.soilMoistureFinalPercent = std::round(lastSummary.averageMoisture * 10.0) / 10.0;
    result.yieldLossPercent = std::round(yieldLoss * 10.0) / 10.0;
    result.estimatedYieldTnHa = std::round(estimatedYield * 100.0) / 100.0;
    result.waterDeficitMm = std::round(totalDeficitMm * 10.0) / 10.0;
    result.memoryUsageMb = std::round(ExecutionTimer::getCurrentMemoryUsageMb() * 10.0) / 10.0;

    // Exportar la matriz espacial resumida de 8x8 para el mapa de calor
    result.spatialGrid = grid.exportVisualizationGrid(8, 8);

    log(result.logs, LogLevel::INFO, "Simulación OpenMP concluida con éxito en " + std::to_string(result.executionTimeSeconds) + " s");
    log(result.logs, LogLevel::INFO, "CWSI estacional promedio: " + std::to_string(result.averageCWSI) + " | Pérdida estimada de rendimiento: " + std::to_string(result.yieldLossPercent) + "%");

    return result;
}

} // namespace agrochaco
