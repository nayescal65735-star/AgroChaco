"""Regresiones de integridad hídrica de la Fase 7B.2A."""

import importlib.util
import json
import os
import re
import subprocess
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from dotenv import dotenv_values
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.api.simulations import (
    GridConfig,
    SimulationCreate,
    _format_simulation_response,
    create_simulation,
)
from app.models import Base, Parametro, Simulacion
from app.models.parametro import (
    SOIL_WATER_LIMITS,
    initial_moisture_check_sql,
    sincronizar_humedad_json,
    validar_humedad_inicial,
)
from app.services.export_service import ExportService
from app.services.motor_service import MotorService

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
MIGRATION_PATH = BACKEND / "alembic/versions/004_humedad_inicial_pmp_cc.py"


def _payload(soil_type, moisture, **overrides):
    data = {
        "name": "Hidrologia 7B2A",
        "zone": "yacuiba",
        "zoneName": "Yacuiba",
        "department": "Tarija",
        "soilType": soil_type,
        "cornVariety": "iniaf_h1",
        "plantingDate": date(2026, 11, 20),
        "simulationDays": 30,
        "gridConfig": GridConfig(rows=50, cols=50, cellSizeMeters=50),
        "initialMoisturePercent": moisture,
        "droughtScenario": "moderado_ssp245",
        "engine": "secuencial",
        "openmpThreads": None,
        "mpiProcesses": None,
        "nodesCount": None,
    }
    data.update(overrides)
    return data


def _cargar_migracion():
    spec = importlib.util.spec_from_file_location("migracion_004", MIGRATION_PATH)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("soil_type", ["suelo_desconocido", None])
def test_suelo_desconocido_o_nulo_rechazado_por_api(soil_type):
    with pytest.raises(ValidationError):
        SimulationCreate(**_payload(soil_type, 18.5))


def test_suelo_ausente_rechazado_por_api():
    data = _payload("franco_arenoso", 18.5)
    data.pop("soilType")
    with pytest.raises(ValidationError):
        SimulationCreate(**data)


@pytest.mark.parametrize(
    "configuracion",
    [
        {"soilType": "suelo_desconocido"},
        {"soilType": None},
        {"engine": "secuencial"},
    ],
)
def test_suelo_invalido_rechazado_porm_y_sql(configuracion):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        simulacion = Simulacion(
            id=f"SIM-7B2A-{uuid.uuid4().hex[:8]}",
            nombre="Suelo invalido",
            fuente_datos="regresion",
            escenario="historico",
            dias=30,
        )
        session.add(simulacion)
        session.commit()
        session.add(
            Parametro(
                simulacion_id=simulacion.id,
                agua_inicial=Decimal("18.50"),
                capacidad_suelo=Decimal("103.00"),
                umbral_hidrico=Decimal("51.50"),
                configuracion_json=configuracion,
            )
        )
        with pytest.raises(ValueError, match="soilType"):
            session.commit()
        session.rollback()

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO simulaciones "
                    "(id, nombre, fuente_datos, escenario, dias) "
                    "VALUES ('SIM-7B2A-SQL', 'sql', 'regresion', 'historico', 30)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO parametros "
                    "(simulacion_id, agua_inicial, capacidad_suelo, umbral_hidrico, configuracion_json) "
                    "VALUES ('SIM-7B2A-SQL', 18.50, 103.00, 51.50, :configuracion)"
                ),
                {"configuracion": json.dumps(configuracion)},
            )
    engine.dispose()


@pytest.mark.parametrize(
    "suelo,pmp,cc",
    [(suelo, limites[0], limites[1]) for suelo, limites in SOIL_WATER_LIMITS.items()],
)
def test_humedad_en_pmp_y_cc_aceptada(suelo, pmp, cc):
    for humedad in (pmp, cc):
        assert validar_humedad_inicial(humedad, suelo) == humedad
        assert SimulationCreate(**_payload(suelo, float(humedad))).initialMoisturePercent == pytest.approx(
            float(humedad)
        )


