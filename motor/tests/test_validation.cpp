#include "agrochaco/types.hpp"
#include "agrochaco/config.hpp"
#include "agrochaco/agronomic_data.hpp"
#include "agrochaco/soil_model.hpp"
#include "agrochaco/crop_model.hpp"
#include "agrochaco/grid.hpp"
#include "agrochaco/water_balance.hpp"
#include "agrochaco/simulation_engine.hpp"
#include "agrochaco/json_serializer.hpp"
#include <mpi.h>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <cmath>
#include <exception>
#include <limits>
#include <string>
#include <vector>

using namespace agrochaco;

static int g_testFailures = 0;

#define REQUIRE(condition)                                                              \
    do {                                                                               \
        if (!(condition)) {                                                            \
            std::cerr << "FAIL " << __FILE__ << ":" << __LINE__ << ": " #condition "\n"; \
            ++g_testFailures;                                                          \
        }                                                                              \
    } while (false)

static void runTest(const char* name, void (*test)()) {
    try {
        test();
    } catch (const std::exception& e) {
        std::cerr << "FAIL " << name << ": excepción inesperada: " << e.what() << "\n";
        ++g_testFailures;
    }
}

// 1. Validación de rechazo de parámetros inválidos
void testValidationRejectsInvalidParameters() {
    std::cout << "[TEST 1/37] Ejecutando: testValidationRejectsInvalidParameters...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    std::vector<std::string> errors;

    REQUIRE(ConfigValidator::validate(cfg, errors) == true);
    REQUIRE(errors.empty());

    // Filas inválidas (<= 0)
    cfg.gridConfig.rows = 0;
    REQUIRE(ConfigValidator::validate(cfg, errors) == false);
    cfg.gridConfig.rows = 20;

    // Columnas inválidas (< 0)
    cfg.gridConfig.cols = -5;
    REQUIRE(ConfigValidator::validate(cfg, errors) == false);
    cfg.gridConfig.cols = 20;

    // Tamaño de celda inválido (<= 0)
    cfg.gridConfig.cellSizeMeters = -10.0;
    REQUIRE(ConfigValidator::validate(cfg, errors) == false);
    cfg.gridConfig.cellSizeMeters = 50.0;

    // Días de simulación inválidos (0 y > 365)
    cfg.simulationDays = 0;
    REQUIRE(ConfigValidator::validate(cfg, errors) == false);
    cfg.simulationDays = 400;
    REQUIRE(ConfigValidator::validate(cfg, errors) == false);
    cfg.simulationDays = 120;

    // Humedad inicial fuera de rango (< 0% o > 100%)
    cfg.initialMoisturePercent = -2.0;
    REQUIRE(ConfigValidator::validate(cfg, errors) == false);
    cfg.initialMoisturePercent = 105.0;
    REQUIRE(ConfigValidator::validate(cfg, errors) == false);
    cfg.initialMoisturePercent = 8.4;

    std::cout << "  -> PASÓ: Parámetros inválidos rechazados correctamente con mensajes explicativos.\n";
}

// 2. Conservación estricta de masa de agua (Celda y Malla 2D)
void testWaterMassConservation() {
    std::cout << "[TEST 2/37] Ejecutando: testWaterMassConservation...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::FRANCO_ARENOSO);

    // Caso A: Celda individual con lluvia moderada
    double initMoist = 12.0; // %
    double rain = 25.0;      // mm
    double etDemand = 4.5;   // mm
    double depth = 0.60;     // m

    auto cellRes = SoilModel::updateCellMoisture(initMoist, soil, etDemand, rain, depth);
    // Identidad de balance: DeltaAlmacenamiento + ETa + Drenaje == Precipitación
    double massBalanceSum = cellRes.deltaStorageMm + cellRes.etActual + cellRes.deepDrainage;
    REQUIRE(std::abs(massBalanceSum - rain) < 1e-11);
    REQUIRE(cellRes.massBalanceError < 1e-11);

    // Caso B: Malla 2D completa con precipitación uniforme
    SpatialGrid grid(10, 10, 50.0, 14.0, soil);
    auto stepSummary = grid.updateDailyStep(soil, 5.0, 18.0, 0.70);

    double gridMassSum = stepSummary.averageDeltaStorage + stepSummary.averageEtActual + stepSummary.averageDeepDrainage;
    REQUIRE(std::abs(gridMassSum - stepSummary.averagePrecipitation) < 1e-11);
    REQUIRE(stepSummary.massBalanceError < 1e-11);

    std::cout << "  -> PASÓ: Conservación estricta de masa hidrológica verificada (error < 1e-11 mm).\n";
}

// 3. Día sin precipitación
void testNoPrecipitationDay() {
    std::cout << "[TEST 3/37] Ejecutando: testNoPrecipitationDay...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::FRANCO_ARCILLOSO);
    double initMoist = 25.0; // Entre WP (17.5) y FC (31.0)
    double rain = 0.0;
    double etDemand = 5.0;
    double depth = 0.50;

    auto cellRes = SoilModel::updateCellMoisture(initMoist, soil, etDemand, rain, depth);

    // Sin lluvia: el agua final debe ser estrictamente menor a la inicial (disminuye por ETa)
    REQUIRE(cellRes.finalWaterMm < cellRes.initialWaterMm);
    REQUIRE(cellRes.deepDrainage == 0.0);
    REQUIRE(cellRes.etActual > 0.0);
    // DeltaStorage es negativo: |DeltaStorage| == ETa
    REQUIRE(std::abs(cellRes.deltaStorageMm + cellRes.etActual) < 1e-11);

    std::cout << "  -> PASÓ: Día seco modela correctamente la extracción pura sin drenaje gravitacional.\n";
}

// 4. Lluvia extrema y saturación (Drenaje de exceso)
void testExtremeRainfall() {
    std::cout << "[TEST 4/37] Ejecutando: testExtremeRainfall...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::ARENOSO); // FC=12.0%, WP=4.8%
    double initMoist = 10.0;
    double extremeRain = 150.0; // mm de lluvia torrencial
    double depth = 0.50;        // 500 mm suelo -> FC = 60 mm agua
    double etDemand = 2.0;

    auto cellRes = SoilModel::updateCellMoisture(initMoist, soil, etDemand, extremeRain, depth);

    // El almacenamiento debe saturar y evacuar el excedente por encima de FC
    double waterMaxMm = (soil.fieldCapacity / 100.0) * (depth * 1000.0);
    REQUIRE(cellRes.deepDrainage > 0.0);
    REQUIRE(cellRes.finalWaterMm <= waterMaxMm);
    // La humedad resultante debe ser muy cercana a FC
    REQUIRE(cellRes.updatedMoisturePercent <= soil.fieldCapacity);
    // La masa se conserva exactamente
    double massSum = cellRes.deltaStorageMm + cellRes.etActual + cellRes.deepDrainage;
    REQUIRE(std::abs(massSum - extremeRain) < 1e-11);

    std::cout << "  -> PASÓ: Lluvia extrema de 150 mm satura el suelo y drena el exceso conservando la masa.\n";
}

