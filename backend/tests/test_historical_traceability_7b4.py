"""Regresiones de la Fase 7B.4: integridad histórica y trazabilidad."""

import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.simulations import SimulationCreate
from app.db.database import Base, get_db
from app.db.repository import SimulationRepository
from app.main import app
from app.models import (
    Parametro,
    ParametroHistorico,
    RecalibracionSimulacion,
    Simulacion,
    SimulationJob,
)
from app.models.parametro import SOIL_WATER_LIMITS, initial_moisture_check_sql

ROOT = Path(__file__).resolve().parents[2]
VERSIONES = ROOT / "backend" / "alembic" / "versions"


@pytest.fixture()
def contexto():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def configurar_conexion(dbapi_connection, _registro):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
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


def _payload(soil_type="franco_arenoso", moisture=16.0, nombre="Simulación trazable"):
    return {
        "name": nombre,
        "zone": "yacuiba",
        "zoneName": "Yacuiba",
        "department": "Tarija",
        "soilType": soil_type,
        "cornVariety": "iniaf_h1",
        "plantingDate": "2026-11-20",
        "simulationDays": 30,
        "gridConfig": {"rows": 50, "cols": 50, "cellSizeMeters": 50},
        "initialMoisturePercent": moisture,
        "droughtScenario": "moderado_ssp245",
        "engine": "secuencial",
        "openmpThreads": None,
        "mpiProcesses": None,
        "nodesCount": None,
    }


def _crear_historica(fabrica, sim_id, *, soil="suelo_desconocido", agua="20.00", es_demo=False):
    configuracion = {"soilType": soil, "initialMoisturePercent": float(agua)}
    with fabrica() as db:
        simulacion = Simulacion(
            id=sim_id,
            nombre=("[DEMO] Corrida histórica" if es_demo else "Corrida histórica"),
            fuente_datos="regresion",
            escenario="historico",
            dias=30,
            estado="completed",
            es_demo=es_demo,
        )
        db.add(simulacion)
        db.flush()
        parametro = Parametro(
            simulacion_id=sim_id,
            agua_inicial=Decimal(agua),
            capacidad_suelo=Decimal("103.00"),
            umbral_hidrico=Decimal("51.50"),
            configuracion_json=configuracion,
            configuracion_heredada=True,
        )
        db.add(parametro)
        db.flush()
        db.add(
            ParametroHistorico(
                parametro_id=parametro.id,
                simulacion_id=sim_id,
                agua_inicial=Decimal(agua),
                configuracion_json=dict(configuracion),
                tiene_resultado=True,
                motivo="resultado_historico",
                fuente="004_pre_migracion",
                revision="004_humedad_inicial_pmp_cc",
            )
        )
        db.commit()


def test_execute_rechaza_configuracion_historica(contexto):
    client, fabrica = contexto
    sim_id = "SIM-HIST-EXEC"
    _crear_historica(fabrica, sim_id)

    respuesta = client.post(f"/api/simulations/{sim_id}/execute")

    assert respuesta.status_code == 409
    assert "configuración histórica" in respuesta.json()["detail"]
    with fabrica() as db:
        assert db.query(SimulationJob).count() == 0


def test_recalibracion_crea_derivacion_y_no_modifica_original(contexto):
    client, fabrica = contexto
    sim_id = "SIM-HIST-RECAL"
    _crear_historica(fabrica, sim_id)

    respuesta = client.post(
        f"/api/simulations/{sim_id}/recalibrate",
        json={
            "initialMoisturePercent": 8.0,
            "soilType": "arenoso",
            "motivo": "Recalibración trazable de prueba",
        },
    )

    assert respuesta.status_code == 201
    datos = respuesta.json()
    nuevo_id = datos["id"]
    assert nuevo_id != sim_id
    assert datos["status"] == "pending"
    assert datos["requiresRecalibration"] is False

    with fabrica() as db:
        original = db.get(ParametroHistorico, 1)
        assert original.simulacion_id == sim_id
        assert original.original_recuperable is True
        parametro_original = db.query(Parametro).filter_by(simulacion_id=sim_id).one()
        assert parametro_original.agua_inicial == Decimal("20.00")
        assert parametro_original.configuracion_heredada is True
        parametro_nuevo = db.query(Parametro).filter_by(simulacion_id=nuevo_id).one()
        assert parametro_nuevo.agua_inicial == Decimal("8.00")
        assert parametro_nuevo.configuracion_heredada is False
        linaje = db.query(RecalibracionSimulacion).one()
        assert linaje.simulacion_origen_id == sim_id
        assert linaje.simulacion_destino_id == nuevo_id
        assert linaje.parametro_historico_id == original.id

    assert client.post(f"/api/simulations/{sim_id}/execute").status_code == 409
    assert client.post(f"/api/simulations/{nuevo_id}/execute").status_code == 202


