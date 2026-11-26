#include "agrochaco/soil_model.hpp"
#include <algorithm>
#include <cmath>
#include <limits>

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

void SoilModel::validateForcing(double etPotential, double precipitation) {
    if (!std::isfinite(precipitation) || precipitation < 0.0) {
        throw std::invalid_argument("La precipitación incidente debe ser finita y no negativa.");
    }
    if (!std::isfinite(etPotential) || etPotential < 0.0) {
        throw std::invalid_argument("La demanda ETc debe ser finita y no negativa.");
    }
}

SoilModel::CellBalanceResult SoilModel::updateCellMoisture(
    double currentMoisture,
    const SoilInfo& soil,
    double etPotential,
    double precipitation,
    double rootDepthMeters
) {
    CellBalanceResult result;

    validateForcing(etPotential, precipitation);

    if (!std::isfinite(currentMoisture) || !std::isfinite(rootDepthMeters) || rootDepthMeters <= 0.05) {
        throw std::invalid_argument("La humedad actual y la profundidad radicular deben ser finitas y positivas.");
    }
    if (!std::isfinite(soil.fieldCapacity) || !std::isfinite(soil.wiltingPoint) ||
        soil.fieldCapacity <= soil.wiltingPoint) {
        throw std::invalid_argument("Propiedades edáficas inválidas: se requiere CC > PMP y valores finitos.");
    }

    // Guardia exclusivamente de redondeo machine-epsilon; no es una tolerancia hidrológica.
    const double scale = std::max({1.0, std::abs(soil.wiltingPoint), std::abs(soil.fieldCapacity)});
    const double roundoff = 32.0 * std::numeric_limits<double>::epsilon() * scale;
    if (currentMoisture < soil.wiltingPoint - roundoff || currentMoisture > soil.fieldCapacity + roundoff) {
        throw std::invalid_argument("La humedad inicial de la celda debe encontrarse en el intervalo físico [PMP, CC].");
    }

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

    // 4. Actualización del contenido final de agua en el suelo.
    // ETa ya está limitada por (W_después_de_lluvia - W_PMP): no se inyecta agua para forzar el PMP.
    double finalWaterMm = waterAfterRainMm - etActual;

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
    double massBalanceResidualMm = (deltaStorageMm + etActual + deepDrainage) - precipitation;
    double massBalanceError = std::abs(massBalanceResidualMm);

    result.updatedMoisturePercent = finalMoisturePercent;
    result.etActual = etActual;
    result.cwsi = cwsi;
    result.deepDrainage = deepDrainage;
    result.deficitMm = std::max(0.0, etPotential - etActual);
    result.initialWaterMm = initialWaterMm;
    result.finalWaterMm = finalWaterMm;
    result.deltaStorageMm = deltaStorageMm;
    result.massBalanceError = massBalanceError;
    result.massBalanceResidualMm = massBalanceResidualMm;

    return result;
}

} // namespace agrochaco
