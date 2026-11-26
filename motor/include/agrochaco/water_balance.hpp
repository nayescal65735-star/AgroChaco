#ifndef AGROCHACO_WATER_BALANCE_HPP
#define AGROCHACO_WATER_BALANCE_HPP

#include "types.hpp"
#include <optional>

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
);

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
);

std::optional<WaterBalanceSummary> makeWaterBalanceSummary(const std::vector<TimelineDataPoint>& points);

}

#endif