def test_respuesta_marca_demo_y_configuracion_historica(contexto):
    client, fabrica = contexto
    sim_id = "SIM-HIST-DEMO"
    _crear_historica(fabrica, sim_id, es_demo=True)

    datos = client.get(f"/api/simulations/{sim_id}").json()

    assert datos["id"] == sim_id
    assert datos["isDemo"] is True
    assert datos["isHistoricalConfig"] is True
    assert datos["requiresRecalibration"] is True
    assert datos["activeJobId"] is None


def test_reconciliacion_pausa_running_sin_trabajo_activo(contexto):
    _, fabrica = contexto
    sin_job = "SIM-RUNNING-SIN-JOB"
    con_job = "SIM-RUNNING-CON-JOB"
    with fabrica() as db:
        for sim_id in (sin_job, con_job):
            db.add(
                Simulacion(
                    id=sim_id,
                    nombre=f"Corrida {sim_id}",
                    fuente_datos="regresion",
                    escenario="historico",
                    dias=30,
                    estado="running",
                )
            )
        db.commit()
        assert SimulationRepository.crear_trabajo_unico(db, con_job) is not None

        assert SimulationRepository.reconciliar_estados_running(db) == 1
        assert db.get(Simulacion, sin_job).estado == "paused"
        assert db.get(Simulacion, con_job).estado == "running"
        eventos = [
            evento.mensaje
            for evento in db.get(Simulacion, sin_job).eventos
            if "sin trabajo activo" in evento.mensaje
        ]
        assert len(eventos) == 1


def test_limites_de_los_cuatro_suelos_en_api(contexto):
    client, _ = contexto
    for suelo, limites in SOIL_WATER_LIMITS.items():
        for humedad in (float(limites[0]), float(limites[1])):
            respuesta = client.post(
                "/api/simulations", json=_payload(suelo, humedad, f"Corrida {suelo}")
            )
            assert respuesta.status_code == 201


def test_rechazo_de_suelo_desconocido_y_ausente_en_api(contexto):
    client, _ = contexto
    for suelo in ("suelo_desconocido", None):
        respuesta = client.post("/api/simulations", json=_payload(suelo, 18.5))
        assert respuesta.status_code == 422
    payload = _payload("arenoso", 8.0)
    payload.pop("soilType")
    assert client.post("/api/simulations", json=payload).status_code == 422


def test_check_sql_coincide_en_modelo_y_migraciones():
    def cargar(nombre):
        ruta = VERSIONES / nombre
        spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo

    esperado = initial_moisture_check_sql()
    assert cargar("004_humedad_inicial_pmp_cc.py").CHECK_SQL == esperado
    assert cargar("005_trazabilidad_historica.py").CHECK_SQL == esperado


def test_null_y_suelo_ausente_rompen_check_de_humedad(contexto):
    _, fabrica = contexto
    for configuracion in ({"soilType": None}, {"engine": "secuencial"}):
        with fabrica() as db:
            simulacion = Simulacion(
                id="SIM-CHECK-NULL",
                nombre="Check NULL",
                fuente_datos="regresion",
                escenario="historico",
                dias=30,
            )
            db.add(simulacion)
            db.flush()
            db.add(
                Parametro(
                    simulacion_id=simulacion.id,
                    agua_inicial=Decimal("18.50"),
                    capacidad_suelo=Decimal("103.00"),
                    umbral_hidrico=Decimal("51.50"),
                    configuracion_json=configuracion,
                )
            )
            with pytest.raises(ValueError, match="soilType"):
                db.commit()
            db.rollback()

    with pytest.raises(ValueError, match="soilType"):
        SimulationCreate(**_payload("suelo_desconocido", 18.5))
