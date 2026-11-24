from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.repository import SimulationRepository
from app.models.evento_ejecucion import EventoEjecucion
from app.models.simulacion import Simulacion
from app.services.motor_service import (
    MotorExecutionError,
    MotorNotFoundError,
    MotorOutputError,
    MotorSecurityError,
    MotorService,
    MotorServiceError,
    MotorTimeoutError,
    PROJECT_ROOT,
)


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
        "timelineData": [],
        "spatialGrid": [],
        "logs": [],
    }

    # Adjuntar métricas HPC si existen registradas en PostgreSQL
    if sim.rendimientos:
        ultimo_rendimiento = sim.rendimientos[-1]
        response_data["executionTimeSeconds"] = float(ultimo_rendimiento.tiempo_segundos)
        response_data["speedup"] = (
            float(ultimo_rendimiento.speedup)
            if ultimo_rendimiento.speedup is not None
            else None
        )
        response_data["efficiency"] = (
            float(ultimo_rendimiento.eficiencia)
            if ultimo_rendimiento.eficiencia is not None
            else None
        )

    # Adjuntar métricas agronómicas si existen registradas en PostgreSQL
    if sim.resultado:
        response_data["averageCWSI"] = float(sim.resultado.deficit_medio)
        response_data["soilMoistureFinalPercent"] = float(sim.resultado.agua_final_media)

        # Recuperar JSON detallado desde archivo_detalle si existe en disco y es seguro
        if sim.resultado.archivo_detalle:
            archivo_path = Path(sim.resultado.archivo_detalle)
            if not archivo_path.is_absolute():
                archivo_path = PROJECT_ROOT / archivo_path

            # Resolución canónica y comprobación estricta de confinamiento en results/simulations
            allowed_dir = (PROJECT_ROOT / "results" / "simulations").resolve()
            try:
                archivo_path = archivo_path.resolve()
                es_valido = archivo_path.is_relative_to(allowed_dir) and archivo_path.is_file()
            except (OSError, RuntimeError):
                es_valido = False

            if es_valido:
                try:
                    with open(archivo_path, "r", encoding="utf-8") as f:
                        detalles = json.load(f)

                    if isinstance(detalles, dict):
                        if "timelineData" in detalles:
                            response_data["timelineData"] = detalles["timelineData"]
                        if "spatialGrid" in detalles:
                            response_data["spatialGrid"] = detalles["spatialGrid"]
                        if "logs" in detalles:
                            response_data["logs"] = detalles["logs"]
                        if "yieldLossPercent" in detalles:
                            response_data["yieldLossPercent"] = float(detalles["yieldLossPercent"])
                        if "estimatedYieldTnHa" in detalles:
                            response_data["estimatedYieldTnHa"] = float(detalles["estimatedYieldTnHa"])
                        if "nominalYieldTnHa" in detalles:
                            response_data["nominalYieldTnHa"] = float(detalles["nominalYieldTnHa"])
                        if "waterDeficitMm" in detalles:
                            response_data["waterDeficitMm"] = float(detalles["waterDeficitMm"])
                        if "memoryUsageMb" in detalles:
                            response_data["memoryUsageMb"] = float(detalles["memoryUsageMb"])
                        if "currentDay" in detalles:
                            response_data["currentDay"] = detalles["currentDay"]
                        if "completedAt" in detalles and detalles["completedAt"]:
                            response_data["completedAt"] = detalles["completedAt"]
                except Exception:
                    pass

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
    try:
        sim_id_seguro = MotorService.validar_simulation_id(simulation_id)
    except MotorSecurityError as err:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Identificador de simulación inválido: {err}",
        ) from err

    simulation = SimulationRepository.obtener_por_id(
        db, sim_id_seguro, cargar_relaciones=True
    )

    if simulation is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Simulación no encontrada.",
        )

    return _format_simulation_response(simulation)


@router.post("/{simulation_id}/execute", status_code=http_status.HTTP_200_OK)
def execute_simulation(simulation_id: str, db: Session = Depends(get_db)):
    # 1. Validación de seguridad en simulation_id (prevención de Path Traversal)
    try:
        sim_id_seguro = MotorService.validar_simulation_id(simulation_id)
    except MotorSecurityError as err:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Identificador de simulación inválido: {err}",
        ) from err

    # 2. Verificar existencia de la simulación
    simulation = SimulationRepository.obtener_por_id(
        db, sim_id_seguro, cargar_relaciones=True
    )

    if simulation is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Simulación '{sim_id_seguro}' no encontrada.",
        )

    # 3. Transición atómica de estado en PostgreSQL:
    # Bloquea la fila y actualiza solo si estado != 'running'
    stmt = (
        update(Simulacion)
        .where(
            Simulacion.id == sim_id_seguro,
            Simulacion.estado != "running",
        )
        .values(estado="running")
    )
    res = db.execute(stmt)

    if res.rowcount == 0:
        # Otra solicitud concurrente ya adquirió la ejecución
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"La simulación '{sim_id_seguro}' ya se encuentra en ejecución por otra solicitud.",
        )

    # Confirmar de inmediato la transición al estado 'running' y el evento de inicio
    config_dict: dict[str, Any] = {}
    if simulation.parametro and isinstance(simulation.parametro.configuracion_json, dict):
        config_dict = dict(simulation.parametro.configuracion_json)

    engine = str(config_dict.get("engine", "secuencial")).lower()

    try:
        evento_inicio = EventoEjecucion(
            simulacion_id=sim_id_seguro,
            nivel="INFO",
            mensaje=f"Iniciando ejecución del motor '{engine}' en C++17.",
        )
        db.add(evento_inicio)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar inicio de ejecución: {exc}",
        ) from exc

    # 4. Ejecución del motor C++17
    try:
        resultado_ejecucion = MotorService.ejecutar(
            simulation_id=sim_id_seguro,
            config_dict=config_dict,
        )

        # 5. Persistencia atómica de resultados biofísicos y métricas HPC en una sola transacción
        MotorService.persistir_resultados_en_db(
            db=db,
            simulation_id=sim_id_seguro,
            config_dict=config_dict,
            resultado_ejecucion=resultado_ejecucion,
        )

    except Exception as error:
        # En caso de fallo, marcar simulación como 'failed' y registrar evento de error
        try:
            SimulationRepository.actualizar_estado(db, sim_id_seguro, "failed")
            SimulationRepository.registrar_evento(
                db,
                sim_id_seguro,
                nivel="ERROR",
                mensaje=f"Fallo en la ejecución del motor '{engine}': {error}",
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante la ejecución del motor de simulación: {error}",
        ) from error

    # 6. Retornar simulación actualizada con sus resultados consolidados
    sim_actualizada = SimulationRepository.obtener_por_id(
        db, sim_id_seguro, cargar_relaciones=True
    )
    return _format_simulation_response(sim_actualizada or simulation)


@router.delete("/{simulation_id}")
def delete_simulation(simulation_id: str, db: Session = Depends(get_db)):
    try:
        sim_id_seguro = MotorService.validar_simulation_id(simulation_id)
    except MotorSecurityError as err:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Identificador de simulación inválido: {err}",
        ) from err

    eliminado = SimulationRepository.eliminar_simulacion(db, sim_id_seguro)

    if not eliminado:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Simulación no encontrada.",
        )

    return {
        "mensaje": "Simulación eliminada correctamente.",
        "id": sim_id_seguro,
    }
