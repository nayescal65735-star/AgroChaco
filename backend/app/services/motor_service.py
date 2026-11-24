"""Servicio de ejecución y coordinación para los motores C++17 de AgroChaco.

Gestiona:
1. Resolución y validación estricta de rutas y ejecutables C++17.
2. Validación de seguridad en identificadores de simulación (prevención de Path Traversal).
3. Construcción del JSON de configuración a partir de PostgreSQL.
4. Creación y limpieza garantizada de archivos temporales de entrada y salida.
5. Construcción de argumentos CLI y ejecución mediante subprocess.run (sin shell=True).
6. Captura de métricas, validación de estado completed y guardado persistente en results/simulations/.
7. Persistencia transaccional atómica de métricas HPC y biofísicas en PostgreSQL mediante SimulationRepository.
"""

from decimal import Decimal
import json
import logging
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any
from sqlalchemy.orm import Session

from app.db.repository import SimulationRepository

logger = logging.getLogger("agrochaco.motor_service")

# Ruta raíz del proyecto AgroChaco (/home/.../AgroChaco)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _decimal_hpc_metric(raw_value: Any, *, is_efficiency: bool = False) -> Decimal | None:
    """Convierte una métrica HPC medida a Decimal, o None si no es medible.

    Los valores nulos, ausentes, no finitos o no positivos no son mediciones válidas.
    La eficiencia reportada como porcentaje (> 1) se normaliza a fracción decimal.
    """

    if raw_value is None:
        return None

    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value) or value <= 0.0:
        return None

    if is_efficiency and value > 1.0:
        value /= 100.0

    return Decimal(str(round(value, 4)))


class MotorServiceError(Exception):
    """Excepción base para errores del servicio del motor."""


class MotorNotFoundError(MotorServiceError):
    """El binario ejecutable del motor no existe o no tiene permisos de ejecución."""


class MotorTimeoutError(MotorServiceError):
    """La ejecución del motor excedió el tiempo límite configurado."""


class MotorExecutionError(MotorServiceError):
    """El proceso del motor retornó un código de error o stderr adverso."""


class MotorOutputError(MotorServiceError):
    """El archivo de resultados JSON no fue generado o es inválido."""


class MotorSecurityError(MotorServiceError):
    """Intento de evasión de seguridad o manipulación de rutas (Path Traversal)."""


