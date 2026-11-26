cmake_minimum_required(VERSION 3.16)
project(AgroChacoMotor VERSION 1.0.0 LANGUAGES CXX)

find_package(OpenMP REQUIRED)
find_package(MPI REQUIRED)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Opciones de compilación y optimización
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(
        -Wall
        -Wextra
        -Wpedantic
        -O3
    )
endif()

# Directorio de salida para binarios compilados
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)

# Directorio de cabeceras públicas
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

# Biblioteca estática con la lógica del modelo agronómico y de cómputo
add_library(agrochaco_core STATIC
    src/common.cpp
    src/agronomic_data.cpp
    src/config.cpp
    src/soil_model.cpp
    src/crop_model.cpp
    src/water_balance.cpp
    src/grid.cpp
    src/metrics.cpp
    src/json_serializer.cpp
    src/mpi_runtime.cpp
    src/simulation_engine.cpp
    src/openmp_engine.cpp
    src/mpi_engine.cpp
    src/hybrid_engine.cpp
)

target_include_directories(agrochaco_core PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)

target_link_libraries(agrochaco_core PUBLIC OpenMP::OpenMP_CXX MPI::MPI_CXX)

# Ejecutable 1: Motor Secuencial C++17 (Baseline)
add_executable(agrochaco_secuencial
    src/main_secuencial.cpp
)
target_link_libraries(agrochaco_secuencial PRIVATE agrochaco_core)

# Ejecutable de Pruebas: Suite de Validación de Entradas y Consistencia
add_executable(test_motor
    tests/test_validation.cpp
)
target_link_libraries(test_motor PRIVATE agrochaco_core)

# Ejecutable 2: Motor paralelo OpenMP
add_executable(agrochaco_openmp
    src/main_openmp.cpp
)
target_link_libraries(agrochaco_openmp PRIVATE agrochaco_core)


# Ejecutable 3: Motor paralelo de memoria distribuida MPI
add_executable(agrochaco_mpi
    src/main_mpi.cpp
)
target_link_libraries(agrochaco_mpi PRIVATE agrochaco_core MPI::MPI_CXX)


# Ejecutable 4: Motor híbrido MPI + OpenMP
add_executable(agrochaco_hibrido
    src/main_hybrid.cpp
)
target_link_libraries(agrochaco_hibrido PRIVATE agrochaco_core MPI::MPI_CXX OpenMP::OpenMP_CXX)

# Ejecutable de pruebas MPI reales
add_executable(test_motor_mpi
    tests/test_mpi_validation.cpp
)
target_link_libraries(test_motor_mpi PRIVATE agrochaco_core MPI::MPI_CXX OpenMP::OpenMP_CXX)

# Registro de pruebas unitarias e integración en CTest
enable_testing()
add_test(NAME AgroChaco_Tests COMMAND test_motor)
add_test(
    NAME AgroChaco_MPI_Tests
    COMMAND ${MPIEXEC_EXECUTABLE} ${MPIEXEC_NUMPROC_FLAG} 3 ${MPIEXEC_PREFLAGS} $<TARGET_FILE:test_motor_mpi> ${MPIEXEC_POSTFLAGS}
)
set_tests_properties(AgroChaco_MPI_Tests PROPERTIES TIMEOUT 60)

find_package(Python3 COMPONENTS Interpreter QUIET)
if(Python3_Interpreter_FOUND)
    add_test(
        NAME AgroChaco_Equivalence_7B3
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/run_equivalence_7b3.py
    )
    set_tests_properties(AgroChaco_Equivalence_7B3 PROPERTIES TIMEOUT 300)
endif()
