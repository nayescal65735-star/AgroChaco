"""Módulo de modelos SQLAlchemy para AgroChaco.

Exporta los seis modelos de dominio biofísico, parámetros y ejecución:
- Simulacion
- Parametro
- Resultado
- Rendimiento
- FuenteDatos
- EventoEjecucion
"""

from app.db.database import Base
from app.models.evento_ejecucion import EventoEjecucion
from app.models.fuente_datos import FuenteDatos
from app.models.parametro import Parametro
from app.models.rendimiento import Rendimiento
from app.models.resultado import Resultado
from app.models.simulacion import Simulacion

__all__ = [
    "Base",
    "Simulacion",
    "Parametro",
    "Resultado",
    "Rendimiento",
    "FuenteDatos",
    "EventoEjecucion",
]

