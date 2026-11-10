#include "agrochaco/types.hpp"
#include "agrochaco/config.hpp"
#include "agrochaco/simulation_engine.hpp"
#include "agrochaco/json_serializer.hpp"

#include <mpi.h>
#include <omp.h>
#include <iostream>
#include <string>
#include <vector>
#include <iomanip>
#include <exception>

using namespace agrochaco;

int main(int argc, char* argv[]) {
    MPI_Init(&argc, &argv);

    int rank = 0;
    int processCount = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &processCount);

    int exitCode = 0;

    try {
        std::string configFile;
        std::string outputFile;
        std::string csvFile;

        int overrideDays = -1;
        int overrideRows = -1;
        int overrideCols = -1;
        int overrideThreads = -1;

        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];

            if (arg == "--help" || arg == "-h") {
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
            else if ((arg == "--config" || arg == "-c") && i + 1 < argc) {
                configFile = argv[++i];
            }
            else if ((arg == "--output" || arg == "-o") && i + 1 < argc) {
                outputFile = argv[++i];
            }
            else if (arg == "--csv" && i + 1 < argc) {
                csvFile = argv[++i];
            }
            else if (arg == "--days" && i + 1 < argc) {
                overrideDays = std::stoi(argv[++i]);
            }
            else if (arg == "--rows" && i + 1 < argc) {
                overrideRows = std::stoi(argv[++i]);
            }
            else if (arg == "--cols" && i + 1 < argc) {
                overrideCols = std::stoi(argv[++i]);
            }
            else if (arg == "--threads" && i + 1 < argc) {
                overrideThreads = std::stoi(argv[++i]);
            }
            else {
                if (rank == 0) {
                    std::cerr << "[ERROR] Argumento desconocido o incompleto: "
                              << arg << "\n";
                }
                exitCode = 1;
                break;
            }
        }

        if (exitCode == 0) {
            SimulationConfig config;

            if (!configFile.empty()) {
                config = ConfigLoader::loadFromFile(configFile);
            } else {
                config = ConfigLoader::createDefault();
            }

            if (overrideDays != -1) config.simulationDays = overrideDays;
            if (overrideRows != -1) config.gridConfig.rows = overrideRows;
            if (overrideCols != -1) config.gridConfig.cols = overrideCols;
            if (overrideThreads != -1) config.openmpThreads = overrideThreads;

            config.engine = SimulationEngine::HIBRIDO;
            config.mpiProcesses = processCount;

            std::vector<std::string> errors;
            if (!ConfigValidator::validate(config, errors)) {
                if (rank == 0) {
                    std::cerr << "[ERROR] Configuración inválida:\n";
                    for (const auto& error : errors) {
                        std::cerr << " - " << error << "\n";
                    }
                }
                exitCode = 2;
            } else {
                HybridEngine engine(config);

                if (rank == 0) {
                    std::cout
                        << "\nAGROCHACO - MOTOR HÍBRIDO MPI + OPENMP\n"
                        << "Zona: " << config.zoneName << "\n"
                        << "Días: " << config.simulationDays << "\n"
                        << "Malla: " << config.gridConfig.rows << "x"
                        << config.gridConfig.cols << "\n"
                        << "Procesos MPI: " << processCount << "\n"
                        << "Hilos OpenMP solicitados: "
                        << config.openmpThreads.value_or(omp_get_max_threads()) << "\n\n";
                }

                SimulationResult result = engine.run();

                if (result.status != "completed") {
                    if (rank == 0) {
                        std::cerr
                            << "[ERROR] La simulación no terminó correctamente.\n";
                    }
                    exitCode = 3;
                } else if (rank == 0) {
                    std::cout << std::fixed << std::setprecision(4)
                              << "Tiempo híbrido: "
                              << result.executionTimeSeconds << " s\n"
                              << std::setprecision(3)
                              << "CWSI promedio: " << result.averageCWSI << "\n"
                              << std::setprecision(1)
                              << "Humedad final: "
                              << result.soilMoistureFinalPercent << " %\n"
                              << "Déficit hídrico: "
                              << result.waterDeficitMm << " mm\n"
                              << "Pérdida de rendimiento: "
                              << result.yieldLossPercent << " %\n"
                              << "Rendimiento estimado: "
                              << result.estimatedYieldTnHa << " tn/ha\n";

                    if (!outputFile.empty()) {
                        if (!JsonSerializer::saveResultToFile(result, outputFile)) {
                            std::cerr << "[ERROR] No se pudo guardar el JSON.\n";
                            exitCode = 4;
                        } else {
                            std::cout << "[OK] JSON guardado: "
                                      << outputFile << "\n";
                        }
                    }

                    if (exitCode == 0 && !csvFile.empty()) {
                        if (!JsonSerializer::exportTimelineToCsv(result, csvFile)) {
                            std::cerr << "[ERROR] No se pudo guardar el CSV.\n";
                            exitCode = 5;
                        } else {
                            std::cout << "[OK] CSV guardado: "
                                      << csvFile << "\n";
                        }
                    }
                }
            }
        }

        MPI_Bcast(&exitCode, 1, MPI_INT, 0, MPI_COMM_WORLD);
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
