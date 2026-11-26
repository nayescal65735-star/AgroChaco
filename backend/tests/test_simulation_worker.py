"""Pruebas del worker independiente de ejecución de simulaciones."""

import json
import os
import signal
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import BigInteger, create_engine, event, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.workers.simulation_worker as modulo_worker
from app.db.repository import SimulationRepository
from app.models import Base, Parametro, Rendimiento, Resultado, Simulacion, SimulationJob
from app.services.motor_service import MotorService
from app.workers.simulation_worker import (
    MENSAJE_ERROR_MOTOR,
    MENSAJE_PERSISTENCIA,
    MENSAJE_SALIDA_INVALIDA,
    MENSAJE_TIMEOUT,
    SimulationWorker,
    detectar_trabajos_abandonados,
    main,
    validar_job_id,
)

CONFIG_BASE = {
    "engine": "secuencial",
    "simulationDays": 10,
    "soilType": "franco_arenoso",
    "initialMoisturePercent": 18.0,
    "gridConfig": {"rows": 2, "cols": 2, "cellSizeMeters": 50.0},
}

SALIDA_OK = {
    "status": "completed",
    "averageCWSI": 0.2,
    "timelineData": [
        {"cwsi": 0.3, "soilMoisture": 18.0},
        {"cwsi": 0.25, "soilMoisture": 17.0},
    ],
    "soilMoistureFinalPercent": 17.5,
    "waterDeficitMm": 12.5,
    "yieldLossPercent": 4.0,
    "executionTimeSeconds": 0.25,
    "progressPercent": 100,
    "currentDay": 10,
}

@compiles(BigInteger, "sqlite")
def _compilar_big_integer_sqlite(_tipo, _compilador, **_kwargs) -> str:
    return "INTEGER"


PLANTILLA_MOTOR = '''
import argparse
import json
import os
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--config")
parser.add_argument("--output")
parser.add_argument("--days", type=int)
parser.add_argument("--rows", type=int)
parser.add_argument("--cols", type=int)
parser.parse_args()

modo = os.environ.get("MOTOR_MODO", "ok")
if modo == "error":
    print("fallo interno con ruta /tmp/secreto", file=sys.stderr)
    raise SystemExit(7)

if modo == "hijo":
    hijo = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    with open(os.environ["MOTOR_PID_FILE"], "w", encoding="utf-8") as handle:
        handle.write(str(hijo.pid))
    time.sleep(float(os.environ.get("MOTOR_ESPERA", "5")))
    raise SystemExit(0)

if modo in ("sleep", "cancelable"):
    with open(parser.parse_args().output if False else SALIDA_ARG, "w", encoding="utf-8") as handle:
        json.dump({"status": "running", "progressPercent": 10, "currentDay": 1}, handle)
    time.sleep(float(os.environ.get("MOTOR_ESPERA", "5")))
    raise SystemExit(0)

with open(SALIDA_ARG, "w", encoding="utf-8") as handle:
    json.dump(SALIDA_CONTENIDO, handle)
print("motor simulado completado")
'''


@pytest.fixture()
def entorno(tmp_path: Path):
    ruta_db = tmp_path / "agrochaco.db"
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
    with fabrica() as sesion:
        yield sesion, fabrica, tmp_path
    engine.dispose()


def crear_motor_falso(tmp_path: Path) -> Path:
    script = tmp_path / "motor_falso.py"
    contenido = (
        "import sys\n"
        "SALIDA_ARG = None\n"
        "SALIDA_CONTENIDO = None\n"
        "sys.argv = sys.argv[:]\n"
        + PLANTILLA_MOTOR.replace("SALIDA_ARG = None", "")
        .replace("SALIDA_CONTENIDO = None", "")
        .replace("SALIDA_ARG", "argparse_output")
        .replace("SALIDA_CONTENIDO", "salida_contenido")
    )
    contenido = contenido.replace(
        "parser.parse_args()\n\nmodo",
        "args = parser.parse_args()\nargparse_output = args.output\n"
        "salida_contenido = " + json.dumps(SALIDA_OK) + "\n\nmodo",
    )
    script.write_text(contenido, encoding="utf-8")
    script.chmod(0o755)
    return script


