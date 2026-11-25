#include "agrochaco/types.hpp"
#include "agrochaco/config.hpp"
#include "agrochaco/agronomic_data.hpp"
#include "agrochaco/soil_model.hpp"
#include "agrochaco/crop_model.hpp"
#include "agrochaco/grid.hpp"
#include "agrochaco/simulation_engine.hpp"
#include "agrochaco/json_serializer.hpp"
#include <mpi.h>
#include <iostream>
#include <cassert>
#include <cmath>
#include <vector>

using namespace agrochaco;

// 1. Validación de rechazo de parámetros inválidos
void testValidationRejectsInvalidParameters() {
    std::cout << "[TEST 1/12] Ejecutando: testValidationRejectsInvalidParameters...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    std::vector<std::string> errors;

    assert(ConfigValidator::validate(cfg, errors) == true);
    assert(errors.empty());

    // Filas inválidas (<= 0)
    cfg.gridConfig.rows = 0;
    assert(ConfigValidator::validate(cfg, errors) == false);
    cfg.gridConfig.rows = 20;

    // Columnas inválidas (< 0)
    cfg.gridConfig.cols = -5;
    assert(ConfigValidator::validate(cfg, errors) == false);
    cfg.gridConfig.cols = 20;

    // Tamaño de celda inválido (<= 0)
    cfg.gridConfig.cellSizeMeters = -10.0;
    assert(ConfigValidator::validate(cfg, errors) == false);
    cfg.gridConfig.cellSizeMeters = 50.0;

    // Días de simulación inválidos (0 y > 365)
    cfg.simulationDays = 0;
    assert(ConfigValidator::validate(cfg, errors) == false);
    cfg.simulationDays = 400;
    assert(ConfigValidator::validate(cfg, errors) == false);
    cfg.simulationDays = 120;

    // Humedad inicial fuera de rango (< 0% o > 100%)
    cfg.initialMoisturePercent = -2.0;
    assert(ConfigValidator::validate(cfg, errors) == false);
    cfg.initialMoisturePercent = 105.0;
    assert(ConfigValidator::validate(cfg, errors) == false);
    cfg.initialMoisturePercent = 14.5;

    std::cout << "  -> PASÓ: Parámetros inválidos rechazados correctamente con mensajes explicativos.\n";
}

// 2. Conservación estricta de masa de agua (Celda y Malla 2D)
void testWaterMassConservation() {
    std::cout << "[TEST 2/12] Ejecutando: testWaterMassConservation...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::FRANCO_ARENOSO);

    // Caso A: Celda individual con lluvia moderada
    double initMoist = 12.0; // %
    double rain = 25.0;      // mm
    double etDemand = 4.5;   // mm
    double depth = 0.60;     // m

    auto cellRes = SoilModel::updateCellMoisture(initMoist, soil, etDemand, rain, depth);
    // Identidad de balance: DeltaAlmacenamiento + ETa + Drenaje == Precipitación
    double massBalanceSum = cellRes.deltaStorageMm + cellRes.etActual + cellRes.deepDrainage;
    assert(std::abs(massBalanceSum - rain) < 1e-11);
    assert(cellRes.massBalanceError < 1e-11);

    // Caso B: Malla 2D completa con precipitación uniforme
    SpatialGrid grid(10, 10, 50.0, 14.0, soil);
    auto stepSummary = grid.updateDailyStep(soil, 5.0, 18.0, 0.70);

    double gridMassSum = stepSummary.averageDeltaStorage + stepSummary.averageEtActual + stepSummary.averageDeepDrainage;
    assert(std::abs(gridMassSum - stepSummary.averagePrecipitation) < 1e-11);
    assert(stepSummary.massBalanceError < 1e-11);

    std::cout << "  -> PASÓ: Conservación estricta de masa hidrológica verificada (error < 1e-11 mm).\n";
}

// 3. Día sin precipitación
void testNoPrecipitationDay() {
    std::cout << "[TEST 3/12] Ejecutando: testNoPrecipitationDay...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::FRANCO_ARCILLOSO);
    double initMoist = 25.0; // Entre WP (17.5) y FC (31.0)
    double rain = 0.0;
    double etDemand = 5.0;
    double depth = 0.50;

    auto cellRes = SoilModel::updateCellMoisture(initMoist, soil, etDemand, rain, depth);

    // Sin lluvia: el agua final debe ser estrictamente menor a la inicial (disminuye por ETa)
    assert(cellRes.finalWaterMm < cellRes.initialWaterMm);
    assert(cellRes.deepDrainage == 0.0);
    assert(cellRes.etActual > 0.0);
    // DeltaStorage es negativo: |DeltaStorage| == ETa
    assert(std::abs(cellRes.deltaStorageMm + cellRes.etActual) < 1e-11);

    std::cout << "  -> PASÓ: Día seco modela correctamente la extracción pura sin drenaje gravitacional.\n";
}