@pytest.mark.parametrize(
    "suelo,humedad",
    [
        (suelo, limites[0] - Decimal("0.01"))
        for suelo, limites in SOIL_WATER_LIMITS.items()
    ]
    + [
        (suelo, limites[1] + Decimal("0.01"))
        for suelo, limites in SOIL_WATER_LIMITS.items()
    ],
)
def test_humedad_fuera_de_limites_rechazada(suelo, humedad):
    with pytest.raises(ValidationError, match="humedad inicial"):
        SimulationCreate(**_payload(suelo, float(humedad)))


def test_inconsistencia_entre_columna_y_json_se_normaliza_en_lectura():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sim_id = "SIM-7B2A-INC"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO simulaciones "
                "(id, nombre, fuente_datos, escenario, dias) "
                "VALUES (:id, 'inconsistente', 'regresion', 'historico', 30)"
            ),
            {"id": sim_id},
        )
        connection.execute(
            text(
                "INSERT INTO parametros "
                "(simulacion_id, agua_inicial, capacidad_suelo, umbral_hidrico, configuracion_json) "
                "VALUES (:id, 8.40, 72.00, 36.00, :configuracion)"
            ),
            {
                "id": sim_id,
                "configuracion": json.dumps(
                    {"soilType": "arenoso", "initialMoisturePercent": 11.50}
                ),
            },
        )

    with Session(engine) as session:
        sim = session.get(Simulacion, sim_id)
        assert sim.parametro.agua_inicial == Decimal("8.40")
        respuesta = _format_simulation_response(sim)
        assert respuesta["config"]["initialMoisturePercent"] == pytest.approx(8.4)
        exportado = ExportService.exportar_simulacion_json(sim)
        assert exportado["parametros"]["configuracion"]["initialMoisturePercent"] == pytest.approx(8.4)
        configuracion_motor = sincronizar_humedad_json(
            sim.parametro.configuracion_json, sim.parametro.agua_inicial
        )
        motor = MotorService.construir_configuracion_json(sim_id, configuracion_motor)
        assert motor["initialMoisturePercent"] == pytest.approx(8.4)
    engine.dispose()


def test_respuesta_no_asigna_suelo_ficticio_a_registro_ambiguo():
    sim = Simulacion(
        id="SIM-7B2A-AMB",
        nombre="ambiguo",
        fuente_datos="regresion",
        escenario="historico",
        dias=30,
    )
    sim.parametro = Parametro(
        agua_inicial=Decimal("8.40"),
        capacidad_suelo=Decimal("72.00"),
        umbral_hidrico=Decimal("36.00"),
        configuracion_json={"initialMoisturePercent": 99.0},
    )
    respuesta = _format_simulation_response(sim)
    assert "soilType" not in respuesta["config"]
    assert respuesta["config"]["initialMoisturePercent"] == pytest.approx(8.4)


def test_creacion_api_usa_agua_inicial_como_canonica_con_precision_decimal():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        respuesta = create_simulation(SimulationCreate(**_payload("franco", 20.005)), session)
        parametro = session.query(Parametro).one()
        assert parametro.agua_inicial == Decimal("20.01")
        assert parametro.configuracion_json["initialMoisturePercent"] == pytest.approx(20.01)
        assert respuesta["config"]["initialMoisturePercent"] == pytest.approx(20.01)
    engine.dispose()


def test_motor_rechaza_configuracion_sin_suelo():
    with pytest.raises(ValueError, match="soilType"):
        MotorService.construir_configuracion_json(
            "SIM-7B2A-MOTOR", {"engine": "secuencial", "simulationDays": 30}
        )