def constructor_comando(script: Path):
    def construir(
        *,
        engine,
        executable_path,
        config_path,
        output_path,
        days,
        rows,
        cols,
        threads,
        processes,
    ) -> list[str]:
        return [
            sys.executable,
            str(script),
            "--config",
            str(config_path),
            "--days",
            str(days),
            "--rows",
            str(rows),
            "--cols",
            str(cols),
            "--output",
            str(output_path),
        ]

    return construir


def crear_worker(fabrica, tmp_path: Path, script: Path, **opciones) -> SimulationWorker:
    temporal = tmp_path / "temporales"
    temporal.mkdir(exist_ok=True)
    parametros = {
        "worker_id": "worker-test",
        "heartbeat_interval": 0.05,
        "poll_interval": 0.02,
        "lease_seconds": 60,
        "timeout_seconds": 2.0,
        "termination_grace_seconds": 0.05,
        "temp_dir": temporal,
        "results_root": tmp_path / "resultados",
        "command_builder": constructor_comando(script),
        "executable_resolver": lambda _engine: script,
    }
    parametros.update(opciones)
    return SimulationWorker(fabrica, **parametros)


def crear_trabajo(sesion, sim_id: str):
    simulacion = Simulacion(
        id=sim_id,
        nombre=f"Simulación {sim_id}",
        fuente_datos="campo",
        escenario="base",
        cantidad_escenarios=1,
        dias=10,
    )
    sesion.add(simulacion)
    sesion.flush()
    sesion.add(
        Parametro(
            simulacion_id=simulacion.id,
            agua_inicial=18.0,
            capacidad_suelo=120.0,
            umbral_hidrico=35.0,
            configuracion_json=CONFIG_BASE,
        )
    )
    sesion.commit()
    trabajo = SimulationRepository.crear_trabajo(sesion, simulacion.id)
    return simulacion, trabajo


def ruta_resultado(tmp_path: Path, sim_id: str) -> Path:
    return tmp_path / "resultados" / "results" / "simulations" / f"{sim_id}.json"


def temporales_restantes(tmp_path: Path) -> list[Path]:
    return list((tmp_path / "temporales").glob("agrochaco_worker_*"))


def temporales_publicacion_restantes(tmp_path: Path) -> list[Path]:
    directorio = tmp_path / "resultados" / "results" / "simulations"
    return list(directorio.glob(".*.tmp"))


def capturar_procesos(monkeypatch):
    procesos: list = []
    grupos: list[int | None] = []
    original = modulo_worker.subprocess.Popen

    def crear(*args, **kwargs):
        proc = original(*args, **kwargs)
        procesos.append(proc)
        try:
            grupos.append(os.getpgid(proc.pid))
        except OSError:
            grupos.append(None)
        return proc

    monkeypatch.setattr(modulo_worker.subprocess, "Popen", crear)
    return procesos, grupos


def grupo_activo(pgid: int | None) -> bool:
    if pgid is None:
        return False
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def proceso_activo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def esperar_proceso_muerto(pid: int, timeout: float = 2.0) -> bool:
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if not proceso_activo(pid):
            return True
        time.sleep(0.02)
    return not proceso_activo(pid)


def assert_procesos_terminados(procesos: list, grupos: list[int | None]) -> None:
    assert procesos
    for proc in procesos:
        assert proc.poll() is not None
    assert all(not grupo_activo(pgid) for pgid in grupos)


def contar_registros(sesion, modelo, sim_id: str) -> int:
    return len(
        sesion.execute(
            select(modelo).where(modelo.simulacion_id == sim_id)
        ).scalars().all()
    )


