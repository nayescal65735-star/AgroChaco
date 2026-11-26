#include "agrochaco/types.hpp"
#include "agrochaco/config.hpp"
#include "agrochaco/simulation_engine.hpp"
#include "agrochaco/json_serializer.hpp"
#include "agrochaco/mpi_runtime.hpp"

#include <mpi.h>
#include <omp.h>
#include <iostream>
#include <string>
#include <vector>
#include <iomanip>
#include <exception>

using namespace agrochaco;

int main(int argc, char* argv[]) {
    int provided = 0;
    const int initResult = MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided);
    if (initResult != MPI_SUCCESS) {
        std::cerr << "[ERROR] No se pudo inicializar MPI.\n";
        return 1;
    }

    int rank = 0;
    int processCount = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &processCount);

    if (provided < MPI_THREAD_FUNNELED) {
        if (rank == 0) {
            std::cerr << "[ERROR] MPI no proporciona MPI_THREAD_FUNNELED.\n";
        }
        MPI_Abort(MPI_COMM_WORLD, 1);
        return 1;
    }

    try {
        std::string configFile;
        std::string outputFile;
        std::string csvFile;
        int overrideDays = -1;
        int overrideRows = -1;
        int overrideCols = -1;
        int overrideThreads = -1;
        int setupDecision = 0;

        if (rank == 0) {
            for (int i = 1; i < argc; ++i) {
                std::string arg = argv[i];
                if (arg == "--help" || arg == "-h") {
                    setupDecision = 1;
                    break;
                } else if ((arg == "--config" || arg == "-c") && i + 1 < argc) {
                    configFile = argv[++i];
                } else if ((arg == "--output" || arg == "-o") && i + 1 < argc) {
                    outputFile = argv[++i];
                } else if (arg == "--csv" && i + 1 < argc) {
                    csvFile = argv[++i];
                } else if (arg == "--days" && i + 1 < argc) {
                    try { overrideDays = std::stoi(argv[++i]); } catch (...) { setupDecision = 2; break; }
                } else if (arg == "--rows" && i + 1 < argc) {
                    try { overrideRows = std::stoi(argv[++i]); } catch (...) { setupDecision = 2; break; }
                } else if (arg == "--cols" && i + 1 < argc) {
                    try { overrideCols = std::stoi(argv[++i]); } catch (...) { setupDecision = 2; break; }
                } else if (arg == "--threads" && i + 1 < argc) {
                    try { overrideThreads = std::stoi(argv[++i]); } catch (...) { setupDecision = 2; break; }
                } else {
                    setupDecision = 2;
                    break;
                }
            }
        }

        setupDecision = broadcastDecision(MPI_COMM_WORLD, rank, setupDecision);
        if (setupDecision == 1) {
            if (rank == 0) {
                std::cout
                    << "AgroChaco - Motor híbrido MPI + OpenMP\n"
                    << "Opciones:\n"
                    << "  --config <archivo.json>\n"
                    << "  --output <archivo.json>\n"
                    << "  --csv <archivo.csv>\n"
                    << "  --days <numero>\n"
                    << "  --rows <numero>\n"
                    << "  --cols <numero>\n"
                    << "  --threads <numero>\n"
                    << "Los procesos se especifican con mpirun -np.\n"
                    << "Los hilos se especifican con --threads o OMP_NUM_THREADS.\n";
            }
            MPI_Finalize();
            return 0;
        }
        if (setupDecision == 2) {
            if (rank == 0) {
                std::cerr << "[ERROR] Argumento desconocido o incompleto.\n";
            }
            MPI_Finalize();
            return 2;
        }

        SimulationConfig config;
        int loadStatus = 0;
        if (rank == 0) {
            try {
                config = configFile.empty() ? ConfigLoader::createDefault()
                                            : ConfigLoader::loadFromFile(configFile);
                if (overrideDays != -1) config.simulationDays = overrideDays;
                if (overrideRows != -1) config.gridConfig.rows = overrideRows;
                if (overrideCols != -1) config.gridConfig.cols = overrideCols;
                if (overrideThreads != -1) config.openmpThreads = overrideThreads;
            } catch (const std::exception& e) {
                std::cerr << "[ERROR] Fallo al cargar la configuración: " << e.what() << "\n";
                loadStatus = 1;
            }
        }

        loadStatus = broadcastDecision(MPI_COMM_WORLD, rank, loadStatus);
        if (loadStatus != 0) {
            MPI_Finalize();
            return 1;
        }

        std::string configError;
        if (!broadcastConfiguration(MPI_COMM_WORLD, rank, config, configError)) {
            if (rank == 0) {
                std::cerr << "[ERROR] Configuración MPI divergente o no distribuible: "
                          << configError << "\n";
            }
            MPI_Finalize();
            return 2;
        }

        config.engine = SimulationEngine::HIBRIDO;
        config.mpiProcesses = processCount;
        config.nodesCount = 1;

        int exitCode = 0;
        HybridEngine engine(config);

        if (rank == 0) {
            std::cout
                << "\nAGROCHACO - MOTOR HÍBRIDO MPI + OPENMP\n"
                << "Zona: " << config.zoneName << "\n"
                << "Días: " << config.simulationDays << "\n"
                << "Malla: " << config.gridConfig.rows << "x"
                << config.gridConfig.cols << "\n"
                << "Procesos MPI efectivos: " << processCount << "\n"
                << "Hilos OpenMP solicitados: "
                << config.openmpThreads.value_or(omp_get_max_threads()) << "\n"
                << "Nodos efectivos: 1\n\n";
        }

        try {
            const SimulationResult result = engine.run();
            if (result.status != "completed") {
                exitCode = 3;
            } else if (rank == 0) {
                std::cout << "Hilos OpenMP efectivos: "
                          << result.config.openmpThreads.value_or(0) << "\n";
                std::cout << std::fixed << std::setprecision(4)
                          << "Tiempo híbrido: " << result.executionTimeSeconds << " s\n"
                          << std::setprecision(3)
                          << "CWSI promedio: " << result.averageCWSI << "\n"
                          << std::setprecision(1)
                          << "Humedad final: " << result.soilMoistureFinalPercent << " %\n"
                          << "Déficit hídrico: " << result.waterDeficitMm << " mm\n"
                          << "Pérdida de rendimiento: " << result.yieldLossPercent << " %\n"
                          << "Rendimiento estimado: " << result.estimatedYieldTnHa << " tn/ha\n";

                if (!outputFile.empty() && !JsonSerializer::saveResultToFile(result, outputFile)) {
                    std::cerr << "[ERROR] No se pudo guardar el JSON.\n";
                    exitCode = 4;
                }
                if (exitCode == 0 && !csvFile.empty() && !JsonSerializer::exportTimelineToCsv(result, csvFile)) {
                    std::cerr << "[ERROR] No se pudo guardar el CSV.\n";
                    exitCode = 5;
                }
            }
        } catch (const std::exception& e) {
            if (rank == 0) {
                std::cerr << "[ERROR] " << e.what() << "\n";
            }
            exitCode = 3;
        }

        exitCode = broadcastDecision(MPI_COMM_WORLD, rank, exitCode);
        MPI_Finalize();
        return exitCode;
    } catch (const std::exception& e) {
        if (rank == 0) {
            std::cerr << "[ERROR] " << e.what() << "\n";
        }
        MPI_Abort(MPI_COMM_WORLD, 1);
        return 1;
    }
}
