#ifndef AGROCHACO_GRID_HPP
#define AGROCHACO_GRID_HPP

#include "types.hpp"
#include <mpi.h>
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
        double averageMoisture{0.0};        // Humedad promedio (% volumétrico)
        double averageCwsi{0.0};            // CWSI promedio del lote
        double averageEtActual{0.0};        // ETa promedio (mm)
        double averageEtPotential{0.0};     // ETc promedio (mm)
        double averagePrecipitation{0.0};   // Precipitación uniforme aplicada (mm)
        double averageDeepDrainage{0.0};    // Drenaje profundo promedio (mm)
        double averageDeltaStorage{0.0};    // Variación neta de almacenamiento en el suelo (mm)
        double averageInitialStorage{0.0};  // Almacenamiento inicial promedio (mm)
        double averageFinalStorage{0.0};    // Almacenamiento final promedio (mm)
        double rootDepthStorageRebaseMm{0.0}; // Rebase del volumen de control por profundidad radicular (mm)
        double massBalanceError{0.0};       // Máximo error absoluto por celda (mm)
        double massBalanceResidualMm{0.0};  // Residuo agregado con signo: DeltaW + ETa + Drenaje - Precipitación (mm)
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
        int processCount,
        MPI_Comm comm = MPI_COMM_WORLD
    );

    StepSummary updateDailyStepHybrid(
        const SoilInfo& soil,
        double etPotential,
        double precipitation,
        double rootDepthMeters,
        int rank,
        int processCount,
        MPI_Comm comm = MPI_COMM_WORLD
    );

    void synchronizeForMPI(int rank, int processCount, MPI_Comm comm = MPI_COMM_WORLD);

    // Exporta la malla para visualización agregada (ej. cuadrícula 8x8 de interfaz)
    std::vector<SpatialCell> exportVisualizationGrid(int targetRows = 8, int targetCols = 8) const;

private:
    int rows_;
    int cols_;
    double cellSizeMeters_;
    std::vector<double> moisture_;     // Humedad en % volumétrico (row-major)
    std::vector<double> cwsi_;         // Índice CWSI por celda
    std::vector<double> depthFactor_;  // Factor de microrelieve edáfico (profundidad efectiva), promedio = 1.0
    double previousFinalStorageSumMm_{0.0};
    bool hasPreviousStorage_{false};
};

} // namespace agrochaco

#endif // AGROCHACO_GRID_HPP
