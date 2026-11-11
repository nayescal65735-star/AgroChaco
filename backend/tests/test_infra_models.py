"""Suite de pruebas de verificación para la infraestructura, modelos y restricciones de AgroChaco.

Verifica:
1. Conexión a PostgreSQL 16.
2. Existencia de las seis tablas.
3. Inserción con relaciones ORM e identificadores compatibles con la API de Nayeli.
4. Integridad referencial y eliminación en cascada (ON DELETE CASCADE).
5. Cumplimiento de restricciones CHECK.
"""

import os
import sys
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

# Asegurar path para imports de app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import (
    Base,
    EventoEjecucion,
    FuenteDatos,
    Parametro,
    Rendimiento,
    Resultado,
    Simulacion,
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://agrochaco_user:agrochaco_dev_2026@localhost:5432/agrochaco",
)


@pytest.fixture(scope="module")
def db_engine():
    """Fixture que provee el engine de conexión a la base de datos."""
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Fixture que provee una sesión aislada con rollback al final del test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


def test_postgres_16_connection(db_engine):
    """Comprueba la conexión con PostgreSQL y valida que la versión sea 16."""
    with db_engine.connect() as conn:
        row = conn.execute(
            text("SELECT current_database(), current_user, version();")
        ).fetchone()

        db_name, user, version_str = row[0], row[1], row[2]

        assert db_name == "agrochaco"
        assert user == "agrochaco_user"
        assert "PostgreSQL 16" in version_str
        print(f"\n[OK] Conectado a {db_name} con usuario {user}: {version_str[:30]}...")


