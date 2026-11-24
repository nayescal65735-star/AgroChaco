"""Worker independiente de ejecución de simulaciones AgroChaco."""

from collections import deque
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.repository import SimulationRepository
from app.models import SimulationJob
from app.services.motor_service import (
    MotorExecutionError,
    MotorNotFoundError,
    MotorOutputError,
    MotorSecurityError,
    MotorService,
    MotorServiceError,
    MotorTimeoutError,
)

logger = logging.getLogger("agrochaco.simulation_worker")

SessionFactory = Callable[[], Session]
CommandBuilder = Callable[..., list[str]]
ExecutableResolver = Callable[[str], Path]
ResultPersister = Callable[..., None]

MENSAJE_TIMEOUT = "La simulación excedió el tiempo límite permitido."
MENSAJE_CANCELACION = "La ejecución fue cancelada por solicitud del usuario."
MENSAJE_ERROR_MOTOR = "El motor finalizó con un error durante la ejecución."
MENSAJE_SALIDA_INVALIDA = "El motor no produjo un resultado JSON válido y completo."
MENSAJE_PERSISTENCIA = "No se pudo persistir el resultado de la simulación."
MENSAJE_INICIO = "No se pudo iniciar el motor de simulación."
MENSAJE_CONFIGURACION = "No se pudo preparar la configuración de la simulación."
MENSAJE_INTERNO = "Se produjo un error interno durante la ejecución."

ESTADO_SIMULACION_POR_TRABAJO = {
    "completed": "completed",
    "failed": "failed",
    "canceled": "paused",
}


class _OwnershipLost(Exception):
    pass


class _ReferenciaTrabajo:
    def __init__(self, job_id: UUID) -> None:
        self.job_id = job_id


class _BoundedOutput:
    def __init__(self, stream: Any, *, line_limit: int, char_limit: int) -> None:
        self._stream = stream
        self._line_limit = line_limit
        self._char_limit = char_limit
        self._lines: deque[str] = deque(maxlen=line_limit)
        self._chars = 0
        self._truncated = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._leer, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def join(self, timeout: float = 2.0) -> None:
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            logger.debug("El lector de salida no finalizó dentro del tiempo esperado")

    def texto(self) -> str:
        with self._lock:
            return "\n".join(self._lines)

    @property
    def truncado(self) -> bool:
        with self._lock:
            return self._truncated

    def _leer(self) -> None:
        try:
            for linea in self._stream:
                with self._lock:
                    restante = self._char_limit - self._chars
                    if restante <= 0:
                        self._truncated = True
                        continue
                    guardada = linea[:restante]
                    self._chars += len(guardada)
                    self._lines.append(guardada.rstrip("\r\n"))
                    if len(guardada) < len(linea):
                        self._truncated = True
        except (OSError, ValueError):
            logger.debug("Se interrumpió la captura acotada de salida", exc_info=True)
        finally:
            try:
                self._stream.close()
            except OSError:
                pass


class _Publicacion:
    def __init__(
        self,
        destino: Path,
        contenido_anterior: bytes | None,
        identidad: tuple[int, int] | None,
    ) -> None:
        self.destino = destino
        self.contenido_anterior = contenido_anterior
        self.identidad = identidad

    def deshacer(self) -> None:
        if self.identidad is None:
            return
        try:
            actual = self.destino.stat()
        except FileNotFoundError:
            return
        except OSError:
            logger.warning("No se pudo comprobar el archivo %s al deshacer", self.destino, exc_info=True)
            return
        if (actual.st_dev, actual.st_ino) != self.identidad:
            logger.warning("El archivo %s fue reemplazado por otro publicador", self.destino)
            return
        if self.contenido_anterior is None:
            self._quitar()
            return
        try:
            _escribir_bytes_atomicos(self.contenido_anterior, self.destino)
        except OSError:
            logger.exception("No se pudo restaurar el contenido anterior de %s", self.destino)

    def _quitar(self) -> None:
        try:
            self.destino.unlink(missing_ok=True)
        except OSError:
            logger.warning("No se pudo retirar %s al deshacer", self.destino, exc_info=True)