def test_ejecucion_completa_reclama_registra_pid_y_persiste_una_sola_vez(
    entorno, tmp_path: Path, monkeypatch
):
    sesion, fabrica, _ = entorno
    monkeypatch.setenv("MOTOR_MODO", "ok")
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-OK")
    worker = crear_worker(fabrica, tmp_path, script)

    finalizado = worker.run(trabajo.job_id)

    sesion.expire_all()
    actual = SimulationRepository.obtener_trabajo(sesion, trabajo.job_id)
    assert finalizado is not None
    assert actual.estado == "completed"
    assert actual.worker_id == "worker-test"
    assert actual.pid is not None and actual.pid > 0
    assert actual.pgid == actual.pid
    assert actual.heartbeat_at is not None
    assert actual.progress_percent == 100
    assert actual.finished_at is not None
    assert actual.error_message is None

    archivo = ruta_resultado(tmp_path, simulacion.id)
    assert archivo.exists()
    assert json.loads(archivo.read_text(encoding="utf-8"))["status"] == "completed"
    assert contar_registros(sesion, Resultado, simulacion.id) == 1
    assert contar_registros(sesion, Rendimiento, simulacion.id) == 1
    assert temporales_restantes(tmp_path) == []


def test_resultados_preexistentes_no_se_duplican(entorno, tmp_path: Path, monkeypatch):
    sesion, fabrica, _ = entorno
    monkeypatch.setenv("MOTOR_MODO", "ok")
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-DUP")

    MotorService.persistir_resultados_en_db(
        db=sesion,
        simulation_id=simulacion.id,
        config_dict=CONFIG_BASE,
        resultado_ejecucion={
            "engine": "secuencial",
            "output_data": SALIDA_OK,
            "archivo_detalle": "results/simulations/SIM-WORKER-DUP.json",
        },
    )
    sesion.expire_all()
    worker = crear_worker(fabrica, tmp_path, script)

    worker.run(trabajo.job_id)

    sesion.expire_all()
    assert contar_registros(sesion, Resultado, simulacion.id) == 1
    assert contar_registros(sesion, Rendimiento, simulacion.id) == 1
    assert SimulationRepository.obtener_trabajo(sesion, trabajo.job_id).estado == "completed"


def test_cancelacion_mata_el_grupo_y_no_persiste_resultado(
    entorno, tmp_path: Path, monkeypatch
):
    sesion, fabrica, _ = entorno
    monkeypatch.setenv("MOTOR_MODO", "cancelable")
    monkeypatch.setenv("MOTOR_ESPERA", "5")
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-CANCEL")
    worker = crear_worker(fabrica, tmp_path, script, timeout_seconds=6)

    hilo = threading.Thread(target=worker.run, args=(trabajo.job_id,))
    hilo.start()
    time.sleep(0.2)
    sesion.expire_all()
    solicitado = SimulationRepository.solicitar_cancelacion(sesion, trabajo.job_id)
    assert solicitado is not None
    time.sleep(0.12)
    sesion.expire_all()
    progreso = SimulationRepository.obtener_trabajo(sesion, trabajo.job_id)
    assert progreso.progress_percent == 10
    hilo.join(timeout=5)

    sesion.expire_all()
    final = SimulationRepository.obtener_trabajo(sesion, trabajo.job_id)
    assert not hilo.is_alive()
    assert final.estado == "canceled"
    assert final.cancel_requested is True
    assert final.error_message == "La ejecución fue cancelada por solicitud del usuario."
    assert not ruta_resultado(tmp_path, simulacion.id).exists()
    assert contar_registros(sesion, Resultado, simulacion.id) == 0
    assert temporales_restantes(tmp_path) == []

    try:
        os.killpg(final.pgid, 0)
    except ProcessLookupError:
        pass
    else:
        os.killpg(final.pgid, signal.SIGKILL)
        pytest.fail("Quedó un grupo de procesos vivo tras la cancelación")