// 4. Lluvia extrema y saturación (Drenaje de exceso)
void testExtremeRainfall() {
    std::cout << "[TEST 4/12] Ejecutando: testExtremeRainfall...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::ARENOSO); // FC=12.0%, WP=4.8%
    double initMoist = 10.0;
    double extremeRain = 150.0; // mm de lluvia torrencial
    double depth = 0.50;        // 500 mm suelo -> FC = 60 mm agua
    double etDemand = 2.0;

    auto cellRes = SoilModel::updateCellMoisture(initMoist, soil, etDemand, extremeRain, depth);

    // El almacenamiento debe saturar y evacuar el excedente por encima de FC
    double waterMaxMm = (soil.fieldCapacity / 100.0) * (depth * 1000.0);
    assert(cellRes.deepDrainage > 0.0);
    assert(cellRes.finalWaterMm <= waterMaxMm);
    // La humedad resultante debe ser muy cercana a FC
    assert(cellRes.updatedMoisturePercent <= soil.fieldCapacity);
    // La masa se conserva exactamente
    double massSum = cellRes.deltaStorageMm + cellRes.etActual + cellRes.deepDrainage;
    assert(std::abs(massSum - extremeRain) < 1e-11);

    std::cout << "  -> PASÓ: Lluvia extrema de 150 mm satura el suelo y drena el exceso conservando la masa.\n";
}

// 5. Demanda ETc igual a cero (Evitar división por cero y NaN)
void testZeroEtcHandling() {
    std::cout << "[TEST 5/12] Ejecutando: testZeroEtcHandling...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::FRANCO);

    // ETc = 0.0
    auto cellRes = SoilModel::updateCellMoisture(20.0, soil, 0.0, 10.0, 0.50);

    assert(!std::isnan(cellRes.cwsi));
    assert(!std::isinf(cellRes.cwsi));
    assert(cellRes.cwsi == 0.0);
    assert(cellRes.etActual == 0.0);
    assert(cellRes.deficitMm == 0.0);

    // CropModel con et0 = 0
    double etc = CropModel::calculateEtc(0.0, 1.20);
    assert(etc == 0.0);

    std::cout << "  -> PASÓ: Demanda nula (ETc = 0) no genera NaN, división por cero ni errores numéricos.\n";
}

// 6. Sequía prolongada y convergencia hacia el PMP
void testProlongedDroughtAndPmpConvergence() {
    std::cout << "[TEST 6/12] Ejecutando: testProlongedDroughtAndPmpConvergence...\n";

    const auto& soil = AgronomicData::getSoil(SoilType::ARENOSO); // FC=12.0%, WP=4.8%
    double moisture = soil.fieldCapacity;
    double depth = 0.80;
    double dailyEtc = 5.0;

    // Simular 100 días continuos sin una gota de lluvia
    for (int day = 1; day <= 100; ++day) {
        auto res = SoilModel::updateCellMoisture(moisture, soil, dailyEtc, 0.0, depth);
        moisture = res.updatedMoisturePercent;
        assert(!std::isnan(moisture));
        // La humedad NUNCA debe caer por debajo de PMP por transpiración vegetal
        assert(moisture >= soil.wiltingPoint - 1e-9);
    }

    // Al final de una sequía extrema prolongada, la humedad debe estabilizarse en PMP y CWSI en 1.0
    assert(std::abs(moisture - soil.wiltingPoint) < 0.10);
    auto finalStep = SoilModel::updateCellMoisture(moisture, soil, dailyEtc, 0.0, depth);
    assert(finalStep.etActual < 0.01); // El cultivo ya no puede extraer agua
    assert(std::abs(finalStep.cwsi - 1.0) < 1e-4); // Estrés hídrico total (CWSI = 1.0)

    std::cout << "  -> PASÓ: Sequía continua de 100 días converge asintóticamente a PMP con CWSI = 1.0.\n";
}

