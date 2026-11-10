#include "agrochaco/agronomic_data.hpp"
#include <cmath>
#include <stdexcept>

namespace agrochaco {

static const std::vector<GranChacoZoneInfo> ZONES = {
    {
        GranChacoZoneId::YACUIBA,
        "Yacuiba",
        "Tarija",
        -22.0167,
        -63.6833,
        780.0,
        "Franco-arenoso",
        "severo",
        24500.0,
        31.4
    },
    {
        GranChacoZoneId::VILLAMONTES,
        "Villa Montes",
        "Tarija",
        -21.2592,
        -63.4694,
        620.0,
        "Arenoso",
        "critico",
        18200.0,
        34.8
    },
    {
        GranChacoZoneId::CHARAGUA,
        "Charagua Iyambae",
        "Santa Cruz",
        -19.7892,
        -63.2083,
        590.0,
        "Franco-arcilloso",
        "severo",
        32000.0,
        33.1
    },
    {
        GranChacoZoneId::MACHARETI,
        "Macharetí",
        "Chuquisaca",
        -20.8033,
        -63.3644,
        540.0,
        "Franco-arenoso",
        "critico",
        14800.0,
        33.9
    },
    {
        GranChacoZoneId::CARAPARI,
        "Caraparí",
        "Tarija",
        -21.8267,
        -63.7433,
        890.0,
        "Franco",
        "moderado",
        11500.0,
        28.5
    },
    {
        GranChacoZoneId::BOYUIBE,
        "Boyuibe",
        "Santa Cruz",
        -20.4317,
        -63.2831,
        610.0,
        "Arenoso",
        "moderado",
        9400.0,
        32.2
    }
};

static const std::vector<SoilInfo> SOILS = {
    {
        SoilType::FRANCO_ARENOSO,
        "Franco-Arenoso (Típico Chaco Central)",
        18.5,
        8.2,
        103.0
    },
    {
        SoilType::FRANCO_ARCILLOSO,
        "Franco-Arcilloso (Aluvial Pilcomayo)",
        31.0,
        17.5,
        135.0
    },
    {
        SoilType::ARENOSO,
        "Arenoso (Dunas paleo eólicas de Charagua)",
        12.0,
        4.8,
        72.0
    },
    {
        SoilType::FRANCO,
        "Franco Equilibrado (Pie de Monte)",
        24.0,
        11.0,
        130.0
    }
};

static const std::vector<CornVarietyInfo> CORN_VARIETIES = {
    {
        CornVarietyId::CHACO_01_CRIOLLO,
        "Chaco 01 Criollo Blanco",
        125,
        3.8,
        "Muy Alta",
        "Floración (R1) - Alta rusticidad radicular"
    },
    {
        CornVarietyId::INIAF_H1,
        "INIAF H1 Chaqueño",
        120,
        5.4,
        "Alta",
        "Espigamiento a llenado de grano (R1-R3)"
    },
    {
        CornVarietyId::DEKALB_7088,
        "Dekalb DKB 7088",
        115,
        6.8,
        "Media",
        "Panoja y fecundación"
    },
    {
        CornVarietyId::PIONEER_30F35,
        "Pioneer 30F35 VyR",
        118,
        6.1,
        "Alta",
        "Floración femenina (R1)"
    }
};

const std::vector<GranChacoZoneInfo>& AgronomicData::getAllZones() {
    return ZONES;
}

const GranChacoZoneInfo& AgronomicData::getZone(GranChacoZoneId id) {
    for (const auto& zone : ZONES) {
        if (zone.id == id) return zone;
    }
    throw std::invalid_argument("Zona no encontrada en la base agronómica");
}

const std::vector<SoilInfo>& AgronomicData::getAllSoils() {
    return SOILS;
}

const SoilInfo& AgronomicData::getSoil(SoilType id) {
    for (const auto& soil : SOILS) {
        if (soil.id == id) return soil;
    }
    throw std::invalid_argument("Suelo no encontrado en la base agronómica");
}

const std::vector<CornVarietyInfo>& AgronomicData::getAllCornVarieties() {
    return CORN_VARIETIES;
}

const CornVarietyInfo& AgronomicData::getCornVariety(CornVarietyId id) {
    for (const auto& variety : CORN_VARIETIES) {
        if (variety.id == id) return variety;
    }
    throw std::invalid_argument("Variedad de maíz no encontrada en la base agronómica");
}

AgronomicData::PhenologyInfo AgronomicData::getPhenology(int day, int cycleDays) {
    if (cycleDays <= 0) cycleDays = 120;
    double frac = static_cast<double>(day) / static_cast<double>(cycleDays);

    PhenologyInfo info;
    // Partición fenológica estándar del maíz FAO-56 / CIAT
    if (frac <= 0.15) {
        // Inicial: Emergencia (VE - V2)
        info.stageIndex = 0;
        info.stageName = "Emergencia (VE - V2)";
        info.kc = 0.40;
        info.ky = 0.20;
        info.isCritical = false;
    } else if (frac <= 0.38) {
        // Vegetativo rápido (V6 - V12)
        info.stageIndex = 1;
        info.stageName = "Desarrollo Vegetativo (V6 - V12)";
        // Interpolación suave de Kc entre 0.40 y 1.20
        double step = (frac - 0.15) / (0.38 - 0.15);
        info.kc = 0.40 + step * (0.80 - 0.40);
        info.ky = 0.40;
        info.isCritical = false;
    } else if (frac <= 0.58) {
        // Floración y Fecundación (R1) - Período crítico
        info.stageIndex = 2;
        info.stageName = "Floración y Polinización (R1)";
        info.kc = 1.20;
        info.ky = 1.25; // Máxima sensibilidad al déficit hídrico
        info.isCritical = true;
    } else if (frac <= 0.80) {
        // Llenado de grano (R2 - R4)
        info.stageIndex = 3;
        info.stageName = "Llenado de Grano (R2 - R4)";
        info.kc = 1.05;
        info.ky = 0.50;
        info.isCritical = false;
    } else {
        // Maduración fisiológica y secado (R5 - R6)
        info.stageIndex = 4;
        info.stageName = "Maduración Fisiológica (R6)";
        double step = (frac - 0.80) / (1.0 - 0.80);
        info.kc = std::max(0.55, 1.05 - step * (1.05 - 0.60));
        info.ky = 0.20;
        info.isCritical = false;
    }

    return info;
}

AgronomicData::DailyClimate AgronomicData::getDailyClimate(int day, GranChacoZoneId zoneId, DroughtScenario scenario) {
    const auto& zone = getZone(zoneId);
    DailyClimate climate;

    // Factores de ajuste según escenario de sequía
    double tempModifier = 0.0;
    double rainMultiplier = 1.0;
    double et0Multiplier = 1.0;

    switch (scenario) {
        case DroughtScenario::HISTORICO:
            tempModifier = 0.0;
            rainMultiplier = 1.0;
            et0Multiplier = 1.0;
            break;
        case DroughtScenario::MODERADO_SSP245:
            tempModifier = +1.5;
            rainMultiplier = 0.75;
            et0Multiplier = 1.10;
            break;
        case DroughtScenario::EXTREMO_SSP585:
            tempModifier = +3.2;
            rainMultiplier = 0.45;
            et0Multiplier = 1.25;
            break;
        case DroughtScenario::SEQUIA_RECENTE_2023:
            tempModifier = +2.8;
            rainMultiplier = 0.50;
            et0Multiplier = 1.20;
            break;
    }

    climate.temperature = zone.averageTempC + tempModifier;

    // Modelo determinista de ET0 diaria según radiación solar y temperatura media del Chaco
    // ET0 base entre 4.0 y 6.8 mm/día con ciclo senoidal estacional
    double solarWave = std::sin(static_cast<double>(day) / 18.0);
    double baseEt0 = 4.5 + solarWave * 1.5 + (climate.temperature - 30.0) * 0.12;
    if (baseEt0 < 3.0) baseEt0 = 3.0;
    climate.et0 = baseEt0 * et0Multiplier;

    // Patrón determinista de eventos de precipitación en la campaña estival chaqueña
    // Días de lluvia calibrados representativos de la temporada (Días 4, 18, 32, 60, 78, 102)
    climate.precipitation = 0.0;

    // Calendario determinista de eventos con milímetros base
    struct RainEvent {
        int day;
        double baseMm;
    };

    static const RainEvent rainEvents[] = {
        {4, 22.0},
        {18, 18.5},
        {32, 26.0},
        {60, 15.0},
        {78, 20.5},
        {102, 14.0}
    };

    for (const auto& ev : rainEvents) {
        if (ev.day == day) {
            // Ajustar según la pluviosidad relativa de la zona (referencia 650 mm promedio)
            double zoneFactor = zone.annualRainfallMm / 650.0;
            climate.precipitation = ev.baseMm * zoneFactor * rainMultiplier;

            // En la sequía 2023, la lluvia del día 60 (R1) fue casi nula en el Chaco
            if (scenario == DroughtScenario::SEQUIA_RECENTE_2023 && day == 60) {
                climate.precipitation = 2.0;
            }
            break;
        }
    }

    return climate;
}

} // namespace agrochaco
