"""Pruebas unitarias para el servicio de exportación CSV y JSON de AgroChaco.

Verifica:
1. Exportación de simulación individual a JSON jerárquico completo.
2. Exportación de historial tabular a CSV con cabeceras y codificación UTF-8.
3. Exportación de trazas de eventos a CSV.
4. Exportación de métricas de aceleración HPC a CSV.
5. Manejo de excepciones ante simulaciones nulas.
6. Correcta serialización de tipos Decimal y fechas ISO-8601.
"""

import csv
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.simulations import export_simulation_csv, export_simulation_json
from app.db.repository import SimulationRepository
from app.models import EventoEjecucion, Rendimiento, Simulacion
from app.services.export_service import ExportService

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


def _crear_simulacion_completa(session: Session, sim_id: str) -> Simulacion:
    """Crea una simulación con todas sus 5 entidades satélite para pruebas de exportación."""
    sim = SimulationRepository.crear_simulacion_con_parametros(
        session,
        {
            "id": sim_id,
            "nombre": "Simulación Completa Exportación Ñandú Yacuiba",
            "fuente_datos": "Estación Agroclimatológica Chaco Central",
            "escenario": "moderado_ssp245",
            "cantidad_escenarios": 10,
            "dias": 120,
            "estado": "completed",
            "semilla": 12345,
        },
        {
            "agua_inicial": Decimal("22.50"),
            "capacidad_suelo": Decimal("125.00"),
            "umbral_hidrico": Decimal("62.50"),
            "configuracion_json": {
                "zone": "yacuiba",
                "zoneName": "Yacuiba",
                "cornVariety": "chaco_01_criollo",
                "soilType": "franco_arenoso",
            },
        },
    )

    SimulationRepository.guardar_resultados(
        session,
        sim_id,
        {
            "deficit_medio": Decimal("0.3120"),
            "deficit_maximo": Decimal("0.7250"),
            "agua_final_media": Decimal("48.30"),
            "agua_minima": Decimal("19.50"),
            "escenarios_con_deficit": 3,
            "archivo_detalle": "/results/SIM-EXP/timeline.csv",
        },
    )

    SimulationRepository.guardar_rendimiento(
        session,
        sim_id,
        {
            "modalidad": "hibrido",
            "hilos": 8,
            "procesos": 4,
            "nodos": 2,
            "tiempo_segundos": Decimal("6.8500"),
            "speedup": Decimal("18.7500"),
            "eficiencia": Decimal("0.7812"),
            "repeticion": 1,
        },
    )

    SimulationRepository.registrar_fuente_datos(
        session,
        simulacion_id=sim_id,
        nombre_archivo="serie_yacuiba_2024.csv",
        formato="csv",
        hash_archivo="a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
        periodo="2020-2024",
        descripcion="Datos pluviométricos validados SENAMHI",
    )

    SimulationRepository.registrar_evento(
        session,
        simulacion_id=sim_id,
        nivel="INFO",
        mensaje="Simulación finalizada y métricas de balance hídrico calculadas.",
    )

    return SimulationRepository.obtener_por_id(session, sim_id)


def test_exportar_simulacion_json(db_session):
    """Verifica que el diccionario JSON contenga la estructura esperada y tipos válidos."""
    sim_id = f"SIM-JSON-{uuid4().hex[:8].upper()}"
    sim = _crear_simulacion_completa(db_session, sim_id)

    data = ExportService.exportar_simulacion_json(sim)

    assert data["id"] == sim_id
    assert data["nombre"] == "Simulación Completa Exportación Ñandú Yacuiba"
    assert data["parametros"]["aguaInicial"] == 22.50
    assert data["parametros"]["configuracion"]["zone"] == "yacuiba"
    assert data["resultados"]["deficitMaximo"] == 0.7250
    assert len(data["rendimiento"]) == 1
    assert data["rendimiento"][0]["modalidad"] == "hibrido"
    assert len(data["fuentesDatos"]) == 1
    assert data["fuentesDatos"][0]["formato"] == "csv"
    assert len(data["eventos"]) >= 2

    # Verificar serialización JSON sin errores
    json_str = ExportService.exportar_simulacion_json_str(sim)
    parsed = json.loads(json_str)
    assert parsed["id"] == sim_id


