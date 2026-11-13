#ifndef AGROCHACO_SIMULATION_ENGINE_HPP
#define AGROCHACO_SIMULATION_ENGINE_HPP

#include "types.hpp"
#include <functional>

namespace agrochaco {

class SequentialEngine {
public:
    explicit SequentialEngine(SimulationConfig config);

    // Ejecuta la simulación secuencial completa
    SimulationResult run();

    // Callback opcional de progreso para interfaces o backend: callback(int diaActual, int totalDias, double cwsiPromedio)
    using ProgressCallback = std::function<void(int, int, double)>;
    void setProgressCallback(ProgressCallback callback) { progressCallback_ = callback; }

private:
    SimulationConfig config_;
    ProgressCallback progressCallback_;

    void log(std::vector<SimulationLog>& logs, LogLevel level, const std::string& message);
};


// Motor paralelo de memoria compartida mediante OpenMP.
class OpenMPEngine {
public:
    explicit OpenMPEngine(SimulationConfig config);

    SimulationResult run();

    using ProgressCallback = std::function<void(int, int, double)>;
    void setProgressCallback(ProgressCallback callback) {
        progressCallback_ = callback;
    }

private:
    SimulationConfig config_;
    ProgressCallback progressCallback_;

    void log(std::vector<SimulationLog>& logs, LogLevel level,
             const std::string& message);
};


// Motor paralelo de memoria distribuida mediante MPI.
class MpiEngine {
public:
    explicit MpiEngine(SimulationConfig config);

    SimulationResult run();

    using ProgressCallback = std::function<void(int, int, double)>;
    void setProgressCallback(ProgressCallback callback) {
        progressCallback_ = callback;
    }

private:
    SimulationConfig config_;
    ProgressCallback progressCallback_;

    void log(std::vector<SimulationLog>& logs, LogLevel level,
             const std::string& message);
};

// Motor híbrido: MPI distribuye celdas y OpenMP usa hilos por proceso.
class HybridEngine {
public:
    explicit HybridEngine(SimulationConfig config);

    SimulationResult run();

    using ProgressCallback = std::function<void(int, int, double)>;
    void setProgressCallback(ProgressCallback callback) {
        progressCallback_ = callback;
    }

private:
    SimulationConfig config_;
    ProgressCallback progressCallback_;

    void log(std::vector<SimulationLog>& logs, LogLevel level,
             const std::string& message);
};

} // namespace agrochaco

#endif // AGROCHACO_SIMULATION_ENGINE_HPP