def test_timeout_termina_el_proceso_y_no_marca_completado(
    entorno, tmp_path: Path, monkeypatch
):
    sesion, fabrica, _ = entorno
    monkeypatch.setenv("MOTOR_MODO", "sleep")
    monkeypatch.setenv("MOTOR_ESPERA", "5")
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-TIMEOUT")
    worker = crear_worker(fabrica, tmp_path, script, timeout_seconds=0.25)

    worker.run(trabajo.job_id)

    sesion.expire_all()
    final = SimulationRepository.obtener_trabajo(sesion, trabajo.job_id)
    assert final.estado == "failed"
    assert final.error_message == MENSAJE_TIMEOUT
    assert not ruta_resultado(tmp_path, simulacion.id).exists()
    assert contar_registros(sesion, Resultado, simulacion.id) == 0
    assert temporales_restantes(tmp_path) == []


def test_error_del_motor_expone_mensaje_generico_sin_trazas(
    entorno, tmp_path: Path, monkeypatch
):
    sesion, fabrica, _ = entorno
    monkeypatch.setenv("MOTOR_MODO", "error")
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-ERROR")
    worker = crear_worker(fabrica, tmp_path, script)

    worker.run(trabajo.job_id)

    sesion.expire_all()
    final = SimulationRepository.obtener_trabajo(sesion, trabajo.job_id)
    assert final.estado == "failed"
    assert final.error_message == MENSAJE_ERROR_MOTOR
    assert "Traceback" not in final.error_message
    assert "/tmp/secreto" not in final.error_message
    assert not ruta_resultado(tmp_path, simulacion.id).exists()
    assert temporales_restantes(tmp_path) == []


def test_salida_incompleta_no_se_publica(entorno, tmp_path: Path, monkeypatch):
    sesion, fabrica, _ = entorno
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-SALIDA")
    worker = crear_worker(fabrica, tmp_path, script, executable_resolver=lambda _: Path("no_importa"))

    def devolver_salida_incompleta(*args, **kwargs):
        return [
            sys.executable,
            "-c",
            "import sys; open(sys.argv[1], 'w').write('no es json')",
            kwargs["output_path"],
        ]

    worker.command_builder = devolver_salida_incompleta
    monkeypatch.delenv("MOTOR_MODO", raising=False)

    worker.run(trabajo.job_id)

    sesion.expire_all()
    final = SimulationRepository.obtener_trabajo(sesion, trabajo.job_id)
    assert final.estado == "failed"
    assert final.error_message == MENSAJE_SALIDA_INVALIDA
    assert not ruta_resultado(tmp_path, simulacion.id).exists()
    assert contar_registros(sesion, Resultado, simulacion.id) == 0


def test_worker_no_propietario_no_ejecuta_ni_cambia_estado(entorno, tmp_path: Path):
    sesion, fabrica, _ = entorno
    script = crear_motor_falso(tmp_path)
    _simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-OLD")
    reclamado = SimulationRepository.reclamar_trabajo(
        sesion, trabajo.job_id, "worker-viejo", lease_seconds=60
    )
    assert reclamado is not None

    llamadas = []

    def constructor_prohibido(**kwargs):
        llamadas.append(kwargs)
        return [sys.executable, "-c", "pass"]

    worker = crear_worker(
        fabrica,
        tmp_path,
        script,
        worker_id="worker-nuevo",
        command_builder=constructor_prohibido,
    )

    resultado = worker.run(trabajo.job_id)

    sesion.expire_all()
    actual = SimulationRepository.obtener_trabajo(sesion, trabajo.job_id)
    assert resultado is None
    assert llamadas == []
    assert actual.estado == "running"
    assert actual.worker_id == "worker-viejo"

    cambio = SimulationRepository.actualizar_estado_trabajo(
        sesion,
        trabajo.job_id,
        "completed",
        estado_esperado="running",
        worker_id="worker-nuevo",
    )
    assert cambio is None