def test_exportar_historial_csv(db_session):
    """Verifica la generación del CSV tabular con cabecera estándar y valores de columnas."""
    sim_id = f"SIM-CSV-{uuid4().hex[:8].upper()}"
    sim = _crear_simulacion_completa(db_session, sim_id)

    csv_content = ExportService.exportar_historial_csv([sim])

    assert "ID_Simulacion,Nombre,Fuente_Datos" in csv_content
    assert sim_id in csv_content
    assert "Yacuiba" in csv_content
    assert "chaco_01_criollo" in csv_content
    assert "0.3120" in csv_content
    assert "hibrido" in csv_content


def test_exportar_eventos_y_rendimientos_csv(db_session):
    """Verifica la exportación individual de eventos y rendimientos a CSV."""
    sim_id = f"SIM-EV-{uuid4().hex[:8].upper()}"
    sim = _crear_simulacion_completa(db_session, sim_id)

    eventos_csv = ExportService.exportar_eventos_csv(sim.eventos)
    assert "ID_Evento,ID_Simulacion,Fecha_Hora,Nivel,Mensaje" in eventos_csv
    assert "INFO" in eventos_csv

    rend_csv = ExportService.exportar_rendimientos_csv(sim.rendimientos)
    assert "ID_Rendimiento,ID_Simulacion,Modalidad,Hilos,Procesos" in rend_csv
    assert "hibrido" in rend_csv
    assert "18.7500" in rend_csv


def test_exportar_metricas_hpc_no_disponibles(db_session):
    """NULL se exporta como null en JSON y vacío en CSV, nunca como 0.0 medido."""
    sim_id = f"SIM-NULL-{uuid4().hex[:8].upper()}"

    SimulationRepository.crear_simulacion_con_parametros(
        db_session,
        {
            "id": sim_id,
            "nombre": "Simulación Sin T1 Pareado",
            "fuente_datos": "SENAMHI",
            "escenario": "historico",
            "cantidad_escenarios": 1,
            "dias": 30,
            "estado": "completed",
        },
        {
            "agua_inicial": Decimal("18.00"),
            "capacidad_suelo": Decimal("100.00"),
            "umbral_hidrico": Decimal("50.00"),
            "configuracion_json": {"engine": "mpi"},
        },
    )

    SimulationRepository.guardar_rendimiento(
        db_session,
        sim_id,
        {
            "modalidad": "mpi",
            "hilos": 1,
            "procesos": 2,
            "nodos": 1,
            "tiempo_segundos": Decimal("0.0682"),
            "speedup": None,
            "eficiencia": None,
            "repeticion": 1,
        },
    )

    sim = SimulationRepository.obtener_por_id(db_session, sim_id)

    data = ExportService.exportar_simulacion_json(sim)
    assert data["rendimiento"][0]["speedup"] is None
    assert data["rendimiento"][0]["eficiencia"] is None
    assert data["rendimiento"][0]["tiempoSegundos"] == 0.0682

    rend_csv = ExportService.exportar_rendimientos_csv(sim.rendimientos)
    filas = list(csv.reader(io.StringIO(rend_csv)))
    assert filas[1][7] == ""
    assert filas[1][8] == ""
    assert "0.0000" not in rend_csv


def test_exportar_simulacion_nula():
    """Verifica que el servicio lance ValueError si se intenta exportar una simulación nula."""
    with pytest.raises(ValueError):
        ExportService.exportar_simulacion_json(None)  # type: ignore


