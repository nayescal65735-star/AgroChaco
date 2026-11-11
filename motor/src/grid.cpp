#include "agrochaco/grid.hpp"
#include "agrochaco/soil_model.hpp"
#include <cmath>
#include <algorithm>
#include <mpi.h>
#include <omp.h>
#include <stdexcept>

namespace agrochaco {

SpatialGrid::SpatialGrid(int rows, int cols, double cellSizeMeters, double initialMoisture, const SoilInfo& soil)
    : rows_(rows > 0 ? rows : 10),
      cols_(cols > 0 ? cols : 10),
      cellSizeMeters_(cellSizeMeters > 0.0 ? cellSizeMeters : 50.0),
      moisture_(rows_ * cols_, initialMoisture),
      cwsi_(rows_ * cols_, 0.0),
      depthFactor_(rows_ * cols_, 1.0) {

    // Inicialización del factor de variación edáfica (profundidad de suelo efectiva)
    // Simula variaciones suaves de micro-topografía en la parcela chaqueña.
    // Se normaliza matemáticamente para que el promedio global sea estrictamente 1.0,
    // garantizando que no se altere el volumen total medio de la parcela.
    double factorSum = 0.0;
    int total = rows_ * cols_;

    for (int r = 0; r < rows_; ++r) {
        for (int c = 0; c < cols_; ++c) {
            int idx = r * cols_ + c;
            double normR = (rows_ > 1) ? (static_cast<double>(r) / (rows_ - 1) - 0.5) : 0.0;
            double normC = (cols_ > 1) ? (static_cast<double>(c) / (cols_ - 1) - 0.5) : 0.0;

            // Gradiente suave de ±5% en profundidad radicular según pendiente local
            double factor = 1.0 + (normR * 0.06) + (normC * 0.04);
            depthFactor_[idx] = factor;
            factorSum += factor;

            // La humedad inicial se acota físicamente entre PMP y Capacidad de Campo
            moisture_[idx] = std::clamp(initialMoisture, soil.wiltingPoint, soil.fieldCapacity);
        }
    }

    // Normalización exacta: promedio de depthFactor_ = 1.000000
    if (total > 0 && factorSum > 0.0) {
        double meanFactor = factorSum / total;
        for (int i = 0; i < total; ++i) {
            depthFactor_[i] /= meanFactor;
        }
    }
}

SpatialGrid::StepSummary SpatialGrid::updateDailyStep(
    const SoilInfo& soil,
    double etPotential,
    double precipitation,
    double rootDepthMeters
) {
    double totalMoisture = 0.0;
    double totalCwsi = 0.0;
    double totalEta = 0.0;
    double totalDrainage = 0.0;
    double totalDeltaStorage = 0.0;
    double maxMassError = 0.0;
    int cellCount = rows_ * cols_;

    // Actualización celda por celda aplicando PRECIPITACIÓN ESTRICTAMENTE UNIFORME
    for (int r = 0; r < rows_; ++r) {
        for (int c = 0; c < cols_; ++c) {
            int idx = r * cols_ + c;

            // 1. Precipitación uniforme en toda la parcela (conservación de masa)
            double cellPrecipitation = precipitation;

            // 2. Profundidad radicular efectiva de la celda según microtopografía
            double cellDepth = rootDepthMeters * depthFactor_[idx];

            auto cellResult = SoilModel::updateCellMoisture(
                moisture_[idx],
                soil,
                etPotential,
                cellPrecipitation,
                cellDepth
            );

            moisture_[idx] = cellResult.updatedMoisturePercent;
            cwsi_[idx] = cellResult.cwsi;

            totalMoisture += cellResult.updatedMoisturePercent;
            totalCwsi += cellResult.cwsi;
            totalEta += cellResult.etActual;
            totalDrainage += cellResult.deepDrainage;
            totalDeltaStorage += cellResult.deltaStorageMm;

            if (cellResult.massBalanceError > maxMassError) {
                maxMassError = cellResult.massBalanceError;
            }
        }
    }

    StepSummary summary;
    summary.averageMoisture = totalMoisture / cellCount;
    summary.averageCwsi = totalCwsi / cellCount;
    summary.averageEtActual = totalEta / cellCount;
    summary.averageEtPotential = etPotential;
    summary.averagePrecipitation = precipitation;
    summary.averageDeepDrainage = totalDrainage / cellCount;
    summary.averageDeltaStorage = totalDeltaStorage / cellCount;
    summary.massBalanceError = maxMassError;

    return summary;
}


SpatialGrid::StepSummary SpatialGrid::updateDailyStepOpenMP(
    const SoilInfo& soil,
    double etPotential,
    double precipitation,
    double rootDepthMeters
) {
    double totalMoisture = 0.0;
    double totalCwsi = 0.0;
    double totalEta = 0.0;
    double totalDrainage = 0.0;
    double totalDeltaStorage = 0.0;
    double maxMassError = 0.0;
    const int cellCount = rows_ * cols_;

    #pragma omp parallel for schedule(static) reduction(+:totalMoisture,totalCwsi,totalEta,totalDrainage,totalDeltaStorage) reduction(max:maxMassError)
    for (int idx = 0; idx < cellCount; ++idx) {
        const double cellDepth = rootDepthMeters * depthFactor_[idx];

        const auto cellResult = SoilModel::updateCellMoisture(
            moisture_[idx], soil, etPotential, precipitation, cellDepth
        );

        moisture_[idx] = cellResult.updatedMoisturePercent;
        cwsi_[idx] = cellResult.cwsi;

        totalMoisture += cellResult.updatedMoisturePercent;
        totalCwsi += cellResult.cwsi;
        totalEta += cellResult.etActual;
        totalDrainage += cellResult.deepDrainage;
        totalDeltaStorage += cellResult.deltaStorageMm;

        maxMassError = std::max(maxMassError, cellResult.massBalanceError);
    }

    StepSummary summary;
    summary.averageMoisture = totalMoisture / cellCount;
    summary.averageCwsi = totalCwsi / cellCount;
    summary.averageEtActual = totalEta / cellCount;
    summary.averageEtPotential = etPotential;
    summary.averagePrecipitation = precipitation;
    summary.averageDeepDrainage = totalDrainage / cellCount;
    summary.averageDeltaStorage = totalDeltaStorage / cellCount;
    summary.massBalanceError = maxMassError;

    return summary;
}



SpatialGrid::StepSummary SpatialGrid::updateDailyStepMPI(
    const SoilInfo& soil,
    double etPotential,
    double precipitation,
    double rootDepthMeters,
    int rank,
    int processCount
) {
    if (processCount <= 0 || rank < 0 || rank >= processCount) {
        throw std::invalid_argument("Rango o cantidad de procesos MPI inválidos");
    }

    const int cellCount = rows_ * cols_;
    const int start = (cellCount * rank) / processCount;
    const int end = (cellCount * (rank + 1)) / processCount;

    double localSums[5] = {0.0, 0.0, 0.0, 0.0, 0.0};
    double localMaxMassError = 0.0;

    for (int idx = start; idx < end; ++idx) {
        const double cellDepth = rootDepthMeters * depthFactor_[idx];

        const auto cellResult = SoilModel::updateCellMoisture(
            moisture_[idx], soil, etPotential, precipitation, cellDepth
        );

        moisture_[idx] = cellResult.updatedMoisturePercent;
        cwsi_[idx] = cellResult.cwsi;

        localSums[0] += cellResult.updatedMoisturePercent;
        localSums[1] += cellResult.cwsi;
        localSums[2] += cellResult.etActual;
        localSums[3] += cellResult.deepDrainage;
        localSums[4] += cellResult.deltaStorageMm;

        localMaxMassError = std::max(
            localMaxMassError, cellResult.massBalanceError
        );
    }

    double globalSums[5] = {};
    double globalMaxMassError = 0.0;

    MPI_Allreduce(
        localSums, globalSums, 5, MPI_DOUBLE, MPI_SUM, MPI_COMM_WORLD
    );

    MPI_Allreduce(
        &localMaxMassError, &globalMaxMassError,
        1, MPI_DOUBLE, MPI_MAX, MPI_COMM_WORLD
    );

    StepSummary summary;
    summary.averageMoisture = globalSums[0] / cellCount;
    summary.averageCwsi = globalSums[1] / cellCount;
    summary.averageEtActual = globalSums[2] / cellCount;
    summary.averageEtPotential = etPotential;
    summary.averagePrecipitation = precipitation;
    summary.averageDeepDrainage = globalSums[3] / cellCount;
    summary.averageDeltaStorage = globalSums[4] / cellCount;
    summary.massBalanceError = globalMaxMassError;

    return summary;
}


SpatialGrid::StepSummary SpatialGrid::updateDailyStepHybrid(
    const SoilInfo& soil,
    double etPotential,
    double precipitation,
    double rootDepthMeters,
    int rank,
    int processCount
) {
    if (processCount <= 0 || rank < 0 || rank >= processCount) {
        throw std::invalid_argument("Rango o cantidad de procesos MPI inválidos");
    }

    const int cellCount = rows_ * cols_;
    const int start = (cellCount * rank) / processCount;
    const int end = (cellCount * (rank + 1)) / processCount;

    double localSums[5] = {0.0, 0.0, 0.0, 0.0, 0.0};
    double localMaxMassError = 0.0;

    #pragma omp parallel for schedule(static) \
        reduction(+:localSums[:5]) reduction(max:localMaxMassError)
    for (int idx = start; idx < end; ++idx) {
        const double cellDepth = rootDepthMeters * depthFactor_[idx];

        const auto cellResult = SoilModel::updateCellMoisture(
            moisture_[idx], soil, etPotential, precipitation, cellDepth
        );

        moisture_[idx] = cellResult.updatedMoisturePercent;
        cwsi_[idx] = cellResult.cwsi;

        localSums[0] += cellResult.updatedMoisturePercent;
        localSums[1] += cellResult.cwsi;
        localSums[2] += cellResult.etActual;
        localSums[3] += cellResult.deepDrainage;
        localSums[4] += cellResult.deltaStorageMm;

        localMaxMassError = std::max(
            localMaxMassError, cellResult.massBalanceError
        );
    }

    double globalSums[5] = {};
    double globalMaxMassError = 0.0;

    MPI_Allreduce(
        localSums, globalSums, 5, MPI_DOUBLE, MPI_SUM, MPI_COMM_WORLD
    );

    MPI_Allreduce(
        &localMaxMassError, &globalMaxMassError,
        1, MPI_DOUBLE, MPI_MAX, MPI_COMM_WORLD
    );

    StepSummary summary;
    summary.averageMoisture = globalSums[0] / cellCount;
    summary.averageCwsi = globalSums[1] / cellCount;
    summary.averageEtActual = globalSums[2] / cellCount;
    summary.averageEtPotential = etPotential;
    summary.averagePrecipitation = precipitation;
    summary.averageDeepDrainage = globalSums[3] / cellCount;
    summary.averageDeltaStorage = globalSums[4] / cellCount;
    summary.massBalanceError = globalMaxMassError;

    return summary;
}


void SpatialGrid::synchronizeForMPI(int rank, int processCount) {
    const int cellCount = rows_ * cols_;
    const int start = (cellCount * rank) / processCount;
    const int end = (cellCount * (rank + 1)) / processCount;

    for (int idx = 0; idx < cellCount; ++idx) {
        if (idx < start || idx >= end) {
            moisture_[idx] = 0.0;
            cwsi_[idx] = 0.0;
        }
    }

    MPI_Allreduce(
        MPI_IN_PLACE, moisture_.data(), cellCount,
        MPI_DOUBLE, MPI_SUM, MPI_COMM_WORLD
    );

    MPI_Allreduce(
        MPI_IN_PLACE, cwsi_.data(), cellCount,
        MPI_DOUBLE, MPI_SUM, MPI_COMM_WORLD
    );
}

std::vector<SpatialCell> SpatialGrid::exportVisualizationGrid(int targetRows, int targetCols) const {
    std::vector<SpatialCell> result;
    if (targetRows <= 0) targetRows = 8;
    if (targetCols <= 0) targetCols = 8;

    result.reserve(targetRows * targetCols);

    for (int tr = 0; tr < targetRows; ++tr) {
        for (int tc = 0; tc < targetCols; ++tc) {
            int rStart = (tr * rows_) / targetRows;
            int rEnd   = ((tr + 1) * rows_) / targetRows;
            int cStart = (tc * cols_) / targetCols;
            int cEnd   = ((tc + 1) * cols_) / targetCols;

            if (rEnd <= rStart) rEnd = rStart + 1;
            if (cEnd <= cStart) cEnd = cStart + 1;
            if (rEnd > rows_) rEnd = rows_;
            if (cEnd > cols_) cEnd = cols_;

            double blockMoistureSum = 0.0;
            double blockCwsiSum = 0.0;
            int blockCount = 0;

            for (int r = rStart; r < rEnd; ++r) {
                for (int c = cStart; c < cEnd; ++c) {
                    int idx = r * cols_ + c;
                    blockMoistureSum += moisture_[idx];
                    blockCwsiSum += cwsi_[idx];
                    blockCount++;
                }
            }

            double avgMoist = (blockCount > 0) ? (blockMoistureSum / blockCount) : 0.0;
            double avgCwsi  = (blockCount > 0) ? (blockCwsiSum / blockCount) : 0.0;

            SpatialCell cell;
            cell.x = tc;
            cell.y = tr;
            cell.moisture = std::round(avgMoist * 10.0) / 10.0;
            cell.cwsi = std::round(avgCwsi * 1000.0) / 1000.0;
            cell.riskLevel = calculateRiskLevel(avgCwsi);

            result.push_back(cell);
        }
    }

    return result;
}

} // namespace agrochaco