def test_validar_job_id_rechaza_rutas_y_valores_arbitrarios():
    with pytest.raises(ValueError, match="inválido"):
        validar_job_id("../../etc/passwd")
    assert str(validar_job_id("d4d4f1d0-0b6d-4b8a-b8b3-5f4d5f0c9a11")) == (
        "d4d4f1d0-0b6d-4b8a-b8b3-5f4d5f0c9a11"
    )
    assert main(["ruta/no/permitida"]) == 2


def test_detectar_abandonados_solo_informa_y_no_reinicia(entorno):
    sesion, fabrica, _ = entorno
    _simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-ABANDONADO")
    SimulationRepository.reclamar_trabajo(
        sesion, trabajo.job_id, "worker-caido", lease_seconds=60
    )
    sesion.expire_all()
    actual = SimulationRepository.obtener_trabajo(sesion, trabajo.job_id)
    actual.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    sesion.commit()
    sesion.expire_all()

    encontrados = detectar_trabajos_abandonados(session_factory=fabrica)

    assert [item.job_id for item in encontrados] == [trabajo.job_id]
    sesion.expire_all()
    assert SimulationRepository.obtener_trabajo(sesion, trabajo.job_id).estado == "running"


def test_persistencia_fallida_no_deja_archivo_ni_estado_completado(
    entorno, tmp_path: Path, monkeypatch
):
    sesion, fabrica, _ = entorno
    monkeypatch.setenv("MOTOR_MODO", "ok")
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-PERSIST")

    def fallar_persistencia(**kwargs):
        raise RuntimeError("error interno de base de datos")

    worker = crear_worker(fabrica, tmp_path, script, result_persister=fallar_persistencia)

    worker.run(trabajo.job_id)

    sesion.expire_all()
    final = SimulationRepository.obtener_trabajo(sesion, trabajo.job_id)
    assert final.estado == "failed"
    assert final.error_message == MENSAJE_PERSISTENCIA
    assert not ruta_resultado(tmp_path, simulacion.id).exists()
    assert contar_registros(sesion, Resultado, simulacion.id) == 0


def test_error_registrar_pid_tras_popen_termina_grupo_y_limpia(
    entorno, tmp_path: Path, monkeypatch
):
    sesion, fabrica, _ = entorno
    monkeypatch.setenv("MOTOR_MODO", "sleep")
    monkeypatch.setenv("MOTOR_ESPERA", "5")
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-PID-FAIL")
    procesos, grupos = capturar_procesos(monkeypatch)

    def fallar_registro(*args, **kwargs):
        raise SQLAlchemyError("fallo al registrar pid/pgid")

    monkeypatch.setattr(SimulationRepository, "registrar_proceso_trabajo", fallar_registro)
    worker = crear_worker(fabrica, tmp_path, script, timeout_seconds=6)

    with pytest.raises(SQLAlchemyError):
        worker.run(trabajo.job_id)

    assert_procesos_terminados(procesos, grupos)
    assert not ruta_resultado(tmp_path, simulacion.id).exists()
    assert temporales_restantes(tmp_path) == []
    assert temporales_publicacion_restantes(tmp_path) == []


def test_error_sql_durante_heartbeat_termina_proceso_real(
    entorno, tmp_path: Path, monkeypatch
):
    sesion, fabrica, _ = entorno
    monkeypatch.setenv("MOTOR_MODO", "sleep")
    monkeypatch.setenv("MOTOR_ESPERA", "5")
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-HEARTBEAT-FAIL")
    procesos, grupos = capturar_procesos(monkeypatch)

    def fallar_heartbeat(*args, **kwargs):
        raise SQLAlchemyError("fallo al registrar heartbeat")

    monkeypatch.setattr(SimulationRepository, "registrar_heartbeat", fallar_heartbeat)
    worker = crear_worker(fabrica, tmp_path, script, timeout_seconds=6)

    with pytest.raises(SQLAlchemyError):
        worker.run(trabajo.job_id)

    assert_procesos_terminados(procesos, grupos)
    assert not ruta_resultado(tmp_path, simulacion.id).exists()
    assert temporales_restantes(tmp_path) == []
    assert temporales_publicacion_restantes(tmp_path) == []


