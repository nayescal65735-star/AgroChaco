from datetime import date, datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


router = APIRouter(prefix="/api/simulations", tags=["Simulations"])


# Tipos permitidos por el formulario de React.
Zone = Literal[
    "yacuiba",
    "villamontes",
    "carapari",
    "charagua",
    "machareti",
    "boyuibe",
]

SoilType = Literal[
    "franco_arenoso",
    "franco_arcilloso",
    "arenoso",
    "franco",
]

CornVariety = Literal[
    "chaco_01_criollo",
    "dekalb_7088",
    "iniaf_h1",
    "pioneer_30f35",
]

Engine = Literal["secuencial", "openmp", "mpi", "hibrido"]

DroughtScenario = Literal[
    "historico",
    "moderado_ssp245",
    "extremo_ssp585",
    "sequia_recente_2023",
]


class GridConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: int = Field(ge=50, le=1000)
    cols: int = Field(ge=50, le=1000)
    cellSizeMeters: int = Field(ge=10, le=200)


class SimulationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=120)
    zone: Zone
    zoneName: str = Field(min_length=2, max_length=100)

    @field_validator("name", "zoneName", mode="before")
    @classmethod
    def clean_text_fields(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value
    department: Literal["Tarija", "Santa Cruz", "Chuquisaca"]
    soilType: SoilType
    cornVariety: CornVariety
    plantingDate: date
    simulationDays: int = Field(ge=30, le=150)
    gridConfig: GridConfig
    initialMoisturePercent: float = Field(ge=5, le=35)
    droughtScenario: DroughtScenario
    engine: Engine
    openmpThreads: int | None = Field(default=None, ge=2, le=16)
    mpiProcesses: int | None = Field(default=None, ge=2, le=16)
    nodesCount: int | None = Field(default=None, ge=1, le=4)

    @model_validator(mode="after")
    def validate_engine_parameters(self):
        allowed_workers = {2, 4, 8, 16}

        if self.engine in ("openmp", "hibrido"):
            if self.openmpThreads not in allowed_workers:
                raise ValueError(
                    "OpenMP requiere 2, 4, 8 o 16 hilos."
                )

        if self.engine in ("mpi", "hibrido"):
            if self.mpiProcesses not in allowed_workers:
                raise ValueError(
                    "MPI requiere 2, 4, 8 o 16 procesos."
                )

        if self.engine in ("mpi", "hibrido"):
            if self.nodesCount not in {1, 2, 4}:
                raise ValueError(
                    "La cantidad de nodos debe ser 1, 2 o 4."
                )

        return self


# Almacenamiento temporal.
# Posteriormente se reemplazará por PostgreSQL junto con Yulenka.
_simulations: dict[str, dict] = {}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_simulation(data: SimulationCreate):
    simulation_id = f"SIM-{uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    simulation = {
        "id": simulation_id,
        "config": data.model_dump(mode="json"),
        "status": "pending",
        "progressPercent": 0,
        "createdAt": now,
        "completedAt": None,
    }

    _simulations[simulation_id] = simulation

    return simulation


@router.get("")
def list_simulations():
    return {
        "total": len(_simulations),
        "simulations": list(_simulations.values()),
    }


@router.get("/{simulation_id}")
def get_simulation(simulation_id: str):
    simulation = _simulations.get(simulation_id)

    if simulation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulación no encontrada.",
        )

    return simulation


@router.post("/{simulation_id}/execute", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def execute_simulation(simulation_id: str):
    if simulation_id not in _simulations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulación no encontrada.",
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "La ejecución todavía no está disponible. "
            "Se requiere integrar el motor de simulación."
        ),
    )


@router.delete("/{simulation_id}")
def delete_simulation(simulation_id: str):
    simulation = _simulations.pop(simulation_id, None)

    if simulation is None:
        raise HTTPException(
            status_code=404,
            detail="Simulación no encontrada."
        )

    return {
        "mensaje": "Simulación eliminada correctamente.",
        "id": simulation_id
    }
