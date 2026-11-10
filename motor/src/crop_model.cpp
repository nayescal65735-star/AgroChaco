#include "agrochaco/crop_model.hpp"
#include <algorithm>
#include <cmath>
#include <numeric>

namespace agrochaco {

double CropModel::calculateRootDepth(int day, int cycleDays) {
    if (cycleDays <= 0) cycleDays = 120;
    double frac = static_cast<double>(day) / static_cast<double>(cycleDays);

    // Crecimiento radicular sigmoide desde 0.25 m hasta 1.00 m en floración
    const double minDepth = 0.25;
    const double maxDepth = 1.00;

    if (frac <= 0.50) {
        // Fase de profundización activa durante el período vegetativo
        double progress = frac / 0.50;
        return minDepth + progress * (maxDepth - minDepth);
    } else {
        // En llenado y madurez la profundidad radicular se mantiene estabilizada
        return maxDepth;
    }
}

double CropModel::calculateEtc(double et0, double kc) {
    if (et0 < 0.0) et0 = 0.0;
    if (kc < 0.0) kc = 0.0;
    return et0 * kc;
}

double CropModel::calculateYieldLoss(
    const std::vector<double>& stageEtc,
    const std::vector<double>& stageEta,
    const std::vector<double>& stageKy,
    const CornVarietyInfo& variety
) {
    // 1. Demanda evaporativa total del ciclo
    double totalEtc = std::accumulate(stageEtc.begin(), stageEtc.end(), 0.0);
    if (totalEtc <= 0.001) {
        return 0.0; // Sin demanda evaporativa, no hay pérdida por déficit hídrico
    }

    // 2. Modelo multiplicativo por etapas de FAO-33 / Jensen (1968, citado en FAO-33 p. 40):
    // Ya / Ym = prod_i [ 1 - Ky_i * (1 - ETa_i / ETc_i) ]
    // Este modelo preserva la no-linealidad del estrés hídrico y penaliza críticamente
    // el déficit durante floración (Ky = 1.25) sin ponderaciones heurísticas.
    double relativeYield = 1.0;
    size_t numStages = std::min({stageEtc.size(), stageEta.size(), stageKy.size()});

    for (size_t i = 0; i < numStages; ++i) {
        if (stageEtc[i] > 0.001) {
            double stageDeficit = 1.0 - (stageEta[i] / stageEtc[i]);
            stageDeficit = std::clamp(stageDeficit, 0.0, 1.0);

            // Factor de rendimiento de la etapa: 1 - Ky * deficit
            double stageYieldFactor = 1.0 - (stageKy[i] * stageDeficit);
            if (stageYieldFactor < 0.0) stageYieldFactor = 0.0;

            relativeYield *= stageYieldFactor;
        }
    }

    // Pérdida base teórica de rendimiento
    double baseYieldLossRatio = 1.0 - relativeYield;
    if (baseYieldLossRatio < 0.0) baseYieldLossRatio = 0.0;

    // 3. Supuesto de modelación comparativa: Factor de adaptación por rusticidad varietal
    // (Ajuste documentado para diferenciar la rusticidad del criollo chaqueño frente a híbridos comerciales)
    double varietyMultiplier = 1.0;
    if (variety.droughtResistance == "Muy Alta") {
        varietyMultiplier = 0.85; // Criollo chaqueño: rusticidad alta amortigua el impacto
    } else if (variety.droughtResistance == "Alta") {
        varietyMultiplier = 0.95; // Híbrido rústico adaptado (INIAF H1, Pioneer)
    } else {
        varietyMultiplier = 1.05; // Híbrido comercial estándar (Dekalb)
    }

    double finalYieldLossPercent = baseYieldLossRatio * varietyMultiplier * 100.0;

    // 4. Límite físico riguroso: la pérdida debe encontrarse estrictamente entre 0% y 100%
    return std::clamp(finalYieldLossPercent, 0.0, 100.0);
}

} // namespace agrochaco
