#ifndef AGROCHACO_JSON_SERIALIZER_HPP
#define AGROCHACO_JSON_SERIALIZER_HPP

#include "types.hpp"
#include <string>

namespace agrochaco {

class JsonSerializer {
public:
    // Serializa el resultado completo a formato JSON compatible con frontend/backend
    static std::string serializeResult(const SimulationResult& result, bool pretty = true);

    // Guarda el resultado en un archivo JSON en disco
    static bool saveResultToFile(const SimulationResult& result, const std::string& filePath);

    // Exporta la serie temporal a formato CSV estándar
    static bool exportTimelineToCsv(const SimulationResult& result, const std::string& filePath);

    // Parser liviano para configuración en formato JSON
    static SimulationConfig parseConfig(const std::string& jsonContent);
};

} // namespace agrochaco

#endif // AGROCHACO_JSON_SERIALIZER_HPP