def test_endpoint_exportar_json(db_session):
    """Verifica que el endpoint JSON devuelva la simulación completa como archivo descargable."""
    sim_id = f"SIM-API-JSON-{uuid4().hex[:8].upper()}"
    _crear_simulacion_completa(db_session, sim_id)

    response = export_simulation_json(sim_id, db=db_session)

    assert isinstance(response, Response)
    assert response.media_type == "application/json"
    assert response.headers["content-type"] == "application/json"
    assert response.headers["content-disposition"] == f'attachment; filename="{sim_id}.json"'

    contenido = response.body.decode("utf-8")
    data = json.loads(contenido)
    assert data["id"] == sim_id
    assert data["parametros"]["configuracion"]["zone"] == "yacuiba"
    assert data["resultados"]["deficitMedio"] == 0.3120
    assert data["rendimiento"][0]["modalidad"] == "hibrido"
    assert data["fuentesDatos"][0]["nombreArchivo"] == "serie_yacuiba_2024.csv"
    assert data["eventos"][0]["nivel"] == "INFO"


def test_endpoint_exportar_csv_solo_simulacion_solicitada(db_session):
    """Verifica que el CSV exportado contenga únicamente la simulación solicitada."""
    sim_id = f"SIM-API-CSV-{uuid4().hex[:8].upper()}"
    otro_id = f"SIM-API-OTRA-{uuid4().hex[:8].upper()}"
    _crear_simulacion_completa(db_session, sim_id)
    _crear_simulacion_completa(db_session, otro_id)

    response = export_simulation_csv(sim_id, db=db_session)

    assert isinstance(response, Response)
    assert response.media_type == "text/csv"
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == f'attachment; filename="{sim_id}.csv"'

    contenido = response.body.decode("utf-8")
    filas = list(csv.reader(io.StringIO(contenido)))
    assert filas[0][0] == "ID_Simulacion"
    assert len(filas) == 2
    assert filas[1][0] == sim_id
    assert otro_id not in contenido


def test_endpoint_exportar_id_inexistente_devuelve_404(db_session):
    """Verifica que ambos endpoints devuelvan HTTP 404 para un ID inexistente."""
    sim_id = "SIM-INEXISTENTE-999"

    for endpoint in (export_simulation_json, export_simulation_csv):
        with pytest.raises(HTTPException) as exc_info:
            endpoint(sim_id, db=db_session)
        assert exc_info.value.status_code == 404


def test_endpoint_exportar_json_conserva_metricas_no_disponibles(db_session):
    """Verifica que speedup y eficiencia nulos lleguen como null al JSON del endpoint."""
    sim_id = f"SIM-API-NULL-{uuid4().hex[:8].upper()}"

    SimulationRepository.crear_simulacion_con_parametros(
        db_session,
        {
            "id": sim_id,
            "nombre": "Simulación API Sin T1 Pareado",
            "fuente_datos": "SENAMHI",
            "escenario": "historico",
            "cantidad_escenarios": 1,
            "dias": 30,
            "estado": "completed",
        },
        {
            "agua_inicial": Decimal("18.00"),
            "capacidad_suelo": Decimal("100.00"),
            "umbral_hidrico": Decimal("50.00"),
            "configuracion_json": {"engine": "mpi"},
        },
    )
    SimulationRepository.guardar_rendimiento(
        db_session,
        sim_id,
        {
            "modalidad": "mpi",
            "hilos": 1,
            "procesos": 2,
            "nodos": 1,
            "tiempo_segundos": Decimal("0.0682"),
            "speedup": None,
            "eficiencia": None,
            "repeticion": 1,
        },
    )

    response = export_simulation_json(sim_id, db=db_session)
    contenido = response.body.decode("utf-8")
    data = json.loads(contenido)

    assert data["rendimiento"][0]["speedup"] is None
    assert data["rendimiento"][0]["eficiencia"] is None
    assert '"speedup": null' in contenido
    assert '"eficiencia": null' in contenido
    assert "0.0000" not in contenido
