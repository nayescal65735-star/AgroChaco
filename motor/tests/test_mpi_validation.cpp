#include "agrochaco/agronomic_data.hpp"
#include "agrochaco/config.hpp"
#include "agrochaco/grid.hpp"
#include "agrochaco/mpi_runtime.hpp"
#include "agrochaco/simulation_engine.hpp"
#include "agrochaco/types.hpp"

#include <mpi.h>
#include <omp.h>

#include <cmath>
#include <iostream>
#include <string>
#include <vector>

using namespace agrochaco;

static int g_testFailures = 0;
static int g_rank = 0;
static int g_size = 1;

#define REQUIRE(condition)                                                              \
    do {                                                                               \
        if (!(condition)) {                                                            \
            std::cerr << "FAIL rank " << g_rank << " " << __FILE__ << ":" << __LINE__   \
                      << ": " #condition "\n";                                         \
            ++g_testFailures;                                                          \
        }                                                                              \
    } while (false)

static void runTest(const char* name, void (*test)()) {
    try {
        test();
    } catch (const std::exception& e) {
        std::cerr << "FAIL rank " << g_rank << " " << name
                  << ": excepción inesperada: " << e.what() << "\n";
        ++g_testFailures;
    }
}

static SimulationConfig smallConfig() {
    SimulationConfig config = ConfigLoader::createDefault();
    config.id = "SIM-7B3-MPI";
    config.simulationDays = 3;
    config.gridConfig.rows = 7;
    config.gridConfig.cols = 11;
    config.initialMoisturePercent = 8.4;
    return config;
}

static void testMpiPartitionCoversEachCellOnce() {
    const std::vector<int> cellCounts{1, 2, 7, 11, 77, 100};
    for (int cellCount : cellCounts) {
        std::vector<int> visits(static_cast<size_t>(cellCount), 0);
        for (int rank = 0; rank < g_size; ++rank) {
            const int start = (cellCount * rank) / g_size;
            const int end = (cellCount * (rank + 1)) / g_size;
            REQUIRE(start >= 0);
            REQUIRE(end >= start);
            REQUIRE(end <= cellCount);
            for (int idx = start; idx < end; ++idx) {
                ++visits[static_cast<size_t>(idx)];
            }
        }
        for (int visit : visits) {
            REQUIRE(visit == 1);
        }
    }
}

static void testMpiGridReconstructionIsComplete() {
    const auto& soil = AgronomicData::getSoil(SoilType::ARENOSO);
    const int rows = 7;
    const int cols = 11;

    SpatialGrid reference(rows, cols, 50.0, 8.4, soil);
    const auto referenceSummary = reference.updateDailyStep(soil, 3.0, 4.0, 0.50);

    SpatialGrid distributed(rows, cols, 50.0, 8.4, soil);
    const auto localSummary = distributed.updateDailyStepMPI(
        soil, 3.0, 4.0, 0.50, g_rank, g_size, MPI_COMM_WORLD
    );
    distributed.synchronizeForMPI(g_rank, g_size, MPI_COMM_WORLD);

    REQUIRE(std::abs(localSummary.averageEtActual - referenceSummary.averageEtActual) < 1e-9);
    REQUIRE(std::abs(localSummary.massBalanceResidualMm - referenceSummary.massBalanceResidualMm) < 1e-9);

    for (int r = 0; r < rows; ++r) {
        for (int c = 0; c < cols; ++c) {
            REQUIRE(std::abs(distributed.getMoisture(r, c) - reference.getMoisture(r, c)) < 1e-9);
            REQUIRE(std::abs(distributed.getCwsi(r, c) - reference.getCwsi(r, c)) < 1e-9);
        }
    }
}

static void testHybridGridEquivalenceWithThreads() {
    omp_set_dynamic(0);
    omp_set_num_threads(2);

    const auto& soil = AgronomicData::getSoil(SoilType::ARENOSO);
    SpatialGrid reference(7, 11, 50.0, 8.4, soil);
    const auto referenceSummary = reference.updateDailyStep(soil, 3.0, 4.0, 0.50);

    SpatialGrid hybrid(7, 11, 50.0, 8.4, soil);
    const auto hybridSummary = hybrid.updateDailyStepHybrid(
        soil, 3.0, 4.0, 0.50, g_rank, g_size, MPI_COMM_WORLD
    );
    hybrid.synchronizeForMPI(g_rank, g_size, MPI_COMM_WORLD);

    REQUIRE(std::abs(hybridSummary.averageMoisture - referenceSummary.averageMoisture) < 1e-9);
    REQUIRE(std::abs(hybridSummary.averageCwsi - referenceSummary.averageCwsi) < 1e-9);
    REQUIRE(std::abs(hybridSummary.massBalanceError - referenceSummary.massBalanceError) < 1e-11);
    REQUIRE(std::abs(hybridSummary.massBalanceResidualMm - referenceSummary.massBalanceResidualMm) < 1e-11);

    for (int r = 0; r < 7; ++r) {
        for (int c = 0; c < 11; ++c) {
            REQUIRE(std::abs(hybrid.getMoisture(r, c) - reference.getMoisture(r, c)) < 1e-9);
        }
    }
}

