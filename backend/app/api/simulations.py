from datetime import date, datetime, timezone
from decimal import Decimal
import json
import logging
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status as http_status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.repository import SimulationRepository
from app.models.evento_ejecucion import EventoEjecucion
from app.models.simulacion import Simulacion
from app.services.export_service import ExportService
from app.services.motor_service import MotorSecurityError, MotorService, PROJECT_ROOT
from app.workers.simulation_worker import MENSAJE_CANCELACION, validar_job_id


logger = logging.getLogger("agrochaco.api.jobs")

router = APIRouter(prefix="/api/simulations", tags=["Simulations"])
jobs_router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


def _iso(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor is not None else None


def _formatear_job(trabajo: Any) -> dict[str, Any]:
    estado = trabajo.estado
    error = trabajo.error_message
    return {
        "job_id": str(trabajo.job_id),
        "simulation_id": trabajo.simulacion_id,
        "estado": estado,
        "status": estado,
        "progressPercent": trabajo.progress_percent,
        "currentDay": trabajo.current_day,
        "pid": trabajo.pid,
        "cancelRequested": bool(trabajo.cancel_requested),
        "createdAt": _iso(trabajo.created_at),
        "startedAt": _iso(trabajo.started_at),
        "updatedAt": _iso(trabajo.updated_at),
        "finishedAt": _iso(trabajo.finished_at),
        "error": error,
        "error_message": error,
    }


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


def _obtener_simulacion_para_exportacion(
    simulation_id: str, db: Session
) -> tuple[Simulacion, str]:
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

    return simulation, sim_id_seguro


def _nombre_archivo_exportacion(simulation_id: str, extension: str) -> str:
    seguro = "".join(
        ch if ch.isascii() and (ch.isalnum() or ch in "-_") else "_"
        for ch in simulation_id
    )
    return f"{seguro or 'simulacion'}.{extension}"


def _respuesta_archivo(contenido: str, media_type: str, nombre_archivo: str) -> Response:
    return Response(
        content=contenido.encode("utf-8"),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@router.get("/{simulation_id}/export/json")
def export_simulation_json(simulation_id: str, db: Session = Depends(get_db)):
    simulation, sim_id_seguro = _obtener_simulacion_para_exportacion(simulation_id, db)
    contenido = ExportService.exportar_simulacion_json_str(simulation)
    return _respuesta_archivo(
        contenido,
        "application/json",
        _nombre_archivo_exportacion(sim_id_seguro, "json"),
    )


@router.get("/{simulation_id}/export/csv")
def export_simulation_csv(simulation_id: str, db: Session = Depends(get_db)):
    simulation, sim_id_seguro = _obtener_simulacion_para_exportacion(simulation_id, db)
    contenido = ExportService.exportar_historial_csv([simulation])
    return _respuesta_archivo(
        contenido,
        "text/csv",
        _nombre_archivo_exportacion(sim_id_seguro, "csv"),
    )


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


@router.post("/{simulation_id}/execute", status_code=http_status.HTTP_202_ACCEPTED)
def execute_simulation(simulation_id: str, db: Session = Depends(get_db)):
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
            detail=f"Simulación '{sim_id_seguro}' no encontrada.",
        )
    if simulation.estado == "running":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"La simulación '{sim_id_seguro}' ya se encuentra en ejecución.",
        )

    try:
        trabajo = SimulationRepository.crear_trabajo_unico(db, sim_id_seguro)
    except ValueError as error:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except Exception as error:
        logger.exception("No se pudo crear el trabajo de %s", sim_id_seguro)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar la ejecución solicitada.",
        ) from error

    if trabajo is None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"La simulación '{sim_id_seguro}' ya tiene un trabajo activo.",
        )

    try:
        SimulationRepository.actualizar_estado_simulacion(
            db, sim_id_seguro, "running", commit=False
        )
        db.add(
            EventoEjecucion(
                simulacion_id=sim_id_seguro,
                nivel="INFO",
                mensaje="Ejecución encolada; esperando a un worker.",
            )
        )
        db.commit()
    except Exception as error:
        db.rollback()
        logger.exception("No se pudo registrar el encolado de %s", sim_id_seguro)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar la ejecución solicitada.",
        ) from error

    return {
        "job_id": str(trabajo.job_id),
        "simulation_id": sim_id_seguro,
        "estado": trabajo.estado,
        "status": trabajo.estado,
        "progressPercent": trabajo.progress_percent,
        "currentDay": trabajo.current_day,
        "createdAt": trabajo.created_at.isoformat() if trabajo.created_at else None,
    }


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


@jobs_router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    try:
        job_uuid = validar_job_id(job_id)
    except ValueError as error:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Identificador de trabajo inválido.",
        ) from error

    db.rollback()
    trabajo = SimulationRepository.obtener_trabajo(db, job_uuid)
    if trabajo is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Trabajo no encontrado.",
        )
    return _formatear_job(trabajo)


@jobs_router.post("/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    try:
        job_uuid = validar_job_id(job_id)
    except ValueError as error:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Identificador de trabajo inválido.",
        ) from error

    db.rollback()
    trabajo = SimulationRepository.obtener_trabajo(db, job_uuid)
    if trabajo is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Trabajo no encontrado.",
        )

    try:
        actualizado = SimulationRepository.solicitar_cancelacion(db, job_uuid)
    except Exception as error:
        logger.exception("No se pudo solicitar la cancelación de %s", job_uuid)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo solicitar la cancelación.",
        ) from error

    if actualizado is None:
        db.rollback()
        actual = SimulationRepository.obtener_trabajo(db, job_uuid)
        estado = actual.estado if actual is not None else "desconocido"
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"El trabajo ya no puede cancelarse; estado actual: {estado}.",
        )

    if actualizado.estado == "queued":
        try:
            cancelado = SimulationRepository.actualizar_estado_trabajo(
                db,
                job_uuid,
                "canceled",
                estado_esperado="queued",
                error_message=MENSAJE_CANCELACION,
                commit=False,
            )
            if cancelado is not None:
                SimulationRepository.actualizar_estado_simulacion(
                    db, cancelado.simulacion_id, "paused", commit=False
                )
                db.commit()
                actualizado = cancelado
        except Exception:
            db.rollback()
            logger.exception("No se pudo consolidar la cancelación de %s", job_uuid)
            actualizado = SimulationRepository.obtener_trabajo(db, job_uuid) or actualizado

    return _formatear_job(actualizado)
