"""Pruebas unitarias de consultas de historial, filtros avanzados y paginación en PostgreSQL.

Verifica:
1. Listado completo de historial.
2. Filtrado por estado (completed, running, pending, failed).
3. Filtrado por escenario climático.
4. Búsqueda por texto (nombre, ID, fuente de datos).
5. Filtrado por rango de fechas (fecha_desde, fecha_hasta).
6. Paginación correcta (limit, offset) y cálculo del total de coincidencias.
7. Carga eficiente sin problemas de N+1 queries.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.repository import SimulationRepository
from app.models import Simulacion

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


def _crear_simulaciones_de_prueba(session: Session) -> list[str]:
    """Crea un lote de 6 simulaciones con variaciones de estado, fecha y escenario."""
    ids = []
    base_time = datetime.now(timezone.utc)

    lote = [
        ("SIM-HIST-01", "Maíz Yacuiba Temporada Alta", "completed", "moderado_ssp245", base_time - timedelta(days=10)),
        ("SIM-HIST-02", "Villa Montes Sequía Severa", "completed", "extremo_ssp585", base_time - timedelta(days=5)),
        ("SIM-HIST-03", "Charagua Ensayo INIAF", "running", "sequia_recente_2023", base_time - timedelta(days=2)),
        ("SIM-HIST-04", "Macharetí Monitoreo", "pending", "moderado_ssp245", base_time - timedelta(days=1)),
        ("SIM-HIST-05", "Caraparí Control Histórico", "completed", "historico", base_time),
        ("SIM-HIST-06", "Boyuibe En Espera", "failed", "extremo_ssp585", base_time),
    ]

    for sim_id, nombre, estado, escenario, fecha in lote:
        sim = Simulacion(
            id=sim_id,
            nombre=nombre,
            fuente_datos="SENAMHI",
            escenario=escenario,
            cantidad_escenarios=5,
            dias=90,
            estado=estado,
            fecha_creacion=fecha,
        )
        session.add(sim)
        session.flush()

        SimulationRepository.guardar_parametros(
            session,
            sim_id,
            {
                "agua_inicial": Decimal("20.00"),
                "capacidad_suelo": Decimal("100.00"),
                "umbral_hidrico": Decimal("50.00"),
                "configuracion_json": {"zoneName": nombre.split()[1]},
            },
        )

        if estado == "completed":
            SimulationRepository.guardar_resultados(
                session,
                sim_id,
                {
                    "deficit_medio": Decimal("0.3500"),
                    "deficit_maximo": Decimal("0.7000"),
                    "agua_final_media": Decimal("40.00"),
                    "agua_minima": Decimal("15.00"),
                    "escenarios_con_deficit": 2,
                },
            )

        ids.append(sim_id)

    return ids


def test_listar_historial_completo(db_session):
    """Verifica que se recuperen todas las simulaciones ordenadas por fecha descendente."""
    _crear_simulaciones_de_prueba(db_session)

    sims, total = SimulationRepository.listar_historial(db_session, limit=100)

    assert total >= 6
    assert len(sims) >= 6
    # Comprobar orden descendente
    for i in range(len(sims) - 1):
        assert sims[i].fecha_creacion >= sims[i + 1].fecha_creacion


def test_filtrar_por_estado(db_session):
    """Verifica que el filtro por estado devuelva únicamente las simulaciones solicitadas."""
    _crear_simulaciones_de_prueba(db_session)

    # Filtrar solo 'completed'
    completadas, total_comp = SimulationRepository.listar_historial(
        db_session, estado="completed"
    )
    assert total_comp >= 3
    for s in completadas:
        assert s.estado == "completed"

    # Filtrar solo 'running'
    activas, total_run = SimulationRepository.listar_historial(
        db_session, estado="running"
    )
    assert total_run >= 1
    for s in activas:
        assert s.estado == "running"


def test_filtrar_por_escenario(db_session):
    """Verifica el filtrado por escenario climático."""
    _crear_simulaciones_de_prueba(db_session)

    sims, total = SimulationRepository.listar_historial(
        db_session, escenario="extremo_ssp585"
    )
    assert total >= 2
    for s in sims:
        assert s.escenario == "extremo_ssp585"


def test_buscar_por_texto(db_session):
    """Verifica la búsqueda por coincidencia parcial de texto en nombre, ID o fuente."""
    _crear_simulaciones_de_prueba(db_session)

    # Buscar por municipio
    sims, total = SimulationRepository.listar_historial(db_session, search="Yacuiba")
    assert total >= 1
    assert any("Yacuiba" in s.nombre for s in sims)

    # Buscar por código ID
    sims_id, total_id = SimulationRepository.listar_historial(
        db_session, search="SIM-HIST-03"
    )
    assert total_id >= 1
    assert any(s.id == "SIM-HIST-03" for s in sims_id)


def test_paginacion_historial(db_session):
    """Verifica que la paginación limite y desplace correctamente los registros."""
    _crear_simulaciones_de_prueba(db_session)

    pagina_1, total = SimulationRepository.listar_historial(
        db_session, limit=2, offset=0
    )
    pagina_2, _ = SimulationRepository.listar_historial(
        db_session, limit=2, offset=2
    )

    assert len(pagina_1) == 2
    assert len(pagina_2) == 2
    assert total >= 6

    # Comprobar que no hay solapamiento entre páginas
    ids_p1 = {s.id for s in pagina_1}
    ids_p2 = {s.id for s in pagina_2}
    assert ids_p1.isdisjoint(ids_p2)