class MotorService:
    """Coordinador de ejecución de los motores biofísicos paralelos en C++17."""

    EXECUTABLE_NAMES = {
        "secuencial": "agrochaco_secuencial",
        "openmp": "agrochaco_openmp",
        "mpi": "agrochaco_mpi",
        "hibrido": "agrochaco_hibrido",
    }

    @classmethod
    def resolver_raiz(cls) -> Path:
        """Retorna la ruta raíz canónica del proyecto AgroChaco."""
        return PROJECT_ROOT.resolve()

    @classmethod
    def validar_simulation_id(cls, simulation_id: str) -> str:
        """Valida que el identificador de simulación sea seguro y prevenga Path Traversal.

        Reglas:
        - No nulo ni vacío.
        - Longitud máxima de 64 caracteres.
        - Solo caracteres alfanuméricos, guiones y guiones bajos (^[a-zA-Z0-9_-]+$).
        - Rechazo estricto de secuencias '.', '/', '\\' o bytes nulos.
        """
        if not simulation_id or not isinstance(simulation_id, str):
            raise MotorSecurityError("El identificador de simulación no puede ser nulo ni vacío.")

        sim_id_clean = simulation_id.strip()

        if any(char in sim_id_clean for char in ("/", "\\", "\x00")) or ".." in sim_id_clean:
            raise MotorSecurityError(
                f"Secuencia de ruta no permitida en simulation_id: '{simulation_id}'"
            )

        if not re.match(r"^[a-zA-Z0-9_\-]{1,64}$", sim_id_clean):
            raise MotorSecurityError(
                f"El identificador '{simulation_id}' contiene caracteres no permitidos. "
                "Solo se permiten caracteres alfanuméricos, guiones (-) y guiones bajos (_)."
            )

        return sim_id_clean

    @classmethod
    def resolver_ejecutable(cls, engine: str) -> Path:
        """Resuelve y valida la existencia del binario C++ correspondiente a la modalidad."""
        nombre_binario = cls.EXECUTABLE_NAMES.get(engine)
        if not nombre_binario:
            raise ValueError(
                f"Modalidad de motor no reconocida: '{engine}'. "
                f"Permitidas: {list(cls.EXECUTABLE_NAMES.keys())}"
            )

        bin_dir = cls.resolver_raiz() / "motor" / "bin"
        executable_path = (bin_dir / nombre_binario).resolve()

        if not executable_path.is_file():
            raise MotorNotFoundError(
                f"No se encontró el ejecutable del motor '{engine}' en: {executable_path}. "
                "Asegúrate de haber compilado el proyecto con CMake."
            )

        if not os.access(executable_path, os.X_OK):
            raise MotorNotFoundError(
                f"El archivo '{executable_path}' existe pero no tiene permisos de ejecución."
            )

        return executable_path

    @classmethod
    def construir_configuracion_json(
        cls,
        simulation_id: str,
        config_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Construye el diccionario de configuración compatible con JsonSerializer::parseConfig."""
        sim_id_seguro = cls.validar_simulation_id(simulation_id)
        grid_config = config_dict.get("gridConfig") or {}
        rows = int(grid_config.get("rows", config_dict.get("rows", 100)))
        cols = int(grid_config.get("cols", config_dict.get("cols", 100)))
        cell_size = float(grid_config.get("cellSizeMeters", config_dict.get("cellSizeMeters", 50.0)))

        config_normalizada: dict[str, Any] = {
            "id": sim_id_seguro,
            "name": config_dict.get("name", f"Simulación {sim_id_seguro}"),
            "description": config_dict.get("description", "Ejecución generada desde AgroChaco API"),
            "zone": config_dict.get("zone", "yacuiba"),
            "zoneName": config_dict.get("zoneName", "Yacuiba"),
            "department": config_dict.get("department", "Tarija"),
            "soilType": config_dict.get("soilType", "franco_arenoso"),
            "cornVariety": config_dict.get("cornVariety", "iniaf_h1"),
            "plantingDate": str(config_dict.get("plantingDate", "2026-11-20")),
            "simulationDays": int(config_dict.get("simulationDays", 120)),
            "initialMoisturePercent": float(config_dict.get("initialMoisturePercent", 18.0)),
            "droughtScenario": config_dict.get("droughtScenario", "moderado_ssp245"),
            "engine": config_dict.get("engine", "secuencial"),
            "rows": rows,
            "cols": cols,
            "cellSizeMeters": cell_size,
            "gridConfig": {
                "rows": rows,
                "cols": cols,
                "cellSizeMeters": cell_size,
            },
        }

        if config_dict.get("openmpThreads") is not None:
            config_normalizada["openmpThreads"] = int(config_dict["openmpThreads"])
        if config_dict.get("mpiProcesses") is not None:
            config_normalizada["mpiProcesses"] = int(config_dict["mpiProcesses"])
        if config_dict.get("nodesCount") is not None:
            config_normalizada["nodesCount"] = int(config_dict["nodesCount"])

        return config_normalizada

    @classmethod
    def construir_comando_cli(
        cls,
        engine: str,
        executable_path: Path,
        config_path: Path,
        output_path: Path,
        days: int,
        rows: int,
        cols: int,
        threads: int | None = None,
        processes: int | None = None,
    ) -> list[str]:
        """Construye la lista de argumentos CLI para invocar el motor de forma segura sin shell=True."""
        base_args = [
            "--config", str(config_path),
            "--days", str(days),
            "--rows", str(rows),
            "--cols", str(cols),
            "--output", str(output_path),
        ]

        if engine == "secuencial":
            return [str(executable_path)] + base_args

        if engine == "openmp":
            hilos = threads or 2
            return [str(executable_path)] + base_args + ["--threads", str(hilos)]

        if engine == "mpi":
            procesos = processes or 2
            return [
                "mpirun",
                "--oversubscribe",
                "-np", str(procesos),
                str(executable_path),
            ] + base_args

        if engine == "hibrido":
            procesos = processes or 2
            hilos = threads or 2
            return [
                "mpirun",
                "--oversubscribe",
                "-np", str(procesos),
                str(executable_path),
            ] + base_args + ["--threads", str(hilos)]

        raise ValueError(f"Modalidad de motor no soportada: {engine}")

    @classmethod
    def ejecutar(
        cls,
        simulation_id: str,
        config_dict: dict[str, Any],
        timeout_seconds: int = 120,
    ) -> dict[str, Any]:
        """Ejecuta el motor C++17 en un subproceso aislado, valida el resultado y persiste el JSON detallado."""
        sim_id_seguro = cls.validar_simulation_id(simulation_id)
        engine = str(config_dict.get("engine", "secuencial")).lower()
        executable_path = cls.resolver_ejecutable(engine)
        config_data = cls.construir_configuracion_json(sim_id_seguro, config_dict)

        days = int(config_data["simulationDays"])
        rows = int(config_data["gridConfig"]["rows"])
        cols = int(config_data["gridConfig"]["cols"])
        threads = config_data.get("openmpThreads")
        processes = config_data.get("mpiProcesses")

        # Directorio destino canónico y comprobación contra Path Traversal
        dest_dir = (cls.resolver_raiz() / "results" / "simulations").resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        permanent_result_path = (dest_dir / f"{sim_id_seguro}.json").resolve()

        if not permanent_result_path.is_relative_to(dest_dir):
            raise MotorSecurityError(
                f"Violación de seguridad detectada: la ruta '{permanent_result_path}' escapa de '{dest_dir}'."
            )

        # Crear archivos temporales independientes para entrada y salida
        temp_cfg_fd, temp_cfg_path_str = tempfile.mkstemp(
            prefix=f"agrochaco_in_{sim_id_seguro}_", suffix=".json"
        )
        temp_out_fd, temp_out_path_str = tempfile.mkstemp(
            prefix=f"agrochaco_out_{sim_id_seguro}_", suffix=".json"
        )
        os.close(temp_cfg_fd)
        os.close(temp_out_fd)

        temp_cfg_path = Path(temp_cfg_path_str)
        temp_out_path = Path(temp_out_path_str)

        try:
            # 1. Escribir JSON de configuración
            with open(temp_cfg_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)

            # 2. Construir comando CLI
            cmd = cls.construir_comando_cli(
                engine=engine,
                executable_path=executable_path,
                config_path=temp_cfg_path,
                output_path=temp_out_path,
                days=days,
                rows=rows,
                cols=cols,
                threads=threads,
                processes=processes,
            )

            logger.info("Ejecutando motor AgroChaco: %s", " ".join(cmd))

            # 3. Invocar subproceso con timeout
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise MotorTimeoutError(
                    f"La simulación '{sim_id_seguro}' excedió el límite de tiempo de {timeout_seconds}s."
                ) from exc

            # 4. Validar returncode
            if proc.returncode != 0:
                stderr_msg = proc.stderr.strip() if proc.stderr else proc.stdout.strip()
                raise MotorExecutionError(
                    f"El ejecutable '{executable_path.name}' finalizó con código {proc.returncode}. "
                    f"Detalle: {stderr_msg}"
                )

            # 5. Leer y validar archivo de salida
            if not temp_out_path.exists() or temp_out_path.stat().st_size == 0:
                raise MotorOutputError(
                    f"El ejecutable '{executable_path.name}' finalizó con código 0 pero no produjo el archivo de salida JSON."
                )

            try:
                with open(temp_out_path, "r", encoding="utf-8") as f:
                    output_data = json.load(f)
            except json.JSONDecodeError as exc:
                raise MotorOutputError(
                    f"El archivo de salida producido por el motor no es un JSON válido: {exc}"
                ) from exc

            # 6. Comprobar que el resultado tenga status completed
            status = output_data.get("status")
            if status != "completed":
                raise MotorExecutionError(
                    f"El motor finalizó pero reportó estado '{status}' en lugar de 'completed'."
                )

            # 7. Conservar resultado permanente en results/simulations/{simulation_id}.json
            with open(permanent_result_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2)

            rel_archivo_detalle = f"results/simulations/{sim_id_seguro}.json"

            return {
                "simulation_id": sim_id_seguro,
                "engine": engine,
                "status": "completed",
                "output_data": output_data,
                "archivo_detalle": rel_archivo_detalle,
                "ruta_absoluta_detalle": str(permanent_result_path),
            }

        finally:
            # Limpieza garantizada de archivos temporales
            for p in (temp_cfg_path, temp_out_path):
                try:
                    if p.exists():
                        p.unlink()
                except OSError:
                    pass

    @classmethod
    def persistir_resultados_en_db(
        cls,
        db: Session,
        simulation_id: str,
        config_dict: dict[str, Any],
        resultado_ejecucion: dict[str, Any],
    ) -> None:
        """Persiste atómicamente métricas biofísicas, HPC, nuevo estado y evento en PostgreSQL.

        ========================================================================
        DOCUMENTACIÓN DE CORRESPONDENCIA SEMÁNTICA Y RESTRICCIONES DE MODELOS:
        ========================================================================
        1. averageCWSI: En el motor (motor/src/soil_model.cpp y README.md 2.1), este
           indicador representa el promedio estacional del Índice de Déficit Relativo
           de Evapotranspiración (RED / ETDI): 1 - (ETa / ETc). Es una magnitud
           adimensional acotada estrictamente en [0.0, 1.0].
           -> Se almacena en `Resultado.deficit_medio` (restringido a [0, 1]).

        2. timelineData[].cwsi: Fracción diaria de demanda insatisfecha [0.0, 1.0].
           -> El valor máximo observado en la serie temporal se almacena en
              `Resultado.deficit_maximo` (restringido a [0, 1]).

        3. waterDeficitMm: Déficit evapotranspirativo estacional acumulado en MILÍMETROS
           de columna de agua (mm). Magnitud física dimensional (20 a 400+ mm).
           -> NOTA CRÍTICA DE INTEGRIDAD: NO se guarda en deficit_medio ni deficit_maximo
              porque violaría la restricción CHECK de PostgreSQL (valores > 1.0).
              Se preserva íntegramente en el archivo JSON detallado (archivo_detalle)
              y se expone directamente en la respuesta del backend bajo 'waterDeficitMm'.

        4. soilMoistureFinalPercent: Porcentaje de humedad volumétrica del suelo (%)
           en el último día del ciclo.
           -> Se almacena en `Resultado.agua_final_media`.

        5. timelineData[].soilMoisture: Humedad volumétrica media diaria del suelo (%).
           -> El mínimo observado se almacena en `Resultado.agua_minima`.

        6. escenarios_con_deficit: En la guía original representaba escenarios Monte Carlo
           con estrés. En el motor espacial 2D, representa si la simulación experimentó
           déficit hídrico o pérdida de rendimiento (1 si hubo déficit, 0 si fue nulo).

        7. Rendimiento.eficiencia: Si el motor reporta porcentaje (> 1.0, ej. 100.0),
           se normaliza a fracción decimal (E <= 1.0) para mantener consistencia con
           las semillas de demostración (seeds.py) y la definición teórica E = S/p.
           Speedup y eficiencia nulos o no positivos se persisten como NULL: no son
           mediciones y no deben transformarse en 0.0.
        ========================================================================
        """
        sim_id_seguro = cls.validar_simulation_id(simulation_id)
        output_data = resultado_ejecucion["output_data"]
        archivo_detalle = resultado_ejecucion["archivo_detalle"]
        engine = resultado_ejecucion["engine"]

        # --- A. CÁLCULO DE MÉTRICAS BIOFÍSICAS NORMALIZADAS ---
        avg_cwsi = float(output_data.get("averageCWSI", 0.0))
        deficit_medio = Decimal(str(round(min(1.0, max(0.0, avg_cwsi)), 4)))

        timeline_data = output_data.get("timelineData") or []
        if timeline_data:
            max_daily_cwsi = max(float(pt.get("cwsi", 0.0)) for pt in timeline_data)
            min_daily_moist = min(float(pt.get("soilMoisture", 0.0)) for pt in timeline_data)
        else:
            max_daily_cwsi = avg_cwsi
            min_daily_moist = float(output_data.get("soilMoistureFinalPercent", 0.0))

        deficit_maximo = Decimal(str(round(min(1.0, max(0.0, max_daily_cwsi)), 4)))
        final_moist = float(output_data.get("soilMoistureFinalPercent", 0.0))
        agua_final_media = Decimal(str(round(final_moist, 2)))
        agua_minima = Decimal(str(round(min_daily_moist, 2)))

        water_def_mm = float(output_data.get("waterDeficitMm", 0.0))
        yield_loss = float(output_data.get("yieldLossPercent", 0.0))
        escenarios_con_deficit = 1 if (water_def_mm > 0.0 or avg_cwsi > 0.0 or yield_loss > 0.0) else 0

        datos_resultados = {
            "deficit_medio": deficit_medio,
            "deficit_maximo": deficit_maximo,
            "agua_final_media": agua_final_media,
            "agua_minima": agua_minima,
            "escenarios_con_deficit": escenarios_con_deficit,
            "archivo_detalle": archivo_detalle,
        }

        # --- B. CÁLCULO DE MÉTRICAS HPC ---
        tiempo_segundos = Decimal(
            str(round(float(output_data.get("executionTimeSeconds", 0.0)), 4))
        )

        speedup = _decimal_hpc_metric(output_data.get("speedup"))
        eficiencia = _decimal_hpc_metric(
            output_data.get("efficiency"), is_efficiency=True
        )

        hilos = 1
        procesos = 1
        if engine in ("openmp", "hibrido"):
            hilos = int(config_dict.get("openmpThreads") or 1)
        if engine in ("mpi", "hibrido"):
            procesos = int(config_dict.get("mpiProcesses") or 1)
        nodos = int(config_dict.get("nodesCount") or 1)

        datos_rendimiento = {
            "modalidad": engine,
            "hilos": hilos,
            "procesos": procesos,
            "nodos": nodos,
            "tiempo_segundos": tiempo_segundos,
            "speedup": speedup,
            "eficiencia": eficiencia,
            "repeticion": 1,
        }

        # --- C. PERSISTENCIA ATÓMICA EN UNA SOLA TRANSACCIÓN ---
        tiempo_str = str(tiempo_segundos)
        mensaje_evento = (
            f"Simulación '{sim_id_seguro}' completada exitosamente "
            f"por motor '{engine}' en {tiempo_str}s."
        )

        SimulationRepository.guardar_ejecucion_completa(
            db=db,
            simulacion_id=sim_id_seguro,
            datos_resultados=datos_resultados,
            datos_rendimiento=datos_rendimiento,
            nuevo_estado="completed",
            mensaje_evento=mensaje_evento,
        )
