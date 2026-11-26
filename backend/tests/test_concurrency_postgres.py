from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys
from threading import Barrier
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, delete, func, select, text, update
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.repository import SimulationRepository
from app.models import Simulacion, SimulationJob

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "agrochaco_user"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "agrochaco"),
    )


@pytest.fixture(scope="module")
def engine():
    creado = create_engine(DATABASE_URL, pool_pre_ping=True)
    yield creado
    creado.dispose()


@pytest.fixture
def registros(engine):
    creados = []

    class Registros:
        @staticmethod
        def crear_simulacion(etiqueta):
            simulacion_id = f"SIM-CONC-{uuid4().hex[:12].upper()}"
            with Session(engine) as db:
                db.add(
                    Simulacion(
                        id=simulacion_id,
                        nombre=f"Concurrencia {etiqueta}",
                        fuente_datos="prueba-concurrencia",
                        escenario=etiqueta,
                        dias=30,
                    )
                )
                db.commit()
            creados.append(simulacion_id)
            return simulacion_id

    yield Registros()

    with Session(engine) as db:
        if creados:
            db.execute(delete(SimulationJob).where(SimulationJob.simulacion_id.in_(creados)))
            db.execute(delete(Simulacion).where(Simulacion.id.in_(creados)))
            db.commit()


def simultaneo(funciones):
    barrera = Barrier(len(funciones))

    def ejecutar(funcion):
        barrera.wait(timeout=15)
        return funcion()

    with ThreadPoolExecutor(max_workers=len(funciones)) as grupo:
        return [futuro.result() for futuro in [grupo.submit(ejecutar, funcion) for funcion in funciones]]


def crear_trabajo(engine, simulacion_id):
    with Session(engine) as db:
        trabajo = SimulationRepository.crear_trabajo(db, simulacion_id)
        return trabajo.job_id


def leer_trabajo(engine, job_id):
    with Session(engine) as db:
        db.rollback()
        return SimulationRepository.obtener_trabajo(db, job_id)


def test_reclamacion_simultanea_da_un_solo_propietario(engine, registros):
    simulacion_id = registros.crear_simulacion("claim")
    job_id = crear_trabajo(engine, simulacion_id)
    workers = [f"conc-claim-{indice}-{uuid4().hex[:6]}" for indice in range(6)]

    def reclamar(worker_id):
        with Session(engine) as db:
            return SimulationRepository.reclamar_trabajo(
                db,
                job_id,
                worker_id,
                lease_seconds=90,
                simulacion_id=simulacion_id,
            )

    resultados = simultaneo([lambda worker=worker: reclamar(worker) for worker in workers])
    ganadores = [resultado for resultado in resultados if resultado is not None]
    assert len(ganadores) == 1
    assert ganadores[0].estado == "running"
    assert ganadores[0].worker_id in workers

    final = leer_trabajo(engine, job_id)
    assert final.estado == "running"
    assert final.worker_id == ganadores[0].worker_id
    assert SimulationRepository._normalizar_fecha_utc(final.lease_expires_at) > datetime.now(timezone.utc)

    with Session(engine) as db:
        propietarios = db.execute(
            select(SimulationJob.worker_id).where(
                SimulationJob.job_id == job_id,
                SimulationJob.estado == "running",
                SimulationJob.worker_id.is_not(None),
            )
        ).scalars().all()
        assert propietarios == [final.worker_id]
        perdedor = next(worker for worker in workers if worker != final.worker_id)
        assert (
            SimulationRepository.registrar_heartbeat(
                db, job_id, perdedor, progress_percent=99
            )
            is None
        )


def test_no_existen_dos_trabajos_activos_para_la_misma_simulacion(engine, registros):
    simulacion_id = registros.crear_simulacion("activos")

    def crear_unico():
        with Session(engine) as db:
            return SimulationRepository.crear_trabajo_unico(db, simulacion_id)

    resultados = simultaneo([crear_unico for _ in range(4)])
    assert len([resultado for resultado in resultados if resultado is not None]) == 1

    with Session(engine) as db:
        activos = db.scalar(
            select(func.count())
            .select_from(SimulationJob)
            .where(
                SimulationJob.simulacion_id == simulacion_id,
                SimulationJob.estado.in_(("queued", "running")),
            )
        )
        assert activos == 1
        definicion = db.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname = 'uq_simulation_jobs_activa_por_simulacion'"
            )
        ).scalar_one()
        assert "CREATE UNIQUE INDEX" in definicion
        assert "queued" in definicion and "running" in definicion


