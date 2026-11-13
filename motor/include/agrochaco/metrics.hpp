#ifndef AGROCHACO_METRICS_HPP
#define AGROCHACO_METRICS_HPP

#include "types.hpp"
#include <chrono>

namespace agrochaco {

class ExecutionTimer {
public:
    ExecutionTimer();

    void start();
    void stop();

    double getElapsedSeconds() const;
    static double getCurrentMemoryUsageMb();

private:
    std::chrono::high_resolution_clock::time_point startTime_;
    std::chrono::high_resolution_clock::time_point endTime_;
    bool isRunning_{false};
};

} // namespace agrochaco

#endif // AGROCHACO_METRICS_HPP
