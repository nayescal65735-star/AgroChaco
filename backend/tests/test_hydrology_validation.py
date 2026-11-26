"""Pruebas T13-T19 de integridad hídrica en la capa backend."""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.simulations import GridConfig, SimulationCreate
from app.models import Base, Parametro, Simulacion
from app.services.motor_service import MotorService


def _payload(soil_type: str, moisture: float, **overrides):
    data = {
        "name": f"Hidrologia {soil_type}",
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


def test_t13_api_rechaza_humedad_inferior_pmp():
    with pytest.raises(ValidationError) as exc:
        SimulationCreate(**_payload("franco_arcilloso", 17.4))
    assert "humedad inicial" in str(exc.value).lower()


def test_t14_api_rechaza_humedad_superior_cc():
    with pytest.raises(ValidationError) as exc:
        SimulationCreate(**_payload("arenoso", 12.1))
    assert "humedad inicial" in str(exc.value).lower()


def test_t14_api_acepta_humedad_en_limite_cc():
    payload = SimulationCreate(**_payload("franco_arenoso", 18.5))
    assert payload.initialMoisturePercent == pytest.approx(18.5)


def test_t15_modelo_rechaza_humedad_incompatible_con_suelo():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        simulacion = Simulacion(
            id="SIM-HID-001",
            nombre="Validacion humedad",
            fuente_datos="test",
            escenario="historico",
            dias=30,
        )
        session.add(simulacion)
        session.commit()

        session.add(
            Parametro(
                simulacion_id=simulacion.id,
                agua_inicial=Decimal("16.00"),
                capacidad_suelo=Decimal("72.00"),
                umbral_hidrico=Decimal("36.00"),
                configuracion_json={"soilType": "arenoso"},
            )
        )
        with pytest.raises(ValueError) as exc:
            session.commit()
        assert "humedad inicial" in str(exc.value).lower()
        session.rollback()

        session.add(
            Parametro(
                simulacion_id=simulacion.id,
                agua_inicial=Decimal("12.00"),
                capacidad_suelo=Decimal("72.00"),
                umbral_hidrico=Decimal("36.00"),
                configuracion_json={"soilType": "arenoso"},
            )
        )
        session.commit()
        assert session.query(Parametro).one().agua_inicial == Decimal("12.00")

    engine.dispose()


def test_t15_check_base_de_datos_rechaza_humedad_incompatible():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO simulaciones "
                "(id, nombre, fuente_datos, escenario, dias) "
                "VALUES ('SIM-HID-002', 'check db', 'test', 'historico', 30)"
            )
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO parametros "
                    "(simulacion_id, agua_inicial, capacidad_suelo, umbral_hidrico, configuracion_json) "
                    "VALUES ('SIM-HID-002', 16.00, 72.00, 36.00, json_object('soilType', 'arenoso'))"
                )
            )

    engine.dispose()


def test_t16_api_rechaza_precipitacion_negativa_no_declarada():
    with pytest.raises(ValidationError):
        SimulationCreate(**_payload("franco_arenoso", 18.0, precipitationMm=-5.0))


def test_t18_valor_por_defecto_del_motor_es_compatible_con_el_suelo():
    configuracion = MotorService.construir_configuracion_json(
        "SIM-HID-003",
        {
            "soilType": "arenoso",
            "gridConfig": {"rows": 50, "cols": 50, "cellSizeMeters": 50},
        },
    )
    assert configuracion["initialMoisturePercent"] == pytest.approx(8.4)
