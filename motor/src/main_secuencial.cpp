#include "agrochaco/types.hpp"
#include "agrochaco/config.hpp"
#include "agrochaco/simulation_engine.hpp"
#include "agrochaco/json_serializer.hpp"
#include <iostream>
#include <string>
#include <vector>
#include <iomanip>

using namespace agrochaco;

void printUsage(const char* progName) {
    std::cout << "===============================================================\n"
              << " AgroChaco — Motor de Simulación Secuencial C++17 (Baseline)\n"
              << " TEL420 Sistemas Paralelos (Gestión 2026)\n"
              << "===============================================================\n\n"
              << "Uso:\n"
              << "  " << progName << " [opciones]\n\n"
              << "Opciones:\n"
              << "  -c, --config <archivo.json>  Ruta al archivo JSON de configuración.\n"
              << "  -o, --output <archivo.json>  Ruta donde se guardará el resultado JSON.\n"
              << "  --csv <archivo.csv>          Ruta opcional para exportar serie temporal CSV.\n"
              << "  -d, --days <número>          Sobrescribir cantidad de días simulados (1-365).\n"
              << "  -r, --rows <número>          Sobrescribir filas de la malla espacial.\n"
              << "  --cols <número>              Sobrescribir columnas de la malla espacial.\n"
              << "  -h, --help                   Muestra este mensaje de ayuda.\n\n"
              << "Ejemplo:\n"
              << "  " << progName << " --config motor/config/simulacion_villamontes.json --output results/res.json\n\n";
}

