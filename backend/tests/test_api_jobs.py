from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, update
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.db.repository import SimulationRepository
from app.main import app
from app.models import Simulacion, SimulationJob
from app.services.motor_service import MotorService
from app.workers.simulation_worker import SimulationWorker, WorkerLoop


@pytest.fixture()
def contexto(tmp_path: Path):
    ruta_db = tmp_path / "jobs.db"
    engine = create_engine(
        f"sqlite:///{ruta_db}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def configurar_conexion(dbapi_connection, _registro):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        with fabrica() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, fabrica
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _payload(nombre: str = "Simulacion Asincrona") -> dict:
    return {
        "name": nombre,
        "zone": "yacuiba",
        "zoneName": "Yacuiba",
        "department": "Tarija",
        "soilType": "franco_arenoso",
        "cornVariety": "iniaf_h1",
        "plantingDate": "2026-11-20",
        "simulationDays": 30,
        "gridConfig": {"rows": 50, "cols": 50, "cellSizeMeters": 50},
        "initialMoisturePercent": 18.5,
        "droughtScenario": "moderado_ssp245",
        "engine": "secuencial",
        "openmpThreads": None,
        "mpiProcesses": None,
        "nodesCount": None,
    }


def _crear_simulacion(client: TestClient, nombre: str = "Simulacion Asincrona") -> str:
    respuesta = client.post("/api/simulations", json=_payload(nombre))
    assert respuesta.status_code == 201
    return respuesta.json()["id"]


def _encolar(client: TestClient, simulation_id: str):
    with patch.object(MotorService, "ejecutar", side_effect=AssertionError), patch.object(
        MotorService, "persistir_resultados_en_db", side_effect=AssertionError
    ):
        return client.post(f"/api/simulations/{simulation_id}/execute")


class WorkerFalso:
    def __init__(self, *, fallos: int = 0) -> None:
        self.worker_id = "worker-loop"
        self.fallos = fallos
        self.llamadas: list[UUID] = []
        self.recuperados: list[UUID] = []
        self.al_segundo_llamado = None

    def run(self, job_id):
        self.llamadas.append(job_id)
        if len(self.llamadas) <= self.fallos:
            raise RuntimeError("fallo inducido del worker")
        if len(self.llamadas) == self.fallos + 1 and self.al_segundo_llamado:
            self.al_segundo_llamado()
        return job_id

    def ejecutar_trabajo(self, trabajo):
        self.recuperados.append(trabajo.job_id)
        return trabajo.job_id


def test_execute_devuelve_202_y_encola_trabajo(contexto):
    client, fabrica = contexto
    simulation_id = _crear_simulacion(client)

    respuesta = _encolar(client, simulation_id)

    assert respuesta.status_code == 202
    datos = respuesta.json()
    assert datos["estado"] == "queued"
    assert datos["status"] == "queued"
    assert datos["simulation_id"] == simulation_id
    assert UUID(datos["job_id"])

    with fabrica() as db:
        db.rollback()
        trabajos = list(db.query(SimulationJob).all())
        assert len(trabajos) == 1
        assert trabajos[0].estado == "queued"
        assert trabajos[0].simulacion_id == simulation_id


def test_execute_simulacion_inexistente_devuelve_404(contexto):
    client, _ = contexto
    respuesta = _encolar(client, "SIM-INEXISTENTE-999")
    assert respuesta.status_code == 404


def test_execute_trabajo_duplicado_devuelve_409(contexto):
    client, fabrica = contexto
    simulation_id = _crear_simulacion(client)

    primera = _encolar(client, simulation_id)
    segunda = _encolar(client, simulation_id)

    assert primera.status_code == 202
    assert segunda.status_code == 409
    with fabrica() as db:
        db.rollback()
        assert db.query(SimulationJob).count() == 1


def test_api_no_ejecuta_subprocess_directamente(contexto):
    client, _ = contexto
    simulation_id = _crear_simulacion(client)

    with patch("subprocess.run", side_effect=AssertionError), patch(
        "subprocess.Popen", side_effect=AssertionError
    ), patch.object(MotorService, "ejecutar", side_effect=AssertionError):
        respuesta = client.post(f"/api/simulations/{simulation_id}/execute")

    assert respuesta.status_code == 202


def test_consultar_estado_devuelve_datos_persistidos(contexto):
    client, fabrica = contexto
    simulation_id = _crear_simulacion(client)
    job_id = _encolar(client, simulation_id).json()["job_id"]

    with fabrica() as db:
        db.rollback()
        assert SimulationRepository.reclamar_trabajo(
            db, job_id, "worker-a", lease_seconds=60
        ) is not None
        db.rollback()
        assert SimulationRepository.registrar_heartbeat(
            db,
            job_id,
            "worker-a",
            lease_seconds=60,
            progress_percent=42,
            current_day=7,
        ) is not None

    respuesta = client.get(f"/api/jobs/{job_id}")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["job_id"] == job_id
    assert datos["simulation_id"] == simulation_id
    assert datos["estado"] == "running"
    assert datos["status"] == "running"
    assert datos["progressPercent"] == 42
    assert datos["currentDay"] == 7
    assert datos["pid"] is None
    assert datos["createdAt"]
    assert datos["startedAt"]
    assert datos["updatedAt"]
    assert datos["finishedAt"] is None
    assert datos["error"] is None
    for campo in ("worker_id", "pgid", "lease_expires_at", "archivo", "ruta"):
        assert campo not in datos


def test_consultar_estado_trabajo_completado(contexto):
    client, fabrica = contexto
    simulation_id = _crear_simulacion(client)
    job_id = _encolar(client, simulation_id).json()["job_id"]

    with fabrica() as db:
        db.rollback()
        SimulationRepository.reclamar_trabajo(db, job_id, "worker-a", lease_seconds=60)
        db.rollback()
        SimulationRepository.actualizar_estado_trabajo(
            db,
            job_id,
            "completed",
            estado_esperado="running",
            worker_id="worker-a",
            progress_percent=100,
            current_day=30,
        )

    respuesta = client.get(f"/api/jobs/{job_id}")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "completed"
    assert datos["progressPercent"] == 100
    assert datos["currentDay"] == 30
    assert datos["finishedAt"]


def test_identificadores_invalidos_devuelven_400(contexto):
    client, _ = contexto

    assert client.get("/api/jobs/no-es-un-uuid").status_code == 400
    assert client.post("/api/jobs/no-es-un-uuid/cancel").status_code == 400
    assert _encolar(client, "SIM*INVAL!DO").status_code == 400


def test_execute_simulacion_en_ejecucion_devuelve_409(contexto):
    client, fabrica = contexto
    simulation_id = _crear_simulacion(client)

    with fabrica() as db:
        db.execute(
            update(Simulacion)
            .where(Simulacion.id == simulation_id)
            .values(estado="running")
        )
        db.commit()

    assert _encolar(client, simulation_id).status_code == 409


def test_cancelar_trabajo_pendiente(contexto):
    client, fabrica = contexto
    simulation_id = _crear_simulacion(client)
    job_id = _encolar(client, simulation_id).json()["job_id"]

    respuesta = client.post(f"/api/jobs/{job_id}/cancel")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "canceled"
    assert datos["cancelRequested"] is True
    assert datos["error"]

    with fabrica() as db:
        db.rollback()
        assert SimulationRepository.obtener_trabajo(db, job_id).estado == "canceled"
    assert client.get(f"/api/simulations/{simulation_id}").json()["status"] == "paused"


def test_cancelar_trabajo_en_ejecucion_respeta_estado_real(contexto):
    client, fabrica = contexto
    simulation_id = _crear_simulacion(client)
    job_id = _encolar(client, simulation_id).json()["job_id"]

    with fabrica() as db:
        db.rollback()
        SimulationRepository.reclamar_trabajo(db, job_id, "worker-a", lease_seconds=60)

    respuesta = client.post(f"/api/jobs/{job_id}/cancel")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "running"
    assert datos["cancelRequested"] is True
    assert client.get(f"/api/jobs/{job_id}").json()["estado"] == "running"


def test_cancelar_trabajo_terminal_devuelve_409(contexto):
    client, _ = contexto
    simulation_id = _crear_simulacion(client)
    job_id = _encolar(client, simulation_id).json()["job_id"]

    assert client.post(f"/api/jobs/{job_id}/cancel").status_code == 200
    segunda = client.post(f"/api/jobs/{job_id}/cancel")

    assert segunda.status_code == 409
    assert "cancelarse" in segunda.json()["detail"]


def test_worker_loop_recoge_trabajos_pendientes(contexto):
    client, fabrica = contexto
    simulation_id = _crear_simulacion(client)
    with fabrica() as db:
        trabajo = SimulationRepository.crear_trabajo(db, simulation_id)
        job_id = trabajo.job_id

    worker = WorkerFalso()
    bucle = WorkerLoop(fabrica, worker=worker, idle_wait_seconds=0)

    assert bucle.ejecutar_ciclo() == 1
    assert [str(item) for item in worker.llamadas] == [str(job_id)]


def test_worker_loop_no_se_detiene_por_error_del_worker(contexto):
    client, fabrica = contexto
    simulation_id = _crear_simulacion(client)
    with fabrica() as db:
        SimulationRepository.crear_trabajo(db, simulation_id)

    worker = WorkerFalso(fallos=1)
    bucle = WorkerLoop(fabrica, worker=worker, idle_wait_seconds=0)
    worker.al_segundo_llamado = bucle.detener
    hilo = threading.Thread(target=bucle.run)
    hilo.start()
    hilo.join(timeout=3)

    assert not hilo.is_alive()
    assert len(worker.llamadas) >= 2


def test_dos_workers_no_ejecutan_dos_veces_el_mismo_trabajo(contexto):
    client, fabrica = contexto
    simulation_id = _crear_simulacion(client)
    with fabrica() as db:
        trabajo = SimulationRepository.crear_trabajo(db, simulation_id)
        job_id = trabajo.job_id

    with patch(
        "app.workers.simulation_worker.SimulationWorker._procesar_trabajo",
        lambda self, db, trabajo: trabajo,
    ):
        primero = SimulationWorker(fabrica, worker_id="worker-1").run(job_id)
        segundo = SimulationWorker(fabrica, worker_id="worker-2").run(job_id)

    assert primero is not None
    assert segundo is None
    with fabrica() as db:
        db.rollback()
        final = SimulationRepository.obtener_trabajo(db, job_id)
        assert final.estado == "running"
        assert final.worker_id == "worker-1"


def test_worker_loop_recupera_trabajo_abandonado(contexto):
    client, fabrica = contexto
    simulation_id = _crear_simulacion(client)
    with fabrica() as db:
        trabajo = SimulationRepository.crear_trabajo(db, simulation_id)
        job_id = trabajo.job_id
        SimulationRepository.reclamar_trabajo(db, job_id, "worker-viejo", lease_seconds=60)
        vencido = datetime.now(timezone.utc) - timedelta(seconds=5)
        db.execute(
            update(SimulationJob)
            .where(SimulationJob.job_id == job_id)
            .values(lease_expires_at=vencido, heartbeat_at=vencido)
        )
        db.commit()

    worker = WorkerFalso()
    bucle = WorkerLoop(fabrica, worker=worker, idle_wait_seconds=0)

    assert bucle.ejecutar_ciclo() == 1
    assert [str(item) for item in worker.recuperados] == [str(job_id)]

    with fabrica() as db:
        db.rollback()
        final = SimulationRepository.obtener_trabajo(db, job_id)
        assert final.estado == "running"
        assert final.worker_id == "worker-loop"
        assert final.attempt == 2
        assert final.pid is None
        assert final.pgid is None
        lease_final = SimulationRepository._normalizar_fecha_utc(final.lease_expires_at)
        assert lease_final > datetime.now(timezone.utc)
