"""Pruebas unitarias de la capa de persistencia y repositorios transaccionales (AgroChaco).

Verifica:
1. Creación atómica de simulación y parámetros.
2. Rollback automático ante fallo en la transacción (Unit of Work).
3. Guardado y actualización de resultados.
4. Registro de métricas de rendimiento HPC.
5. Registro de fuentes de datos con hash SHA-256.
6. Registro de trazas de eventos.
7. Eliminación en cascada y actualización de estado.
"""

from decimal import Decimal
import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# Asegurar path para imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.repository import SimulationRepository
from app.models import EventoEjecucion, Parametro, Rendimiento, Resultado, Simulacion

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://agrochaco_user:agrochaco_dev_2026@localhost:5432/agrochaco",
)


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


def test_crear_simulacion_con_parametros_exitoso(db_session):
    """Verifica que la creación atómica persista la simulación, sus parámetros y el evento inicial."""
    sim_id = f"SIM-{uuid4().hex[:12].upper()}"

    datos_sim = {
        "id": sim_id,
        "nombre": "Test Persistencia Yacuiba",
        "fuente_datos": "SENAMHI",
        "escenario": "moderado_ssp245",
        "cantidad_escenarios": 4,
        "dias": 100,
        "estado": "pending",
        "semilla": 9999,
    }

    datos_param = {
        "agua_inicial": Decimal("20.00"),
        "capacidad_suelo": Decimal("110.00"),
        "umbral_hidrico": Decimal("55.00"),
        "configuracion_json": {
            "zone": "yacuiba",
            "department": "Tarija",
            "cornVariety": "chaco_01_criollo",
        },
    }

    simulacion = SimulationRepository.crear_simulacion_con_parametros(
        db_session, datos_sim, datos_param
    )

    assert simulacion.id == sim_id
    assert simulacion.parametro is not None
    assert simulacion.parametro.capacidad_suelo == Decimal("110.00")
    assert len(simulacion.eventos) == 1
    assert "creada en estado 'pending'" in simulacion.eventos[0].mensaje


def test_rollback_ante_error_en_parametros(db_session):
    """Verifica que si los parámetros violan restricciones CHECK, la simulación NO queda huérfana."""
    sim_id = f"SIM-{uuid4().hex[:12].upper()}"

    datos_sim = {
        "id": sim_id,
        "nombre": "Simulación Fallida",
        "fuente_datos": "Test",
        "escenario": "historico",
        "cantidad_escenarios": 1,
        "dias": 90,
        "estado": "pending",
    }

    # Parámetros inválidos (capacidad de suelo = 0 viola CHECK capacidad_suelo > 0)
    datos_param_invalidos = {
        "agua_inicial": Decimal("20.00"),
        "capacidad_suelo": Decimal("0.00"),  # CHECK Violation
        "umbral_hidrico": Decimal("50.00"),
        "configuracion_json": {},
    }

    with pytest.raises(RuntimeError) as exc_info:
        SimulationRepository.crear_simulacion_con_parametros(
            db_session, datos_sim, datos_param_invalidos
        )

    assert "Error al crear simulación y parámetros" in str(exc_info.value)

    # Verificar que NO se guardó la simulación (Rollback garantizado)
    recuperada = db_session.get(Simulacion, sim_id)
    assert recuperada is None, "La simulación no debió persistirse tras el fallo."


def test_guardar_resultados_y_rendimiento(db_session):
    """Verifica el guardado y posterior consulta de resultados biofísicos y métricas HPC."""
    sim_id = f"SIM-{uuid4().hex[:12].upper()}"

    sim = SimulationRepository.crear_simulacion(
        db_session,
        {
            "id": sim_id,
            "nombre": "Simulacion para Resultados",
            "fuente_datos": "INIAF",
            "escenario": "extremo_ssp585",
            "cantidad_escenarios": 10,
            "dias": 130,
            "estado": "running",
        },
    )

    # Guardar resultados
    res = SimulationRepository.guardar_resultados(
        db_session,
        sim_id,
        {
            "deficit_medio": Decimal("0.4500"),
            "deficit_maximo": Decimal("0.8900"),
            "agua_final_media": Decimal("32.50"),
            "agua_minima": Decimal("11.20"),
            "escenarios_con_deficit": 8,
            "archivo_detalle": "/results/test.csv",
        },
    )
    assert res.id is not None
    assert res.deficit_medio == Decimal("0.4500")

    # Guardar rendimiento HPC
    rend = SimulationRepository.guardar_rendimiento(
        db_session,
        sim_id,
        {
            "modalidad": "openmp",
            "hilos": 8,
            "procesos": 1,
            "nodos": 1,
            "tiempo_segundos": Decimal("12.4500"),
            "speedup": Decimal("6.8000"),
            "eficiencia": Decimal("0.8500"),
            "repeticion": 1,
        },
    )
    assert rend.id is not None
    assert rend.speedup == Decimal("6.8000")

    # Actualizar estado a completed
    sim_actualizada = SimulationRepository.actualizar_estado(
        db_session, sim_id, "completed"
    )
    assert sim_actualizada.estado == "completed"


def test_registrar_fuente_datos_y_eventos(db_session):
    """Verifica el registro de fuentes de datos climáticas y trazas de eventos."""
    sim_id = f"SIM-{uuid4().hex[:12].upper()}"

    SimulationRepository.crear_simulacion(
        db_session,
        {
            "id": sim_id,
            "nombre": "Simulacion Auditoria",
            "fuente_datos": "SENAMHI",
            "escenario": "historico",
            "cantidad_escenarios": 1,
            "dias": 60,
            "estado": "pending",
        },
    )

    # Registrar fuente
    fuente = SimulationRepository.registrar_fuente_datos(
        db_session,
        simulacion_id=sim_id,
        nombre_archivo="precipitacion_test.csv",
        formato="csv",
        hash_archivo="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        periodo="2020-2024",
        descripcion="Datos meteorológicos validados",
    )
    assert fuente.id is not None
    assert fuente.formato == "csv"

    # Registrar evento
    evento = SimulationRepository.registrar_evento(
        db_session,
        simulacion_id=sim_id,
        nivel="WARNING",
        mensaje="Humedad de suelo descendió por debajo del umbral crítico.",
    )
    assert evento.id is not None
    assert evento.nivel == "WARNING"


def test_eliminar_simulacion(db_session):
    """Verifica la eliminación en cascada a través del repositorio."""
    sim_id = f"SIM-{uuid4().hex[:12].upper()}"

    sim = SimulationRepository.crear_simulacion_con_parametros(
        db_session,
        {
            "id": sim_id,
            "nombre": "Simulacion a Borrar",
            "fuente_datos": "Test",
            "escenario": "historico",
            "cantidad_escenarios": 1,
            "dias": 30,
            "estado": "failed",
        },
        {
            "agua_inicial": Decimal("10.00"),
            "capacidad_suelo": Decimal("80.00"),
            "umbral_hidrico": Decimal("40.00"),
            "configuracion_json": {},
        },
    )

    assert SimulationRepository.obtener_por_id(db_session, sim_id) is not None

    eliminado = SimulationRepository.eliminar_simulacion(db_session, sim_id)
    assert eliminado is True

    # Verificar que ya no existe
    assert SimulationRepository.obtener_por_id(db_session, sim_id) is None

