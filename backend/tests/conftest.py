"""Configuración común de PostgreSQL para las pruebas de AgroChaco."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Cargar las variables del proyecto antes de importar los tests.
load_dotenv(PROJECT_ROOT / ".env", override=False)

# Construir una URL segura si no existe DATABASE_URL.
if not os.getenv("DATABASE_URL"):
    password = os.getenv("POSTGRES_PASSWORD")

    if not password:
        raise RuntimeError(
            "Falta POSTGRES_PASSWORD en el archivo .env de AgroChaco."
        )

    database_url = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "agrochaco_user"),
        password=password,
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "agrochaco"),
    )

    os.environ["DATABASE_URL"] = database_url.render_as_string(
        hide_password=False
    )
