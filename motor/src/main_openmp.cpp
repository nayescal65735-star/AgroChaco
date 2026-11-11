#include "agrochaco/types.hpp"
#include "agrochaco/config.hpp"
#include "agrochaco/simulation_engine.hpp"
#include "agrochaco/json_serializer.hpp"

#include <iostream>
#include <string>
#include <vector>
#include <iomanip>
#include <algorithm>

using namespace agrochaco;

int main(int argc, char* argv[]) {
    std::string configFile;
    std::string outputFile;
    std::string csvFile;

    int threads = 0;
    int overrideDays = -1;
    int overrideRows = -1;
    int overrideCols = -1;

    try {
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];

            if (arg == "--help" || arg == "-h") {
                std::cout << "AgroChaco - Motor paralelo OpenMP\n"
                          << "Opciones:\n"
                          << "  --config <archivo.json>\n"
                          << "  --threads <numero>\n"
                          << "  --output <archivo.json>\n"
                          << "  --csv <archivo.csv>\n"
                          << "  --days <numero>\n"
                          << "  --rows <numero>\n"
                          << "  --cols <numero>\n";
                return 0;
            } else if ((arg == "--config" || arg == "-c") && i + 1 < argc) {
                configFile = argv[++i];
            } else if (arg == "--threads" && i + 1 < argc) {
                threads = std::stoi(argv[++i]);
            } else if ((arg == "--output" || arg == "-o") && i + 1 < argc) {
                outputFile = argv[++i];
            } else if (arg == "--csv" && i + 1 < argc) {
                csvFile = argv[++i];
            } else if (arg == "--days" && i + 1 < argc) {
                overrideDays = std::stoi(argv[++i]);
            } else if (arg == "--rows" && i + 1 < argc) {
                overrideRows = std::stoi(argv[++i]);
            } else if (arg == "--cols" && i + 1 < argc) {
                overrideCols = std::stoi(argv[++i]);
            } else {
                std::cerr << "[ERROR] Argumento desconocido o incompleto: " << arg << "\n";
                return 1;
            }
        }

        SimulationConfig config;

        if (!configFile.empty()) {
            config = ConfigLoader::loadFromFile(configFile);
        } else {
            config = ConfigLoader::createDefault();
        }

        if (threads != 0) {
            config.openmpThreads = threads;
        }

        if (overrideDays != -1) config.simulationDays = overrideDays;
        if (overrideRows != -1) config.gridConfig.rows = overrideRows;
        if (overrideCols != -1) config.gridConfig.cols = overrideCols;

        std::vector<std::string> errors;
        if (!ConfigValidator::validate(config, errors)) {
            std::cerr << "[ERROR] Configuración inválida:\n";
            for (const auto& error : errors) {
                std::cerr << " - " << error << "\n";
            }
            return 2;
        }

        OpenMPEngine engine(config);

        std::cout << "\nAGROCHACO - MOTOR PARALELO OPENMP\n"
                  << "Zona: " << config.zoneName << "\n"
                  << "Días: " << config.simulationDays << "\n"
                  << "Malla: " << config.gridConfig.rows << "x"
                  << config.gridConfig.cols << "\n"
                  << "Hilos solicitados: "
                  << config.openmpThreads.value_or(0) << "\n\n";

        SimulationResult result = engine.run();

        if (result.status != "completed") {
            std::cerr << "[ERROR] La simulación no terminó correctamente.\n";
            return 3;
        }

        std::cout << std::fixed << std::setprecision(4)
                  << "Tiempo OpenMP: " << result.executionTimeSeconds << " s\n"
                  << std::setprecision(3)
                  << "CWSI promedio: " << result.averageCWSI << "\n"
                  << std::setprecision(1)
                  << "Humedad final: " << result.soilMoistureFinalPercent << " %\n"
                  << "Déficit hídrico: " << result.waterDeficitMm << " mm\n"
                  << "Pérdida de rendimiento: " << result.yieldLossPercent << " %\n"
                  << "Rendimiento estimado: " << result.estimatedYieldTnHa << " tn/ha\n";

        if (!outputFile.empty()) {
            if (!JsonSerializer::saveResultToFile(result, outputFile)) {
                std::cerr << "[ERROR] No se pudo guardar el JSON.\n";
                return 4;
            }
            std::cout << "[OK] JSON guardado: " << outputFile << "\n";
        }

        if (!csvFile.empty()) {
            if (!JsonSerializer::exportTimelineToCsv(result, csvFile)) {
                std::cerr << "[ERROR] No se pudo guardar el CSV.\n";
                return 5;
            }
            std::cout << "[OK] CSV guardado: " << csvFile << "\n";
        }

        return 0;

    } catch (const std::exception& e) {
        std::cerr << "[ERROR] " << e.what() << "\n";
        return 1;
    }
}