// 5. Demanda ETc igual a cero (Evitar división por cero y NaN)
void testZeroEtcHandling() {
    std::cout << "[TEST 5/37] Ejecutando: testZeroEtcHandling...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::FRANCO);

    // ETc = 0.0
    auto cellRes = SoilModel::updateCellMoisture(20.0, soil, 0.0, 10.0, 0.50);

    REQUIRE(!std::isnan(cellRes.cwsi));
    REQUIRE(!std::isinf(cellRes.cwsi));
    REQUIRE(cellRes.cwsi == 0.0);
    REQUIRE(cellRes.etActual == 0.0);
    REQUIRE(cellRes.deficitMm == 0.0);

    // CropModel con et0 = 0
    double etc = CropModel::calculateEtc(0.0, 1.20);
    REQUIRE(etc == 0.0);

    std::cout << "  -> PASÓ: Demanda nula (ETc = 0) no genera NaN, división por cero ni errores numéricos.\n";
}

// 6. Sequía prolongada y convergencia hacia el PMP
void testProlongedDroughtAndPmpConvergence() {
    std::cout << "[TEST 6/37] Ejecutando: testProlongedDroughtAndPmpConvergence...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::ARENOSO); // FC=12.0%, WP=4.8%
    double moisture = soil.fieldCapacity;
    double depth = 0.80;
    double dailyEtc = 5.0;

    // Simular 100 días continuos sin una gota de lluvia
    for (int day = 1; day <= 100; ++day) {
        auto res = SoilModel::updateCellMoisture(moisture, soil, dailyEtc, 0.0, depth);
        moisture = res.updatedMoisturePercent;
        REQUIRE(!std::isnan(moisture));
        // La humedad NUNCA debe caer por debajo de PMP por transpiración vegetal
        REQUIRE(moisture >= soil.wiltingPoint - 1e-9);
    }

    // Al final de una sequía extrema prolongada, la humedad debe estabilizarse en PMP y CWSI en 1.0
    REQUIRE(std::abs(moisture - soil.wiltingPoint) < 0.10);
    auto finalStep = SoilModel::updateCellMoisture(moisture, soil, dailyEtc, 0.0, depth);
    REQUIRE(finalStep.etActual < 0.01); // El cultivo ya no puede extraer agua
    REQUIRE(std::abs(finalStep.cwsi - 1.0) < 1e-4); // Estrés hídrico total (CWSI = 1.0)

    std::cout << "  -> PASÓ: Sequía continua de 100 días converge asintóticamente a PMP con CWSI = 1.0.\n";
}

// 7. Modelo aditivo ponderado de pérdida de rendimiento
void testFao33YieldLossCalculation() {
    std::cout << "[TEST 7/37] Ejecutando: testFao33YieldLossCalculation...\n";

    const auto& variety = AgronomicData::getCornVariety(CornVarietyId::CHACO_01_CRIOLLO);

    std::vector<double> stageEtc = {30.0, 100.0, 150.0, 120.0, 50.0};
    std::vector<double> stageEtaFull = stageEtc;
    std::vector<double> stageKy  = {0.20,  0.40,  1.25,  0.50,  0.20};

    double lossZero = CropModel::calculateYieldLoss(stageEtc, stageEtaFull, stageKy, variety);
    REQUIRE(std::abs(lossZero) < 1e-9);

    std::vector<double> etaStressFlowering = stageEtc;
    etaStressFlowering[2] = stageEtc[2] * 0.60;

    std::vector<double> etaStressMaturation = stageEtc;
    etaStressMaturation[4] = stageEtc[4] * 0.60;

    double lossFlowering = CropModel::calculateYieldLoss(stageEtc, etaStressFlowering, stageKy, variety);
    double lossMaturation = CropModel::calculateYieldLoss(stageEtc, etaStressMaturation, stageKy, variety);

    REQUIRE(std::abs(lossFlowering - 16.6667) < 0.01);
    REQUIRE(std::abs(lossMaturation - 0.8889) < 0.01);
    REQUIRE(lossFlowering > lossMaturation * 10.0);

    std::vector<double> etaZero = {0.0, 0.0, 0.0, 0.0, 0.0};
    double lossMax = CropModel::calculateYieldLoss(stageEtc, etaZero, stageKy, variety);
    REQUIRE(std::abs(lossMax - 67.4444) < 0.01);
    REQUIRE(lossMax < 100.0);

    std::cout << "  -> PASÓ: La pérdida es aditiva, ponderada por ETc y continua en todo el rango.\n";
}

// 8. Reproducibilidad y determinismo de la simulación secuencial
void testSequentialEngineReproducibility() {
    std::cout << "[TEST 8/37] Ejecutando: testSequentialEngineReproducibility...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.gridConfig.rows = 15;
    cfg.gridConfig.cols = 15;
    cfg.simulationDays = 60;

    SequentialEngine engine1(cfg);
    auto res1 = engine1.run();

    SequentialEngine engine2(cfg);
    auto res2 = engine2.run();

    REQUIRE(res1.status == "completed");
    REQUIRE(res2.status == "completed");
    REQUIRE(res1.speedup.has_value() && res1.speedup.value() == 1.0);
    REQUIRE(res1.efficiency.has_value() && res1.efficiency.value() == 100.0);
    REQUIRE(res1.timelineData.size() == 60);
    REQUIRE(res2.timelineData.size() == 60);

    // Igualdad numérica exacta bit a bit
    REQUIRE(std::abs(res1.averageCWSI - res2.averageCWSI) < 1e-12);
    REQUIRE(std::abs(res1.soilMoistureFinalPercent - res2.soilMoistureFinalPercent) < 1e-12);
    REQUIRE(std::abs(res1.yieldLossPercent - res2.yieldLossPercent) < 1e-12);
    REQUIRE(std::abs(res1.waterDeficitMm - res2.waterDeficitMm) < 1e-12);
    REQUIRE(res1.spatialGrid.size() == 64);

    std::cout << "  -> PASÓ: Determinismo numérico bit a bit confirmado para línea base secuencial T1.\n";
}

void testOptionalMetricsSerialization() {
    std::cout << "[TEST 9/37] Ejecutando: testOptionalMetricsSerialization...\n";

    SimulationResult result;
    result.executionTimeSeconds = 0.123;
    result.speedup = std::nullopt;
    result.efficiency = std::nullopt;

    std::string json = JsonSerializer::serializeResult(result, false);
    REQUIRE(json.find("\"speedup\": null") != std::string::npos);
    REQUIRE(json.find("\"efficiency\": null") != std::string::npos);
    REQUIRE(json.find("\"executionTimeSeconds\": 0.123") != std::string::npos);

    result.speedup = 3.85;
    result.efficiency = 96.25;
    json = JsonSerializer::serializeResult(result, false);
    REQUIRE(json.find("\"speedup\": 3.850") != std::string::npos);
    REQUIRE(json.find("\"efficiency\": 96.250") != std::string::npos);

    std::cout << "  -> PASÓ: speedup y eficiencia nulos se serializan como JSON null.\n";
}

