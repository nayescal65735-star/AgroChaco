#ifndef AGROCHACO_AGRONOMIC_DATA_HPP
#define AGROCHACO_AGRONOMIC_DATA_HPP

#include "types.hpp"
#include <vector>
#include <string>

namespace agrochaco {

class AgronomicData {
public:
    static const std::vector<GranChacoZoneInfo>& getAllZones();
    static const GranChacoZoneInfo& getZone(GranChacoZoneId id);

    static const std::vector<SoilInfo>& getAllSoils();
    static const SoilInfo& getSoil(SoilType id);

    static const std::vector<CornVarietyInfo>& getAllCornVarieties();
    static const CornVarietyInfo& getCornVariety(CornVarietyId id);

    // Etapa fenológica y Kc según el día de simulación y duración del ciclo
    struct PhenologyInfo {
        int stageIndex{0}; // 0: Inicial, 1: Vegetativo, 2: Floración, 3: Llenado, 4: Maduración
        std::string stageName;
        double kc{0.0};
        double ky{0.0}; // Coeficiente de respuesta de rendimiento FAO-33
        bool isCritical{false};
    };

    static PhenologyInfo getPhenology(int day, int cycleDays);

    // Parámetros climáticos diarios según zona y escenario de sequía
    struct DailyClimate {
        double et0;           // mm/día
        double precipitation; // mm/día
        double temperature;   // °C
    };

    static DailyClimate getDailyClimate(int day, GranChacoZoneId zone, DroughtScenario scenario);
};

} // namespace agrochaco

#endif // AGROCHACO_AGRONOMIC_DATA_HPP
