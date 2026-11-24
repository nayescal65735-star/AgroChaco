"""Pruebas del modelo y repositorio de trabajos de simulación."""

import contextlib
import importlib.util
import io
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.db.repository import SimulationRepository
from app.models import Base, Simulacion, SimulationJob
from app.models.simulation_job import TRANSICIONES_TRABAJO, transiciones_permitidas_desde

RAIZ_BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def activar_claves_foraneas(dbapi_connection, _registro_conexion):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine)
    with fabrica() as sesion:
        yield sesion
    engine.dispose()


def crear_simulacion(db_session: Session, sim_id: str) -> Simulacion:
    simulacion = Simulacion(
        id=sim_id,
        nombre=f"Simulación {sim_id}",
        fuente_datos="campo",
        escenario="base",
        dias=120,
    )
    db_session.add(simulacion)
    db_session.commit()
    return simulacion


def cargar_migracion_003():
    ruta = RAIZ_BACKEND / "alembic" / "versions" / "003_simulation_jobs.py"
    especificacion = importlib.util.spec_from_file_location("migracion_003_simulation_jobs", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def generar_sql_offline(operacion: str) -> str:
    configuracion = Config(str(RAIZ_BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(RAIZ_BACKEND / "alembic"))
    configuracion.set_main_option("path_separator", "os")
    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        if operacion == "upgrade":
            command.upgrade(configuracion, "002_metricas_hpc_nullable:head", sql=True)
        else:
            command.downgrade(configuracion, "head:002_metricas_hpc_nullable", sql=True)
    return salida.getvalue()


class InspectorFalso:
    def __init__(self, columnas, definiciones_indices=None, restricciones=()):
        self.columnas = set(columnas)
        self.definiciones_indices = dict(definiciones_indices or {})
        self.restricciones = set(restricciones)

    def get_columns(self, _tabla):
        return [{"name": nombre, "nullable": False} for nombre in self.columnas]

    def get_indexes(self, _tabla):
        return [
            {
                "name": nombre,
                "column_names": list(columnas),
                "unique": 1 if nombre.startswith("uq_") else 0,
                "dialect_options": (
                    {"sqlite_where": "estado IN ('queued', 'running')"}
                    if nombre.startswith("uq_")
                    else {}
                ),
            }
            for nombre, columnas in self.definiciones_indices.items()
        ]

    def get_check_constraints(self, _tabla):
        return [{"name": nombre} for nombre in self.restricciones]

    def get_pk_constraint(self, _tabla):
        return {"constrained_columns": ["job_id"]}

    def get_foreign_keys(self, _tabla):
        return [
            {
                "constrained_columns": ["simulacion_id"],
                "referred_table": "simulaciones",
                "options": {"ondelete": "CASCADE"},
            }
        ]


def test_modelo_simulation_job_expone_columnas_y_estados():
    columnas = set(SimulationJob.__table__.c.keys())
    esperadas = {
        "job_id",
        "simulacion_id",
        "estado",
        "pid",
        "pgid",
        "worker_id",
        "heartbeat_at",
        "lease_expires_at",
        "progress_percent",
        "current_day",
        "cancel_requested",
        "error_message",
        "started_at",
        "finished_at",
        "attempt",
        "created_at",
        "updated_at",
    }
    assert esperadas.issubset(columnas)
    assert "simulation_jobs" in Base.metadata.tables

    restriccion_estado = next(
        restriccion
        for restriccion in SimulationJob.__table__.constraints
        if restriccion.name == "chk_simulation_jobs_estado"
    )
    texto = str(restriccion_estado.sqltext)
    for estado in ("queued", "running", "completed", "failed", "canceled"):
        assert estado in texto


def test_crear_trabajo_establece_valores_iniciales_y_relacion(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-001")

    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)

    assert isinstance(trabajo.job_id, UUID)
    assert trabajo.simulacion_id == simulacion.id
    assert trabajo.estado == "queued"
    assert trabajo.progress_percent is None
    assert trabajo.current_day is None
    assert trabajo.cancel_requested is False
    assert trabajo.attempt == 1
    assert trabajo.worker_id is None
    assert trabajo.pid is None
    assert trabajo.pgid is None
    assert [item.job_id for item in simulacion.trabajos] == [trabajo.job_id]

    recuperado = SimulationRepository.obtener_trabajo(db_session, str(trabajo.job_id))
    assert recuperado is not None
    assert recuperado.job_id == trabajo.job_id


def test_crear_trabajo_rechaza_simulacion_inexistente(db_session: Session):
    with pytest.raises(ValueError, match="Simulación no encontrada"):
        SimulationRepository.crear_trabajo(db_session, "SIM-NO-EXISTE")


def test_reclamar_trabajo_es_unico_y_llena_lease(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-002")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)

    reclamado = SimulationRepository.reclamar_trabajo(
        db_session, trabajo.job_id, "worker-a", lease_seconds=90
    )

    assert reclamado is not None
    assert reclamado.estado == "running"
    assert reclamado.worker_id == "worker-a"
    assert reclamado.started_at is not None
    assert reclamado.heartbeat_at is not None
    assert reclamado.lease_expires_at is not None
    assert reclamado.lease_expires_at > reclamado.heartbeat_at
    assert reclamado.progress_percent is None
    assert reclamado.current_day is None

    segundo_intento = SimulationRepository.reclamar_trabajo(
        db_session, trabajo.job_id, "worker-b"
    )
    assert segundo_intento is None


def test_reclamar_trabajo_valida_parametros(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-003")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)

    with pytest.raises(ValueError, match="worker_id"):
        SimulationRepository.reclamar_trabajo(db_session, trabajo.job_id, "")
    with pytest.raises(ValueError, match="lease_seconds"):
        SimulationRepository.reclamar_trabajo(
            db_session, trabajo.job_id, "worker-a", lease_seconds=0
        )


def test_actualizar_estado_trabajo_registra_fin_y_limpia_lease(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-004")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)
    SimulationRepository.reclamar_trabajo(db_session, trabajo.job_id, "worker-a")

    finalizado = SimulationRepository.actualizar_estado_trabajo(
        db_session,
        trabajo.job_id,
        "completed",
        progress_percent=100,
        current_day=120,
    )

    assert finalizado is not None
    assert finalizado.estado == "completed"
    assert finalizado.progress_percent == 100
    assert finalizado.current_day == 120
    assert finalizado.finished_at is not None
    assert finalizado.lease_expires_at is None


def test_actualizar_estado_trabajo_valida_estado_y_progreso(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-005")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)

    with pytest.raises(ValueError, match="Estado de trabajo inválido"):
        SimulationRepository.actualizar_estado_trabajo(db_session, trabajo.job_id, "paused")
    with pytest.raises(ValueError, match="progress_percent"):
        SimulationRepository.actualizar_estado_trabajo(
            db_session, trabajo.job_id, "completed", progress_percent=101
        )


def test_registrar_heartbeat_renueva_lease_y_valida_worker(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-006")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)
    SimulationRepository.reclamar_trabajo(db_session, trabajo.job_id, "worker-a")
    lease_original = SimulationRepository.obtener_trabajo(db_session, trabajo.job_id).lease_expires_at

    actualizado = SimulationRepository.registrar_heartbeat(
        db_session, trabajo.job_id, "worker-a", lease_seconds=120
    )

    assert actualizado is not None
    assert actualizado.lease_expires_at > lease_original
    assert SimulationRepository.registrar_heartbeat(
        db_session, trabajo.job_id, "worker-b"
    ) is None


def test_registrar_heartbeat_no_modifica_trabajo_en_cola(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-007")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)

    assert (
        SimulationRepository.registrar_heartbeat(db_session, trabajo.job_id, "worker-a") is None
    )


def test_solicitar_cancelacion_es_idempotente_y_solo_para_estados_activos(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-008")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)

    cancelado = SimulationRepository.solicitar_cancelacion(db_session, trabajo.job_id)
    assert cancelado is not None
    assert cancelado.cancel_requested is True
    assert SimulationRepository.solicitar_cancelacion(db_session, trabajo.job_id).cancel_requested is True

    SimulationRepository.actualizar_estado_trabajo(db_session, trabajo.job_id, "canceled")
    assert SimulationRepository.solicitar_cancelacion(db_session, trabajo.job_id) is None


def test_listar_trabajos_pendientes_y_abandonados(db_session: Session):
    simulacion_1 = crear_simulacion(db_session, "SIM-JOB-009-A")
    simulacion_2 = crear_simulacion(db_session, "SIM-JOB-009-B")
    simulacion_3 = crear_simulacion(db_session, "SIM-JOB-009-C")

    pendiente_1 = SimulationRepository.crear_trabajo(db_session, simulacion_1.id)
    pendiente_2 = SimulationRepository.crear_trabajo(db_session, simulacion_2.id)
    abandonado = SimulationRepository.crear_trabajo(db_session, simulacion_3.id)
    SimulationRepository.reclamar_trabajo(db_session, abandonado.job_id, "worker-a")

    ahora = datetime.now(timezone.utc)
    db_session.execute(
        SimulationJob.__table__.update()
        .where(SimulationJob.job_id == abandonado.job_id)
        .values(lease_expires_at=ahora - timedelta(minutes=5))
    )
    db_session.commit()

    pendientes = SimulationRepository.listar_trabajos_pendientes(db_session)
    assert {item.job_id for item in pendientes} == {
        pendiente_1.job_id,
        pendiente_2.job_id,
    }

    abandonados = SimulationRepository.listar_trabajos_abandonados(db_session, ahora=ahora)
    assert [item.job_id for item in abandonados] == [abandonado.job_id]


def test_solo_un_trabajo_activo_por_simulacion(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-010")
    SimulationRepository.crear_trabajo(db_session, simulacion.id)

    with pytest.raises(RuntimeError, match="Error al crear trabajo"):
        SimulationRepository.crear_trabajo(db_session, simulacion.id)


def test_eliminar_simulacion_elimina_sus_trabajos(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-011")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)
    job_id = trabajo.job_id

    assert SimulationRepository.eliminar_simulacion(db_session, simulacion.id) is True
    assert SimulationRepository.obtener_trabajo(db_session, job_id) is None


def test_transiciones_permitidas_estan_definidas():
    assert transiciones_permitidas_desde("queued") == ("running", "failed", "canceled")
    assert transiciones_permitidas_desde("running") == ("completed", "failed", "canceled")
    for estado in ("completed", "failed", "canceled"):
        assert transiciones_permitidas_desde(estado) == ()
    assert set(TRANSICIONES_TRABAJO) == {
        "queued",
        "running",
        "completed",
        "failed",
        "canceled",
    }


def test_transiciones_invalidas_no_modifican_estado(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-012")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)
    SimulationRepository.reclamar_trabajo(db_session, trabajo.job_id, "worker-a")
    SimulationRepository.actualizar_estado_trabajo(db_session, trabajo.job_id, "completed")

    with pytest.raises(ValueError, match="Transición no permitida"):
        SimulationRepository.actualizar_estado_trabajo(db_session, trabajo.job_id, "running")
    with pytest.raises(ValueError, match="Transición no permitida"):
        SimulationRepository.actualizar_estado_trabajo(db_session, trabajo.job_id, "queued")
    assert SimulationRepository.obtener_trabajo(db_session, trabajo.job_id).estado == "completed"

    simulacion_inicial = crear_simulacion(db_session, "SIM-JOB-013")
    trabajo_inicial = SimulationRepository.crear_trabajo(db_session, simulacion_inicial.id)
    with pytest.raises(ValueError, match="Transición no permitida"):
        SimulationRepository.actualizar_estado_trabajo(
            db_session, trabajo_inicial.job_id, "completed"
        )
    assert SimulationRepository.obtener_trabajo(db_session, trabajo_inicial.job_id).estado == "queued"


def test_actualizacion_tardia_no_sobrescribe_estado_terminal(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-014")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)
    SimulationRepository.reclamar_trabajo(db_session, trabajo.job_id, "worker-a")
    SimulationRepository.actualizar_estado_trabajo(db_session, trabajo.job_id, "completed")

    tardio = SimulationRepository.actualizar_estado_trabajo(
        db_session,
        trabajo.job_id,
        "failed",
        estado_esperado="running",
        error_message="fallo tardío",
    )

    assert tardio is None
    trabajo_final = SimulationRepository.obtener_trabajo(db_session, trabajo.job_id)
    assert trabajo_final.estado == "completed"
    assert trabajo_final.error_message is None


def test_reclamacion_concurrente_solo_un_worker_gana(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-015")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)

    with Session(db_session.bind) as segunda_sesion:
        ganador = SimulationRepository.reclamar_trabajo(db_session, trabajo.job_id, "worker-a")
        perdedor = SimulationRepository.reclamar_trabajo(
            segunda_sesion, trabajo.job_id, "worker-b"
        )

    assert ganador is not None
    assert ganador.estado == "running"
    assert perdedor is None
    trabajo_final = SimulationRepository.obtener_trabajo(db_session, trabajo.job_id)
    assert trabajo_final.worker_id == "worker-a"


def test_reclamacion_rechaza_trabajo_con_cancelacion_solicitada(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-016")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)
    SimulationRepository.solicitar_cancelacion(db_session, trabajo.job_id)

    assert SimulationRepository.reclamar_trabajo(db_session, trabajo.job_id, "worker-a") is None


def test_cancelacion_impide_finalizacion_tardia(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-017")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)
    SimulationRepository.reclamar_trabajo(db_session, trabajo.job_id, "worker-a")
    SimulationRepository.solicitar_cancelacion(db_session, trabajo.job_id)

    assert (
        SimulationRepository.actualizar_estado_trabajo(
            db_session, trabajo.job_id, "completed"
        )
        is None
    )
    trabajo_pendiente = SimulationRepository.obtener_trabajo(db_session, trabajo.job_id)
    assert trabajo_pendiente.estado == "running"
    assert trabajo_pendiente.cancel_requested is True

    cancelado = SimulationRepository.actualizar_estado_trabajo(
        db_session, trabajo.job_id, "canceled"
    )
    assert cancelado is not None
    assert cancelado.estado == "canceled"


def test_solicitar_cancelacion_rechaza_estado_terminal(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-018")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)
    SimulationRepository.reclamar_trabajo(db_session, trabajo.job_id, "worker-a")
    SimulationRepository.actualizar_estado_trabajo(db_session, trabajo.job_id, "completed")

    assert SimulationRepository.solicitar_cancelacion(db_session, trabajo.job_id) is None
    assert (
        SimulationRepository.obtener_trabajo(db_session, trabajo.job_id).cancel_requested is False
    )


def test_heartbeat_de_worker_incorrecto_no_modifica_trabajo(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-019")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)
    SimulationRepository.reclamar_trabajo(db_session, trabajo.job_id, "worker-a")
    propio = SimulationRepository.registrar_heartbeat(
        db_session, trabajo.job_id, "worker-a", progress_percent=40, current_day=50
    )
    heartbeat_original = propio.heartbeat_at

    ajeno = SimulationRepository.registrar_heartbeat(
        db_session, trabajo.job_id, "worker-b", progress_percent=99, current_day=99
    )

    assert ajeno is None
    trabajo_final = SimulationRepository.obtener_trabajo(db_session, trabajo.job_id)
    assert trabajo_final.worker_id == "worker-a"
    assert trabajo_final.progress_percent == 40
    assert trabajo_final.current_day == 50
    assert trabajo_final.heartbeat_at == heartbeat_original


def test_heartbeat_no_permite_retroceso_de_progreso_ni_dia(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-020")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)
    SimulationRepository.reclamar_trabajo(db_session, trabajo.job_id, "worker-a")
    SimulationRepository.registrar_heartbeat(
        db_session, trabajo.job_id, "worker-a", progress_percent=60, current_day=90
    )

    atrasado = SimulationRepository.registrar_heartbeat(
        db_session, trabajo.job_id, "worker-a", progress_percent=50, current_day=80
    )

    assert atrasado is None
    trabajo_final = SimulationRepository.obtener_trabajo(db_session, trabajo.job_id)
    assert trabajo_final.progress_percent == 60
    assert trabajo_final.current_day == 90
    assert (
        SimulationRepository.registrar_heartbeat(
            db_session, trabajo.job_id, "worker-a", progress_percent=60, current_day=90
        )
        is not None
    )


def test_heartbeat_no_inventa_progreso(db_session: Session):
    simulacion = crear_simulacion(db_session, "SIM-JOB-021")
    trabajo = SimulationRepository.crear_trabajo(db_session, simulacion.id)
    SimulationRepository.reclamar_trabajo(db_session, trabajo.job_id, "worker-a")

    actualizado = SimulationRepository.registrar_heartbeat(
        db_session, trabajo.job_id, "worker-a"
    )

    assert actualizado is not None
    assert actualizado.progress_percent is None
    assert actualizado.current_day is None


def test_indices_del_modelo_coinciden_con_migracion_y_esquema_sqlite(db_session: Session):
    modulo = cargar_migracion_003()
    nombres_modelo = {indice.name for indice in SimulationJob.__table__.indexes}
    nombres_reales = {
        indice["name"] for indice in inspect(db_session.bind).get_indexes("simulation_jobs")
    }
    sql_upgrade = generar_sql_offline("upgrade")

    assert nombres_modelo == set(modulo.INDICES_ESPERADOS)
    assert nombres_reales == nombres_modelo
    for indice in SimulationJob.__table__.indexes:
        columnas = tuple(columna.name for columna in indice.columns)
        assert columnas == modulo.DEFINICIONES_INDICES[indice.name]
    for nombre in nombres_modelo:
        assert f"INDEX {nombre}" in sql_upgrade


def test_sql_offline_de_migracion_y_esquema():
    modulo = cargar_migracion_003()
    sql_upgrade = generar_sql_offline("upgrade")
    sql_downgrade = generar_sql_offline("downgrade")

    assert "CREATE TABLE simulation_jobs" in sql_upgrade
    for columna in modulo.COLUMNAS_ESPERADAS:
        assert re.search(rf"\b{columna}\b", sql_upgrade) is not None
    for restriccion in modulo.RESTRICCIONES_ESPERADAS:
        assert restriccion in sql_upgrade
    assert "CREATE UNIQUE INDEX uq_simulation_jobs_activa_por_simulacion" in sql_upgrade
    assert "WHERE estado IN ('queued', 'running')" in sql_upgrade

    assert "DROP TABLE simulation_jobs" in sql_downgrade
    for nombre in modulo.INDICES_ESPERADOS:
        assert f"DROP INDEX {nombre}" in sql_downgrade


def test_validacion_de_esquema_rechaza_esquema_incompleto():
    modulo = cargar_migracion_003()

    with pytest.raises(RuntimeError, match="faltan columnas.*lease_expires_at"):
        modulo.validar_esquema(
            InspectorFalso(
                modulo.COLUMNAS_ESPERADAS - {"lease_expires_at"},
                modulo.DEFINICIONES_INDICES,
                modulo.RESTRICCIONES_ESPERADAS,
            )
        )
    with pytest.raises(RuntimeError, match="faltan índices"):
        definiciones_incompletas = dict(modulo.DEFINICIONES_INDICES)
        definiciones_incompletas.pop("uq_simulation_jobs_activa_por_simulacion")
        modulo.validar_esquema(
            InspectorFalso(
                modulo.COLUMNAS_ESPERADAS,
                definiciones_incompletas,
                modulo.RESTRICCIONES_ESPERADAS,
            )
        )
    with pytest.raises(RuntimeError, match="faltan restricciones"):
        modulo.validar_esquema(
            InspectorFalso(
                modulo.COLUMNAS_ESPERADAS,
                modulo.DEFINICIONES_INDICES,
                modulo.RESTRICCIONES_ESPERADAS - {"chk_simulation_jobs_estado"},
            )
        )
    definiciones_incorrectas = dict(modulo.DEFINICIONES_INDICES)
    definiciones_incorrectas["idx_simulation_jobs_lease"] = ("estado",)
    with pytest.raises(RuntimeError, match="debe cubrir"):
        modulo.validar_esquema(
            InspectorFalso(
                modulo.COLUMNAS_ESPERADAS,
                definiciones_incorrectas,
                modulo.RESTRICCIONES_ESPERADAS,
            )
        )


def test_validacion_de_esquema_acepta_esquema_completo():
    modulo = cargar_migracion_003()
    modulo.validar_esquema(
        InspectorFalso(
            modulo.COLUMNAS_ESPERADAS,
            modulo.DEFINICIONES_INDICES,
            modulo.RESTRICCIONES_ESPERADAS,
        )
    )