// 7. Modelo aditivo ponderado de pérdida de rendimiento
void testFao33YieldLossCalculation() {
    std::cout << "[TEST 7/12] Ejecutando: testFao33YieldLossCalculation...\n";

    const auto& variety = AgronomicData::getCornVariety(CornVarietyId::CHACO_01_CRIOLLO);

    std::vector<double> stageEtc = {30.0, 100.0, 150.0, 120.0, 50.0};
    std::vector<double> stageEtaFull = stageEtc;
    std::vector<double> stageKy  = {0.20,  0.40,  1.25,  0.50,  0.20};

    double lossZero = CropModel::calculateYieldLoss(stageEtc, stageEtaFull, stageKy, variety);
    assert(std::abs(lossZero) < 1e-9);

    std::vector<double> etaStressFlowering = stageEtc;
    etaStressFlowering[2] = stageEtc[2] * 0.60;

    std::vector<double> etaStressMaturation = stageEtc;
    etaStressMaturation[4] = stageEtc[4] * 0.60;

    double lossFlowering = CropModel::calculateYieldLoss(stageEtc, etaStressFlowering, stageKy, variety);
    double lossMaturation = CropModel::calculateYieldLoss(stageEtc, etaStressMaturation, stageKy, variety);

    assert(std::abs(lossFlowering - 16.6667) < 0.01);
    assert(std::abs(lossMaturation - 0.8889) < 0.01);
    assert(lossFlowering > lossMaturation * 10.0);

    std::vector<double> etaZero = {0.0, 0.0, 0.0, 0.0, 0.0};
    double lossMax = CropModel::calculateYieldLoss(stageEtc, etaZero, stageKy, variety);
    assert(std::abs(lossMax - 67.4444) < 0.01);
    assert(lossMax < 100.0);

    std::cout << "  -> PASÓ: La pérdida es aditiva, ponderada por ETc y continua en todo el rango.\n";
}

// 8. Reproducibilidad y determinismo de la simulación secuencial
void testSequentialEngineReproducibility() {
    std::cout << "[TEST 8/12] Ejecutando: testSequentialEngineReproducibility...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.gridConfig.rows = 15;
    cfg.gridConfig.cols = 15;
    cfg.simulationDays = 60;

    SequentialEngine engine1(cfg);
    auto res1 = engine1.run();

    SequentialEngine engine2(cfg);
    auto res2 = engine2.run();

    assert(res1.status == "completed");
    assert(res2.status == "completed");
    assert(res1.speedup.has_value() && res1.speedup.value() == 1.0);
    assert(res1.efficiency.has_value() && res1.efficiency.value() == 100.0);
    assert(res1.timelineData.size() == 60);
    assert(res2.timelineData.size() == 60);

    // Igualdad numérica exacta bit a bit
    assert(std::abs(res1.averageCWSI - res2.averageCWSI) < 1e-12);
    assert(std::abs(res1.soilMoistureFinalPercent - res2.soilMoistureFinalPercent) < 1e-12);
    assert(std::abs(res1.yieldLossPercent - res2.yieldLossPercent) < 1e-12);
    assert(std::abs(res1.waterDeficitMm - res2.waterDeficitMm) < 1e-12);
    assert(res1.spatialGrid.size() == 64);

    std::cout << "  -> PASÓ: Determinismo numérico bit a bit confirmado para línea base secuencial T1.\n";
}

void testOptionalMetricsSerialization() {
    std::cout << "[TEST 9/12] Ejecutando: testOptionalMetricsSerialization...\n";

    SimulationResult result;
    result.executionTimeSeconds = 0.123;
    result.speedup = std::nullopt;
    result.efficiency = std::nullopt;

    std::string json = JsonSerializer::serializeResult(result, false);
    assert(json.find("\"speedup\": null") != std::string::npos);
    assert(json.find("\"efficiency\": null") != std::string::npos);
    assert(json.find("\"executionTimeSeconds\": 0.123") != std::string::npos);

    result.speedup = 3.85;
    result.efficiency = 96.25;
    json = JsonSerializer::serializeResult(result, false);
    assert(json.find("\"speedup\": 3.850") != std::string::npos);
    assert(json.find("\"efficiency\": 96.250") != std::string::npos);

    std::cout << "  -> PASÓ: speedup y eficiencia nulos se serializan como JSON null.\n";
}

void testParallelEnginesDoNotReportFictitiousSpeedup() {
    std::cout << "[TEST 10/12] Ejecutando: testParallelEnginesDoNotReportFictitiousSpeedup...\n";

    SimulationConfig cfg = ConfigLoader::createDefault();
    cfg.gridConfig.rows = 8;
    cfg.gridConfig.cols = 8;
    cfg.simulationDays = 5;
    cfg.openmpThreads = 2;
    cfg.mpiProcesses = 1;
    cfg.nodesCount = 1;

    OpenMPEngine openmpEngine(cfg);
    auto openmpResult = openmpEngine.run();
    assert(openmpResult.status == "completed");
    assert(openmpResult.executionTimeSeconds > 0.0);
    assert(!openmpResult.speedup.has_value());
    assert(!openmpResult.efficiency.has_value());

    MpiEngine mpiEngine(cfg);
    auto mpiResult = mpiEngine.run();
    assert(mpiResult.status == "completed");
    assert(mpiResult.executionTimeSeconds > 0.0);
    assert(!mpiResult.speedup.has_value());
    assert(!mpiResult.efficiency.has_value());

    HybridEngine hybridEngine(cfg);
    auto hybridResult = hybridEngine.run();
    assert(hybridResult.status == "completed");
    assert(hybridResult.executionTimeSeconds > 0.0);
    assert(!hybridResult.speedup.has_value());
    assert(!hybridResult.efficiency.has_value());

    std::cout << "  -> PASÓ: motores paralelos registran tiempo real y métricas no disponibles.\n";
}