def _escribir_bytes_atomicos(contenido: bytes, destino: Path) -> None:
    fd, nombre = tempfile.mkstemp(
        prefix=f".{destino.name}.",
        suffix=".tmp",
        dir=destino.parent,
    )
    temporal = Path(nombre)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(contenido)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporal, destino)
    except Exception:
        temporal.unlink(missing_ok=True)
        raise


class SimulationWorker:
    """Ejecuta un SimulationJob en un proceso aislado y persiste su resultado."""

    def __init__(
        self,
        session_factory: SessionFactory | None = None,
        *,
        worker_id: str | None = None,
        heartbeat_interval: float = 15.0,
        poll_interval: float = 0.5,
        lease_seconds: int = 60,
        timeout_seconds: float = 120.0,
        termination_grace_seconds: float = 5.0,
        output_line_limit: int = 100,
        output_char_limit: int = 65536,
        temp_dir: str | Path | None = None,
        results_root: Path | None = None,
        command_builder: CommandBuilder | None = None,
        executable_resolver: ExecutableResolver | None = None,
        result_persister: ResultPersister | None = None,
    ) -> None:
        if heartbeat_interval <= 0 or poll_interval <= 0 or timeout_seconds <= 0:
            raise ValueError("Los intervalos y el timeout deben ser mayores que 0")
        if lease_seconds <= 0 or termination_grace_seconds <= 0:
            raise ValueError("El lease y la gracia de terminación deben ser mayores que 0")
        if output_line_limit <= 0 or output_char_limit <= 0:
            raise ValueError("Los límites de salida deben ser mayores que 0")
        if temp_dir is not None and not Path(temp_dir).is_dir():
            raise ValueError("El directorio temporal debe existir")

        identificado = worker_id or f"{socket.gethostname()}:{os.getpid()}"
        self.worker_id = identificado[:64]
        self.session_factory = session_factory or SessionLocal
        self.heartbeat_interval = heartbeat_interval
        self.poll_interval = poll_interval
        self.lease_seconds = lease_seconds
        self.timeout_seconds = timeout_seconds
        self.termination_grace_seconds = termination_grace_seconds
        self.output_line_limit = output_line_limit
        self.output_char_limit = output_char_limit
        self.temp_dir = temp_dir
        self.results_root = results_root or MotorService.resolver_raiz()
        self.command_builder = command_builder or MotorService.construir_comando_cli
        self.executable_resolver = executable_resolver or MotorService.resolver_ejecutable
        self.result_persister = result_persister or MotorService.persistir_resultados_en_db

    def run(self, job_id: str | UUID) -> SimulationJob | None:
        job_uuid = validar_job_id(job_id)
        db = self.session_factory()
        try:
            trabajo = SimulationRepository.reclamar_trabajo(
                db,
                job_uuid,
                self.worker_id,
                lease_seconds=self.lease_seconds,
            )
            if trabajo is None:
                logger.info("El trabajo %s no estaba disponible para reclamación", job_uuid)
                return None
            return self._procesar_trabajo(db, trabajo)
        finally:
            db.close()

    def ejecutar_trabajo(self, trabajo: SimulationJob | None) -> SimulationJob | None:
        if trabajo is None:
            return None
        db = self.session_factory()
        try:
            actual = SimulationRepository.obtener_trabajo(db, trabajo.job_id)
            if (
                actual is None
                or actual.estado != "running"
                or actual.worker_id != self.worker_id
            ):
                return None
            return self._procesar_trabajo(db, actual)
        finally:
            db.close()

    def _procesar_trabajo(self, db: Session, trabajo: SimulationJob) -> SimulationJob | None:
        job_uuid = trabajo.job_id
        simulacion_id = trabajo.simulacion_id
        temp_cfg_path: Path | None = None
        temp_out_path: Path | None = None
        proc: subprocess.Popen | None = None
        pgid: int | None = None
        stdout: _BoundedOutput | None = None
        stderr: _BoundedOutput | None = None
        publicacion: _Publicacion | None = None

        try:
            try:
                sim_id = MotorService.validar_simulation_id(simulacion_id)
                config_dict = self._obtener_configuracion(db, simulacion_id)
                engine = str(config_dict.get("engine", "secuencial")).lower()
                executable_path = self.executable_resolver(engine)
                config_data = MotorService.construir_configuracion_json(sim_id, config_dict)
                dest_dir = (self.results_root / "results" / "simulations").resolve()
                permanent_path = (dest_dir / f"{sim_id}.json").resolve()
                if not permanent_path.is_relative_to(dest_dir):
                    raise MotorSecurityError("Ruta de resultado fuera del directorio permitido")
                dest_dir.mkdir(parents=True, exist_ok=True)
                days = int(config_data["simulationDays"])
                rows = int(config_data["gridConfig"]["rows"])
                cols = int(config_data["gridConfig"]["cols"])
            except (MotorServiceError, ValueError, KeyError, TypeError, OSError) as error:
                logger.exception("No se pudo preparar el trabajo %s", job_uuid)
                return self._finalizar(
                    db,
                    job_uuid,
                    "failed",
                    error_message=self._mensaje_publico(error, MENSAJE_CONFIGURACION),
                )

            temp_cfg_path = self._crear_temporal(sim_id, "in")
            temp_out_path = self._crear_temporal(sim_id, "out")
            with open(temp_cfg_path, "w", encoding="utf-8") as handle:
                json.dump(config_data, handle, indent=2)

            cmd = self.command_builder(
                engine=engine,
                executable_path=executable_path,
                config_path=temp_cfg_path,
                output_path=temp_out_path,
                days=days,
                rows=rows,
                cols=cols,
                threads=config_data.get("openmpThreads"),
                processes=config_data.get("mpiProcesses"),
            )
            logger.info("Worker %s ejecutando trabajo %s", self.worker_id, job_uuid)

            try:
                proc = subprocess.Popen(
                    cmd,
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    start_new_session=True,
                )
            except OSError:
                logger.exception("No se pudo iniciar el motor para el trabajo %s", job_uuid)
                return self._finalizar(
                    db,
                    job_uuid,
                    "failed",
                    error_message=MENSAJE_INICIO,
                )

            getpgid = getattr(os, "getpgid", None)
            try:
                pgid = getpgid(proc.pid) if getpgid is not None else proc.pid
            except OSError:
                pgid = proc.pid

            registrado = SimulationRepository.registrar_proceso_trabajo(
                db,
                job_uuid,
                self.worker_id,
                pid=proc.pid,
                pgid=pgid,
            )
            if registrado is None:
                logger.warning("Se perdió la propiedad del trabajo %s al registrar el proceso", job_uuid)
                self._terminar_grupo(proc, pgid)
                return None

            stdout = _BoundedOutput(
                proc.stdout,
                line_limit=self.output_line_limit,
                char_limit=self.output_char_limit,
            )
            stderr = _BoundedOutput(
                proc.stderr,
                line_limit=self.output_line_limit,
                char_limit=self.output_char_limit,
            )
            stdout.start()
            stderr.start()

            motivo, detalle = self._esperar_proceso(
                proc,
                pgid,
                db,
                job_uuid,
                temp_out_path,
            )
            stdout.join()
            stderr.join()

            if motivo == "sin_propietario":
                return None
            if motivo == "cancelado":
                return self._finalizar(
                    db,
                    job_uuid,
                    "canceled",
                    error_message=MENSAJE_CANCELACION,
                )
            if motivo == "timeout":
                logger.warning("Timeout del trabajo %s", job_uuid)
                return self._finalizar(
                    db,
                    job_uuid,
                    "failed",
                    error_message=MENSAJE_TIMEOUT,
                )
            if motivo == "error_proceso":
                logger.error(
                    "Motor finalizó con código %s en trabajo %s. stdout=%s stderr=%s",
                    detalle,
                    job_uuid,
                    stdout.texto(),
                    stderr.texto(),
                )
                return self._finalizar(
                    db,
                    job_uuid,
                    "failed",
                    error_message=MENSAJE_ERROR_MOTOR,
                )

            try:
                output_data = self._validar_salida(temp_out_path, executable_path.name)
            except (MotorServiceError, ValueError, OSError) as error:
                logger.exception("Salida inválida en trabajo %s", job_uuid)
                return self._finalizar(
                    db,
                    job_uuid,
                    "failed",
                    error_message=self._mensaje_publico(error, MENSAJE_SALIDA_INVALIDA),
                )

            def sigue_siendo_propietario() -> bool:
                actual = SimulationRepository.obtener_trabajo(db, job_uuid)
                return (
                    actual is not None
                    and actual.estado == "running"
                    and actual.worker_id == self.worker_id
                    and not actual.cancel_requested
                )

            try:
                publicacion = self._publicar_resultado(
                    output_data,
                    permanent_path,
                    job_uuid,
                    sigue_siendo_propietario,
                )
                if not sigue_siendo_propietario():
                    publicacion.deshacer()
                    return None

                ruta_relativa = f"results/simulations/{sim_id}.json"
                resultado_ejecucion = {
                    "simulation_id": sim_id,
                    "engine": engine,
                    "status": "completed",
                    "output_data": output_data,
                    "archivo_detalle": ruta_relativa,
                    "ruta_absoluta_detalle": str(permanent_path),
                }

                reservado = SimulationRepository.verificar_propiedad_para_publicacion(
                    db, job_uuid, self.worker_id
                )
                if reservado is None:
                    db.rollback()
                    publicacion.deshacer()
                    return self._finalizar_cancelada(db, job_uuid)

                if SimulationRepository.tiene_resultados(db, sim_id):
                    logger.info("La simulación %s ya tenía resultados; no se duplicarán", sim_id)
                else:
                    self.result_persister(
                        db=db,
                        simulation_id=sim_id,
                        config_dict=config_dict,
                        resultado_ejecucion=resultado_ejecucion,
                        commit=False,
                    )

                finalizado = SimulationRepository.actualizar_estado_trabajo(
                    db,
                    job_uuid,
                    "completed",
                    estado_esperado="running",
                    worker_id=self.worker_id,
                    progress_percent=100,
                    current_day=days,
                    commit=False,
                )
                if finalizado is None:
                    db.rollback()
                    publicacion.deshacer()
                    return self._finalizar_cancelada(db, job_uuid)

                SimulationRepository.actualizar_estado_simulacion(
                    db, sim_id, ESTADO_SIMULACION_POR_TRABAJO["completed"], commit=False
                )
                db.commit()
                return finalizado
            except _OwnershipLost:
                if publicacion is not None:
                    publicacion.deshacer()
                logger.warning("Se perdió la propiedad antes de publicar el resultado de %s", job_uuid)
                return None
            except Exception:
                db.rollback()
                if publicacion is not None:
                    publicacion.deshacer()
                logger.exception("Falló la publicación o persistencia del trabajo %s", job_uuid)
                return self._finalizar(
                    db,
                    job_uuid,
                    "failed",
                    error_message=MENSAJE_PERSISTENCIA,
                )
        finally:
            if proc is not None and pgid is not None:
                try:
                    self._asegurar_terminacion(proc, pgid)
                except Exception:
                    logger.exception("No se pudo garantizar la terminación del grupo %s", pgid)
            if stdout is not None:
                stdout.join()
            if stderr is not None:
                stderr.join()
            for ruta in (temp_cfg_path, temp_out_path):
                if ruta is not None:
                    try:
                        ruta.unlink(missing_ok=True)
                    except OSError:
                        logger.debug("No se pudo eliminar el temporal %s", ruta, exc_info=True)

    def _obtener_configuracion(self, db: Session, simulacion_id: str) -> dict[str, Any]:
        simulacion = SimulationRepository.obtener_por_id(db, simulacion_id, cargar_relaciones=True)
        if simulacion is None or simulacion.parametro is None:
            raise ValueError("Simulación o parámetros no disponibles")
        configuracion = simulacion.parametro.configuracion_json
        if not isinstance(configuracion, dict):
            raise ValueError("Configuración JSON inválida")
        return configuracion

    def _crear_temporal(self, sim_id: str, proposito: str) -> Path:
        fd, nombre = tempfile.mkstemp(
            prefix=f"agrochaco_worker_{sim_id}_{proposito}_",
            suffix=".json",
            dir=self.temp_dir,
        )
        os.close(fd)
        return Path(nombre)

    def _validar_salida(self, ruta: Path, nombre_motor: str) -> dict[str, Any]:
        if not ruta.exists() or ruta.stat().st_size == 0:
            raise MotorOutputError(f"El motor '{nombre_motor}' no generó el archivo de salida")
        try:
            with open(ruta, "r", encoding="utf-8") as handle:
                datos = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            raise MotorOutputError("El archivo de salida no es JSON válido") from error
        if not isinstance(datos, dict):
            raise MotorOutputError("El archivo de salida debe contener un objeto JSON")
        if datos.get("status") != "completed":
            raise MotorExecutionError("El motor no reportó el estado 'completed'")
        return datos

    def _escribir_json_atomico(
        self,
        datos: dict[str, Any],
        destino: Path,
        *,
        puede_reemplazar: Callable[[], bool] | None = None,
    ) -> None:
        fd, nombre = tempfile.mkstemp(
            prefix=f".{destino.name}.",
            suffix=".tmp",
            dir=destino.parent,
        )
        temporal = Path(nombre)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(datos, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            if puede_reemplazar is not None and not puede_reemplazar():
                raise _OwnershipLost()
            os.replace(temporal, destino)
        except Exception:
            temporal.unlink(missing_ok=True)
            raise

    def _publicar_resultado(
        self,
        datos: dict[str, Any],
        destino: Path,
        job_uuid: UUID,
        puede_reemplazar: Callable[[], bool],
    ) -> _Publicacion:
        contenido_anterior: bytes | None = None
        if destino.exists():
            contenido_anterior = destino.read_bytes()
            if self._es_json_completado(contenido_anterior):
                logger.info("Se conserva el JSON válido preexistente de %s", job_uuid)
                if not puede_reemplazar():
                    raise _OwnershipLost()
                return _Publicacion(destino, None, None)

        self._escribir_json_atomico(
            datos,
            destino,
            puede_reemplazar=puede_reemplazar,
        )
        estado = destino.stat()
        return _Publicacion(destino, contenido_anterior, (estado.st_dev, estado.st_ino))

    @staticmethod
    def _es_json_completado(contenido: bytes) -> bool:
        try:
            datos = json.loads(contenido.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        return isinstance(datos, dict) and datos.get("status") == "completed"

    def _asegurar_terminacion(self, proc: subprocess.Popen, pgid: int) -> None:
        if proc.poll() is not None and not self._grupo_activo(pgid):
            return
        logger.warning("Terminando el grupo %s desde la limpieza final", pgid)
        self._terminar_grupo(proc, pgid)

    def _finalizar_cancelada(self, db: Session, job_uuid: UUID) -> SimulationJob | None:
        return self._finalizar(
            db,
            job_uuid,
            "canceled",
            error_message=MENSAJE_CANCELACION,
        )

    def _esperar_proceso(
        self,
        proc: subprocess.Popen,
        pgid: int,
        db: Session,
        job_uuid: UUID,
        output_path: Path,
    ) -> tuple[str, str | None]:
        deadline = time.monotonic() + self.timeout_seconds
        ultimo_heartbeat = 0.0
        ultimo_poll = 0.0

        while True:
            ahora = time.monotonic()
            if ahora >= deadline:
                logger.warning("Timeout del proceso del trabajo %s", job_uuid)
                self._terminar_grupo(proc, pgid)
                return "timeout", None

            codigo = proc.poll()
            if codigo is not None:
                self._limpiar_grupo_huerfano(pgid)
                if codigo == 0:
                    return "completado", None
                return "error_proceso", str(codigo)

            if ahora - ultimo_poll >= self.poll_interval:
                ultimo_poll = ahora
                db.rollback()
                trabajo = SimulationRepository.obtener_trabajo(db, job_uuid)
                if (
                    trabajo is None
                    or trabajo.estado != "running"
                    or trabajo.worker_id != self.worker_id
                ):
                    logger.warning("El trabajo %s cambió de propietario o de estado", job_uuid)
                    self._terminar_grupo(proc, pgid)
                    return "sin_propietario", None
                if trabajo.cancel_requested:
                    logger.info("Cancelación solicitada para el trabajo %s", job_uuid)
                    self._terminar_grupo(proc, pgid)
                    return "cancelado", None

            if ahora - ultimo_heartbeat >= self.heartbeat_interval:
                ultimo_heartbeat = ahora
                progreso, dia = self._leer_progreso(output_path)
                latido = SimulationRepository.registrar_heartbeat(
                    db,
                    job_uuid,
                    self.worker_id,
                    lease_seconds=self.lease_seconds,
                    progress_percent=progreso,
                    current_day=dia,
                )
                if latido is None:
                    logger.warning("No se pudo renovar el lease del trabajo %s", job_uuid)
                    self._terminar_grupo(proc, pgid)
                    return "sin_propietario", None
                if progreso is not None:
                    logger.debug("Progreso del trabajo %s: %s%%", job_uuid, progreso)

            restante = max(0.01, deadline - time.monotonic())
            time.sleep(min(self.poll_interval, restante))

    def _leer_progreso(self, ruta: Path) -> tuple[int | None, int | None]:
        try:
            with open(ruta, "r", encoding="utf-8") as handle:
                datos = json.load(handle)
        except (OSError, ValueError):
            return None, None
        if not isinstance(datos, dict):
            return None, None

        progreso: int | None = None
        dia: int | None = None
        try:
            if datos.get("progressPercent") is not None:
                progreso = max(0, min(100, int(datos["progressPercent"])))
            if datos.get("currentDay") is not None:
                dia = max(0, int(datos["currentDay"]))
        except (TypeError, ValueError):
            return None, None
        return progreso, dia

    def _senal_grupo(self, pgid: int, senal: int) -> None:
        try:
            os.killpg(pgid, senal)
        except ProcessLookupError:
            pass
        except OSError:
            logger.warning("No se pudo enviar la señal %s al grupo %s", senal, pgid, exc_info=True)

    def _grupo_activo(self, pgid: int) -> bool:
        try:
            os.killpg(pgid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            logger.debug("No se pudo comprobar el grupo de procesos %s", pgid, exc_info=True)
            return False

    def _limpiar_grupo_huerfano(self, pgid: int) -> None:
        if self._grupo_activo(pgid):
            logger.warning("Se detectaron procesos huérfanos en el grupo %s", pgid)
            self._senal_grupo(pgid, signal.SIGKILL)

    def _terminar_grupo(self, proc: subprocess.Popen, pgid: int) -> None:
        self._senal_grupo(pgid, signal.SIGTERM)
        try:
            proc.wait(timeout=self.termination_grace_seconds)
        except subprocess.TimeoutExpired:
            logger.warning("El grupo %s no respondió a SIGTERM; se envía SIGKILL", pgid)
            self._senal_grupo(pgid, signal.SIGKILL)
            try:
                proc.wait(timeout=self.termination_grace_seconds)
            except subprocess.TimeoutExpired:
                logger.error("El proceso principal del grupo %s no pudo ser reaped", pgid)

        if self._grupo_activo(pgid):
            logger.warning("Quedan procesos vivos en el grupo %s tras la terminación", pgid)
            self._senal_grupo(pgid, signal.SIGKILL)

    def _finalizar(
        self,
        db: Session,
        job_uuid: UUID,
        estado: str,
        *,
        error_message: str | None = None,
        progress_percent: int | None = None,
        current_day: int | None = None,
    ) -> SimulationJob | None:
        db.rollback()
        if estado in ("failed", "completed"):
            actual = SimulationRepository.obtener_trabajo(db, job_uuid)
            if actual is not None and actual.cancel_requested:
                estado = "canceled"
                error_message = MENSAJE_CANCELACION
        try:
            finalizado = SimulationRepository.actualizar_estado_trabajo(
                db,
                job_uuid,
                estado,
                estado_esperado="running",
                worker_id=self.worker_id,
                error_message=error_message,
                progress_percent=progress_percent,
                current_day=current_day,
                commit=False,
            )
            if finalizado is not None:
                SimulationRepository.actualizar_estado_simulacion(
                    db,
                    finalizado.simulacion_id,
                    ESTADO_SIMULACION_POR_TRABAJO[estado],
                    commit=False,
                )
                db.commit()
            else:
                db.rollback()
            return finalizado
        except ValueError:
            db.rollback()
            logger.info("El trabajo %s ya no estaba en un estado finalizable", job_uuid)
            return None
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _mensaje_publico(error: Exception, alternativa: str) -> str:
        if isinstance(error, MotorTimeoutError):
            return MENSAJE_TIMEOUT
        if isinstance(error, MotorSecurityError):
            return "La solicitud contiene parámetros no permitidos."
        if isinstance(error, MotorNotFoundError):
            return "No se encontró el motor solicitado."
        if isinstance(error, MotorOutputError):
            return MENSAJE_SALIDA_INVALIDA
        if isinstance(error, MotorExecutionError):
            return MENSAJE_ERROR_MOTOR
        if isinstance(error, MotorServiceError):
            return alternativa
        return alternativa


def validar_job_id(job_id: str | UUID) -> UUID:
    """Valida el job_id sin aceptar rutas ni valores arbitrarios del exterior."""
    if isinstance(job_id, UUID):
        return job_id
    try:
        return UUID(str(job_id))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("Identificador de trabajo inválido.") from None


def detectar_trabajos_abandonados(
    *,
    ahora: datetime | None = None,
    limit: int = 50,
    session_factory: SessionFactory | None = None,
) -> list[SimulationJob]:
    """Devuelve trabajos con lease vencido; no los reinicia ni agenda nada."""
    factory = session_factory or SessionLocal
    db = factory()
    try:
        return SimulationRepository.listar_trabajos_abandonados(db, ahora=ahora, limit=limit)
    finally:
        db.close()


class WorkerLoop:
    def __init__(
        self,
        session_factory: SessionFactory | None = None,
        *,
        worker: Any | None = None,
        worker_id: str | None = None,
        idle_wait_seconds: float = 2.0,
        batch_size: int = 10,
        lease_seconds: int = 60,
        **opciones: Any,
    ) -> None:
        if idle_wait_seconds < 0 or batch_size <= 0 or lease_seconds <= 0:
            raise ValueError("Los parámetros del bucle del worker no son válidos")
        self.session_factory = session_factory or SessionLocal
        self.worker = worker or SimulationWorker(
            session_factory=self.session_factory,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            **opciones,
        )
        self.idle_wait_seconds = idle_wait_seconds
        self.batch_size = batch_size
        self.lease_seconds = lease_seconds
        self._stop = threading.Event()
        self._senales: list[tuple[int, Any]] = []

    def detener(self) -> None:
        self._stop.set()

    def _instalar_senales(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return
        for senal in (signal.SIGTERM, signal.SIGINT):
            anterior = signal.getsignal(senal)
            signal.signal(senal, lambda _numero, _marco: self.detener())
            self._senales.append((senal, anterior))

    def _restaurar_senales(self) -> None:
        for senal, anterior in reversed(self._senales):
            signal.signal(senal, anterior)
        self._senales.clear()

    def ejecutar_ciclo(self) -> int:
        db = self.session_factory()
        procesados = 0
        try:
            db.rollback()
            abandonados = [
                (trabajo.job_id, trabajo.worker_id)
                for trabajo in SimulationRepository.listar_trabajos_abandonados(
                    db, limit=self.batch_size
                )
            ]
            db.rollback()

            for job_id, worker_anterior in abandonados:
                if self._stop.is_set():
                    break
                try:
                    recuperado = SimulationRepository.recuperar_trabajo_abandonado(
                        db,
                        job_id,
                        self.worker.worker_id,
                        lease_seconds=self.lease_seconds,
                        worker_id_anterior=worker_anterior,
                    )
                except Exception:
                    logger.exception("No se pudo recuperar el trabajo abandonado %s", job_id)
                    db.rollback()
                    continue
                if recuperado is None:
                    db.rollback()
                    continue
                job_recuperado = recuperado.job_id
                db.rollback()
                try:
                    resultado = self.worker.ejecutar_trabajo(
                        _ReferenciaTrabajo(job_recuperado)
                    )
                except Exception:
                    logger.exception("Falló la ejecución recuperada de %s", job_recuperado)
                    continue
                if resultado is not None:
                    procesados += 1
                db.rollback()

            db.rollback()
            pendientes = [
                trabajo.job_id
                for trabajo in SimulationRepository.listar_trabajos_pendientes(
                    db, limit=self.batch_size
                )
            ]
            db.rollback()

            for job_id in pendientes:
                if self._stop.is_set():
                    break
                db.rollback()
                try:
                    resultado = self.worker.run(job_id)
                except Exception:
                    logger.exception("Falló la ejecución del trabajo %s", job_id)
                    continue
                if resultado is not None:
                    procesados += 1

            return procesados
        finally:
            db.close()

    def run(self) -> None:
        self._instalar_senales()
        try:
            while not self._stop.is_set():
                try:
                    procesados = self.ejecutar_ciclo()
                except Exception:
                    logger.exception("Error en el ciclo del worker; se reintentará")
                    procesados = 0
                if procesados == 0 and not self._stop.is_set():
                    self._stop.wait(self.idle_wait_seconds)
        finally:
            self._restaurar_senales()


def main(argv: list[str] | None = None) -> int:
    argumentos = sys.argv[1:] if argv is None else list(argv)
    modo_bucle = bool(argumentos) and argumentos[0] in ("--loop", "-l")

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if modo_bucle:
        espera = float(os.getenv("WORKER_IDLE_WAIT_SECONDS", "2"))
        if len(argumentos) > 1:
            if len(argumentos) != 3 or argumentos[1] != "--idle-wait":
                print(
                    "Uso: python -m app.workers.simulation_worker --loop [--idle-wait SEGUNDOS]",
                    file=sys.stderr,
                )
                return 2
            try:
                espera = float(argumentos[2])
            except ValueError:
                print("El espera indicado no es válido.", file=sys.stderr)
                return 2
        try:
            WorkerLoop(idle_wait_seconds=espera).run()
            return 0
        except Exception:
            logger.exception("Error no controlado del bucle del worker")
            print(MENSAJE_INTERNO, file=sys.stderr)
            return 1

    if len(argumentos) != 1:
        print(
            "Uso: python -m app.workers.simulation_worker <job_id> | --loop [--idle-wait SEGUNDOS]",
            file=sys.stderr,
        )
        return 2

    try:
        job_uuid = validar_job_id(argumentos[0])
    except ValueError:
        print("Identificador de trabajo inválido.", file=sys.stderr)
        return 2

    try:
        SimulationWorker().run(job_uuid)
        return 0
    except Exception:
        logger.exception("Error no controlado del worker para el trabajo %s", job_uuid)
        print(MENSAJE_INTERNO, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
