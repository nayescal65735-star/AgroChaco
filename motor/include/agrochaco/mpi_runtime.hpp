#ifndef AGROCHACO_MPI_RUNTIME_HPP
#define AGROCHACO_MPI_RUNTIME_HPP

#include "config.hpp"
#include <mpi.h>
#include <string>

namespace agrochaco {

int broadcastDecision(MPI_Comm comm, int rank, int rootDecision);

bool broadcastConfiguration(
    MPI_Comm comm,
    int rank,
    SimulationConfig& config,
    std::string& error
);

}

#endif
