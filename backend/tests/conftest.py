"""Configuración común: todas las suites PostgreSQL usan una base temporal aislada."""

import atexit
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env", override=False)

_usuario = os.getenv("POSTGRES_USER", "agrochaco_user")
_clave = os.getenv("POSTGRES_PASSWORD")
if not _clave:
    raise RuntimeError("Falta POSTGRES_PASSWORD en el archivo .env de AgroChaco.")

_host = os.getenv("POSTGRES_HOST", "localhost")
_puerto = int(os.getenv("POSTGRES_PORT", "5432"))
_base_temporal = f"agrochaco_tests_{uuid4().hex[:8]}"


def _url_postgres(base_de_datos: str) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=_usuario,
        password=_clave,
        host=_host,
        port=_puerto,
        database=base_de_datos,
    )


_admin = create_engine(
    _url_postgres("postgres"), isolation_level="AUTOCOMMIT", pool_pre_ping=True
)
with _admin.connect() as conexion:
    conexion.execute(text(f'CREATE DATABASE "{_base_temporal}"'))

DATABASE_URL = _url_postgres(_base_temporal).render_as_string(hide_password=False)
os.environ["DATABASE_URL"] = DATABASE_URL

from app.db.database import Base  # noqa: E402
from app import models  # noqa: E402, F401

_aislado = create_engine(DATABASE_URL, pool_pre_ping=True)
Base.metadata.create_all(_aislado)
_aislado.dispose()


def _eliminar_base_temporal() -> None:
    motor = create_engine(
        _url_postgres("postgres"), isolation_level="AUTOCOMMIT", pool_pre_ping=True
    )
    try:
        with motor.connect() as conexion:
            conexion.execute(
                text(f'DROP DATABASE IF EXISTS "{_base_temporal}" WITH (FORCE)')
            )
    finally:
        motor.dispose()


atexit.register(_eliminar_base_temporal)