def test_six_tables_exist(db_engine):
    """Comprueba que las seis tablas requeridas existen en el esquema público."""
    with db_engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name;
                """
            )
        ).fetchall()

        tables = {row[0] for row in result}
        expected = {
            "simulaciones",
            "parametros",
            "resultados",
            "rendimiento",
            "fuentes_datos",
            "eventos_ejecucion",
        }

        assert expected.issubset(tables), f"Faltan tablas: {expected - tables}"
        print(f"\n[OK] Seis tablas verificadas en information_schema: {tables}")


def test_insertion_and_relationships(db_session):
    """Inserta una simulación completa con ID compatible con Nayeli y comprueba sus relaciones."""
    sim_id = f"SIM-{uuid4().hex[:12].upper()}"

    sim = Simulacion(
        id=sim_id,
        nombre="Test Cultivo Maíz Yacuiba",
        fuente_datos="SENAMHI Yacuiba 2024",
        escenario="sequia_recente_2023",
        cantidad_escenarios=5,
        dias=120,
        estado="completed",
        semilla=424242,
    )

    param = Parametro(
        simulacion=sim,
        agua_inicial=Decimal("22.50"),
        capacidad_suelo=Decimal("120.00"),
        umbral_hidrico=Decimal("60.00"),
        configuracion_json={
            "zone": "yacuiba",
            "soilType": "franco_arenoso",
            "cornVariety": "chaco_01_criollo",
            "gridConfig": {"rows": 100, "cols": 100, "cellSizeMeters": 50},
        },
    )

    res = Resultado(
        simulacion=sim,
        deficit_medio=Decimal("0.3421"),
        deficit_maximo=Decimal("0.7812"),
        agua_final_media=Decimal("45.20"),
        agua_minima=Decimal("18.40"),
        escenarios_con_deficit=3,
        archivo_detalle="/results/SIM-TEST/timeline.csv",
    )

    rend = Rendimiento(
        simulacion=sim,
        modalidad="hibrido",
        hilos=8,
        procesos=4,
        nodos=2,
        tiempo_segundos=Decimal("14.5620"),
        speedup=Decimal("3.8500"),
        eficiencia=Decimal("0.9625"),
        repeticion=1,
    )

    fuente = FuenteDatos(
        simulacion=sim,
        nombre_archivo="precipitacion_yacuiba_2024.csv",
        formato="csv",
        hash_archivo="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        periodo="2020-2024",
        descripcion="Datos meteorológicos validados SENAMHI",
    )

    evento = EventoEjecucion(
        simulacion=sim,
        nivel="INFO",
        mensaje="Simulación híbrida MPI+OpenMP finalizada exitosamente.",
    )

    db_session.add(sim)
    db_session.flush()

    # Consultar y verificar relaciones
    loaded_sim = db_session.get(Simulacion, sim_id)
    assert loaded_sim is not None
    assert loaded_sim.nombre == "Test Cultivo Maíz Yacuiba"
    assert loaded_sim.parametro.capacidad_suelo == Decimal("120.00")
    assert loaded_sim.parametro.configuracion_json["zone"] == "yacuiba"
    assert loaded_sim.resultado.deficit_maximo == Decimal("0.7812")
    assert len(loaded_sim.rendimientos) == 1
    assert loaded_sim.rendimientos[0].modalidad == "hibrido"
    assert len(loaded_sim.fuentes_datos) == 1
    assert loaded_sim.fuentes_datos[0].formato == "csv"
    assert len(loaded_sim.eventos) == 1
    assert loaded_sim.eventos[0].nivel == "INFO"
    print(f"\n[OK] Simulación y sus 5 relaciones satélites insertadas y recuperadas correctamente ({sim_id}).")


def test_cascade_delete(db_session):
    """Comprueba que al eliminar una simulación, todos sus registros dependientes se eliminan automáticamente."""
    sim_id = f"SIM-{uuid4().hex[:12].upper()}"

    sim = Simulacion(
        id=sim_id,
        nombre="Simulación a Eliminar en Cascada",
        fuente_datos="INIAF",
        escenario="historico",
        cantidad_escenarios=1,
        dias=90,
        estado="failed",
    )

    Parametro(
        simulacion=sim,
        agua_inicial=Decimal("15.00"),
        capacidad_suelo=Decimal("100.00"),
        umbral_hidrico=Decimal("50.00"),
        configuracion_json={"zone": "villamontes"},
    )
    Resultado(
        simulacion=sim,
        deficit_medio=Decimal("0.5000"),
        deficit_maximo=Decimal("0.8500"),
        agua_final_media=Decimal("30.00"),
        agua_minima=Decimal("10.00"),
    )
    Rendimiento(
        simulacion=sim,
        modalidad="secuencial",
        hilos=1,
        procesos=1,
        nodos=1,
        tiempo_segundos=Decimal("45.2000"),
    )
    EventoEjecucion(simulacion=sim, nivel="ERROR", mensaje="Error de convergencia")

    db_session.add(sim)
    db_session.flush()

    # Confirmar inserción previa
    assert db_session.get(Simulacion, sim_id) is not None

    # Eliminar simulación
    db_session.delete(sim)
    db_session.flush()

    # Comprobar que no quedó ningún registro satélite huérfano
    param_count = db_session.execute(
        select(Parametro).where(Parametro.simulacion_id == sim_id)
    ).scalars().all()
    res_count = db_session.execute(
        select(Resultado).where(Resultado.simulacion_id == sim_id)
    ).scalars().all()
    rend_count = db_session.execute(
        select(Rendimiento).where(Rendimiento.simulacion_id == sim_id)
    ).scalars().all()
    event_count = db_session.execute(
        select(EventoEjecucion).where(EventoEjecucion.simulacion_id == sim_id)
    ).scalars().all()

    assert len(param_count) == 0
    assert len(res_count) == 0
    assert len(rend_count) == 0
    assert len(event_count) == 0
    print(f"\n[OK] Eliminación en cascada comprobada exitosamente para {sim_id}.")


def test_check_constraints(db_session):
    """Comprueba que las restricciones CHECK rechazan valores inválidos."""
    # 1. Días fuera de rango (0 días)
    with pytest.raises(IntegrityError):
        invalid_sim = Simulacion(
            id=f"SIM-{uuid4().hex[:12].upper()}",
            nombre="Sim Inválida",
            fuente_datos="Test",
            escenario="historico",
            cantidad_escenarios=1,
            dias=0,  # Inválido: debe ser entre 1 y 365
            estado="pending",
        )
        db_session.add(invalid_sim)
        db_session.flush()
    db_session.rollback()

    # 2. Estado no permitido
    with pytest.raises(IntegrityError):
        invalid_sim = Simulacion(
            id=f"SIM-{uuid4().hex[:12].upper()}",
            nombre="Sim Inválida",
            fuente_datos="Test",
            escenario="historico",
            cantidad_escenarios=1,
            dias=90,
            estado="estado_desconocido",  # Inválido
        )
        db_session.add(invalid_sim)
        db_session.flush()
    db_session.rollback()

    # 3. Déficit medio fuera del rango [0, 1]
    with pytest.raises(IntegrityError):
        sim = Simulacion(
            id=f"SIM-{uuid4().hex[:12].upper()}",
            nombre="Sim Base",
            fuente_datos="Test",
            escenario="historico",
            cantidad_escenarios=1,
            dias=90,
            estado="pending",
        )
        db_session.add(sim)
        db_session.flush()

        invalid_res = Resultado(
            simulacion=sim,
            deficit_medio=Decimal("1.5000"),  # Inválido: debe ser <= 1
            deficit_maximo=Decimal("0.5000"),
            agua_final_media=Decimal("20.00"),
            agua_minima=Decimal("10.00"),
        )
        db_session.add(invalid_res)
        db_session.flush()
    db_session.rollback()

    # 4. Modalidad no permitida en rendimiento
    with pytest.raises(IntegrityError):
        sim = Simulacion(
            id=f"SIM-{uuid4().hex[:12].upper()}",
            nombre="Sim Base 2",
            fuente_datos="Test",
            escenario="historico",
            cantidad_escenarios=1,
            dias=90,
            estado="pending",
        )
        db_session.add(sim)
        db_session.flush()

        invalid_rend = Rendimiento(
            simulacion=sim,
            modalidad="cuantica",  # Inválido
            hilos=1,
            procesos=1,
            nodos=1,
            tiempo_segundos=Decimal("10.0"),
        )
        db_session.add(invalid_rend)
        db_session.flush()
    db_session.rollback()

    print("\n[OK] Todas las restricciones CHECK rechazaron correctamente valores inválidos.")

