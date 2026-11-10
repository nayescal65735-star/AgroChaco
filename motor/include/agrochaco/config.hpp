#ifndef AGROCHACO_CONFIG_HPP
#define AGROCHACO_CONFIG_HPP

#include "types.hpp"
#include <string>
#include <vector>

namespace agrochaco {

class ConfigValidator {
public:
    // Valida la configuración y retorna true si es válida.
    // Llena la lista errors con los mensajes explicativos de cualquier anomalía.
    static bool validate(const SimulationConfig& config, std::vector<std::string>& errors);
};

class ConfigLoader {
public:
    // Carga la configuración desde un archivo JSON
    static SimulationConfig loadFromFile(const std::string& filePath);

    // Carga la configuración desde un string con formato JSON
    static SimulationConfig loadFromString(const std::string& jsonString);

    // Genera una configuración por defecto representativa
    static SimulationConfig createDefault();
};

} // namespace agrochaco

#endif // AGROCHACO_CONFIG_HPP
