#include "agrochaco/config.hpp"
#include "agrochaco/agronomic_data.hpp"
#include "agrochaco/json_serializer.hpp"
#include <fstream>
#include <sstream>
#include <stdexcept>

namespace agrochaco {

bool ConfigValidator::validate(const SimulationConfig& config, std::vector<std::string>& errors) {
    errors.clear();

    // 1. Validación de la malla espacial
    if (config.gridConfig.rows <= 0) {
        errors.push_back("El número de filas de la malla (rows) debe ser mayor a cero.");
    }
    if (config.gridConfig.cols <= 0) {
        errors.push_back("El número de columnas de la malla (cols) debe ser mayor a cero.");
    }
    if (config.gridConfig.rows * config.gridConfig.cols > 1000000) {
        errors.push_back("El tamaño total de la malla excede el límite máximo permitido (1,000,000 celdas).");
    }
    if (config.gridConfig.cellSizeMeters <= 0.0) {
        errors.push_back("El tamaño de celda (cellSizeMeters) debe ser estrictamente positivo.");
    }

    // 2. Validación del horizonte temporal
    if (config.simulationDays <= 0) {
        errors.push_back("Los días de simulación (simulationDays) deben ser mayores a cero.");
    }
    if (config.simulationDays > 365) {
        errors.push_back("Los días de simulación no pueden superar un ciclo anual completo (máximo 365 días).");
    }

    // 3. Validación de humedad inicial
    if (config.initialMoisturePercent < 0.0 || config.initialMoisturePercent > 100.0) {
        errors.push_back("La humedad inicial del suelo debe encontrarse entre 0% y 100%.");
    }

    // 4. Validación de consistencia edáfica
    try {
        const auto& soil = AgronomicData::getSoil(config.soilType);
        if (soil.fieldCapacity <= soil.wiltingPoint) {
            errors.push_back("Inconsistencia en el suelo: la Capacidad de Campo (" +
                             std::to_string(soil.fieldCapacity) +
                             "%) debe ser mayor al Punto de Marchitez (" +
                             std::to_string(soil.wiltingPoint) + "%).");
        }
        if (config.initialMoisturePercent < soil.wiltingPoint * 0.5) {
            errors.push_back("Advertencia crítica: La humedad inicial está severamente por debajo del punto de marchitez permanente.");
        }
    } catch (const std::exception& e) {
        errors.push_back(std::string("Error al validar el tipo de suelo: ") + e.what());
    }

    // 5. Validación de variedad y zona
    try {
        AgronomicData::getZone(config.zone);
    } catch (const std::exception& e) {
        errors.push_back(std::string("Error al validar la zona: ") + e.what());
    }

    try {
        AgronomicData::getCornVariety(config.cornVariety);
    } catch (const std::exception& e) {
        errors.push_back(std::string("Error al validar la variedad de maíz: ") + e.what());
    }

    // 6. Validación de concurrencia si aplican
    if (config.openmpThreads.has_value() && config.openmpThreads.value() <= 0) {
        errors.push_back("El número de hilos OpenMP debe ser mayor a cero.");
    }
    if (config.mpiProcesses.has_value() && config.mpiProcesses.value() <= 0) {
        errors.push_back("El número de procesos MPI debe ser mayor a cero.");
    }
    if (config.nodesCount.has_value() && config.nodesCount.value() <= 0) {
        errors.push_back("El número de nodos de cómputo debe ser mayor a cero.");
    }

    return errors.empty();
}

SimulationConfig ConfigLoader::loadFromFile(const std::string& filePath) {
    std::ifstream file(filePath);
    if (!file.is_open()) {
        throw std::runtime_error("No fue posible abrir el archivo de configuración: " + filePath);
    }
    std::stringstream buffer;
    buffer << file.rdbuf();
    return loadFromString(buffer.str());
}

SimulationConfig ConfigLoader::loadFromString(const std::string& jsonString) {
    return JsonSerializer::parseConfig(jsonString);
}

SimulationConfig ConfigLoader::createDefault() {
    SimulationConfig config;
    config.id = "SIM-GC-DEFAULT-001";
    config.name = "Simulación Base - Villa Montes (Maíz Criollo)";
    config.description = "Configuración por defecto para calibración de referencia en el Chaco tarijeño.";
    config.zone = GranChacoZoneId::VILLAMONTES;
    config.zoneName = "Villa Montes";
    config.department = "Tarija";
    config.soilType = SoilType::ARENOSO;
    config.cornVariety = CornVarietyId::CHACO_01_CRIOLLO;
    config.plantingDate = "2026-11-15";
    config.simulationDays = 120;
    config.gridConfig.rows = 20;
    config.gridConfig.cols = 20;
    config.gridConfig.cellSizeMeters = 50.0;
    config.initialMoisturePercent = 14.5;
    config.droughtScenario = DroughtScenario::EXTREMO_SSP585;
    config.engine = SimulationEngine::SECUENCIAL;
    config.createdAt = "2026-11-10 12:00";
    return config;
}

} // namespace agrochaco