def test_error_sql_durante_polling_termina_proceso_real(
    entorno, tmp_path: Path, monkeypatch
):
    sesion, fabrica, _ = entorno
    monkeypatch.setenv("MOTOR_MODO", "sleep")
    monkeypatch.setenv("MOTOR_ESPERA", "5")
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-POLL-FAIL")
    procesos, grupos = capturar_procesos(monkeypatch)
    original_obtener = SimulationRepository.obtener_trabajo
    original_registro = SimulationRepository.registrar_proceso_trabajo
    bandera = {"fallar": False}

    def obtener_con_fallo(db, job_id):
        if bandera["fallar"]:
            raise SQLAlchemyError("fallo durante polling")
        return original_obtener(db, job_id)

    def registrar_y_activar(*args, **kwargs):
        resultado = original_registro(*args, **kwargs)
        bandera["fallar"] = True
        return resultado

    monkeypatch.setattr(SimulationRepository, "obtener_trabajo", obtener_con_fallo)
    monkeypatch.setattr(SimulationRepository, "registrar_proceso_trabajo", registrar_y_activar)
    worker = crear_worker(fabrica, tmp_path, script, timeout_seconds=6)

    with pytest.raises(SQLAlchemyError):
        worker.run(trabajo.job_id)

    assert_procesos_terminados(procesos, grupos)
    assert not ruta_resultado(tmp_path, simulacion.id).exists()
    assert temporales_restantes(tmp_path) == []
    assert temporales_publicacion_restantes(tmp_path) == []


def test_proceso_hijo_real_no_queda_tras_cancelacion(
    entorno, tmp_path: Path, monkeypatch
):
    sesion, fabrica, _ = entorno
    archivo_pid = tmp_path / "hijo.pid"
    monkeypatch.setenv("MOTOR_MODO", "hijo")
    monkeypatch.setenv("MOTOR_ESPERA", "5")
    monkeypatch.setenv("MOTOR_PID_FILE", str(archivo_pid))
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-HIJO")
    worker = crear_worker(fabrica, tmp_path, script, timeout_seconds=6)

    hilo = threading.Thread(target=worker.run, args=(trabajo.job_id,))
    hilo.start()
    for _ in range(100):
        if archivo_pid.exists() and archivo_pid.read_text(encoding="utf-8").strip():
            break
        time.sleep(0.02)
    else:
        pytest.fail("El motor auxiliar no publicó el PID del hijo")

    pid_hijo = int(archivo_pid.read_text(encoding="utf-8").strip())
    assert proceso_activo(pid_hijo)
    sesion.expire_all()
    cancelado = SimulationRepository.solicitar_cancelacion(sesion, trabajo.job_id)
    assert cancelado is not None
    sesion.rollback()
    hilo.join(timeout=5)

    assert not hilo.is_alive()
    assert esperar_proceso_muerto(pid_hijo)
    sesion.expire_all()
    assert SimulationRepository.obtener_trabajo(sesion, trabajo.job_id).estado == "canceled"
    assert not ruta_resultado(tmp_path, simulacion.id).exists()
    assert temporales_restantes(tmp_path) == []
    assert temporales_publicacion_restantes(tmp_path) == []