static void testConfigurationBroadcastConverges() {
    SimulationConfig config = smallConfig();
    if (g_rank == 0) {
        config.simulationDays = 4;
        config.gridConfig.rows = 6;
        config.gridConfig.cols = 7;
    } else {
        config.simulationDays = 999;
        config.gridConfig.rows = 1;
        config.gridConfig.cols = 1;
    }

    std::string error;
    REQUIRE(broadcastConfiguration(MPI_COMM_WORLD, g_rank, config, error));
    REQUIRE(error.empty());
    REQUIRE(config.simulationDays == 4);
    REQUIRE(config.gridConfig.rows == 6);
    REQUIRE(config.gridConfig.cols == 7);
}

static void testEnginesReportEffectiveResources() {
    SimulationConfig config = smallConfig();
    config.openmpThreads = 2;

    const auto mpiResult = MpiEngine(config).run();
    REQUIRE(mpiResult.status == "completed");
    REQUIRE(mpiResult.config.engine == SimulationEngine::MPI);
    REQUIRE(mpiResult.config.mpiProcesses.value_or(-1) == g_size);
    REQUIRE(!mpiResult.speedup.has_value());
    REQUIRE(!mpiResult.efficiency.has_value());

    const auto hybridResult = HybridEngine(config).run();
    REQUIRE(hybridResult.status == "completed");
    REQUIRE(hybridResult.config.engine == SimulationEngine::HIBRIDO);
    REQUIRE(hybridResult.config.mpiProcesses.value_or(-1) == g_size);
    REQUIRE(hybridResult.config.openmpThreads.value_or(-1) == 2);
    REQUIRE(!hybridResult.speedup.has_value());
    REQUIRE(!hybridResult.efficiency.has_value());
}

static void testInvalidConfigurationFailsCollectively() {
    SimulationConfig config = smallConfig();
    config.simulationDays = 0;

    const auto result = MpiEngine(config).run();
    REQUIRE(result.status == "failed");
}

int main(int argc, char** argv) {
    int provided = 0;
    MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided);
    MPI_Comm_rank(MPI_COMM_WORLD, &g_rank);
    MPI_Comm_size(MPI_COMM_WORLD, &g_size);

    if (provided < MPI_THREAD_FUNNELED) {
        if (g_rank == 0) {
            std::cerr << "[ERROR] MPI no proporciona MPI_THREAD_FUNNELED.\n";
        }
        MPI_Abort(MPI_COMM_WORLD, 1);
        return 1;
    }

    runTest("testMpiPartitionCoversEachCellOnce", testMpiPartitionCoversEachCellOnce);
    runTest("testMpiGridReconstructionIsComplete", testMpiGridReconstructionIsComplete);
    runTest("testHybridGridEquivalenceWithThreads", testHybridGridEquivalenceWithThreads);
    runTest("testConfigurationBroadcastConverges", testConfigurationBroadcastConverges);
    runTest("testEnginesReportEffectiveResources", testEnginesReportEffectiveResources);
    runTest("testInvalidConfigurationFailsCollectively", testInvalidConfigurationFailsCollectively);

    int globalFailures = 0;
    MPI_Allreduce(&g_testFailures, &globalFailures, 1, MPI_INT, MPI_MAX, MPI_COMM_WORLD);

    if (g_rank == 0) {
        if (globalFailures == 0) {
            std::cout << "\n[OK] PRUEBAS MPI REALES PASARON CON ÉXITO (6/6) CON "
                      << g_size << " PROCESOS.\n\n";
        } else {
            std::cerr << "\n[FAIL] " << globalFailures
                      << " comprobación(es) MPI fallaron.\n\n";
        }
    }

    MPI_Finalize();
    return globalFailures == 0 ? 0 : 1;
}