int main(int argc, char* argv[]) {
    std::string configFile = "";
    std::string outputFile = "";
    std::string csvFile = "";
    int overrideDays = -1;
    int overrideRows = -1;
    int overrideCols = -1;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-h" || arg == "--help") {
            printUsage(argv[0]);
            return 0;
        } else if ((arg == "-c" || arg == "--config") && i + 1 < argc) {
            configFile = argv[++i];
        } else if ((arg == "-o" || arg == "--output") && i + 1 < argc) {
            outputFile = argv[++i];
        } else if (arg == "--csv" && i + 1 < argc) {
            csvFile = argv[++i];
        } else if ((arg == "-d" || arg == "--days") && i + 1 < argc) {
            overrideDays = std::stoi(argv[++i]);
        } else if ((arg == "-r" || arg == "--rows") && i + 1 < argc) {
            overrideRows = std::stoi(argv[++i]);
        } else if (arg == "--cols" && i + 1 < argc) {
            overrideCols = std::stoi(argv[++i]);
        } else if (configFile.empty() && arg[0] != '-') {
            configFile = arg; // Argumento posicional
        } else {
            std::cerr << "[ERROR] Argumento no reconocido: " << arg << "\n";
            printUsage(argv[0]);
            return 1;
        }
    }

    std::cout << "\n===============================================================\n"
              << "          AGROCHACO — SIMULADOR SECUENCIAL C++17               \n"
              << "  Estrés Hídrico y Balance de Sequía en Maíz del Gran Chaco    \n"
              << "===============================================================\n\n";

    SimulationConfig config;
    try {
        if (!configFile.empty()) {
            std::cout << "[INFO] Cargando configuración desde: " << configFile << "\n";
            config = ConfigLoader::loadFromFile(configFile);
        } else {
            std::cout << "[INFO] No se especificó archivo de configuración. Usando configuración por defecto.\n";
            config = ConfigLoader::createDefault();
        }
    } catch (const std::exception& e) {
        std::cerr << "[ERROR] Fallo al cargar la configuración: " << e.what() << "\n";
        return 1;
    }

    // Sobrescrituras desde CLI
    if (overrideDays != -1) config.simulationDays = overrideDays;
    if (overrideRows != -1) config.gridConfig.rows = overrideRows;
    if (overrideCols != -1) config.gridConfig.cols = overrideCols;

    std::cout << "[CONFIG] ID Simulación:       " << config.id << "\n"
              << "[CONFIG] Nombre:              " << config.name << "\n"
              << "[CONFIG] Zona Gran Chaco:     " << zoneToString(config.zone) << " (" << config.zoneName << ", " << config.department << ")\n"
              << "[CONFIG] Suelo:               " << soilToString(config.soilType) << "\n"
              << "[CONFIG] Variedad de Maíz:    " << varietyToString(config.cornVariety) << "\n"
              << "[CONFIG] Escenario Sequía:    " << scenarioToString(config.droughtScenario) << "\n"
              << "[CONFIG] Días simulados:      " << config.simulationDays << "\n"
              << "[CONFIG] Malla espacial:      " << config.gridConfig.rows << "x" << config.gridConfig.cols
              << " (" << (config.gridConfig.rows * config.gridConfig.cols) << " celdas de " << config.gridConfig.cellSizeMeters << " m)\n\n";

    // Validación formal
    std::vector<std::string> errors;
    if (!ConfigValidator::validate(config, errors)) {
        std::cerr << "[ERROR] Validación de configuración fallida con los siguientes errores:\n";
        for (const auto& err : errors) {
            std::cerr << "  - " << err << "\n";
        }
        return 2;
    }

    SequentialEngine engine(config);

    std::cout << "[INFO] Ejecutando simulación temporal y espacial día a día...\n";
    auto result = engine.run();

    if (result.status != "completed") {
        std::cerr << "[ERROR] La simulación no concluyó exitosamente. Estado: " << result.status << "\n";
        return 3;
    }

    std::cout << "\n===============================================================\n"
              << "                   RESUMEN DE RESULTADOS                       \n"
              << "===============================================================\n"
              << std::fixed;
    if (result.executionTimeSeconds < 0.01) {
        std::cout << "  Tiempo de ejecución (T1):      " << std::setprecision(4) << result.executionTimeSeconds << " s ("
                  << std::setprecision(2) << (result.executionTimeSeconds * 1000.0) << " ms)\n";
    } else {
        std::cout << "  Tiempo de ejecución (T1):      " << std::setprecision(4) << result.executionTimeSeconds << " s\n";
    }
    std::cout << std::setprecision(2)
              << "  Speedup de referencia (S1):    " << result.speedup << "x\n"
              << "  Eficiencia paralela:           " << result.efficiency << "%\n"
              << "  Memoria residente estimada:    " << result.memoryUsageMb << " MB\n"
              << "  CWSI estacional promedio:      " << std::setprecision(3) << result.averageCWSI << "\n"
              << "  Humedad final del suelo:       " << std::setprecision(1) << result.soilMoistureFinalPercent << " %\n"
              << "  Déficit hídrico acumulado:     " << result.waterDeficitMm << " mm\n"
              << "  Rendimiento potencial nominal: " << std::setprecision(2) << result.nominalYieldTnHa << " tn/ha\n"
              << "  Rendimiento estimado final:    " << result.estimatedYieldTnHa << " tn/ha\n"
              << "  Pérdida de rendimiento:        " << std::setprecision(1) << result.yieldLossPercent << " %\n"
              << "===============================================================\n\n";

    // Guardar salida JSON
    if (!outputFile.empty()) {
        std::cout << "[INFO] Guardando resultados JSON en: " << outputFile << "\n";
        if (!JsonSerializer::saveResultToFile(result, outputFile)) {
            std::cerr << "[ADVERTENCIA] No fue posible escribir el archivo JSON en: " << outputFile << "\n";
        } else {
            std::cout << "[OK] Archivo JSON generado exitosamente.\n";
        }
    }

    // Guardar salida CSV
    if (!csvFile.empty()) {
        std::cout << "[INFO] Guardando serie temporal CSV en: " << csvFile << "\n";
        if (!JsonSerializer::exportTimelineToCsv(result, csvFile)) {
            std::cerr << "[ADVERTENCIA] No fue posible escribir el archivo CSV en: " << csvFile << "\n";
        } else {
            std::cout << "[OK] Archivo CSV generado exitosamente.\n";
        }
    }

    return 0;
}
