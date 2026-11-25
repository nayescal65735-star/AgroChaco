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
     * Calcula el porcentaje acumulado de pérdida de rendimiento con la relación
     * aditiva ponderada por demanda:
     * 1 - Ya/Ym = sum_i [ Ky_i * (1 - ETa_i/ETc_i) * (ETc_i/ETc_total) ]
     *
     * ETa_i se acota a [0, ETc_i]. Las etapas con ETc_i <= 0.001 mm se omiten y,
     * si ETc_total <= 0.001 mm, la pérdida es 0. No se aplica ningún multiplicador
     * varietal: los factores 0.85/0.95/1.05 se eliminaron por no estar calibrados.
     * El parámetro variety se conserva únicamente por compatibilidad de firma.
     * Esta formulación no constituye una calibración experimental del maíz del Gran Chaco.
     *
     * @param stageEtc Vector de ETc acumulada por etapa fenológica (mm)
     * @param stageEta Vector de ETa acumulada por etapa fenológica (mm)
     * @param stageKy  Vector de coeficientes de sensibilidad Ky por etapa
     * @param variety  Información agronómica de la variedad de maíz (no utilizada en la ecuación)
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
