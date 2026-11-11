#include "agrochaco/json_serializer.hpp"
#include <fstream>
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <cctype>

namespace agrochaco {

static std::string escapeJson(const std::string& s) {
    std::ostringstream o;
    for (char c : s) {
        switch (c) {
            case '"': o << "\\\""; break;
            case '\\': o << "\\\\"; break;
            case '\b': o << "\\b"; break;
            case '\f': o << "\\f"; break;
            case '\n': o << "\\n"; break;
            case '\r': o << "\\r"; break;
            case '\t': o << "\\t"; break;
            default:
                if (static_cast<unsigned char>(c) <= 0x1f) {
                    o << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<int>(c);
                } else {
                    o << c;
                }
        }
    }
    return o.str();
}

std::string JsonSerializer::serializeResult(const SimulationResult& result, bool pretty) {
    std::ostringstream ss;
    std::string indent = pretty ? "  " : "";
    std::string indent2 = pretty ? "    " : "";
    std::string indent3 = pretty ? "      " : "";
    std::string nl = pretty ? "\n" : "";

    ss << std::fixed << std::setprecision(3);

    ss << "{" << nl;
    ss << indent << "\"id\": \"" << escapeJson(result.id) << "\"," << nl;

    // Objeto config
    ss << indent << "\"config\": {" << nl;
    ss << indent2 << "\"id\": \"" << escapeJson(result.config.id) << "\"," << nl;
    ss << indent2 << "\"name\": \"" << escapeJson(result.config.name) << "\"," << nl;
    ss << indent2 << "\"description\": \"" << escapeJson(result.config.description) << "\"," << nl;
    ss << indent2 << "\"zone\": \"" << zoneToString(result.config.zone) << "\"," << nl;
    ss << indent2 << "\"zoneName\": \"" << escapeJson(result.config.zoneName) << "\"," << nl;
    ss << indent2 << "\"department\": \"" << escapeJson(result.config.department) << "\"," << nl;
    ss << indent2 << "\"soilType\": \"" << soilToString(result.config.soilType) << "\"," << nl;
    ss << indent2 << "\"cornVariety\": \"" << varietyToString(result.config.cornVariety) << "\"," << nl;
    ss << indent2 << "\"plantingDate\": \"" << escapeJson(result.config.plantingDate) << "\"," << nl;
    ss << indent2 << "\"simulationDays\": " << result.config.simulationDays << "," << nl;
    ss << indent2 << "\"gridConfig\": {" << nl;
    ss << indent3 << "\"rows\": " << result.config.gridConfig.rows << "," << nl;
    ss << indent3 << "\"cols\": " << result.config.gridConfig.cols << "," << nl;
    ss << indent3 << "\"cellSizeMeters\": " << result.config.gridConfig.cellSizeMeters << nl;
    ss << indent2 << "}," << nl;
    ss << indent2 << "\"initialMoisturePercent\": " << result.config.initialMoisturePercent << "," << nl;
    ss << indent2 << "\"droughtScenario\": \"" << scenarioToString(result.config.droughtScenario) << "\"," << nl;
    ss << indent2 << "\"engine\": \"" << engineToString(result.config.engine) << "\"," << nl;
    if (result.config.openmpThreads.has_value()) {
        ss << indent2 << "\"openmpThreads\": " << result.config.openmpThreads.value() << "," << nl;
    }
    if (result.config.mpiProcesses.has_value()) {
        ss << indent2 << "\"mpiProcesses\": " << result.config.mpiProcesses.value() << "," << nl;
    }
    if (result.config.nodesCount.has_value()) {
        ss << indent2 << "\"nodesCount\": " << result.config.nodesCount.value() << "," << nl;
    }
    ss << indent2 << "\"createdAt\": \"" << escapeJson(result.config.createdAt) << "\"" << nl;
    ss << indent << "}," << nl;

    ss << indent << "\"status\": \"" << escapeJson(result.status) << "\"," << nl;
    ss << indent << "\"progressPercent\": " << result.progressPercent << "," << nl;
    ss << indent << "\"currentDay\": " << result.currentDay << "," << nl;
    ss << indent << "\"createdAt\": \"" << escapeJson(result.createdAt) << "\"," << nl;
    ss << indent << "\"completedAt\": \"" << escapeJson(result.completedAt) << "\"," << nl;
    ss << indent << "\"executionTimeSeconds\": " << result.executionTimeSeconds << "," << nl;
    ss << indent << "\"speedup\": " << result.speedup << "," << nl;
    ss << indent << "\"efficiency\": " << result.efficiency << "," << nl;
    ss << indent << "\"averageCWSI\": " << result.averageCWSI << "," << nl;
    ss << indent << "\"soilMoistureFinalPercent\": " << result.soilMoistureFinalPercent << "," << nl;
    ss << indent << "\"yieldLossPercent\": " << result.yieldLossPercent << "," << nl;
    ss << indent << "\"estimatedYieldTnHa\": " << result.estimatedYieldTnHa << "," << nl;
    ss << indent << "\"nominalYieldTnHa\": " << result.nominalYieldTnHa << "," << nl;
    ss << indent << "\"waterDeficitMm\": " << result.waterDeficitMm << "," << nl;
    ss << indent << "\"memoryUsageMb\": " << result.memoryUsageMb << "," << nl;

    // Timeline array
    ss << indent << "\"timelineData\": [" << nl;
    for (size_t i = 0; i < result.timelineData.size(); ++i) {
        const auto& pt = result.timelineData[i];
        ss << indent2 << "{"
           << "\"day\": " << pt.day << ", "
           << "\"date\": \"" << escapeJson(pt.date) << "\", "
           << "\"phenologicalStage\": \"" << escapeJson(pt.phenologicalStage) << "\", "
           << "\"etActual\": " << pt.etActual << ", "
           << "\"etPotential\": " << pt.etPotential << ", "
           << "\"cwsi\": " << pt.cwsi << ", "
           << "\"soilMoisture\": " << pt.soilMoisture << ", "
           << "\"precipitation\": " << pt.precipitation << "}";
        if (i + 1 < result.timelineData.size()) ss << ",";
        ss << nl;
    }
    ss << indent << "]," << nl;

    // Spatial grid array
    ss << indent << "\"spatialGrid\": [" << nl;
    for (size_t i = 0; i < result.spatialGrid.size(); ++i) {
        const auto& cell = result.spatialGrid[i];
        ss << indent2 << "{"
           << "\"x\": " << cell.x << ", "
           << "\"y\": " << cell.y << ", "
           << "\"moisture\": " << cell.moisture << ", "
           << "\"cwsi\": " << cell.cwsi << ", "
           << "\"riskLevel\": \"" << riskLevelToString(cell.riskLevel) << "\"}";
        if (i + 1 < result.spatialGrid.size()) ss << ",";
        ss << nl;
    }
    ss << indent << "]," << nl;

    // Logs array
    ss << indent << "\"logs\": [" << nl;
    for (size_t i = 0; i < result.logs.size(); ++i) {
        const auto& log = result.logs[i];
        ss << indent2 << "{"
           << "\"timestamp\": \"" << escapeJson(log.timestamp) << "\", "
           << "\"level\": \"" << logLevelToString(log.level) << "\", "
           << "\"message\": \"" << escapeJson(log.message) << "\"}";
        if (i + 1 < result.logs.size()) ss << ",";
        ss << nl;
    }
    ss << indent << "]" << nl;

    ss << "}";
    return ss.str();
}

bool JsonSerializer::saveResultToFile(const SimulationResult& result, const std::string& filePath) {
    std::ofstream file(filePath);
    if (!file.is_open()) return false;
    file << serializeResult(result, true);
    return file.good();
}

bool JsonSerializer::exportTimelineToCsv(const SimulationResult& result, const std::string& filePath) {
    std::ofstream file(filePath);
    if (!file.is_open()) return false;

    file << "Dia,Etapa,ET_Actual_mm,ET_Potencial_mm,CWSI,Humedad_Suelo_Porc,Precipitacion_mm\n";
    for (const auto& row : result.timelineData) {
        file << row.day << ",\""
             << row.phenologicalStage << "\","
             << std::fixed << std::setprecision(2)
             << row.etActual << ","
             << row.etPotential << ","
             << std::setprecision(3)
             << row.cwsi << ","
             << std::setprecision(1)
             << row.soilMoisture << ","
             << row.precipitation << "\n";
    }
    return file.good();
}

// Implementación de parser JSON liviano y robusto para configuración
static std::string extractJsonStringField(const std::string& json, const std::string& key) {
    std::string pattern = "\"" + key + "\"";
    size_t pos = json.find(pattern);
    if (pos == std::string::npos) return "";

    size_t colonPos = json.find(':', pos + pattern.length());
    if (colonPos == std::string::npos) return "";

    size_t quoteStart = json.find('"', colonPos + 1);
    if (quoteStart == std::string::npos) return "";

    size_t quoteEnd = json.find('"', quoteStart + 1);
    if (quoteEnd == std::string::npos) return "";

    return json.substr(quoteStart + 1, quoteEnd - quoteStart - 1);
}

static double extractJsonNumberField(const std::string& json, const std::string& key, double defaultVal = 0.0) {
    std::string pattern = "\"" + key + "\"";
    size_t pos = json.find(pattern);
    if (pos == std::string::npos) return defaultVal;

    size_t colonPos = json.find(':', pos + pattern.length());
    if (colonPos == std::string::npos) return defaultVal;

    size_t valStart = json.find_first_of("-0123456789.", colonPos + 1);
    if (valStart == std::string::npos) return defaultVal;

    size_t valEnd = json.find_first_not_of("-0123456789.eE", valStart);
    std::string numStr = json.substr(valStart, valEnd - valStart);

    try {
        return std::stod(numStr);
    } catch (...) {
        return defaultVal;
    }
}

SimulationConfig JsonSerializer::parseConfig(const std::string& jsonContent) {
    SimulationConfig config;

    std::string id = extractJsonStringField(jsonContent, "id");
    if (!id.empty()) config.id = id;

    std::string name = extractJsonStringField(jsonContent, "name");
    if (!name.empty()) config.name = name;

    std::string desc = extractJsonStringField(jsonContent, "description");
    config.description = desc;

    std::string zoneStr = extractJsonStringField(jsonContent, "zone");
    if (!zoneStr.empty()) config.zone = stringToZone(zoneStr);

    std::string zoneName = extractJsonStringField(jsonContent, "zoneName");
    if (!zoneName.empty()) config.zoneName = zoneName;

    std::string dep = extractJsonStringField(jsonContent, "department");
    if (!dep.empty()) config.department = dep;

    std::string soilStr = extractJsonStringField(jsonContent, "soilType");
    if (!soilStr.empty()) config.soilType = stringToSoil(soilStr);

    std::string varStr = extractJsonStringField(jsonContent, "cornVariety");
    if (!varStr.empty()) config.cornVariety = stringToVariety(varStr);

    std::string pDate = extractJsonStringField(jsonContent, "plantingDate");
    if (!pDate.empty()) config.plantingDate = pDate;

    double days = extractJsonNumberField(jsonContent, "simulationDays", 120.0);
    config.simulationDays = static_cast<int>(days);

    double initMoist = extractJsonNumberField(jsonContent, "initialMoisturePercent", 16.0);
    config.initialMoisturePercent = initMoist;

    std::string scenStr = extractJsonStringField(jsonContent, "droughtScenario");
    if (!scenStr.empty()) config.droughtScenario = stringToScenario(scenStr);

    std::string engStr = extractJsonStringField(jsonContent, "engine");
    if (!engStr.empty()) config.engine = stringToEngine(engStr);

    // Malla espacial anidada en gridConfig o a nivel raíz
    double rows = extractJsonNumberField(jsonContent, "rows", 20.0);
    double cols = extractJsonNumberField(jsonContent, "cols", 20.0);
    double cellSize = extractJsonNumberField(jsonContent, "cellSizeMeters", 50.0);

    config.gridConfig.rows = static_cast<int>(rows);
    config.gridConfig.cols = static_cast<int>(cols);
    config.gridConfig.cellSizeMeters = cellSize;

    // Hilos y procesos opcionales
    double threads = extractJsonNumberField(jsonContent, "openmpThreads", -1.0);
    if (threads > 0.0) config.openmpThreads = static_cast<int>(threads);

    double procs = extractJsonNumberField(jsonContent, "mpiProcesses", -1.0);
    if (procs > 0.0) config.mpiProcesses = static_cast<int>(procs);

    double nodes = extractJsonNumberField(jsonContent, "nodesCount", -1.0);
    if (nodes > 0.0) config.nodesCount = static_cast<int>(nodes);

    std::string cAt = extractJsonStringField(jsonContent, "createdAt");
    if (!cAt.empty()) config.createdAt = cAt;

    return config;
}

} // namespace agrochaco
