#include "agrochaco/crop_model.hpp"
#include <algorithm>

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
    (void)variety;

    constexpr double kMinEtcMm = 0.001;
    const size_t numStages = std::min({stageEtc.size(), stageEta.size(), stageKy.size()});

    double totalEtc = 0.0;
    for (size_t i = 0; i < numStages; ++i) {
        if (stageEtc[i] > kMinEtcMm) {
            totalEtc += stageEtc[i];
        }
    }
    if (totalEtc <= kMinEtcMm) {
        return 0.0;
    }

    double lossRatio = 0.0;
    for (size_t i = 0; i < numStages; ++i) {
        if (stageEtc[i] <= kMinEtcMm) {
            continue;
        }

        const double eta = std::clamp(stageEta[i], 0.0, stageEtc[i]);
        const double stageDeficit = std::clamp(1.0 - eta / stageEtc[i], 0.0, 1.0);
        const double demandWeight = stageEtc[i] / totalEtc;
        lossRatio += stageKy[i] * stageDeficit * demandWeight;
    }

    return std::clamp(lossRatio * 100.0, 0.0, 100.0);
}

} // namespace agrochaco