def test_json_preexistente_valido_se_conserva_si_falla_persistencia(
    entorno, tmp_path: Path, monkeypatch
):
    sesion, fabrica, _ = entorno
    monkeypatch.setenv("MOTOR_MODO", "ok")
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-JSON-ANTERIOR")
    destino = ruta_resultado(tmp_path, simulacion.id)
    destino.parent.mkdir(parents=True, exist_ok=True)
    contenido_anterior = json.dumps({"status": "completed", "origen": "anterior"})
    destino.write_text(contenido_anterior, encoding="utf-8")

    def fallar_persistencia(**kwargs):
        raise RuntimeError("fallo de base de datos")

    worker = crear_worker(fabrica, tmp_path, script, result_persister=fallar_persistencia)

    worker.run(trabajo.job_id)

    sesion.expire_all()
    final = SimulationRepository.obtener_trabajo(sesion, trabajo.job_id)
    assert final.estado == "failed"
    assert final.error_message == MENSAJE_PERSISTENCIA
    assert destino.read_text(encoding="utf-8") == contenido_anterior
    assert contar_registros(sesion, Resultado, simulacion.id) == 0
    assert temporales_restantes(tmp_path) == []
    assert temporales_publicacion_restantes(tmp_path) == []


def test_cancelacion_durante_publicacion_no_marca_completed(
    entorno, tmp_path: Path, monkeypatch
):
    sesion, fabrica, _ = entorno
    monkeypatch.setenv("MOTOR_MODO", "ok")
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-CANCEL-RACE")
    job_uuid = trabajo.job_id
    original_tiene = SimulationRepository.tiene_resultados

    def tiene_y_cancela(db, simulacion_id):
        SimulationRepository.solicitar_cancelacion(db, job_uuid)
        return original_tiene(db, simulacion_id)

    monkeypatch.setattr(SimulationRepository, "tiene_resultados", tiene_y_cancela)
    worker = crear_worker(fabrica, tmp_path, script)

    worker.run(job_uuid)

    sesion.expire_all()
    final = SimulationRepository.obtener_trabajo(sesion, job_uuid)
    assert final.estado == "canceled"
    assert contar_registros(sesion, Resultado, simulacion.id) == 0
    assert not ruta_resultado(tmp_path, simulacion.id).exists()
    assert temporales_restantes(tmp_path) == []
    assert temporales_publicacion_restantes(tmp_path) == []


def test_perdida_propiedad_antes_de_publicar_evita_escribir_resultado(
    entorno, tmp_path: Path, monkeypatch
):
    sesion, fabrica, _ = entorno
    monkeypatch.setenv("MOTOR_MODO", "ok")
    script = crear_motor_falso(tmp_path)
    simulacion, trabajo = crear_trabajo(sesion, "SIM-WORKER-NO-OWNER")
    job_uuid = trabajo.job_id
    worker = crear_worker(fabrica, tmp_path, script)
    original_validar = worker._validar_salida

    def validar_y_perder(ruta, nombre_motor):
        datos = original_validar(ruta, nombre_motor)
        with fabrica() as sesion_cambio:
            objetivo = sesion_cambio.get(SimulationJob, job_uuid)
            objetivo.worker_id = "otro-worker"
            sesion_cambio.commit()
        original_obtener = SimulationRepository.obtener_trabajo

        def obtener_con_expiracion(db, id_trabajo):
            db.expire_all()
            return original_obtener(db, id_trabajo)

        monkeypatch.setattr(SimulationRepository, "obtener_trabajo", obtener_con_expiracion)
        return datos

    monkeypatch.setattr(worker, "_validar_salida", validar_y_perder)

    worker.run(job_uuid)

    sesion.expire_all()
    final = SimulationRepository.obtener_trabajo(sesion, job_uuid)
    assert final.estado == "running"
    assert final.worker_id == "otro-worker"
    assert contar_registros(sesion, Resultado, simulacion.id) == 0
    assert not ruta_resultado(tmp_path, simulacion.id).exists()
    assert temporales_restantes(tmp_path) == []
    assert temporales_publicacion_restantes(tmp_path) == []