def test_limites_motor_python_y_sql_coinciden_exactamente():
    codigo = (ROOT / "motor/src/agronomic_data.cpp").read_text(encoding="utf-8")
    bloque = codigo.split("static const std::vector<SoilInfo> SOILS = {", 1)[1].split("};", 1)[0]
    encontrados = re.findall(
        r"SoilType::(\w+),.*?(\d+\.\d+),\s*(\d+\.\d+),\s*(\d+\.\d+)",
        bloque,
        re.DOTALL,
    )
    equivalencias = {
        "FRANCO_ARENOSO": "franco_arenoso",
        "FRANCO_ARCILLOSO": "franco_arcilloso",
        "ARENOSO": "arenoso",
        "FRANCO": "franco",
    }
    assert len(encontrados) == 4
    migracion = _cargar_migracion()
    sql_backend = initial_moisture_check_sql()
    assert sql_backend == migracion.CHECK_SQL
    for enum_cpp, cc, pmp, _capacidad in encontrados:
        suelo = equivalencias[enum_cpp]
        pmp_sql = Decimal(pmp).quantize(Decimal("0.01"))
        cc_sql = Decimal(cc).quantize(Decimal("0.01"))
        assert SOIL_WATER_LIMITS[suelo] == (pmp_sql, cc_sql)
        restriccion = (
            f"WHEN '{suelo}' THEN agua_inicial BETWEEN {pmp_sql} AND {cc_sql}"
        )
        assert restriccion in sql_backend
        assert restriccion in migracion.CHECK_SQL


