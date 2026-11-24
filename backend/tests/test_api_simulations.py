"""Suite exhaustiva de pruebas unitarias y de integración para AgroChaco.

Verifica:
1. Creación de una simulación y persistencia real en PostgreSQL (tablas simulaciones y parametros).
2. Compatibilidad del formato de respuesta con la interfaz esperada por React.
3. Listado de simulaciones desde PostgreSQL.
4. Consulta individual por ID con precarga de relaciones y detalle.
5. Eliminación de simulación con borrado en cascada en PostgreSQL.
6. Manejo de error HTTP 404 ante registros inexistentes.
7. Manejo de error de validación ante esquemas inválidos (Pydantic).
8. Selección y resolución de los cuatro motores C++17 (secuencial, openmp, mpi, hibrido).
9. Construcción rigurosa de argumentos CLI (sin shell=True).
10. Generación de configuración JSON para el motor.
11. Manejo de timeout configurable en subprocesos.
12. Manejo de error de ejecución del binario (código != 0 y stderr).
13. Manejo de JSON de salida ausente o inválido.
14. Concurrencia atómica: rechazo con HTTP 409 Conflict si la simulación ya está running.
15. Persistencia atómica de resultados y transición a estado 'completed'.
16. Persistencia fallida y rollback atómico completo (sin persistencia parcial).
17. Semántica de métricas biofísicas, normalización y respeto estricto de límites CHECK.
18. Seguridad: validación de simulation_id y mitigación de Path Traversal.
19. Integración real de punta a punta ejecutando el binario físico agrochaco_secuencial.
20. Speedup y eficiencia no disponibles se persisten y exponen como NULL.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker

# Asegurar path para imports
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    user = os.getenv("POSTGRES_USER", "agrochaco_user")
    pwd = os.getenv("POSTGRES_PASSWORD", "AgroChaco_2026_Seguro")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "agrochaco")
    DATABASE_URL = f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}"

from app.api.simulations import (
    GridConfig,
    SimulationCreate,
    create_simulation,
    delete_simulation,
    execute_simulation,
    get_simulation,
    list_simulations,
)
from app.models import EventoEjecucion, Parametro, Rendimiento, Resultado, Simulacion
from app.db.repository import SimulationRepository
from app.services.motor_service import (
    MotorExecutionError,
    MotorNotFoundError,
    MotorOutputError,
    MotorSecurityError,
    MotorService,
    MotorTimeoutError,
)


class TestApiSimulationsPostgres(unittest.TestCase):
    """Suite de pruebas para validar los endpoints de simulaciones y el motor C++17."""

    @classmethod
    def setUpClass(cls):
        """Inicializa la conexión con la base de datos."""
        cls.engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        cls.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=cls.engine
        )

    @classmethod
    def tearDownClass(cls):
        """Libera los recursos del motor SQLAlchemy."""
        cls.engine.dispose()

    def setUp(self):
        """Abre una sesión de base de datos para cada prueba."""
        self.db: Session = self.SessionLocal()

    def tearDown(self):
        """Cierra la sesión de base de datos tras cada prueba."""
        self.db.close()

    def _configuracion_de_simulacion(self, sim_id: str) -> dict[str, Any]:
        """Recupera la configuración persistida para ejecutar el motor directamente."""
        simulacion = SimulationRepository.obtener_por_id(
            self.db, sim_id, cargar_relaciones=True
        )
        if simulacion is None or simulacion.parametro is None:
            self.fail(f"No hay configuración persistida para {sim_id}")
        return simulacion.parametro.configuracion_json

    def _sample_payload(self, **overrides) -> SimulationCreate:
        """Genera un payload válido para creación de simulación."""
        base_data = {
            "name": f"Simulacion Test {uuid4().hex[:6]}",
            "zone": "yacuiba",
            "zoneName": "Yacuiba",
            "department": "Tarija",
            "soilType": "franco_arenoso",
            "cornVariety": "iniaf_h1",
            "plantingDate": date(2026, 11, 20),
            "simulationDays": 120,
            "gridConfig": GridConfig(rows=100, cols=100, cellSizeMeters=50),
            "initialMoisturePercent": 18.5,
            "droughtScenario": "moderado_ssp245",
            "engine": "openmp",
            "openmpThreads": 8,
            "mpiProcesses": None,
            "nodesCount": None,
        }
        base_data.update(overrides)
        return SimulationCreate(**base_data)

    # --------------------------------------------------------------------------
    # 1. Pruebas CRUD y Persistencia Base
    # --------------------------------------------------------------------------

    def test_1_crear_simulacion_persistencia_real_postgres(self):
        """1. Verifica creación de simulación y persistencia real en PostgreSQL."""
        payload = self._sample_payload()
        response = create_simulation(payload, db=self.db)

        self.assertIn("id", response)
        self.assertTrue(response["id"].startswith("SIM-"))
        self.assertEqual(response["status"], "pending")
        self.assertEqual(response["progressPercent"], 0)
        self.assertIsNotNone(response["createdAt"])
        self.assertIn("config", response)
        self.assertEqual(response["config"]["name"], payload.name)

        sim_id = response["id"]
        try:
            sim_db = self.db.get(Simulacion, sim_id)
            self.assertIsNotNone(sim_db)
            self.assertEqual(sim_db.nombre, payload.name)
            self.assertEqual(sim_db.estado, "pending")
        finally:
            delete_simulation(sim_id, db=self.db)

    def test_2_listar_historial_simulaciones(self):
        """2. Verifica que list_simulations recupere registros de PostgreSQL."""
        payload = self._sample_payload(name="Simulacion Para Historial")
        created = create_simulation(payload, db=self.db)
        created_id = created["id"]

        try:
            historial = list_simulations(limit=20, db=self.db)
            self.assertIn("total", historial)
            self.assertGreaterEqual(historial["total"], 1)
            ids = [s["id"] for s in historial["simulations"]]
            self.assertIn(created_id, ids)
        finally:
            delete_simulation(created_id, db=self.db)

    def test_3_consulta_individual_obtener_por_id(self):
        """3. Verifica get_simulation recuperando datos y parámetros de PostgreSQL."""
        payload = self._sample_payload(name="Simulacion Consulta Individual")
        created = create_simulation(payload, db=self.db)
        sim_id = created["id"]

        try:
            fetched = get_simulation(sim_id, db=self.db)
            self.assertEqual(fetched["id"], sim_id)
            self.assertEqual(fetched["config"]["name"], "Simulacion Consulta Individual")
            self.assertEqual(fetched["status"], "pending")
        finally:
            delete_simulation(sim_id, db=self.db)

    def test_4_eliminacion_en_cascada_postgres(self):
        """4. Verifica eliminación en PostgreSQL y borrado de tablas dependientes."""
        payload = self._sample_payload(name="Simulacion a Eliminar")
        created = create_simulation(payload, db=self.db)
        sim_id = created["id"]

        self.assertIsNotNone(self.db.get(Simulacion, sim_id))
        resp_delete = delete_simulation(sim_id, db=self.db)
        self.assertEqual(resp_delete["id"], sim_id)
        self.assertIsNone(self.db.get(Simulacion, sim_id))

    def test_5_respuestas_404_para_registros_inexistentes(self):
        """5. Verifica que consultas y eliminaciones con ID inexistente devuelvan HTTP 404."""
        non_existent_id = "SIM-INEXISTENTE-999"

        with self.assertRaises(HTTPException) as cm_get:
            get_simulation(non_existent_id, db=self.db)
        self.assertEqual(cm_get.exception.status_code, 404)

        with self.assertRaises(HTTPException) as cm_del:
            delete_simulation(non_existent_id, db=self.db)
        self.assertEqual(cm_del.exception.status_code, 404)

        with self.assertRaises(HTTPException) as cm_exe:
            execute_simulation(non_existent_id, db=self.db)
        self.assertEqual(cm_exe.exception.status_code, 404)

    def test_6_validacion_pydantic_rechaza_datos_invalidos_422(self):
        """6. Verifica que esquemas inválidos sean rechazados por Pydantic."""
        with self.assertRaises(ValidationError):
            self._sample_payload(
                gridConfig=GridConfig(rows=10, cols=100, cellSizeMeters=50)
            )

        with self.assertRaises(ValidationError):
            self._sample_payload(simulationDays=10)

        with self.assertRaises(ValidationError):
            self._sample_payload(engine="openmp", openmpThreads=3)

    # --------------------------------------------------------------------------
    # 2. Pruebas Unitarias del Servicio del Motor (MotorService)
    # --------------------------------------------------------------------------

    def test_7_motor_service_seleccion_cuatro_motores(self):
        """7. Verifica resolución de los ejecutables de los 4 motores y rechazo de desconocidos."""
        binarios = {
            "secuencial": "agrochaco_secuencial",
            "openmp": "agrochaco_openmp",
            "mpi": "agrochaco_mpi",
            "hibrido": "agrochaco_hibrido",
        }

        for engine, bin_name in binarios.items():
            exe_path = MotorService.resolver_ejecutable(engine)
            self.assertTrue(exe_path.exists(), f"El binario {bin_name} no existe.")
            self.assertEqual(exe_path.name, bin_name)

        with self.assertRaises(ValueError):
            MotorService.resolver_ejecutable("cuantico_invalido")

    def test_8_motor_service_construccion_argumentos_cli(self):
        """8. Verifica construcción de argumentos CLI para cada modalidad."""
        dummy_exe = Path("/tmp/dummy_motor")
        dummy_in = Path("/tmp/dummy_in.json")
        dummy_out = Path("/tmp/dummy_out.json")

        cmd_seq = MotorService.construir_comando_cli(
            engine="secuencial",
            executable_path=dummy_exe,
            config_path=dummy_in,
            output_path=dummy_out,
            days=120,
            rows=200,
            cols=200,
        )
        self.assertEqual(cmd_seq[0], str(dummy_exe))
        self.assertIn("--config", cmd_seq)
        self.assertNotIn("--threads", cmd_seq)
        self.assertNotIn("mpirun", cmd_seq)

        cmd_omp = MotorService.construir_comando_cli(
            engine="openmp",
            executable_path=dummy_exe,
            config_path=dummy_in,
            output_path=dummy_out,
            days=100,
            rows=100,
            cols=100,
            threads=8,
        )
        self.assertIn("--threads", cmd_omp)
        self.assertEqual(cmd_omp[cmd_omp.index("--threads") + 1], "8")

        cmd_mpi = MotorService.construir_comando_cli(
            engine="mpi",
            executable_path=dummy_exe,
            config_path=dummy_in,
            output_path=dummy_out,
            days=100,
            rows=100,
            cols=100,
            processes=4,
        )
        self.assertEqual(cmd_mpi[0], "mpirun")
        self.assertIn("-np", cmd_mpi)
        self.assertEqual(cmd_mpi[cmd_mpi.index("-np") + 1], "4")

        cmd_hib = MotorService.construir_comando_cli(
            engine="hibrido",
            executable_path=dummy_exe,
            config_path=dummy_in,
            output_path=dummy_out,
            days=90,
            rows=150,
            cols=150,
            threads=4,
            processes=2,
        )
        self.assertEqual(cmd_hib[0], "mpirun")
        self.assertIn("-np", cmd_hib)
        self.assertIn("--threads", cmd_hib)

    def test_9_motor_service_construccion_config_json(self):
        """9. Verifica que construir_configuracion_json arme el formato requerido."""
        cfg = {
            "name": "Simulacion Test JSON",
            "zone": "yacuiba",
            "zoneName": "Yacuiba",
            "soilType": "franco_arenoso",
            "cornVariety": "iniaf_h1",
            "simulationDays": 100,
            "initialMoisturePercent": 20.0,
            "droughtScenario": "extremo_ssp585",
            "engine": "hibrido",
            "gridConfig": {"rows": 80, "cols": 80, "cellSizeMeters": 50},
            "openmpThreads": 4,
            "mpiProcesses": 2,
            "nodesCount": 2,
        }

        normalizado = MotorService.construir_configuracion_json("SIM-TEST-001", cfg)
        self.assertEqual(normalizado["id"], "SIM-TEST-001")
        self.assertEqual(normalizado["simulationDays"], 100)
        self.assertEqual(normalizado["gridConfig"]["rows"], 80)
        self.assertEqual(normalizado["gridConfig"]["cols"], 80)
        self.assertEqual(normalizado["openmpThreads"], 4)
        self.assertEqual(normalizado["mpiProcesses"], 2)

    @patch("app.services.motor_service.subprocess.run")
    def test_10_motor_service_manejo_timeout(self, mock_run):
        """10. Verifica captura y excepción adecuada ante timeout del proceso."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["dummy"], timeout=5)

        with self.assertRaises(MotorTimeoutError):
            MotorService.ejecutar(
                simulation_id="SIM-TIMEOUT-001",
                config_dict={"engine": "secuencial", "simulationDays": 30},
                timeout_seconds=5,
            )

    @patch("app.services.motor_service.subprocess.run")
    def test_11_motor_service_error_ejecucion_binario(self, mock_run):
        """11. Verifica captura de error cuando el proceso retorna código distinto de 0."""
        mock_proc = MagicMock()
        mock_proc.returncode = 139
        mock_proc.stderr = "Segmentation fault (core dumped)"
        mock_proc.stdout = ""
        mock_run.return_value = mock_proc

        with self.assertRaises(MotorExecutionError) as ctx:
            MotorService.ejecutar(
                simulation_id="SIM-FAIL-001",
                config_dict={"engine": "secuencial"},
            )
        self.assertIn("código 139", str(ctx.exception))

    @patch("app.services.motor_service.subprocess.run")
    def test_12_motor_service_json_salida_invalido(self, mock_run):
        """12. Verifica que un archivo de salida corrupto dispare MotorOutputError."""
        def fake_run(cmd, **kwargs):
            out_idx = cmd.index("--output")
            out_path = Path(cmd[out_idx + 1])
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("ESTO NO ES UN JSON VALIDO")
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            return mock_proc

        mock_run.side_effect = fake_run

        with self.assertRaises(MotorOutputError):
            MotorService.ejecutar(
                simulation_id="SIM-CORRUPT-001",
                config_dict={"engine": "secuencial"},
            )

    # --------------------------------------------------------------------------
    # 3. Concurrencia y Transición Atómica (HTTP 409)
    # --------------------------------------------------------------------------

    def test_13_concurrencia_dos_solicitudes_simultaneas_retorna_409(self):
        """13. Verifica que la transición atómica en PostgreSQL impida ejecuciones duplicadas (HTTP 409)."""
        payload = self._sample_payload(name="Simulacion Para Concurrencia")
        created = create_simulation(payload, db=self.db)
        sim_id = created["id"]

        try:
            # Solicitud 1 adquiere la ejecución
            # Simular transición directa atómica
            stmt = (
                update(Simulacion)
                .where(Simulacion.id == sim_id, Simulacion.estado != "running")
                .values(estado="running")
            )
            res1 = self.db.execute(stmt)
            self.assertEqual(res1.rowcount, 1, "La primera solicitud debe adquirir la ejecución.")
            self.db.commit()

            # Solicitud 2 intenta ejecutar simultáneamente la misma simulación
            with self.assertRaises(HTTPException) as ctx:
                execute_simulation(sim_id, db=self.db)
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertIn("ya se encuentra en ejecución", ctx.exception.detail)

        finally:
            delete_simulation(sim_id, db=self.db)

    # --------------------------------------------------------------------------
    # 4. Persistencia Atómica, Rollback y Recuperación de Fallos
    # --------------------------------------------------------------------------

    @patch("app.services.motor_service.subprocess.run")
    def test_14_execute_persistencia_resultados_y_estado_completed(self, mock_run):
        """14. Verifica flujo completo de ejecución: transición a completed y persistencia en PostgreSQL."""
        payload = self._sample_payload(
            name="Simulacion Exitosa",
            engine="openmp",
            openmpThreads=4,
        )
        created = create_simulation(payload, db=self.db)
        sim_id = created["id"]

        def fake_motor_run(cmd, **kwargs):
            out_idx = cmd.index("--output")
            out_path = Path(cmd[out_idx + 1])
            mock_result = {
                "id": sim_id,
                "status": "completed",
                "progressPercent": 100,
                "currentDay": 120,
                "createdAt": "2026-11-16 10:00:00",
                "completedAt": "2026-11-16 10:00:01",
                "executionTimeSeconds": 0.0425,
                "speedup": 3.8500,
                "efficiency": 96.2500,
                "averageCWSI": 0.3250,
                "soilMoistureFinalPercent": 14.80,
                "yieldLossPercent": 22.50,
                "estimatedYieldTnHa": 4.18,
                "nominalYieldTnHa": 5.40,
                "waterDeficitMm": 45.20,
                "memoryUsageMb": 8.50,
                "timelineData": [
                    {
                        "day": 1,
                        "date": "Día 1",
                        "phenologicalStage": "Emergencia",
                        "etActual": 2.1,
                        "etPotential": 2.1,
                        "cwsi": 0.10,
                        "soilMoisture": 18.0,
                        "precipitation": 0.0,
                    },
                    {
                        "day": 2,
                        "date": "Día 2",
                        "phenologicalStage": "Emergencia",
                        "etActual": 2.0,
                        "etPotential": 2.5,
                        "cwsi": 0.45,
                        "soilMoisture": 14.8,
                        "precipitation": 0.0,
                    },
                ],
                "logs": [],
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(mock_result, f)

            proc = MagicMock()
            proc.returncode = 0
            return proc

        mock_run.side_effect = fake_motor_run
        config_dict = self._configuracion_de_simulacion(sim_id)

        try:
            ejecucion = MotorService.ejecutar(
                simulation_id=sim_id,
                config_dict=config_dict,
            )
            MotorService.persistir_resultados_en_db(
                db=self.db,
                simulation_id=sim_id,
                config_dict=config_dict,
                resultado_ejecucion=ejecucion,
            )
            resp = get_simulation(sim_id, db=self.db)

            self.assertEqual(resp["id"], sim_id)
            self.assertEqual(resp["status"], "completed")
            self.assertEqual(resp["progressPercent"], 100)
            self.assertAlmostEqual(resp["averageCWSI"], 0.3250, places=3)
            self.assertAlmostEqual(resp["executionTimeSeconds"], 0.0425, places=3)
            self.assertEqual(len(resp["timelineData"]), 2)

            sim_db = self.db.get(Simulacion, sim_id)
            self.assertEqual(sim_db.estado, "completed")

            stmt_res = select(Resultado).where(Resultado.simulacion_id == sim_id)
            res_db = self.db.execute(stmt_res).scalar_one_or_none()
            self.assertIsNotNone(res_db)
            self.assertEqual(res_db.deficit_medio, Decimal("0.3250"))
            self.assertEqual(res_db.deficit_maximo, Decimal("0.4500"))
            self.assertEqual(res_db.agua_final_media, Decimal("14.80"))

            stmt_rend = select(Rendimiento).where(Rendimiento.simulacion_id == sim_id)
            rend_db = self.db.execute(stmt_rend).scalar_one_or_none()
            self.assertIsNotNone(rend_db)
            self.assertEqual(rend_db.modalidad, "openmp")
            self.assertEqual(rend_db.hilos, 4)
            self.assertEqual(rend_db.tiempo_segundos, Decimal("0.0425"))

            stmt_eve = select(EventoEjecucion).where(EventoEjecucion.simulacion_id == sim_id)
            eventos = self.db.execute(stmt_eve).scalars().all()
            mensajes = [e.mensaje for e in eventos]
            self.assertTrue(any("completada exitosamente" in m for m in mensajes))

            perm_file = PROJECT_ROOT / "results" / "simulations" / f"{sim_id}.json"
            self.assertTrue(perm_file.is_file())

            fetched = get_simulation(sim_id, db=self.db)
            self.assertEqual(len(fetched["timelineData"]), 2)
            self.assertEqual(fetched["yieldLossPercent"], 22.50)

        finally:
            delete_simulation(sim_id, db=self.db)
            perm_file = PROJECT_ROOT / "results" / "simulations" / f"{sim_id}.json"
            if perm_file.exists():
                perm_file.unlink(missing_ok=True)

    @patch("app.db.repository.SimulationRepository.guardar_rendimiento")
    @patch("app.services.motor_service.subprocess.run")
    def test_15_execute_persistencia_fallida_rollback_atomico(self, mock_run, mock_rend):
        """15. Verifica que ante fallo en persistencia se aplique rollback y no queden datos parciales."""
        payload = self._sample_payload(name="Simulacion Rollback Test")
        created = create_simulation(payload, db=self.db)
        sim_id = created["id"]

        def fake_motor_run(cmd, **kwargs):
            out_idx = cmd.index("--output")
            out_path = Path(cmd[out_idx + 1])
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"status": "completed", "averageCWSI": 0.2, "soilMoistureFinalPercent": 15.0}, f)
            p = MagicMock()
            p.returncode = 0
            return p

        mock_run.side_effect = fake_motor_run
        config_dict = self._configuracion_de_simulacion(sim_id)
        # Inducir fallo en la persistencia del rendimiento
        mock_rend.side_effect = RuntimeError("Error inducido de I/O en base de datos")

        try:
            ejecucion = MotorService.ejecutar(
                simulation_id=sim_id,
                config_dict=config_dict,
            )
            with self.assertRaises(RuntimeError):
                MotorService.persistir_resultados_en_db(
                    db=self.db,
                    simulation_id=sim_id,
                    config_dict=config_dict,
                    resultado_ejecucion=ejecucion,
                )

            # Verificar que NO quedó un Resultado huérfano persistido
            stmt_res = select(Resultado).where(Resultado.simulacion_id == sim_id)
            res_db = self.db.execute(stmt_res).scalar_one_or_none()
            self.assertIsNone(res_db, "El rollback atómico debe impedir la persistencia parcial de Resultado.")

            sim_db = self.db.get(Simulacion, sim_id)
            self.assertEqual(sim_db.estado, "pending")

        finally:
            delete_simulation(sim_id, db=self.db)
            perm_file = PROJECT_ROOT / "results" / "simulations" / f"{sim_id}.json"
            if perm_file.exists():
                perm_file.unlink(missing_ok=True)

    # --------------------------------------------------------------------------
    # 5. Semántica de Métricas y Límites
    # --------------------------------------------------------------------------

    def test_16_semantica_metricas_y_limites_campos(self):
        """16. Verifica la correspondencia semántica rigurosa y el acotamiento en [0, 1]."""
        payload = self._sample_payload(name="Simulacion Metricas Semantica")
        created = create_simulation(payload, db=self.db)
        sim_id = created["id"]

        try:
            # Simular salida con valores límite (ej. flotante ligeramente superior a 1 y déficit en mm grande)
            resultado_motor = {
                "engine": "secuencial",
                "archivo_detalle": f"results/simulations/{sim_id}.json",
                "output_data": {
                    "averageCWSI": 1.0005,      # Requiere clamping a 1.0 para chk_resultados_deficit_medio
                    "waterDeficitMm": 385.40,    # NO debe entrar a deficit_medio
                    "soilMoistureFinalPercent": 8.50,
                    "executionTimeSeconds": 0.2450,
                    "speedup": 1.0,
                    "efficiency": 100.0,         # Porcentaje -> normalizar a 1.0000
                    "timelineData": [
                        {"day": 1, "cwsi": 0.15, "soilMoisture": 18.0},
                        {"day": 2, "cwsi": 0.98, "soilMoisture": 8.5},
                    ],
                },
            }

            MotorService.persistir_resultados_en_db(
                db=self.db,
                simulation_id=sim_id,
                config_dict={"engine": "secuencial"},
                resultado_ejecucion=resultado_motor,
            )

            # Consultar en PostgreSQL
            stmt_res = select(Resultado).where(Resultado.simulacion_id == sim_id)
            res_db = self.db.execute(stmt_res).scalar_one()

            # 1. deficit_medio debe ser exactamente 1.0000 (clamp), nunca 385.40 mm
            self.assertEqual(res_db.deficit_medio, Decimal("1.0000"))
            self.assertNotEqual(res_db.deficit_medio, Decimal("385.40"))

            # 2. deficit_maximo debe ser el pico de timelineData (0.9800)
            self.assertEqual(res_db.deficit_maximo, Decimal("0.9800"))

            # 3. agua_final_media debe ser 8.50% y agua_minima 8.50%
            self.assertEqual(res_db.agua_final_media, Decimal("8.50"))
            self.assertEqual(res_db.agua_minima, Decimal("8.50"))

            # 4. eficiencia en tabla rendimiento debe estar normalizada a 1.0000 (no 100.0)
            stmt_rend = select(Rendimiento).where(Rendimiento.simulacion_id == sim_id)
            rend_db = self.db.execute(stmt_rend).scalar_one()
            self.assertEqual(rend_db.eficiencia, Decimal("1.0000"))

        finally:
            delete_simulation(sim_id, db=self.db)

    # --------------------------------------------------------------------------
    # 6. Seguridad y Mitigación de Path Traversal
    # --------------------------------------------------------------------------

    def test_17_seguridad_identificadores_invalidos_path_traversal(self):
        """17. Verifica rechazo estricto de identificadores maliciosos y confinamiento en results/simulations."""
        ataques_path_traversal = [
            "../../etc/passwd",
            "../results/simulations/hack",
            "SIM/EVIL",
            "SIM\\EVIL",
            "SIM\x00NULL",
            "SIM ID CON ESPACIOS",
            "SIM*INVAL!DO",
            "",
            "   ",
        ]

        for payload_id in ataques_path_traversal:
            with self.subTest(simulation_id=payload_id):
                # 1. Nivel MotorService
                with self.assertRaises(MotorSecurityError):
                    MotorService.validar_simulation_id(payload_id)

                # 2. Nivel Endpoint HTTP (debe retornar HTTP 400 Bad Request)
                with self.assertRaises(HTTPException) as ctx_get:
                    get_simulation(payload_id, db=self.db)
                self.assertEqual(ctx_get.exception.status_code, 400)

                with self.assertRaises(HTTPException) as ctx_exe:
                    execute_simulation(payload_id, db=self.db)
                self.assertEqual(ctx_exe.exception.status_code, 400)

                with self.assertRaises(HTTPException) as ctx_del:
                    delete_simulation(payload_id, db=self.db)
                self.assertEqual(ctx_del.exception.status_code, 400)

        # 3. Nivel archivo_detalle: asegurar que no se lean archivos ni symlinks fuera de results/simulations
        sim_externa = create_simulation(self._sample_payload(name="Sim Archivo Externo"), db=self.db)
        sim_ext_id = sim_externa["id"]
        try:
            ruta_externa = str(PROJECT_ROOT / "backend" / "app" / "main.py")
            res_obj = Resultado(
                simulacion_id=sim_ext_id,
                deficit_medio=Decimal("0.1000"),
                deficit_maximo=Decimal("0.1000"),
                agua_final_media=Decimal("20.00"),
                agua_minima=Decimal("20.00"),
                escenarios_con_deficit=0,
                archivo_detalle=ruta_externa,
            )
            self.db.add(res_obj)
            self.db.commit()

            fetched = get_simulation(sim_ext_id, db=self.db)
            self.assertEqual(fetched["timelineData"], [], "Archivos fuera de results/simulations no deben ser leídos.")

            # Comprobar que enlaces simbólicos que escapen del directorio permitido sean rechazados
            sims_dir = PROJECT_ROOT / "results" / "simulations"
            sims_dir.mkdir(parents=True, exist_ok=True)
            symlink_path = sims_dir / f"symlink_test_{sim_ext_id}.json"
            try:
                symlink_path.symlink_to(PROJECT_ROOT / "backend" / "app" / "main.py")
                res_obj.archivo_detalle = str(symlink_path)
                self.db.commit()

                fetched_sym = get_simulation(sim_ext_id, db=self.db)
                self.assertEqual(
                    fetched_sym["timelineData"],
                    [],
                    "Los enlaces simbólicos que escapen de results/simulations deben ser rechazados.",
                )
            finally:
                if symlink_path.is_symlink() or symlink_path.exists():
                    symlink_path.unlink()
        finally:
            delete_simulation(sim_ext_id, db=self.db)

    # --------------------------------------------------------------------------
    # 7. Integración Real de Punta a Punta
    # --------------------------------------------------------------------------

    def test_18_execute_secuencial_real_e2e(self):
        """18. Prueba de integración real de punta a punta ejecutando el binario físico agrochaco_secuencial."""
        payload = self._sample_payload(
            name="E2E Secuencial Real",
            engine="secuencial",
            simulationDays=30,
            gridConfig=GridConfig(rows=50, cols=50, cellSizeMeters=50),
        )
        created = create_simulation(payload, db=self.db)
        sim_id = created["id"]

        try:
            config_dict = self._configuracion_de_simulacion(sim_id)
            ejecucion = MotorService.ejecutar(sim_id, config_dict)
            MotorService.persistir_resultados_en_db(
                db=self.db,
                simulation_id=sim_id,
                config_dict=config_dict,
                resultado_ejecucion=ejecucion,
            )
            resultado = get_simulation(sim_id, db=self.db)

            self.assertEqual(resultado["id"], sim_id)
            self.assertEqual(resultado["status"], "completed")
            self.assertEqual(resultado["progressPercent"], 100)
            self.assertGreater(len(resultado["timelineData"]), 0)
            self.assertGreater(resultado["averageCWSI"], 0.0)

            perm_file = PROJECT_ROOT / "results" / "simulations" / f"{sim_id}.json"
            self.assertTrue(perm_file.is_file())

        finally:
            delete_simulation(sim_id, db=self.db)
            perm_file = PROJECT_ROOT / "results" / "simulations" / f"{sim_id}.json"
            if perm_file.exists():
                perm_file.unlink(missing_ok=True)

    def test_20_metricas_no_disponibles_son_null_en_postgresql_y_fastapi(self):
        """20. NULL (y cero) no se convierten en speedup/eficiencia medidos."""
        payload = self._sample_payload(name="Simulacion Metricas Null", engine="openmp", openmpThreads=4)
        created = create_simulation(payload, db=self.db)
        sim_id = created["id"]

        base_output = {
            "averageCWSI": 0.2,
            "soilMoistureFinalPercent": 15.0,
            "waterDeficitMm": 20.0,
            "yieldLossPercent": 10.0,
            "executionTimeSeconds": 0.0425,
            "timelineData": [
                {"cwsi": 0.1, "soilMoisture": 18.0},
                {"cwsi": 0.2, "soilMoisture": 15.0},
            ],
        }

        try:
            for velocidad, eficiencia in ((None, None), (0.0, 0.0)):
                resultado_motor = {
                    "engine": "openmp",
                    "archivo_detalle": f"results/simulations/{sim_id}.json",
                    "output_data": {
                        **base_output,
                        "speedup": velocidad,
                        "efficiency": eficiencia,
                    },
                }
                MotorService.persistir_resultados_en_db(
                    db=self.db,
                    simulation_id=sim_id,
                    config_dict={"engine": "openmp", "openmpThreads": 4},
                    resultado_ejecucion=resultado_motor,
                )

            registros = self.db.execute(
                select(Rendimiento).where(Rendimiento.simulacion_id == sim_id)
            ).scalars().all()
            self.assertEqual(len(registros), 2)
            self.assertTrue(all(r.speedup is None for r in registros))
            self.assertTrue(all(r.eficiencia is None for r in registros))
            self.assertTrue(all(r.tiempo_segundos == Decimal("0.0425") for r in registros))

            fetched = get_simulation(sim_id, db=self.db)
            self.assertIsNone(fetched["speedup"])
            self.assertIsNone(fetched["efficiency"])
            self.assertAlmostEqual(fetched["executionTimeSeconds"], 0.0425, places=4)
        finally:
            delete_simulation(sim_id, db=self.db)


if __name__ == "__main__":
    unittest.main()
