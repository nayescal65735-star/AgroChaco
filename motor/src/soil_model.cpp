#include "agrochaco/soil_model.hpp"
#include <algorithm>
#include <cmath>

namespace agrochaco {

double SoilModel::calculateKs(double moisture, double fc, double wp, double depletionFraction) {
    if (fc <= wp) return 0.0;
    if (moisture >= fc) return 1.0;
    if (moisture <= wp) return 0.0;

    // Umbral crítico de humedad theta* por debajo del cual se induce estrés hídrico
    // Según FAO-56: theta* = FC - p * (FC - WP)
    double thetaStar = fc - depletionFraction * (fc - wp);

    if (moisture >= thetaStar) {
        return 1.0;
    }

    // Coeficiente de reducción lineal de estrés Ks en el rango [WP, theta*]
    double ks = (moisture - wp) / (thetaStar - wp);
    return std::clamp(ks, 0.0, 1.0);
}

SoilModel::CellBalanceResult SoilModel::updateCellMoisture(
    double currentMoisture,
    const SoilInfo& soil,
    double etPotential,
    double precipitation,
    double rootDepthMeters
) {
    CellBalanceResult result;

    if (rootDepthMeters <= 0.05) rootDepthMeters = 0.30;
    if (precipitation < 0.0) precipitation = 0.0;
    if (etPotential < 0.0) etPotential = 0.0;

    double depthMm = rootDepthMeters * 1000.0;

    // Capacidad de retención en mm de columna de agua
    double waterMaxMm = (soil.fieldCapacity / 100.0) * depthMm;
    double waterWpMm  = (soil.wiltingPoint / 100.0) * depthMm;
    double initialWaterMm = (currentMoisture / 100.0) * depthMm;

    // 1. Infiltración y drenaje profundo gravitacional (exceso sobre Capacidad de Campo)
    double waterAfterRainMm = initialWaterMm + precipitation;
    double deepDrainage = 0.0;

    if (waterAfterRainMm > waterMaxMm) {
        deepDrainage = waterAfterRainMm - waterMaxMm;
        waterAfterRainMm = waterMaxMm;
    }

    // 2. Cálculo del factor de estrés Ks sobre la humedad resultante de la infiltración
    double tempMoisture = (waterAfterRainMm / depthMm) * 100.0;
    double ks = calculateKs(tempMoisture, soil.fieldCapacity, soil.wiltingPoint, 0.50);

    // 3. Demanda y transpiración real del cultivo (ETa)
    // El cultivo no puede extraer agua por debajo del punto de marchitez permanente (PMP)
    double availableExtractableMm = std::max(0.0, waterAfterRainMm - waterWpMm);
    double etDemand = etPotential * ks;
    double etActual = std::min(etDemand, availableExtractableMm);

    // 4. Actualización del contenido final de agua en el suelo
    // Conservación estricta: W_final = W_después_de_lluvia - ETa
    double finalWaterMm = waterAfterRainMm - etActual;

    // Límite físico de seguridad: no caer por debajo de PMP por transpiración
    if (finalWaterMm < waterWpMm) {
        finalWaterMm = waterWpMm;
    }

    double finalMoisturePercent = (finalWaterMm / depthMm) * 100.0;

    // 5. Cálculo del Déficit Relativo de Evapotranspiración (CWSI)
    double cwsi = 0.0;
    if (etPotential > 0.001) {
        cwsi = 1.0 - (etActual / etPotential);
        cwsi = std::clamp(cwsi, 0.0, 1.0);
    } else {
        // Demanda nula (días muy fríos o sin radiación): sin estrés evaporativo
        cwsi = 0.0;
    }

    // 6. Verificación de balance de masa: DeltaW + ETa + Drenaje == Precipitación
    double deltaStorageMm = finalWaterMm - initialWaterMm;
    double massBalanceError = std::abs((deltaStorageMm + etActual + deepDrainage) - precipitation);

    result.updatedMoisturePercent = finalMoisturePercent;
    result.etActual = etActual;
    result.cwsi = cwsi;
    result.deepDrainage = deepDrainage;
    result.deficitMm = std::max(0.0, etPotential - etActual);
    result.initialWaterMm = initialWaterMm;
    result.finalWaterMm = finalWaterMm;
    result.deltaStorageMm = deltaStorageMm;
    result.massBalanceError = massBalanceError;

    return result;
}

} // namespace agrochaco