def test_migracion_004_repara_y_consolida_sin_tocar_resultados():
    migracion = _cargar_migracion()
    assert initial_moisture_check_sql() == migracion.CHECK_SQL

    cfg = dotenv_values(ROOT / ".env")
    host = cfg.get("POSTGRES_HOST", "localhost")
    port = int(cfg.get("POSTGRES_PORT", "5432"))
    usuario, clave = cfg["POSTGRES_USER"], cfg["POSTGRES_PASSWORD"]
    db_tmp = f"agrochaco_7b2a_{uuid.uuid4().hex[:8]}"

    def admin():
        return psycopg.connect(
            host=host, port=port, dbname="postgres", user=usuario, password=clave, autocommit=True
        )

    def temporal():
        return psycopg.connect(
            host=host, port=port, dbname=db_tmp, user=usuario, password=clave
        )

    entorno = os.environ.copy()
    entorno["DATABASE_URL"] = URL.create(
        "postgresql+psycopg",
        username=usuario,
        password=clave,
        host=host,
        port=port,
        database=db_tmp,
    ).render_as_string(hide_password=False)

    def alembic(*argumentos):
        resultado = subprocess.run(
            [str(BACKEND / "venv/bin/alembic"), *argumentos],
            cwd=BACKEND,
            env=entorno,
            text=True,
            capture_output=True,
        )
        if resultado.returncode:
            raise RuntimeError(f"alembic {' '.join(argumentos)} falló:\n{resultado.stderr}")

    def insertar(sim_id, estado, agua, configuracion, con_resultado=False):
        with temporal() as conn:
            conn.execute(
                "INSERT INTO simulaciones "
                "(id, nombre, fuente_datos, escenario, dias, estado) "
                "VALUES (%s, 'migracion', 'regresion', 'historico', 30, %s)",
                (sim_id, estado),
            )
            conn.execute(
                "INSERT INTO parametros "
                "(simulacion_id, agua_inicial, capacidad_suelo, umbral_hidrico, configuracion_json) "
                "VALUES (%s, %s, 103.00, 51.50, %s)",
                (sim_id, agua, psycopg.types.json.Json(configuracion)),
            )
            if con_resultado:
                conn.execute(
                    "INSERT INTO resultados "
                    "(simulacion_id, deficit_medio, deficit_maximo, agua_final_media, agua_minima, "
                    "escenarios_con_deficit) "
                    "VALUES (%s, 0.1234, 0.5678, 45.67, 12.34, 1)",
                    (sim_id,),
                )

    def intentar_insertar(sim_id, agua, configuracion):
        try:
            with temporal() as conn:
                conn.execute(
                    "INSERT INTO simulaciones "
                    "(id, nombre, fuente_datos, escenario, dias) "
                    "VALUES (%s, 'nueva', 'regresion', 'historico', 30)",
                    (sim_id,),
                )
                conn.execute(
                    "INSERT INTO parametros "
                    "(simulacion_id, agua_inicial, capacidad_suelo, umbral_hidrico, configuracion_json) "
                    "VALUES (%s, %s, 103.00, 51.50, %s)",
                    (sim_id, agua, psycopg.types.json.Json(configuracion)),
                )
        except psycopg.errors.CheckViolation:
            return False
        return True

    with admin() as conn:
        conn.execute(f'CREATE DATABASE "{db_tmp}"')
    try:
        alembic("upgrade", "003_simulation_jobs")
        with temporal() as conn:
            conn.execute("ALTER TABLE parametros DROP CONSTRAINT IF EXISTS chk_parametros_agua_inicial")
        insertar(
            "SIM-7B2A-KNOWN",
            "completed",
            Decimal("22.50"),
            {"soilType": "franco_arenoso", "initialMoisturePercent": 21.0},
            con_resultado=True,
        )
        insertar(
            "SIM-7B2A-UNKNOWN",
            "pending",
            Decimal("20.00"),
            {"soilType": "suelo_desconocido", "initialMoisturePercent": 15.0},
        )
        insertar(
            "SIM-7B2A-MISSING",
            "pending",
            Decimal("10.00"),
            {"initialMoisturePercent": 99.0},
        )
        insertar(
            "SIM-7B2A-NULL",
            "pending",
            Decimal("10.00"),
            {"soilType": None, "initialMoisturePercent": 99.0},
        )
        with temporal() as conn:
            resultado_antes = conn.execute(
                "SELECT deficit_medio, deficit_maximo, agua_final_media, agua_minima "
                "FROM resultados WHERE simulacion_id = 'SIM-7B2A-KNOWN'"
            ).fetchone()

        alembic("upgrade", "head")

        with temporal() as conn:
            filas = {
                fila[0]: (Decimal(str(fila[1])), fila[2])
                for fila in conn.execute(
                    "SELECT simulacion_id, agua_inicial, configuracion_json FROM parametros"
                ).fetchall()
            }
            resultado_despues = conn.execute(
                "SELECT deficit_medio, deficit_maximo, agua_final_media, agua_minima "
                "FROM resultados WHERE simulacion_id = 'SIM-7B2A-KNOWN'"
            ).fetchone()
            estado_despues = conn.execute(
                "SELECT estado FROM simulaciones WHERE id = 'SIM-7B2A-KNOWN'"
            ).fetchone()[0]

        agua, configuracion = filas["SIM-7B2A-KNOWN"]
        assert agua == Decimal("18.50")
        assert Decimal(str(configuracion["initialMoisturePercent"])) == agua
        for sim_id, suelo_esperado in (
            ("SIM-7B2A-UNKNOWN", "suelo_desconocido"),
            ("SIM-7B2A-MISSING", None),
            ("SIM-7B2A-NULL", None),
        ):
            agua_ambigua, configuracion_ambigua = filas[sim_id]
            assert configuracion_ambigua.get("soilType") == suelo_esperado
            assert Decimal(str(configuracion_ambigua["initialMoisturePercent"])) == agua_ambigua
        assert "soilType" not in filas["SIM-7B2A-MISSING"][1]
        assert "soilType" in filas["SIM-7B2A-NULL"][1]
        assert resultado_despues == resultado_antes
        assert estado_despues == "completed"

        assert not intentar_insertar(
            "SIM-7B2A-NEW-UNKNOWN", Decimal("18.50"), {"soilType": "suelo_desconocido"}
        )
        assert not intentar_insertar("SIM-7B2A-NEW-MISSING", Decimal("18.50"), {})
        assert not intentar_insertar(
            "SIM-7B2A-NEW-NULL", Decimal("18.50"), {"soilType": None}
        )
        assert not intentar_insertar(
            "SIM-7B2A-NEW-OUT", Decimal("16.00"), {"soilType": "arenoso"}
        )
        assert intentar_insertar(
            "SIM-7B2A-NEW-OK", Decimal("12.00"), {"soilType": "arenoso"}
        )
    finally:
        with admin() as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{db_tmp}" WITH (FORCE)')
