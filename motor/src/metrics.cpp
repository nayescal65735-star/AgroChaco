#include "agrochaco/metrics.hpp"
#include <fstream>
#include <unistd.h>
#include <sys/resource.h>

namespace agrochaco {

ExecutionTimer::ExecutionTimer()
    : startTime_(std::chrono::high_resolution_clock::now()),
      endTime_(startTime_),
      isRunning_(false) {}

void ExecutionTimer::start() {
    startTime_ = std::chrono::high_resolution_clock::now();
    isRunning_ = true;
}

void ExecutionTimer::stop() {
    endTime_ = std::chrono::high_resolution_clock::now();
    isRunning_ = false;
}

double ExecutionTimer::getElapsedSeconds() const {
    auto endPoint = isRunning_ ? std::chrono::high_resolution_clock::now() : endTime_;
    std::chrono::duration<double> duration = endPoint - startTime_;
    return duration.count();
}

double ExecutionTimer::getCurrentMemoryUsageMb() {
    // Intento 1: lectura de /proc/self/statm en Linux (memoria residente RSS exacta)
    std::ifstream statm("/proc/self/statm");
    if (statm.is_open()) {
        long totalPages = 0;
        long residentPages = 0;
        if (statm >> totalPages >> residentPages) {
            long pageSizeBytes = sysconf(_SC_PAGESIZE);
            double memoryMb = (residentPages * pageSizeBytes) / (1024.0 * 1024.0);
            return memoryMb;
        }
    }

    // Intento 2: getrusage (POSIX estándar)
    struct rusage usage;
    if (getrusage(RUSAGE_SELF, &usage) == 0) {
        // En Linux, ru_maxrss viene expresado en kilobytes
        return usage.ru_maxrss / 1024.0;
    }

    return 0.0;
}

} // namespace agrochaco
