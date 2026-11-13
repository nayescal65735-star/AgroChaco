#include "agrochaco/types.hpp"
#include <algorithm>
#include <cctype>

namespace agrochaco {

static std::string toLower(std::string str) {
    std::transform(str.begin(), str.end(), str.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return str;
}

std::string zoneToString(GranChacoZoneId zone) {
    switch (zone) {
        case GranChacoZoneId::YACUIBA: return "yacuiba";
        case GranChacoZoneId::VILLAMONTES: return "villamontes";
        case GranChacoZoneId::CARAPARI: return "carapari";
        case GranChacoZoneId::CHARAGUA: return "charagua";
        case GranChacoZoneId::MACHARETI: return "machareti";
        case GranChacoZoneId::BOYUIBE: return "boyuibe";
    }
    return "villamontes";
}

GranChacoZoneId stringToZone(const std::string& str) {
    std::string s = toLower(str);
    if (s == "yacuiba") return GranChacoZoneId::YACUIBA;
    if (s == "villamontes" || s == "villa montes") return GranChacoZoneId::VILLAMONTES;
    if (s == "carapari" || s == "caraparí") return GranChacoZoneId::CARAPARI;
    if (s == "charagua" || s == "charagua iyambae") return GranChacoZoneId::CHARAGUA;
    if (s == "machareti" || s == "macharetí") return GranChacoZoneId::MACHARETI;
    if (s == "boyuibe") return GranChacoZoneId::BOYUIBE;
    throw std::invalid_argument("Zona del Gran Chaco no válida: " + str);
}

std::string soilToString(SoilType soil) {
    switch (soil) {
        case SoilType::FRANCO_ARENOSO: return "franco_arenoso";
        case SoilType::FRANCO_ARCILLOSO: return "franco_arcilloso";
        case SoilType::ARENOSO: return "arenoso";
        case SoilType::FRANCO: return "franco";
    }
    return "franco_arenoso";
}

SoilType stringToSoil(const std::string& str) {
    std::string s = toLower(str);
    if (s == "franco_arenoso" || s == "franco-arenoso") return SoilType::FRANCO_ARENOSO;
    if (s == "franco_arcilloso" || s == "franco-arcilloso") return SoilType::FRANCO_ARCILLOSO;
    if (s == "arenoso") return SoilType::ARENOSO;
    if (s == "franco") return SoilType::FRANCO;
    throw std::invalid_argument("Tipo de suelo no válido: " + str);
}

std::string varietyToString(CornVarietyId variety) {
    switch (variety) {
        case CornVarietyId::CHACO_01_CRIOLLO: return "chaco_01_criollo";
        case CornVarietyId::DEKALB_7088: return "dekalb_7088";
        case CornVarietyId::INIAF_H1: return "iniaf_h1";
        case CornVarietyId::PIONEER_30F35: return "pioneer_30f35";
    }
    return "chaco_01_criollo";
}

CornVarietyId stringToVariety(const std::string& str) {
    std::string s = toLower(str);
    if (s == "chaco_01_criollo" || s == "criollo") return CornVarietyId::CHACO_01_CRIOLLO;
    if (s == "dekalb_7088" || s == "dkb_7088" || s == "dkb7088") return CornVarietyId::DEKALB_7088;
    if (s == "iniaf_h1" || s == "iniaf") return CornVarietyId::INIAF_H1;
    if (s == "pioneer_30f35" || s == "pioneer") return CornVarietyId::PIONEER_30F35;
    throw std::invalid_argument("Variedad de maíz no válida: " + str);
}

std::string scenarioToString(DroughtScenario scenario) {
    switch (scenario) {
        case DroughtScenario::HISTORICO: return "historico";
        case DroughtScenario::MODERADO_SSP245: return "moderado_ssp245";
        case DroughtScenario::EXTREMO_SSP585: return "extremo_ssp585";
        case DroughtScenario::SEQUIA_RECENTE_2023: return "sequia_recente_2023";
    }
    return "historico";
}

DroughtScenario stringToScenario(const std::string& str) {
    std::string s = toLower(str);
    if (s == "historico") return DroughtScenario::HISTORICO;
    if (s == "moderado_ssp245" || s == "ssp245") return DroughtScenario::MODERADO_SSP245;
    if (s == "extremo_ssp585" || s == "ssp585") return DroughtScenario::EXTREMO_SSP585;
    if (s == "sequia_recente_2023" || s == "2023") return DroughtScenario::SEQUIA_RECENTE_2023;
    throw std::invalid_argument("Escenario de sequía no válido: " + str);
}

std::string engineToString(SimulationEngine engine) {
    switch (engine) {
        case SimulationEngine::SECUENCIAL: return "secuencial";
        case SimulationEngine::OPENMP: return "openmp";
        case SimulationEngine::MPI: return "mpi";
        case SimulationEngine::HIBRIDO: return "hibrido";
    }
    return "secuencial";
}

SimulationEngine stringToEngine(const std::string& str) {
    std::string s = toLower(str);
    if (s == "secuencial") return SimulationEngine::SECUENCIAL;
    if (s == "openmp") return SimulationEngine::OPENMP;
    if (s == "mpi") return SimulationEngine::MPI;
    if (s == "hibrido") return SimulationEngine::HIBRIDO;
    throw std::invalid_argument("Motor de simulación no válido: " + str);
}

std::string riskLevelToString(RiskLevel risk) {
    switch (risk) {
        case RiskLevel::BAJO: return "bajo";
        case RiskLevel::MODERADO: return "moderado";
        case RiskLevel::SEVERO: return "severo";
        case RiskLevel::CRITICO: return "critico";
    }
    return "bajo";
}

RiskLevel calculateRiskLevel(double cwsi) {
    if (cwsi >= 0.70) return RiskLevel::CRITICO;
    if (cwsi >= 0.50) return RiskLevel::SEVERO;
    if (cwsi >= 0.30) return RiskLevel::MODERADO;
    return RiskLevel::BAJO;
}

std::string logLevelToString(LogLevel level) {
    switch (level) {
        case LogLevel::INFO: return "INFO";
        case LogLevel::MPI: return "MPI";
        case LogLevel::OMP: return "OMP";
        case LogLevel::WARN: return "WARN";
        case LogLevel::ERROR: return "ERROR";
    }
    return "INFO";
}

} // namespace agrochaco
