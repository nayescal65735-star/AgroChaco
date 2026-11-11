#ifndef AGROCHACO_CROP_MODEL_HPP
#define AGROCHACO_CROP_MODEL_HPP

#include "types.hpp"
#include "agronomic_data.hpp"
#include <vector>

namespace agrochaco {

class CropModel {
public:
    /**
     * Calcula la profundidad radicular activa en metros para el día de simulación.
     */
    static double calculateRootDepth(int day, int cycleDays);

    /**
     * Calcula la demanda hídrica potencial del cultivo ETc (mm/día).
     */
    static double calculateEtc(double et0, double kc);

    /**
     * Calcula el porcentaje acumulado de pérdida de rendimiento según el modelo aditivo de FAO-33:
     * 1 - (Ya / Ym) = sum_i [ Ky_i * (1 - ETa_i / ETc_i) * (ETc_i / ETc_total) ] * Factor_variedad
     *
     * @param stageEtc Vector de ETc acumulada por etapa fenológica (mm)
     * @param stageEta Vector de ETa acumulada por etapa fenológica (mm)
     * @param stageKy  Vector de coeficientes de sensibilidad Ky por etapa
     * @param variety  Información agronómica de la variedad de maíz
     * @return Porcentaje de reducción de rendimiento [0.0, 100.0]%
     */
    static double calculateYieldLoss(
        const std::vector<double>& stageEtc,
        const std::vector<double>& stageEta,
        const std::vector<double>& stageKy,
        const CornVarietyInfo& variety
    );
};

} // namespace agrochaco

#endif // AGROCHACO_CROP_MODEL_HPP
