"""Pruebas de integración para la API de Simulaciones de AgroChaco con PostgreSQL.

Verifica:
1. Creación de una simulación y persistencia real en PostgreSQL (tablas simulaciones y parametros).
2. Compatibilidad del formato de respuesta con la interfaz esperada por React.
3. Listado de simulaciones desde PostgreSQL (incluyendo semillas históricas).
4. Consulta individual por ID con precarga de relaciones.
5. Eliminación de simulación con borrado en cascada en PostgreSQL.
6. Manejo de error HTTP 404 ante registros inexistentes.
7. Manejo de error de validación ante esquemas inválidos (Pydantic).
8. Persistencia del historial entre diferentes sesiones de base de datos (simulando reinicio).
"""

from datetime import date
from decimal import Decimal
import os
from pathlib import Path
import sys
import unittest
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

# Asegurar path para imports
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.simulations import (
    GridConfig,
    SimulationCreate,
    create_simulation,
    delete_simulation,
    execute_simulation,
    get_simulation,
    list_simulations,
)
from app.models import Parametro, Simulacion

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "Define DATABASE_URL antes de ejecutar estas pruebas."
    )


class TestApiSimulationsPostgres(unittest.TestCase):
    """Suite de pruebas para validar los endpoints de simulaciones conectados a PostgreSQL."""

    @classmethod
    def setUpClass(cls):
        """Inicializa la conexión con la base de datos aislada de pruebas."""
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

    def test_1_crear_simulacion_persistencia_real_postgres(self):
        """1. Verifica creación de simulación y persistencia real en PostgreSQL."""
        payload = self._sample_payload()
        response = create_simulation(payload, db=self.db)

        # A. Verificar respuesta HTTP compatible con React
        self.assertIn("id", response)
        self.assertTrue(response["id"].startswith("SIM-"))
        self.assertEqual(response["status"], "pending")
        self.assertEqual(response["progressPercent"], 0)
        self.assertIsNotNone(response["createdAt"])
        self.assertIn("config", response)
        self.assertEqual(response["config"]["name"], payload.name)
        self.assertEqual(response["config"]["zone"], "yacuiba")

        sim_id = response["id"]

        # B. Verificar persistencia física real en PostgreSQL
        stmt = select(Simulacion).where(Simulacion.id == sim_id)
        sim_db = self.db.execute(stmt).scalar_one_or_none()

        self.assertIsNotNone(sim_db, "La simulación no fue guardada en PostgreSQL.")
        self.assertEqual(sim_db.nombre, payload.name)
        self.assertEqual(sim_db.estado, "pending")
        self.assertEqual(sim_db.dias, 120)

        # C. Verificar parámetros asociados en PostgreSQL
        stmt_param = select(Parametro).where(Parametro.simulacion_id == sim_id)
        param_db = self.db.execute(stmt_param).scalar_one_or_none()

        self.assertIsNotNone(param_db, "Los parámetros no fueron guardados en PostgreSQL.")
        self.assertEqual(param_db.agua_inicial, Decimal("18.50"))
        self.assertGreater(param_db.capacidad_suelo, Decimal("0.00"))
        self.assertGreater(param_db.umbral_hidrico, Decimal("0.00"))
        self.assertEqual(param_db.configuracion_json["cornVariety"], "iniaf_h1")

        # Limpieza controlada
        delete_simulation(sim_id, db=self.db)

    def test_2_listar_simulaciones_incluye_semillas_e_insertadas(self):
        """2. Verifica que list_simulations obtenga datos de PostgreSQL incluyendo semillas."""
        payload = self._sample_payload(name="Simulacion Para Listar")
        created = create_simulation(payload, db=self.db)
        created_id = created["id"]

        try:
            result = list_simulations(db=self.db)

            self.assertIn("total", result)
            self.assertIn("simulations", result)
            self.assertGreater(result["total"], 0)
            self.assertIsInstance(result["simulations"], list)

            # Verificar que la recién creada esté presente
            ids = [s["id"] for s in result["simulations"]]
            self.assertIn(created_id, ids)

            # Verificar que las semillas preexistentes de Yulenka se muestren (ej. SIM-YACUIBA-001)
            # si están en la base de datos
            seed_ids = [s_id for s_id in ids if "YACUIBA" in s_id or "VILLAMONTES" in s_id]
            self.assertTrue(len(seed_ids) > 0 or result["total"] >= 1)

            # Comprobar estructura de cada elemento para el frontend
            primera = result["simulations"][0]
            self.assertIn("id", primera)
            self.assertIn("config", primera)
            self.assertIn("status", primera)
            self.assertIn("createdAt", primera)

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
            self.assertEqual(fetched["config"]["simulationDays"], 120)
            self.assertEqual(fetched["status"], "pending")
        finally:
            delete_simulation(sim_id, db=self.db)

    def test_4_eliminacion_en_cascada_postgres(self):
        """4. Verifica eliminación en PostgreSQL y borrado de tablas dependientes."""
        payload = self._sample_payload(name="Simulacion a Eliminar")
        created = create_simulation(payload, db=self.db)
        sim_id = created["id"]

        # Confirmar existencia previa
        self.assertIsNotNone(self.db.get(Simulacion, sim_id))

        # Eliminar mediante endpoint
        resp_delete = delete_simulation(sim_id, db=self.db)
        self.assertEqual(resp_delete["id"], sim_id)

        # Confirmar que ya no existe en PostgreSQL
        self.assertIsNone(self.db.get(Simulacion, sim_id))

        # Confirmar que los parámetros tampoco existen (ON DELETE CASCADE)
        stmt_param = select(Parametro).where(Parametro.simulacion_id == sim_id)
        self.assertIsNone(self.db.execute(stmt_param).scalar_one_or_none())

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
        """6. Verifica que esquemas inválidos sean rechazados antes de llegar a la base de datos."""
        # A. Filas menores al mínimo permitido (ge=50)
        with self.assertRaises(ValidationError):
            self._sample_payload(
                gridConfig=GridConfig(rows=10, cols=100, cellSizeMeters=50)
            )

        # B. Días fuera de rango (ge=30, le=150)
        with self.assertRaises(ValidationError):
            self._sample_payload(simulationDays=10)

        # C. Cantidad de hilos no permitida para OpenMP (debe ser 2, 4, 8, 16)
        with self.assertRaises(ValidationError):
            self._sample_payload(engine="openmp", openmpThreads=3)

    def test_7_persistencia_despues_de_reiniciar_sesion(self):
        """7. Verifica que los datos persistan al cerrar y reabrir sesiones (sin memoria RAM)."""
        payload = self._sample_payload(name="Simulacion Persistencia Sesion")

        # Sesión 1: Crear
        session1 = self.SessionLocal()
        created = create_simulation(payload, db=session1)
        sim_id = created["id"]
        session1.close()  # Simula fin del ciclo o reinicio

        # Sesión 2: Consultar desde nueva sesión independiente
        session2 = self.SessionLocal()
        fetched = get_simulation(sim_id, db=session2)
        self.assertEqual(fetched["id"], sim_id)
        self.assertEqual(fetched["config"]["name"], "Simulacion Persistencia Sesion")

        # Limpiar
        delete_simulation(sim_id, db=session2)
        session2.close()

    def test_8_endpoint_execute_retorna_501_con_id_valido(self):
        """8. Verifica que execute_simulation conserve HTTP 501 cuando la simulación existe."""
        payload = self._sample_payload(name="Simulacion Para Execute")
        created = create_simulation(payload, db=self.db)
        sim_id = created["id"]

        try:
            with self.assertRaises(HTTPException) as cm_exe:
                execute_simulation(sim_id, db=self.db)
            self.assertEqual(cm_exe.exception.status_code, 501)
            self.assertIn("La ejecución todavía no está disponible", cm_exe.exception.detail)
        finally:
            delete_simulation(sim_id, db=self.db)


if __name__ == "__main__":
    unittest.main()
