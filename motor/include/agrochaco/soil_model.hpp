#ifndef AGROCHACO_SOIL_MODEL_HPP
#define AGROCHACO_SOIL_MODEL_HPP

#include "types.hpp"

namespace agrochaco {

class SoilModel {
public:
    // Estructura para el resultado del balance diario en una celda
    struct CellBalanceResult {
        double updatedMoisturePercent; // Humedad final del día (%)
        double etActual;               // mm/día
        double cwsi;                   // Índice de déficit relativo [0, 1]
        double deepDrainage;           // Exceso percolado / escorrentía gravitacional (mm)
        double deficitMm;              // Déficit diario ETc - ETa (mm)
        double initialWaterMm;         // Agua inicial en zona radicular (mm)
        double finalWaterMm;           // Agua final en zona radicular (mm)
        double deltaStorageMm;         // Cambio de almacenamiento: finalWaterMm - initialWaterMm (mm)
        double massBalanceError;       // Error de masa: |deltaStorageMm + etActual + deepDrainage - precipitation| (mm)
    };

    /**
     * Calcula el balance hídrico diario para una celda de suelo con conservación estricta de masa.
     * @param currentMoisture Humedad actual (% volumétrico)
     * @param soil Propiedades edáficas (CC, PMP, agua útil)
     * @param etPotential Demanda evaporativa del cultivo ETc (mm)
     * @param precipitation Precipitación incidente uniforme (mm)
     * @param rootDepthMeters Profundidad radicular activa (m)
     * @return Resultado del balance diario con balance de masa
     */
    static CellBalanceResult updateCellMoisture(
        double currentMoisture,
        const SoilInfo& soil,
        double etPotential,
        double precipitation,
        double rootDepthMeters
    );

    /**
     * Calcula el factor de reducción por estrés hídrico Ks (FAO-56).
     * @param moisture Humedad actual (%)
     * @param fc Capacidad de campo (%)
     * @param wp Punto de marchitez permanente (%)
     * @param depletionFraction Fracción de agotamiento fácilmente utilizable p (típicamente 0.50 a 0.55 para maíz)
     */
    static double calculateKs(double moisture, double fc, double wp, double depletionFraction = 0.50);
};

} // namespace agrochaco

#endif // AGROCHACO_SOIL_MODEL_HPP