void testParallelEnginesDoNotReportFictitiousSpeedup() {
    std::cout << "[TEST 10/37] Ejecutando: testParallelEnginesDoNotReportFictitiousSpeedup...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.gridConfig.rows = 8;
    cfg.gridConfig.cols = 8;
    cfg.simulationDays = 5;
    cfg.openmpThreads = 2;
    cfg.mpiProcesses = 1;
    cfg.nodesCount = 1;

    OpenMPEngine openmpEngine(cfg);
    auto openmpResult = openmpEngine.run();
    REQUIRE(openmpResult.status == "completed");
    REQUIRE(openmpResult.executionTimeSeconds > 0.0);
    REQUIRE(!openmpResult.speedup.has_value());
    REQUIRE(!openmpResult.efficiency.has_value());

    MpiEngine mpiEngine(cfg);
    auto mpiResult = mpiEngine.run();
    REQUIRE(mpiResult.status == "completed");
    REQUIRE(mpiResult.executionTimeSeconds > 0.0);
    REQUIRE(!mpiResult.speedup.has_value());
    REQUIRE(!mpiResult.efficiency.has_value());

    HybridEngine hybridEngine(cfg);
    auto hybridResult = hybridEngine.run();
    REQUIRE(hybridResult.status == "completed");
    REQUIRE(hybridResult.executionTimeSeconds > 0.0);
    REQUIRE(!hybridResult.speedup.has_value());
    REQUIRE(!hybridResult.efficiency.has_value());

    std::cout << "  -> PASÓ: motores paralelos registran tiempo real y métricas no disponibles.\n";
}

void testYieldLossNumericalStability() {
    std::cout << "[TEST 11/37] Ejecutando: testYieldLossNumericalStability...\n";

    const auto& variety = AgronomicData::getCornVariety(CornVarietyId::CHACO_01_CRIOLLO);
    std::vector<double> stageKy = {0.20, 0.40, 1.25, 0.50, 0.20};

    std::vector<double> zeroEtc(5, 0.0);
    REQUIRE(CropModel::calculateYieldLoss(zeroEtc, zeroEtc, stageKy, variety) == 0.0);

    std::vector<double> stageEtc = {0.0, 100.0, 150.0, 120.0, 50.0};
    std::vector<double> etaNoStress = stageEtc;
    REQUIRE(std::abs(CropModel::calculateYieldLoss(stageEtc, etaNoStress, stageKy, variety)) < 1e-9);

    std::vector<double> etaExcess = etaNoStress;
    etaExcess[2] = stageEtc[2] * 1.5;
    REQUIRE(std::abs(CropModel::calculateYieldLoss(stageEtc, etaExcess, stageKy, variety)) < 1e-9);

    std::vector<double> etaBefore = etaNoStress;
    etaBefore[2] = stageEtc[2] * 0.21;
    std::vector<double> etaAfter = etaNoStress;
    etaAfter[2] = stageEtc[2] * 0.19;

    double lossBefore = CropModel::calculateYieldLoss(stageEtc, etaBefore, stageKy, variety);
    double lossAfter = CropModel::calculateYieldLoss(stageEtc, etaAfter, stageKy, variety);
    double expectedDelta = 1.25 * 0.02 * (150.0 / 420.0) * 100.0;

    REQUIRE(lossAfter > lossBefore);
    REQUIRE(std::abs((lossAfter - lossBefore) - expectedDelta) < 1e-6);

    std::cout << "  -> PASÓ: denominadores protegidos, ETa acotada y respuesta continua sin saltos.\n";
}

void testVarietyDoesNotAlterScientificLoss() {
    std::cout << "[TEST 12/37] Ejecutando: testVarietyDoesNotAlterScientificLoss...\n";

    const auto& criollo = AgronomicData::getCornVariety(CornVarietyId::CHACO_01_CRIOLLO);
    const auto& dekalb = AgronomicData::getCornVariety(CornVarietyId::DEKALB_7088);

    std::vector<double> stageEtc = {30.0, 100.0, 150.0, 120.0, 50.0};
    std::vector<double> stageEta = stageEtc;
    stageEta[2] *= 0.60;
    std::vector<double> stageKy = {0.20, 0.40, 1.25, 0.50, 0.20};

    double lossCriollo = CropModel::calculateYieldLoss(stageEtc, stageEta, stageKy, criollo);
    double lossDekalb = CropModel::calculateYieldLoss(stageEtc, stageEta, stageKy, dekalb);

    REQUIRE(std::abs(lossCriollo - lossDekalb) < 1e-12);
    REQUIRE(std::abs(lossCriollo - 16.6667) < 0.01);

    std::cout << "  -> PASÓ: la ecuación científica no depende del multiplicador varietal heurístico.\n";
}

