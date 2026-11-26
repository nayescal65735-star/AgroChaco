#include "agrochaco/mpi_runtime.hpp"
#include "agrochaco/json_serializer.hpp"
#include <stdexcept>
#include <string>

namespace agrochaco {

static void checkMpiCall(int code, const char* operation) {
    if (code != MPI_SUCCESS) {
        throw std::runtime_error(std::string("Fallo MPI en ") + operation);
    }
}

int broadcastDecision(MPI_Comm comm, int rank, int rootDecision) {
    int decision = (rank == 0) ? rootDecision : 0;
    checkMpiCall(MPI_Bcast(&decision, 1, MPI_INT, 0, comm), "MPI_Bcast(decision)");
    return decision;
}

bool broadcastConfiguration(
    MPI_Comm comm,
    int rank,
    SimulationConfig& config,
    std::string& error
) {
    std::string payload;
    if (rank == 0) {
        try {
            payload = JsonSerializer::serializeConfig(config);
        } catch (const std::exception& e) {
            error = e.what();
        }
    }

    int localOk = error.empty() ? 1 : 0;
    int globalOk = 1;
    checkMpiCall(
        MPI_Allreduce(&localOk, &globalOk, 1, MPI_INT, MPI_MIN, comm),
        "MPI_Allreduce(config serialization)"
    );
    if (globalOk == 0) {
        if (rank == 0 && error.empty()) {
            error = "No fue posible serializar la configuración del proceso maestro.";
        }
        return false;
    }

    int length = static_cast<int>(payload.size());
    checkMpiCall(MPI_Bcast(&length, 1, MPI_INT, 0, comm), "MPI_Bcast(config length)");

    if (rank != 0) {
        payload.resize(static_cast<size_t>(length));
    }
    checkMpiCall(
        MPI_Bcast(&payload[0], length, MPI_CHAR, 0, comm),
        "MPI_Bcast(config payload)"
    );

    try {
        if (rank != 0) {
            config = ConfigLoader::loadFromString(payload);
        }
    } catch (const std::exception& e) {
        error = e.what();
    }

    localOk = error.empty() ? 1 : 0;
    checkMpiCall(
        MPI_Allreduce(&localOk, &globalOk, 1, MPI_INT, MPI_MIN, comm),
        "MPI_Allreduce(config parse)"
    );
    return globalOk != 0;
}

}
