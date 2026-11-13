from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.repository import SimulationRepository
from app.models.simulacion import Simulacion


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


# Valores biofísicos de referencia según la base agronómica del Chaco (SOILS en motor/src/agronomic_data.cpp)
# (Capacidad de agua disponible en mm/m y umbral hídrico aproximado del 50%)
SOIL_WATER_CAPACITY_MAP: dict[str, tuple[Decimal, Decimal]] = {
    "franco_arenoso": (Decimal("103.00"), Decimal("51.50")),
    "franco_arcilloso": (Decimal("135.00"), Decimal("67.50")),
    "arenoso": (Decimal("72.00"), Decimal("36.00")),
    "franco": (Decimal("130.00"), Decimal("65.00")),
}
DEFAULT_SOIL_CAPACITY = Decimal("100.00")
DEFAULT_WATER_THRESHOLD = Decimal("50.00")


def _format_simulation_response(sim: Simulacion) -> dict[str, Any]:
    """Serializa una entidad Simulacion de SQLAlchemy al formato JSON esperado por el frontend React."""
    config_dict: dict[str, Any] = {}
    if sim.parametro and isinstance(sim.parametro.configuracion_json, dict):
        config_dict = dict(sim.parametro.configuracion_json)

    # Asegurar campos esenciales requeridos por el frontend si la simulación proviene de semillas u orígenes externos
    if "name" not in config_dict:
        config_dict["name"] = sim.nombre
    if "droughtScenario" not in config_dict:
        config_dict["droughtScenario"] = sim.escenario
    if "simulationDays" not in config_dict:
        config_dict["simulationDays"] = sim.dias
    if "initialMoisturePercent" not in config_dict and sim.parametro:
        config_dict["initialMoisturePercent"] = float(sim.parametro.agua_inicial)
    if "zone" not in config_dict:
        config_dict["zone"] = "yacuiba"
    if "zoneName" not in config_dict:
        config_dict["zoneName"] = config_dict.get("zone", "Yacuiba").capitalize()
    if "department" not in config_dict:
        config_dict["department"] = "Tarija"
    if "soilType" not in config_dict:
        config_dict["soilType"] = "franco_arenoso"
    if "cornVariety" not in config_dict:
        config_dict["cornVariety"] = "chaco_01_criollo"
    if "engine" not in config_dict:
        config_dict["engine"] = "secuencial"
    if "gridConfig" not in config_dict:
        config_dict["gridConfig"] = {"rows": 100, "cols": 100, "cellSizeMeters": 50}

    created_iso = (
        sim.fecha_creacion.isoformat()
        if sim.fecha_creacion
        else datetime.now(timezone.utc).isoformat()
    )

    response_data: dict[str, Any] = {
        "id": sim.id,
        "config": config_dict,
        "status": sim.estado,
        "progressPercent": 100 if sim.estado == "completed" else 0,
        "createdAt": created_iso,
        "completedAt": created_iso if sim.estado == "completed" else None,
    }

    # Adjuntar métricas HPC si existen registradas en PostgreSQL
    if sim.rendimientos:
        ultimo_rendimiento = sim.rendimientos[-1]
        response_data["executionTimeSeconds"] = float(ultimo_rendimiento.tiempo_segundos)
        response_data["speedup"] = float(ultimo_rendimiento.speedup)
        response_data["efficiency"] = float(ultimo_rendimiento.eficiencia)

    # Adjuntar métricas agronómicas si existen registradas en PostgreSQL
    if sim.resultado:
        response_data["averageCWSI"] = float(sim.resultado.deficit_medio)
        response_data["soilMoistureFinalPercent"] = float(sim.resultado.agua_final_media)

    return response_data


@router.post("", status_code=http_status.HTTP_201_CREATED)
def create_simulation(data: SimulationCreate, db: Session = Depends(get_db)):
    simulation_id = f"SIM-{uuid4().hex[:12].upper()}"
    config_dict = data.model_dump(mode="json")

    cap_suelo, umbral_hid = SOIL_WATER_CAPACITY_MAP.get(
        data.soilType, (DEFAULT_SOIL_CAPACITY, DEFAULT_WATER_THRESHOLD)
    )

    datos_sim = {
        "id": simulation_id,
        "nombre": data.name,
        "fuente_datos": f"Estación {data.zoneName}",
        "escenario": data.droughtScenario,
        "cantidad_escenarios": 1,
        "dias": data.simulationDays,
        "estado": "pending",
        "semilla": None,
    }

    datos_param = {
        "agua_inicial": Decimal(str(data.initialMoisturePercent)),
        "capacidad_suelo": cap_suelo,
        "umbral_hidrico": umbral_hid,
        "configuracion_json": config_dict,
    }

    try:
        sim = SimulationRepository.crear_simulacion_con_parametros(
            db, datos_sim, datos_param
        )
    except Exception as error:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al persistir la simulación en la base de datos: {error}",
        ) from error

    return _format_simulation_response(sim)


@router.get("")
def list_simulations(
    search: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    try:
        simulaciones, total = SimulationRepository.listar_historial(
            db, search=search, estado=status, limit=limit, offset=offset
        )
    except Exception as error:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar el historial de simulaciones: {error}",
        ) from error

    return {
        "total": total,
        "simulations": [_format_simulation_response(s) for s in simulaciones],
    }


@router.get("/{simulation_id}")
def get_simulation(simulation_id: str, db: Session = Depends(get_db)):
    simulation = SimulationRepository.obtener_por_id(
        db, simulation_id, cargar_relaciones=True
    )

    if simulation is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Simulación no encontrada.",
        )

    return _format_simulation_response(simulation)


@router.post("/{simulation_id}/execute", status_code=http_status.HTTP_501_NOT_IMPLEMENTED)
def execute_simulation(simulation_id: str, db: Session = Depends(get_db)):
    simulation = SimulationRepository.obtener_por_id(
        db, simulation_id, cargar_relaciones=False
    )

    if simulation is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Simulación no encontrada.",
        )

    raise HTTPException(
        status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "La ejecución todavía no está disponible. "
            "Se requiere integrar el motor de simulación."
        ),
    )


@router.delete("/{simulation_id}")
def delete_simulation(simulation_id: str, db: Session = Depends(get_db)):
    eliminado = SimulationRepository.eliminar_simulacion(db, simulation_id)

    if not eliminado:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Simulación no encontrada.",
        )

    return {
        "mensaje": "Simulación eliminada correctamente.",
        "id": simulation_id,
    }