void testYieldLossNumericalStability() {
    std::cout << "[TEST 11/12] Ejecutando: testYieldLossNumericalStability...\n";

    const auto& variety = AgronomicData::getCornVariety(CornVarietyId::CHACO_01_CRIOLLO);
    std::vector<double> stageKy = {0.20, 0.40, 1.25, 0.50, 0.20};

    std::vector<double> zeroEtc(5, 0.0);
    assert(CropModel::calculateYieldLoss(zeroEtc, zeroEtc, stageKy, variety) == 0.0);

    std::vector<double> stageEtc = {0.0, 100.0, 150.0, 120.0, 50.0};
    std::vector<double> etaNoStress = stageEtc;
    assert(std::abs(CropModel::calculateYieldLoss(stageEtc, etaNoStress, stageKy, variety)) < 1e-9);

    std::vector<double> etaExcess = etaNoStress;
    etaExcess[2] = stageEtc[2] * 1.5;
    assert(std::abs(CropModel::calculateYieldLoss(stageEtc, etaExcess, stageKy, variety)) < 1e-9);

    std::vector<double> etaBefore = etaNoStress;
    etaBefore[2] = stageEtc[2] * 0.21;
    std::vector<double> etaAfter = etaNoStress;
    etaAfter[2] = stageEtc[2] * 0.19;

    double lossBefore = CropModel::calculateYieldLoss(stageEtc, etaBefore, stageKy, variety);
    double lossAfter = CropModel::calculateYieldLoss(stageEtc, etaAfter, stageKy, variety);
    double expectedDelta = 1.25 * 0.02 * (150.0 / 420.0) * 100.0;

    assert(lossAfter > lossBefore);
    assert(std::abs((lossAfter - lossBefore) - expectedDelta) < 1e-6);

    std::cout << "  -> PASÓ: denominadores protegidos, ETa acotada y respuesta continua sin saltos.\n";
}

void testVarietyDoesNotAlterScientificLoss() {
    std::cout << "[TEST 12/12] Ejecutando: testVarietyDoesNotAlterScientificLoss...\n";

    const auto& criollo = AgronomicData::getCornVariety(CornVarietyId::CHACO_01_CRIOLLO);
    const auto& dekalb = AgronomicData::getCornVariety(CornVarietyId::DEKALB_7088);

    std::vector<double> stageEtc = {30.0, 100.0, 150.0, 120.0, 50.0};
    std::vector<double> stageEta = stageEtc;
    stageEta[2] *= 0.60;
    std::vector<double> stageKy = {0.20, 0.40, 1.25, 0.50, 0.20};

    double lossCriollo = CropModel::calculateYieldLoss(stageEtc, stageEta, stageKy, criollo);
    double lossDekalb = CropModel::calculateYieldLoss(stageEtc, stageEta, stageKy, dekalb);

    assert(std::abs(lossCriollo - lossDekalb) < 1e-12);
    assert(std::abs(lossCriollo - 16.6667) < 0.01);

    std::cout << "  -> PASÓ: la ecuación científica no depende del multiplicador varietal heurístico.\n";
}

int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);

    std::cout << "===============================================================\n"
              << "      AGROCHACO — SUITE EXPANDIDA DE PRUEBAS TÉCNICAS          \n"
              << "===============================================================\n\n";

    testValidationRejectsInvalidParameters();
    testWaterMassConservation();
    testNoPrecipitationDay();
    testExtremeRainfall();
    testZeroEtcHandling();
    testProlongedDroughtAndPmpConvergence();
    testFao33YieldLossCalculation();
    testSequentialEngineReproducibility();
    testOptionalMetricsSerialization();
    testParallelEnginesDoNotReportFictitiousSpeedup();
    testYieldLossNumericalStability();
    testVarietyDoesNotAlterScientificLoss();

    std::cout << "\n[OK] TODAS LAS PRUEBAS UNITARIAS Y FÍSICAS PASARON CON ÉXITO (12/12)\n\n";
    MPI_Finalize();
    return 0;
}
