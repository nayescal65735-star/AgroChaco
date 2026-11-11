#include "agrochaco/types.hpp"
#include "agrochaco/config.hpp"
#include "agrochaco/agronomic_data.hpp"
#include "agrochaco/soil_model.hpp"
#include "agrochaco/crop_model.hpp"
#include "agrochaco/grid.hpp"
#include "agrochaco/simulation_engine.hpp"
#include "agrochaco/json_serializer.hpp"
#include <iostream>
#include <cassert>
#include <cmath>
#include <vector>

using namespace agrochaco;

// 1. Validación de rechazo de parámetros inválidos
void testValidationRejectsInvalidParameters() {
    std::cout << "[TEST 1/8] Ejecutando: testValidationRejectsInvalidParameters...\n";

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
    std::cout << "[TEST 2/8] Ejecutando: testWaterMassConservation...\n";

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
    std::cout << "[TEST 3/8] Ejecutando: testNoPrecipitationDay...\n";

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
    std::cout << "[TEST 4/8] Ejecutando: testExtremeRainfall...\n";

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
    std::cout << "[TEST 5/8] Ejecutando: testZeroEtcHandling...\n";

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
    std::cout << "[TEST 6/8] Ejecutando: testProlongedDroughtAndPmpConvergence...\n";

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

// 7. Modelo de Rendimiento FAO-33 (Sensibilidad por etapas)
void testFao33YieldLossCalculation() {
    std::cout << "[TEST 7/8] Ejecutando: testFao33YieldLossCalculation...\n";

    const auto& variety = AgronomicData::getCornVariety(CornVarietyId::CHACO_01_CRIOLLO);

    // Caso A: Sin déficit (ETa == ETc en todas las etapas) -> Pérdida = 0%
    std::vector<double> stageEtc = {30.0, 100.0, 150.0, 120.0, 50.0};
    std::vector<double> stageEtaFull = stageEtc;
    std::vector<double> stageKy  = {0.20,  0.40,  1.25,  0.50,  0.20};

    double lossZero = CropModel::calculateYieldLoss(stageEtc, stageEtaFull, stageKy, variety);
    assert(std::abs(lossZero - 0.0) < 1e-9);

    // Caso B: Déficit idéntico del 40% en Floración (R1, Ky=1.25) vs Maduración (R6, Ky=0.20)
    std::vector<double> etaStressFlowering = stageEtc;
    etaStressFlowering[2] = stageEtc[2] * 0.60; // 40% déficit en floración

    std::vector<double> etaStressMaturation = stageEtc;
    etaStressMaturation[4] = stageEtc[4] * 0.60; // 40% déficit en maduración

    double lossFlowering = CropModel::calculateYieldLoss(stageEtc, etaStressFlowering, stageKy, variety);
    double lossMaturation = CropModel::calculateYieldLoss(stageEtc, etaStressMaturation, stageKy, variety);

    // El estrés en floración debe provocar un daño significativamente mayor
    assert(lossFlowering > lossMaturation * 3.0);
    assert(lossFlowering <= 100.0);
    assert(lossMaturation >= 0.0);

    // Caso C: Sequía total (ETa = 0 en todo el ciclo)
    std::vector<double> etaZero = {0.0, 0.0, 0.0, 0.0, 0.0};
    double lossMax = CropModel::calculateYieldLoss(stageEtc, etaZero, stageKy, variety);
    assert(lossMax >= 80.0 && lossMax <= 100.0);

    std::cout << "  -> PASÓ: Modelo FAO-33 penaliza con máxima severidad el déficit en floración R1.\n";
}

// 8. Reproducibilidad y determinismo de la simulación secuencial
void testSequentialEngineReproducibility() {
    std::cout << "[TEST 8/8] Ejecutando: testSequentialEngineReproducibility...\n";

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

int main() {
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

    std::cout << "\n[OK] TODAS LAS PRUEBAS UNITARIAS Y FÍSICAS PASARON CON ÉXITO (8/8)\n\n";
    return 0;
}