def test_lease_vencido_recuperado_por_un_solo_worker(engine, registros):
    simulacion_id = registros.crear_simulacion("lease")
    job_id = crear_trabajo(engine, simulacion_id)
    worker_anterior = f"conc-lease-viejo-{uuid4().hex[:6]}"
    vencido = datetime.now(timezone.utc) - timedelta(seconds=5)

    with Session(engine) as db:
        assert (
            SimulationRepository.reclamar_trabajo(
                db, job_id, worker_anterior, lease_seconds=60
            )
            is not None
        )
        db.execute(
            update(SimulationJob)
            .where(SimulationJob.job_id == job_id)
            .values(lease_expires_at=vencido, heartbeat_at=vencido)
        )
        db.commit()

    nuevos = [f"conc-lease-nuevo-{indice}-{uuid4().hex[:6]}" for indice in range(2)]

    def recuperar(worker_id):
        with Session(engine) as db:
            return SimulationRepository.recuperar_trabajo_abandonado(
                db,
                job_id,
                worker_id,
                lease_seconds=90,
                worker_id_anterior=worker_anterior,
            )

    resultados = simultaneo([lambda worker=worker: recuperar(worker) for worker in nuevos])
    ganadores = [resultado for resultado in resultados if resultado is not None]
    assert len(ganadores) == 1
    assert ganadores[0].worker_id in nuevos

    final = leer_trabajo(engine, job_id)
    assert final.estado == "running"
    assert final.worker_id == ganadores[0].worker_id
    assert final.attempt == 2
    assert final.pid is None and final.pgid is None
    assert SimulationRepository._normalizar_fecha_utc(final.lease_expires_at) > datetime.now(timezone.utc)

    with Session(engine) as db:
        propietarios = db.execute(
            select(func.count())
            .select_from(SimulationJob)
            .where(
                SimulationJob.job_id == job_id,
                SimulationJob.estado == "running",
                SimulationJob.worker_id.is_not(None),
            )
        ).scalar_one()
        assert propietarios == 1
        assert (
            SimulationRepository.registrar_heartbeat(db, job_id, worker_anterior) is None
        )


def test_cancelacion_concurrente_mantiene_consistencia(engine, registros):
    for intento in range(8):
        simulacion_id = registros.crear_simulacion(f"cancel-{intento}")
        job_id = crear_trabajo(engine, simulacion_id)
        worker = f"conc-cancel-{uuid4().hex[:6]}"

        with Session(engine) as db:
            assert (
                SimulationRepository.reclamar_trabajo(
                    db, job_id, worker, lease_seconds=120
                )
                is not None
            )

        def finalizar():
            with Session(engine) as db:
                return SimulationRepository.actualizar_estado_trabajo(
                    db, job_id, "completed", worker_id=worker
                )

        def cancelar():
            with Session(engine) as db:
                return SimulationRepository.solicitar_cancelacion(db, job_id)

        finalizacion, cancelacion = simultaneo([finalizar, cancelar])
        final = leer_trabajo(engine, job_id)
        assert not (final.estado == "completed" and final.cancel_requested)
        assert final.worker_id == worker
        if final.estado == "completed":
            assert finalizacion is not None
            assert final.cancel_requested is False
        else:
            assert final.estado == "running"
            assert final.cancel_requested is True
            assert cancelacion is not None


def test_rollback_descarta_cambios_y_sesion_permanece_utilizable(engine, registros):
    simulacion_id = registros.crear_simulacion("rollback")
    job_id = crear_trabajo(engine, simulacion_id)

    with Session(engine) as db:
        db.execute(
            update(SimulationJob)
            .where(SimulationJob.job_id == job_id)
            .values(estado="running", worker_id="conc-rollback-temporal")
        )
        db.rollback()
        inicial = SimulationRepository.obtener_trabajo(db, job_id)
        assert inicial.estado == "queued"
        assert inicial.worker_id is None

        ganador = SimulationRepository.reclamar_trabajo(
            db, job_id, "conc-rollback-ganador", lease_seconds=60
        )
        assert ganador is not None
        perdedor = SimulationRepository.reclamar_trabajo(
            db, job_id, "conc-rollback-perdedor", lease_seconds=60
        )
        assert perdedor is None
        assert (
            SimulationRepository.obtener_trabajo(db, job_id).worker_id
            == "conc-rollback-ganador"
        )

        assert (
            SimulationRepository.verificar_propiedad_para_publicacion(
                db, job_id, "conc-rollback-ajeno"
            )
            is None
        )
        db.rollback()
        assert (
            SimulationRepository.obtener_trabajo(db, job_id).worker_id
            == "conc-rollback-ganador"
        )
