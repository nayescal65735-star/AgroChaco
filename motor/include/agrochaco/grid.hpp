#ifndef AGROCHACO_GRID_HPP
#define AGROCHACO_GRID_HPP

#include "types.hpp"
#include <vector>

namespace agrochaco {

class SpatialGrid {
public:
    SpatialGrid(int rows, int cols, double cellSizeMeters, double initialMoisture, const SoilInfo& soil);

    int getRows() const { return rows_; }
    int getCols() const { return cols_; }
    int getTotalCells() const { return rows_ * cols_; }
    double getCellSize() const { return cellSizeMeters_; }

    double getMoisture(int r, int c) const { return moisture_[r * cols_ + c]; }
    double getCwsi(int r, int c) const { return cwsi_[r * cols_ + c]; }

    // Resumen diario con métricas completas de conservación de masa hidrológica
    struct StepSummary {
        double averageMoisture;        // Humedad promedio (% volumétrico)
        double averageCwsi;            // CWSI promedio del lote
        double averageEtActual;        // ETa promedio (mm)
        double averageEtPotential;     // ETc promedio (mm)
        double averagePrecipitation;   // Precipitación uniforme aplicada (mm)
        double averageDeepDrainage;    // Drenaje profundo / escorrentía promedio (mm)
        double averageDeltaStorage;    // Variación neta de almacenamiento en el suelo (mm)
        double massBalanceError;       // Error de conservación: |DeltaW + ETa + Drenaje - Precipitación| (mm)
    };

    // Actualiza el balance hídrico aplicando precipitación uniforme a todas las celdas
    StepSummary updateDailyStep(
        const SoilInfo& soil,
        double etPotential,
        double precipitation,
        double rootDepthMeters
    );

    StepSummary updateDailyStepOpenMP(
        const SoilInfo& soil,
        double etPotential,
        double precipitation,
        double rootDepthMeters
    );


    StepSummary updateDailyStepMPI(
        const SoilInfo& soil,
        double etPotential,
        double precipitation,
        double rootDepthMeters,
        int rank,
        int processCount
    );

    StepSummary updateDailyStepHybrid(
        const SoilInfo& soil,
        double etPotential,
        double precipitation,
        double rootDepthMeters,
        int rank,
        int processCount
    );

    void synchronizeForMPI(int rank, int processCount);

    // Exporta la malla para visualización agregada (ej. cuadrícula 8x8 de interfaz)
    std::vector<SpatialCell> exportVisualizationGrid(int targetRows = 8, int targetCols = 8) const;

private:
    int rows_;
    int cols_;
    double cellSizeMeters_;
    std::vector<double> moisture_;     // Humedad en % volumétrico (row-major)
    std::vector<double> cwsi_;         // Índice CWSI por celda
    std::vector<double> depthFactor_;  // Factor de microrelieve edáfico (profundidad efectiva), promedio = 1.0
};

} // namespace agrochaco

#endif // AGROCHACO_GRID_HPP