void testInitialMoistureBelowPmpRejected() {
    std::cout << "[TEST 13/37] Ejecutando: testInitialMoistureBelowPmpRejected...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::ARENOSO);
    SimulationConfig cfg = ConfigLoader::createDefault();
    REQUIRE(std::abs(cfg.initialMoisturePercent - 8.4) < 1e-12);

    cfg.initialMoisturePercent = soil.wiltingPoint - 0.1;
    std::vector<std::string> errors;
    REQUIRE(ConfigValidator::validate(cfg, errors) == false);
    REQUIRE(errors.empty() == false);

    bool rejected = false;
    try {
        SpatialGrid grid(2, 2, 50.0, cfg.initialMoisturePercent, soil);
        (void)grid;
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    REQUIRE(rejected);

    std::cout << "  -> PASÓ: humedad < PMP rechazada sin recorte silencioso en SpatialGrid.\n";
}

void testInitialMoistureAboveCcRejectedAndReportedExactly() {
    std::cout << "[TEST 14/37] Ejecutando: testInitialMoistureAboveCcRejectedAndReportedExactly...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::ARENOSO);
    SimulationConfig cfg = ConfigLoader::createDefault();

    cfg.initialMoisturePercent = soil.fieldCapacity + 0.1;
    std::vector<std::string> errors;
    REQUIRE(ConfigValidator::validate(cfg, errors) == false);

    bool rejected = false;
    try {
        SpatialGrid grid(2, 2, 50.0, cfg.initialMoisturePercent, soil);
        (void)grid;
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    REQUIRE(rejected);

    cfg.initialMoisturePercent = 8.4;
    cfg.simulationDays = 1;
    cfg.gridConfig.rows = 3;
    cfg.gridConfig.cols = 3;
    REQUIRE(ConfigValidator::validate(cfg, errors) == true);

    SpatialGrid grid(cfg.gridConfig.rows, cfg.gridConfig.cols, 50.0, cfg.initialMoisturePercent, soil);
    for (int r = 0; r < cfg.gridConfig.rows; ++r) {
        for (int c = 0; c < cfg.gridConfig.cols; ++c) {
            REQUIRE(grid.getMoisture(r, c) == cfg.initialMoisturePercent);
        }
    }

    SequentialEngine engine(cfg);
    const auto result = engine.run();
    REQUIRE(result.status == "completed");
    REQUIRE(result.config.initialMoisturePercent == cfg.initialMoisturePercent);

    std::cout << "  -> PASÓ: humedad > CC rechazada; valor válido simulado = valor reportado.\n";
}

void testInvalidStateDoesNotInjectWater() {
    std::cout << "[TEST 15/37] Ejecutando: testInvalidStateDoesNotInjectWater...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::ARENOSO);
    const double depth = 0.50;

    bool rejected = false;
    try {
        SoilModel::updateCellMoisture(soil.wiltingPoint - 0.5, soil, 0.0, 0.0, depth);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    REQUIRE(rejected);

    const double waterWpMm = (soil.wiltingPoint / 100.0) * (depth * 1000.0);
    const auto atPmp = SoilModel::updateCellMoisture(soil.wiltingPoint, soil, 5.0, 0.0, depth);
    REQUIRE(atPmp.etActual == 0.0);
    REQUIRE(std::abs(atPmp.finalWaterMm - waterWpMm) < 1e-11);
    REQUIRE(atPmp.deepDrainage == 0.0);
    REQUIRE(std::abs(atPmp.deltaStorageMm + atPmp.etActual + atPmp.deepDrainage) < 1e-11);
    REQUIRE(atPmp.massBalanceError < 1e-11);

    std::cout << "  -> PASÓ: estado inválido rechazado; sin agua artificial en estado límite PMP.\n";
}

void testNegativePrecipitationRejected() {
    std::cout << "[TEST 16/37] Ejecutando: testNegativePrecipitationRejected...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::FRANCO_ARENOSO);
    std::vector<std::string> errors;
    REQUIRE(ConfigValidator::validateForcing(3.0, -1.0, errors) == false);
    REQUIRE(errors.empty() == false);

    bool rejected = false;
    try {
        SoilModel::updateCellMoisture(15.0, soil, 3.0, -1.0, 0.50);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    REQUIRE(rejected);

    const auto zeroRain = SoilModel::updateCellMoisture(15.0, soil, 0.0, 0.0, 0.50);
    REQUIRE(zeroRain.etActual == 0.0);
    REQUIRE(zeroRain.deepDrainage == 0.0);
    REQUIRE(zeroRain.finalWaterMm == zeroRain.initialWaterMm);
    REQUIRE(zeroRain.massBalanceError < 1e-11);

    std::cout << "  -> PASÓ: lluvia negativa rechazada; lluvia nula conserva el almacenamiento.\n";
}

void testNegativeEtcRejectedAndZeroDemandBalance() {
    std::cout << "[TEST 17/37] Ejecutando: testNegativeEtcRejectedAndZeroDemandBalance...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::ARENOSO);
    std::vector<std::string> errors;
    REQUIRE(ConfigValidator::validateForcing(-1.0, 0.0, errors) == false);

    bool rejected = false;
    try {
        CropModel::calculateEtc(-1.0, 1.20);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    REQUIRE(rejected);

    rejected = false;
    try {
        SoilModel::updateCellMoisture(10.0, soil, -2.0, 0.0, 0.50);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    REQUIRE(rejected);

    const auto zeroDemand = SoilModel::updateCellMoisture(10.0, soil, 0.0, 7.5, 0.50);
    REQUIRE(zeroDemand.etActual == 0.0);
    REQUIRE(std::abs(zeroDemand.updatedMoisturePercent - 11.5) < 1e-11);
    REQUIRE(zeroDemand.massBalanceError < 1e-11);

    std::cout << "  -> PASÓ: ETc negativa rechazada; demanda nula con lluvia conserva la masa.\n";
}

void testReproducibleMassBalanceNumbers() {
    std::cout << "[TEST 18/37] Ejecutando: testReproducibleMassBalanceNumbers...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::FRANCO_ARENOSO);
    const auto cell = SoilModel::updateCellMoisture(15.0, soil, 4.0, 25.0, 0.60);

    REQUIRE(std::abs(cell.initialWaterMm - 90.0) < 1e-11);
    REQUIRE(std::abs(cell.deepDrainage - 4.0) < 1e-11);
    REQUIRE(std::abs(cell.etActual - 4.0) < 1e-11);
    REQUIRE(std::abs(cell.finalWaterMm - 107.0) < 1e-11);
    REQUIRE(std::abs(cell.deltaStorageMm - 17.0) < 1e-11);
    REQUIRE(std::abs(cell.updatedMoisturePercent - 17.833333333333332) < 1e-11);
    REQUIRE(cell.massBalanceError < 1e-11);

    SpatialGrid grid(5, 5, 50.0, 15.0, soil);
    const auto step = grid.updateDailyStep(soil, 4.0, 25.0, 0.60);
    REQUIRE(std::abs(step.averagePrecipitation - 25.0) < 1e-12);
    REQUIRE(std::abs(step.averageDeltaStorage + step.averageEtActual + step.averageDeepDrainage - 25.0) < 1e-11);
    REQUIRE(step.massBalanceError < 1e-11);

    std::cout << "  -> PASÓ: números de balance reproducibles (dW=17, ETa=4, drenaje=4, P=25 mm).\n";
}

void testEnginesNumericalEquivalence() {
    std::cout << "[TEST 19/37] Ejecutando: testEnginesNumericalEquivalence...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.gridConfig.rows = 8;
    cfg.gridConfig.cols = 8;
    cfg.simulationDays = 5;
    cfg.openmpThreads = 2;
    cfg.mpiProcesses = 1;
    cfg.nodesCount = 1;

    SequentialEngine sequential(cfg);
    OpenMPEngine openmp(cfg);
    MpiEngine mpi(cfg);
    HybridEngine hybrid(cfg);

    const std::vector<SimulationResult> results = {
        sequential.run(), openmp.run(), mpi.run(), hybrid.run()
    };

    for (const auto& result : results) {
        REQUIRE(result.status == "completed");
        REQUIRE(result.timelineData.size() == 5);
    }

    for (size_t i = 1; i < results.size(); ++i) {
        REQUIRE(std::abs(results[i].averageCWSI - results[0].averageCWSI) < 1e-9);
        REQUIRE(std::abs(results[i].soilMoistureFinalPercent - results[0].soilMoistureFinalPercent) < 1e-9);
        REQUIRE(std::abs(results[i].yieldLossPercent - results[0].yieldLossPercent) < 1e-9);
        REQUIRE(std::abs(results[i].waterDeficitMm - results[0].waterDeficitMm) < 1e-9);
    }

    std::cout << "  -> PASÓ: los cuatro motores producen la misma respuesta agronómica.\n";
}

static void requireWaterBalanceClose(const WaterBalanceData& a, const WaterBalanceData& b) {
    REQUIRE(std::abs(a.precipitationMm - b.precipitationMm) < 1e-9);
    REQUIRE(std::abs(a.etcMm - b.etcMm) < 1e-9);
    REQUIRE(std::abs(a.etaMm - b.etaMm) < 1e-9);
    REQUIRE(std::abs(a.deepDrainageMm - b.deepDrainageMm) < 1e-9);
    REQUIRE(std::abs(a.storageInitialMm - b.storageInitialMm) < 1e-9);
    REQUIRE(std::abs(a.storageFinalMm - b.storageFinalMm) < 1e-9);
    REQUIRE(std::abs(a.storageChangeMm - b.storageChangeMm) < 1e-9);
    REQUIRE(std::abs(a.balanceErrorMm - b.balanceErrorMm) < 1e-9);
    REQUIRE(std::abs(a.balanceResidualMm - b.balanceResidualMm) < 1e-9);
    REQUIRE(std::abs(a.rootDepthMm - b.rootDepthMm) < 1e-9);
    REQUIRE(std::abs(a.rootDepthStorageRebaseMm - b.rootDepthStorageRebaseMm) < 1e-9);
}

static void requireSummaryClose(const WaterBalanceSummary& a, const WaterBalanceSummary& b) {
    REQUIRE(std::abs(a.precipitationTotalMm - b.precipitationTotalMm) < 1e-9);
    REQUIRE(std::abs(a.etcTotalMm - b.etcTotalMm) < 1e-9);
    REQUIRE(std::abs(a.etaTotalMm - b.etaTotalMm) < 1e-9);
    REQUIRE(std::abs(a.deepDrainageTotalMm - b.deepDrainageTotalMm) < 1e-9);
    REQUIRE(std::abs(a.storageInitialMm - b.storageInitialMm) < 1e-9);
    REQUIRE(std::abs(a.storageFinalMm - b.storageFinalMm) < 1e-9);
    REQUIRE(std::abs(a.storageChangeMm - b.storageChangeMm) < 1e-9);
    REQUIRE(std::abs(a.maxDailyBalanceErrorMm - b.maxDailyBalanceErrorMm) < 1e-9);
    REQUIRE(std::abs(a.massBalanceResidualMm - b.massBalanceResidualMm) < 1e-9);
    REQUIRE(std::abs(a.rootDepthStorageRebaseTotalMm - b.rootDepthStorageRebaseTotalMm) < 1e-9);
}

void testCellWaterBalanceDiagnostics() {
    std::cout << "[TEST 20/37] Ejecutando: testCellWaterBalanceDiagnostics...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::FRANCO_ARENOSO);
    const auto cell = SoilModel::updateCellMoisture(15.0, soil, 4.0, 25.0, 0.60);
    const auto balance = makeWaterBalanceData(
        25.0,
        4.0,
        cell.etActual,
        cell.deepDrainage,
        cell.initialWaterMm,
        cell.finalWaterMm,
        cell.deltaStorageMm,
        cell.massBalanceError,
        600.0,
        0.0
    );

    REQUIRE(std::abs(balance.storageInitialMm - 90.0) < 1e-11);
    REQUIRE(std::abs(balance.storageFinalMm - 107.0) < 1e-11);
    REQUIRE(std::abs(balance.storageChangeMm - 17.0) < 1e-11);
    REQUIRE(std::abs(balance.storageChangeMm + balance.etaMm + balance.deepDrainageMm - balance.precipitationMm) < 1e-11);
    REQUIRE(!balance.surfaceRunoffMm.has_value());

    std::cout << "  -> PASÓ: diagnósticos diarios reproducen P, ETa, drenaje y almacenamiento.\n";
}

void testGridWaterBalanceDiagnostics() {
    std::cout << "[TEST 21/37] Ejecutando: testGridWaterBalanceDiagnostics...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::FRANCO_ARENOSO);
    SpatialGrid grid(10, 10, 50.0, 14.0, soil);
    const auto summary = grid.updateDailyStep(soil, 5.0, 18.0, 0.70);

    REQUIRE(std::abs(summary.averageInitialStorage - 98.0) < 1e-10);
    REQUIRE(std::abs(summary.averageFinalStorage - summary.averageInitialStorage - summary.averageDeltaStorage) < 1e-11);
    REQUIRE(summary.rootDepthStorageRebaseMm == 0.0);
    REQUIRE(std::abs(summary.averageDeltaStorage + summary.averageEtActual + summary.averageDeepDrainage - summary.averagePrecipitation) < 1e-11);

    std::cout << "  -> PASÓ: la malla reporta almacenamiento inicial, final y rebase inicial nulo.\n";
}

void testDryDayWaterBalanceDiagnostics() {
    std::cout << "[TEST 22/37] Ejecutando: testDryDayWaterBalanceDiagnostics...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::FRANCO_ARCILLOSO);
    const auto cell = SoilModel::updateCellMoisture(25.0, soil, 5.0, 0.0, 0.50);
    const auto balance = makeWaterBalanceData(
        0.0, 5.0, cell.etActual, cell.deepDrainage,
        cell.initialWaterMm, cell.finalWaterMm, cell.deltaStorageMm,
        cell.massBalanceError, 500.0, 0.0
    );

    REQUIRE(std::abs(balance.storageChangeMm + balance.etaMm) < 1e-11);
    REQUIRE(balance.deepDrainageMm == 0.0);
    REQUIRE(balance.balanceErrorMm < 1e-11);

    std::cout << "  -> PASÓ: día seco reporta extracción pura sin drenaje ni agua ficticia.\n";
}

void testExtremeRainDiagnosticsSeparateDrainage() {
    std::cout << "[TEST 23/37] Ejecutando: testExtremeRainDiagnosticsSeparateDrainage...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::ARENOSO);
    const auto cell = SoilModel::updateCellMoisture(10.0, soil, 2.0, 150.0, 0.50);
    const auto balance = makeWaterBalanceData(
        150.0, 2.0, cell.etActual, cell.deepDrainage,
        cell.initialWaterMm, cell.finalWaterMm, cell.deltaStorageMm,
        cell.massBalanceError, 500.0, 0.0
    );

    REQUIRE(std::abs(balance.deepDrainageMm - 140.0) < 1e-11);
    REQUIRE(std::abs(balance.storageChangeMm + balance.etaMm + balance.deepDrainageMm - 150.0) < 1e-11);
    REQUIRE(!balance.surfaceRunoffMm.has_value());

    std::cout << "  -> PASÓ: lluvia extrema separa drenaje profundo de escorrentía no modelada.\n";
}

void testZeroDemandWaterBalanceDiagnostics() {
    std::cout << "[TEST 24/37] Ejecutando: testZeroDemandWaterBalanceDiagnostics...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::ARENOSO);
    const auto cell = SoilModel::updateCellMoisture(10.0, soil, 0.0, 7.5, 0.50);
    const auto balance = makeWaterBalanceData(
        7.5, 0.0, cell.etActual, cell.deepDrainage,
        cell.initialWaterMm, cell.finalWaterMm, cell.deltaStorageMm,
        cell.massBalanceError, 500.0, 0.0
    );

    REQUIRE(balance.etaMm == 0.0);
    REQUIRE(std::abs(balance.storageChangeMm - 7.5) < 1e-11);
    REQUIRE(balance.deepDrainageMm == 0.0);
    REQUIRE(balance.balanceErrorMm < 1e-11);

    std::cout << "  -> PASÓ: demanda nula conserva el agua de lluvia en almacenamiento.\n";
}

void testRootDepthGrowthReportedAsRebase() {
    std::cout << "[TEST 25/37] Ejecutando: testRootDepthGrowthReportedAsRebase...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::FRANCO_ARENOSO);
    SpatialGrid grid(2, 2, 50.0, 15.0, soil);
    const auto first = grid.updateDailyStep(soil, 0.0, 0.0, 0.25);
    const auto second = grid.updateDailyStep(soil, 0.0, 0.0, 0.50);

    REQUIRE(first.rootDepthStorageRebaseMm == 0.0);
    REQUIRE(second.rootDepthStorageRebaseMm > 0.0);
    REQUIRE(std::abs(second.rootDepthStorageRebaseMm - second.averagePrecipitation) > 1.0);
    REQUIRE(std::abs(second.averageDeltaStorage + second.averageEtActual + second.averageDeepDrainage - second.averagePrecipitation) < 1e-11);

    std::cout << "  -> PASÓ: crecimiento radicular se reporta como rebase, no como precipitación.\n";
}

void testFourEnginesWaterBalanceDiagnosticsEquivalent() {
    std::cout << "[TEST 26/37] Ejecutando: testFourEnginesWaterBalanceDiagnosticsEquivalent...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.gridConfig.rows = 8;
    cfg.gridConfig.cols = 8;
    cfg.simulationDays = 5;
    cfg.openmpThreads = 2;
    cfg.mpiProcesses = 1;
    cfg.nodesCount = 1;

    SequentialEngine sequential(cfg);
    OpenMPEngine openmp(cfg);
    MpiEngine mpi(cfg);
    HybridEngine hybrid(cfg);
    const std::vector<SimulationResult> results = {
        sequential.run(), openmp.run(), mpi.run(), hybrid.run()
    };

    for (const auto& result : results) {
        REQUIRE(result.status == "completed");
        REQUIRE(result.timelineData.size() == 5);
        REQUIRE(result.waterBalanceSummary.has_value());
    }

    for (size_t i = 1; i < results.size(); ++i) {
        for (size_t j = 0; j < results[0].timelineData.size(); ++j) {
            REQUIRE(results[i].timelineData[j].waterBalance.has_value());
            REQUIRE(results[0].timelineData[j].waterBalance.has_value());
            requireWaterBalanceClose(
                results[i].timelineData[j].waterBalance.value(),
                results[0].timelineData[j].waterBalance.value()
            );
        }
        requireSummaryClose(
            results[i].waterBalanceSummary.value(),
            results[0].waterBalanceSummary.value()
        );
    }

    std::cout << "  -> PASÓ: los cuatro motores producen diagnósticos de balance equivalentes.\n";
}

void testWaterBalanceSummaryTotals() {
    std::cout << "[TEST 27/37] Ejecutando: testWaterBalanceSummaryTotals...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.gridConfig.rows = 4;
    cfg.gridConfig.cols = 4;
    cfg.simulationDays = 4;
    SequentialEngine engine(cfg);
    const auto result = engine.run();

    REQUIRE(result.waterBalanceSummary.has_value());
    const auto& summary = result.waterBalanceSummary.value();

    double p = 0.0;
    double etc = 0.0;
    double eta = 0.0;
    double drainage = 0.0;
    double errorMax = 0.0;
    for (const auto& point : result.timelineData) {
        const auto& b = point.waterBalance.value();
        p += b.precipitationMm;
        etc += b.etcMm;
        eta += b.etaMm;
        drainage += b.deepDrainageMm;
        errorMax = std::max(errorMax, std::abs(b.balanceErrorMm));
    }

    REQUIRE(std::abs(summary.precipitationTotalMm - p) < 1e-9);
    REQUIRE(std::abs(summary.etcTotalMm - etc) < 1e-9);
    REQUIRE(std::abs(summary.etaTotalMm - eta) < 1e-9);
    REQUIRE(std::abs(summary.deepDrainageTotalMm - drainage) < 1e-9);
    REQUIRE(std::abs(summary.maxDailyBalanceErrorMm - errorMax) < 1e-9);
    REQUIRE(std::abs(summary.storageInitialMm - result.timelineData.front().waterBalance.value().storageInitialMm) < 1e-9);
    REQUIRE(std::abs(summary.storageFinalMm - result.timelineData.back().waterBalance.value().storageFinalMm) < 1e-9);

    std::cout << "  -> PASÓ: el resumen estacional agrega exactamente la serie diaria.\n";
}

void testWaterBalanceJsonSerialization() {
    std::cout << "[TEST 28/37] Ejecutando: testWaterBalanceJsonSerialization...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.gridConfig.rows = 4;
    cfg.gridConfig.cols = 4;
    cfg.simulationDays = 2;
    SequentialEngine engine(cfg);
    const auto json = JsonSerializer::serializeResult(engine.run(), true);

    REQUIRE(json.find("\"waterBalanceSummary\"") != std::string::npos);
    REQUIRE(json.find("\"precipitationTotalMm\"") != std::string::npos);
    REQUIRE(json.find("\"maxDailyBalanceErrorMm\"") != std::string::npos);
    REQUIRE(json.find("\"waterBalance\": {") != std::string::npos);
    REQUIRE(json.find("\"deepDrainageMm\"") != std::string::npos);
    REQUIRE(json.find("\"rootDepthStorageRebaseMm\"") != std::string::npos);

    std::cout << "  -> PASÓ: JSON serializa resumen y diagnósticos diarios del balance.\n";
}

void testHistoricalWaterBalanceSerializesAsNull() {
    std::cout << "[TEST 29/37] Ejecutando: testHistoricalWaterBalanceSerializesAsNull...\n";

    SimulationResult historical;
    historical.id = "SIM-HISTORICO";
    historical.timelineData.push_back(TimelineDataPoint{});
    const auto json = JsonSerializer::serializeResult(historical, true);

    REQUIRE(json.find("\"waterBalanceSummary\": null") != std::string::npos);
    REQUIRE(json.find("\"waterBalance\": null") != std::string::npos);

    std::cout << "  -> PASÓ: resultados históricos exponen diagnósticos ausentes como null.\n";
}

void testWaterBalanceCsvExportIncludesDiagnostics() {
    std::cout << "[TEST 30/37] Ejecutando: testWaterBalanceCsvExportIncludesDiagnostics...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.gridConfig.rows = 4;
    cfg.gridConfig.cols = 4;
    cfg.simulationDays = 2;
    SequentialEngine engine(cfg);
    const auto result = engine.run();
    const std::string path = "/tmp/agrochaco_7b2b_balance.csv";

    std::remove(path.c_str());
    REQUIRE(JsonSerializer::exportTimelineToCsv(result, path));
    std::ifstream file(path);
    std::string header;
    std::getline(file, header);

    REQUIRE(header.find("Drenaje_Profundo_mm") != std::string::npos);
    REQUIRE(header.find("Escorrentia_Superficial_mm") != std::string::npos);
    REQUIRE(header.find("Error_Balance_mm") != std::string::npos);
    REQUIRE(header.find("Rebase_Profundidad_mm") != std::string::npos);

    std::remove(path.c_str());
    std::cout << "  -> PASÓ: CSV detallado incorpora columnas de balance y rebase radicular.\n";
}

void testSurfaceRunoffIsNotFictitious() {
    std::cout << "[TEST 31/37] Ejecutando: testSurfaceRunoffIsNotFictitious...\n";

    const auto balance = makeWaterBalanceData(10.0, 2.0, 1.0, 3.0, 50.0, 56.0, 6.0, 0.0, 500.0, 0.0);
    REQUIRE(!balance.surfaceRunoffMm.has_value());

    TimelineDataPoint point;
    point.waterBalance = balance;
    std::vector<TimelineDataPoint> points{point};
    const auto summary = makeWaterBalanceSummary(points);
    REQUIRE(summary.has_value());
    REQUIRE(!summary->surfaceRunoffTotalMm.has_value());

    const auto& soil = AgronomicData::getSoil(SoilType::FRANCO_ARENOSO);
    SpatialGrid grid(4, 4, 50.0, 15.0, soil);
    grid.updateDailyStep(soil, 2.0, 10.0, 0.50);
    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.gridConfig.rows = 4;
    cfg.gridConfig.cols = 4;
    cfg.simulationDays = 1;
    SequentialEngine engine(cfg);
    const auto json = JsonSerializer::serializeResult(engine.run(), true);

    REQUIRE(json.find("\"surfaceRunoffMm\": null") != std::string::npos);
    REQUIRE(json.find("\"surfaceRunoffTotalMm\": null") != std::string::npos);

    std::cout << "  -> PASÓ: escorrentía no modelada se reporta como no disponible, nunca como cero.\n";
}

void testSignedBalanceResidualIsDistinctFromAbsoluteError() {
    std::cout << "[TEST 32/37] Ejecutando: testSignedBalanceResidualIsDistinctFromAbsoluteError...\n";

    const auto deficit = makeWaterBalanceData(
        10.0, 2.0, 3.0, 4.0, 50.0, 52.0, 2.0, 1.25, -1.25, 0.50, 0.0
    );
    const auto surplus = makeWaterBalanceData(
        10.0, 2.0, 3.0, 4.0, 50.0, 55.0, 5.0, 1.25, 1.25, 0.50, 0.0
    );
    const auto computed = makeWaterBalanceData(
        10.0, 2.0, 3.0, 4.0, 50.0, 52.0, 2.0, 1.0, 0.50, 0.0
    );

    REQUIRE(deficit.balanceResidualMm < 0.0);
    REQUIRE(surplus.balanceResidualMm > 0.0);
    REQUIRE(std::abs(deficit.balanceResidualMm - surplus.balanceResidualMm) > 2.0);
    REQUIRE(std::abs(deficit.balanceErrorMm - surplus.balanceErrorMm) < 1e-12);
    REQUIRE(std::abs(std::abs(deficit.balanceResidualMm) - deficit.balanceErrorMm) < 1e-12);
    REQUIRE(std::abs(computed.balanceResidualMm + 1.0) < 1e-12);

    std::cout << "  -> PASÓ: residuo con signo y error máximo absoluto son métricas distintas.\n";
}

void testIncompleteOrNonFiniteSummaryIsNull() {
    std::cout << "[TEST 33/37] Ejecutando: testIncompleteOrNonFiniteSummaryIsNull...\n";

    const std::vector<TimelineDataPoint> empty;
    REQUIRE(!makeWaterBalanceSummary(empty).has_value());

    TimelineDataPoint withoutBalance;
    withoutBalance.day = 1;
    REQUIRE(!makeWaterBalanceSummary({withoutBalance}).has_value());

    TimelineDataPoint withNonFinite;
    withNonFinite.day = 2;
    withNonFinite.waterBalance = makeWaterBalanceData(
        10.0, 2.0, 3.0, 4.0, 50.0, 52.0, 2.0,
        std::numeric_limits<double>::quiet_NaN(), 0.0, 0.50, 0.0
    );
    REQUIRE(!makeWaterBalanceSummary({withNonFinite}).has_value());

    TimelineDataPoint complete;
    complete.day = 3;
    complete.waterBalance = makeWaterBalanceData(
        10.0, 2.0, 3.0, 4.0, 50.0, 52.0, 2.0, 1.0, -1.0, 0.50, 0.0
    );
    REQUIRE(makeWaterBalanceSummary({complete}).has_value());

    std::cout << "  -> PASÓ: resúmenes incompletos o no finitos no generan ceros ficticios.\n";
}

void testStorageIdentityAndResidualAggregation() {
    std::cout << "[TEST 34/37] Ejecutando: testStorageIdentityAndResidualAggregation...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.simulationDays = 12;
    cfg.gridConfig.rows = 7;
    cfg.gridConfig.cols = 11;
    const auto result = SequentialEngine(cfg).run();

    REQUIRE(result.waterBalanceSummary.has_value());
    const auto& summary = result.waterBalanceSummary.value();
    const double totalChange = summary.storageFinalMm - summary.storageInitialMm;
    const double reportedChange = summary.storageChangeMm + summary.rootDepthStorageRebaseTotalMm;

    REQUIRE(std::abs(totalChange - reportedChange) < 1e-9);
    REQUIRE(summary.maxDailyBalanceErrorMm + 1e-9 >= std::abs(summary.massBalanceResidualMm));

    double residualSum = 0.0;
    for (const auto& point : result.timelineData) {
        REQUIRE(point.waterBalance.has_value());
        residualSum += point.waterBalance->balanceResidualMm;
    }
    REQUIRE(std::abs(residualSum - summary.massBalanceResidualMm) < 1e-9);

    std::cout << "  -> PASÓ: identidad ΔW total = suma diaria + rebase radicular.\n";
}

void testCsvColumnCountsWithAndWithoutDiagnostics() {
    std::cout << "[TEST 35/37] Ejecutando: testCsvColumnCountsWithAndWithoutDiagnostics...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.simulationDays = 2;
    cfg.gridConfig.rows = 4;
    cfg.gridConfig.cols = 4;
    auto result = SequentialEngine(cfg).run();

    const auto countFields = [](const std::string& line) {
        int fields = 1;
        for (char character : line) {
            if (character == ',') {
                ++fields;
            }
        }
        return fields;
    };

    const std::string completePath = "/tmp/agrochaco_7b3_complete.csv";
    std::remove(completePath.c_str());
    REQUIRE(JsonSerializer::exportTimelineToCsv(result, completePath));
    std::ifstream completeFile(completePath);
    std::string header;
    std::getline(completeFile, header);
    REQUIRE(countFields(header) == 16);
    REQUIRE(header.find("Residuo_Balance_mm") != std::string::npos);
    std::string line;
    while (std::getline(completeFile, line)) {
        REQUIRE(countFields(line) == 16);
    }

    for (auto& point : result.timelineData) {
        point.waterBalance.reset();
    }
    const std::string absentPath = "/tmp/agrochaco_7b3_absent.csv";
    std::remove(absentPath.c_str());
    REQUIRE(JsonSerializer::exportTimelineToCsv(result, absentPath));
    std::ifstream absentFile(absentPath);
    std::getline(absentFile, header);
    REQUIRE(countFields(header) == 16);
    while (std::getline(absentFile, line)) {
        REQUIRE(countFields(line) == 16);
    }

    std::remove(completePath.c_str());
    std::remove(absentPath.c_str());
    std::cout << "  -> PASÓ: CSV conserva 16 columnas con y sin diagnóstico de balance.\n";
}

void testSequentialReportsEffectiveBaselineIdentity() {
    std::cout << "[TEST 36/37] Ejecutando: testSequentialReportsEffectiveBaselineIdentity...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.simulationDays = 2;
    cfg.gridConfig.rows = 4;
    cfg.gridConfig.cols = 4;
    cfg.engine = SimulationEngine::OPENMP;
    cfg.nodesCount = 3;
    const auto result = SequentialEngine(cfg).run();

    REQUIRE(result.status == "completed");
    REQUIRE(result.config.engine == SimulationEngine::SECUENCIAL);
    REQUIRE(result.config.nodesCount.value_or(-1) == 1);
    REQUIRE(result.speedup.has_value());
    REQUIRE(std::abs(result.speedup.value() - 1.0) < 1e-12);
    REQUIRE(result.efficiency.has_value());
    REQUIRE(std::abs(result.efficiency.value() - 100.0) < 1e-12);

    std::cout << "  -> PASÓ: el motor secuencial declara su identidad y su línea base explícita.\n";
}

void testCanonicalConfigSerializationRoundTrip() {
    std::cout << "[TEST 37/37] Ejecutando: testCanonicalConfigSerializationRoundTrip...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.simulationDays = 9;
    cfg.gridConfig.rows = 6;
    cfg.gridConfig.cols = 7;
    cfg.engine = SimulationEngine::HIBRIDO;
    cfg.openmpThreads = 3;
    cfg.mpiProcesses = 2;
    cfg.nodesCount = 1;

    const std::string payload = JsonSerializer::serializeConfig(cfg);
    const auto parsed = ConfigLoader::loadFromString(payload);

    REQUIRE(parsed.simulationDays == cfg.simulationDays);
    REQUIRE(parsed.gridConfig.rows == cfg.gridConfig.rows);
    REQUIRE(parsed.gridConfig.cols == cfg.gridConfig.cols);
    REQUIRE(parsed.engine == cfg.engine);
    REQUIRE(parsed.openmpThreads.value_or(-1) == 3);
    REQUIRE(parsed.mpiProcesses.value_or(-1) == 2);
    REQUIRE(parsed.nodesCount.value_or(-1) == 1);
    REQUIRE(JsonSerializer::serializeConfig(parsed) == payload);

    std::cout << "  -> PASÓ: la configuración canónica sobrevive a serialización y broadcast.\n";
}

int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);

    std::cout << "===============================================================\n"
              << "      AGROCHACO — SUITE EXPANDIDA DE PRUEBAS TÉCNICAS          \n"
              << "===============================================================\n\n";

    runTest("testValidationRejectsInvalidParameters", testValidationRejectsInvalidParameters);
    runTest("testWaterMassConservation", testWaterMassConservation);
    runTest("testNoPrecipitationDay", testNoPrecipitationDay);
    runTest("testExtremeRainfall", testExtremeRainfall);
    runTest("testZeroEtcHandling", testZeroEtcHandling);
    runTest("testProlongedDroughtAndPmpConvergence", testProlongedDroughtAndPmpConvergence);
    runTest("testFao33YieldLossCalculation", testFao33YieldLossCalculation);
    runTest("testSequentialEngineReproducibility", testSequentialEngineReproducibility);
    runTest("testOptionalMetricsSerialization", testOptionalMetricsSerialization);
    runTest("testParallelEnginesDoNotReportFictitiousSpeedup", testParallelEnginesDoNotReportFictitiousSpeedup);
    runTest("testYieldLossNumericalStability", testYieldLossNumericalStability);
    runTest("testVarietyDoesNotAlterScientificLoss", testVarietyDoesNotAlterScientificLoss);
    runTest("testInitialMoistureBelowPmpRejected", testInitialMoistureBelowPmpRejected);
    runTest("testInitialMoistureAboveCcRejectedAndReportedExactly", testInitialMoistureAboveCcRejectedAndReportedExactly);
    runTest("testInvalidStateDoesNotInjectWater", testInvalidStateDoesNotInjectWater);
    runTest("testNegativePrecipitationRejected", testNegativePrecipitationRejected);
    runTest("testNegativeEtcRejectedAndZeroDemandBalance", testNegativeEtcRejectedAndZeroDemandBalance);
    runTest("testReproducibleMassBalanceNumbers", testReproducibleMassBalanceNumbers);
    runTest("testEnginesNumericalEquivalence", testEnginesNumericalEquivalence);
    runTest("testCellWaterBalanceDiagnostics", testCellWaterBalanceDiagnostics);
    runTest("testGridWaterBalanceDiagnostics", testGridWaterBalanceDiagnostics);
    runTest("testDryDayWaterBalanceDiagnostics", testDryDayWaterBalanceDiagnostics);
    runTest("testExtremeRainDiagnosticsSeparateDrainage", testExtremeRainDiagnosticsSeparateDrainage);
    runTest("testZeroDemandWaterBalanceDiagnostics", testZeroDemandWaterBalanceDiagnostics);
    runTest("testRootDepthGrowthReportedAsRebase", testRootDepthGrowthReportedAsRebase);
    runTest("testFourEnginesWaterBalanceDiagnosticsEquivalent", testFourEnginesWaterBalanceDiagnosticsEquivalent);
    runTest("testWaterBalanceSummaryTotals", testWaterBalanceSummaryTotals);
    runTest("testWaterBalanceJsonSerialization", testWaterBalanceJsonSerialization);
    runTest("testHistoricalWaterBalanceSerializesAsNull", testHistoricalWaterBalanceSerializesAsNull);
    runTest("testWaterBalanceCsvExportIncludesDiagnostics", testWaterBalanceCsvExportIncludesDiagnostics);
    runTest("testSurfaceRunoffIsNotFictitious", testSurfaceRunoffIsNotFictitious);
    runTest("testSignedBalanceResidualIsDistinctFromAbsoluteError", testSignedBalanceResidualIsDistinctFromAbsoluteError);
    runTest("testIncompleteOrNonFiniteSummaryIsNull", testIncompleteOrNonFiniteSummaryIsNull);
    runTest("testStorageIdentityAndResidualAggregation", testStorageIdentityAndResidualAggregation);
    runTest("testCsvColumnCountsWithAndWithoutDiagnostics", testCsvColumnCountsWithAndWithoutDiagnostics);
    runTest("testSequentialReportsEffectiveBaselineIdentity", testSequentialReportsEffectiveBaselineIdentity);
    runTest("testCanonicalConfigSerializationRoundTrip", testCanonicalConfigSerializationRoundTrip);

    if (g_testFailures != 0) {
        std::cerr << "\n[FAIL] " << g_testFailures << " comprobación(es) fallaron.\n\n";
        MPI_Finalize();
        return 1;
    }

    std::cout << "\n[OK] TODAS LAS PRUEBAS UNITARIAS Y FÍSICAS PASARON CON ÉXITO (37/37)\n\n";
    MPI_Finalize();
    return 0;
}
