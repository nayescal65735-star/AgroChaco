#include "agrochaco/water_balance.hpp"
#include <algorithm>
#include <cmath>

namespace agrochaco {

WaterBalanceData makeWaterBalanceData(
    double precipitationMm,
    double etcMm,
    double etaMm,
    double deepDrainageMm,
    double storageInitialMm,
    double storageFinalMm,
    double storageChangeMm,
    double balanceErrorMm,
    double balanceResidualMm,
    double rootDepthMm,
    double rootDepthStorageRebaseMm
) {
    WaterBalanceData data;
    data.precipitationMm = precipitationMm;
    data.etcMm = etcMm;
    data.etaMm = etaMm;
    data.deepDrainageMm = deepDrainageMm;
    data.storageInitialMm = storageInitialMm;
    data.storageFinalMm = storageFinalMm;
    data.storageChangeMm = storageChangeMm;
    data.balanceErrorMm = balanceErrorMm;
    data.balanceResidualMm = balanceResidualMm;
    data.rootDepthMm = rootDepthMm;
    data.rootDepthStorageRebaseMm = rootDepthStorageRebaseMm;
    return data;
}

WaterBalanceData makeWaterBalanceData(
    double precipitationMm,
    double etcMm,
    double etaMm,
    double deepDrainageMm,
    double storageInitialMm,
    double storageFinalMm,
    double storageChangeMm,
    double balanceErrorMm,
    double rootDepthMm,
    double rootDepthStorageRebaseMm
) {
    const double residual = (storageChangeMm + etaMm + deepDrainageMm) - precipitationMm;
    return makeWaterBalanceData(
        precipitationMm, etcMm, etaMm, deepDrainageMm,
        storageInitialMm, storageFinalMm, storageChangeMm,
        balanceErrorMm, residual, rootDepthMm, rootDepthStorageRebaseMm
    );
}

std::optional<WaterBalanceSummary> makeWaterBalanceSummary(const std::vector<TimelineDataPoint>& points) {
    if (points.empty()) {
        return std::nullopt;
    }

    WaterBalanceSummary summary;

    for (const auto& point : points) {
        if (!point.waterBalance.has_value()) {
            return std::nullopt;
        }

        const auto& balance = point.waterBalance.value();
        const bool complete = std::isfinite(balance.precipitationMm) &&
                              std::isfinite(balance.etcMm) &&
                              std::isfinite(balance.etaMm) &&
                              std::isfinite(balance.deepDrainageMm) &&
                              std::isfinite(balance.storageInitialMm) &&
                              std::isfinite(balance.storageFinalMm) &&
                              std::isfinite(balance.storageChangeMm) &&
                              std::isfinite(balance.balanceErrorMm) &&
                              std::isfinite(balance.balanceResidualMm) &&
                              std::isfinite(balance.rootDepthMm) &&
                              std::isfinite(balance.rootDepthStorageRebaseMm);
        if (!complete) {
            return std::nullopt;
        }

        if (&point == &points.front()) {
            summary.storageInitialMm = balance.storageInitialMm;
        }

        summary.precipitationTotalMm += balance.precipitationMm;
        summary.etcTotalMm += balance.etcMm;
        summary.etaTotalMm += balance.etaMm;
        summary.deepDrainageTotalMm += balance.deepDrainageMm;
        summary.storageChangeMm += balance.storageChangeMm;
        summary.massBalanceResidualMm += balance.balanceResidualMm;
        summary.rootDepthStorageRebaseTotalMm += balance.rootDepthStorageRebaseMm;
        summary.maxDailyBalanceErrorMm = std::max(
            summary.maxDailyBalanceErrorMm, std::abs(balance.balanceErrorMm)
        );
        summary.storageFinalMm = balance.storageFinalMm;
    }

    return summary;
}

}
