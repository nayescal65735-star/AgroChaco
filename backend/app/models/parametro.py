"""Modelo SQLAlchemy para los parámetros agronómicos y de configuración de la simulación."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.db.database import Base


SOIL_WATER_LIMITS: dict[str, tuple[Decimal, Decimal]] = {
    "franco_arenoso": (Decimal("8.20"), Decimal("18.50")),
    "franco_arcilloso": (Decimal("17.50"), Decimal("31.00")),
    "arenoso": (Decimal("4.80"), Decimal("12.00")),
    "franco": (Decimal("11.00"), Decimal("24.00")),
}
SOIL_TYPES = tuple(SOIL_WATER_LIMITS)
SOIL_MOISTURE_DOMAIN = (Decimal("0.00"), Decimal("100.00"))
MOISTURE_QUANTUM = Decimal("0.01")


def validar_soil_type(soil_type: object) -> str:
    if not isinstance(soil_type, str) or soil_type not in SOIL_WATER_LIMITS:
        raise ValueError(f"soilType debe ser uno de: {', '.join(SOIL_TYPES)}.")
    return soil_type


def soil_moisture_limits(soil_type: object) -> tuple[Decimal, Decimal]:
    return SOIL_WATER_LIMITS[validar_soil_type(soil_type)]


def initial_moisture_check_sql() -> str:
    cases = " ".join(
        f"WHEN '{soil}' THEN agua_inicial BETWEEN {limits[0]} AND {limits[1]}"
        for soil, limits in SOIL_WATER_LIMITS.items()
    )
    tipos = ", ".join(f"'{soil}'" for soil in SOIL_TYPES)
    return (
        "configuracion_heredada OR ("
        f"configuracion_json->>'soilType' IS NOT NULL "
        f"AND configuracion_json->>'soilType' IN ({tipos}) "
        "AND agua_inicial >= 0 AND agua_inicial <= 100 "
        f"AND (CASE configuracion_json->>'soilType' {cases} ELSE 1 = 0 END)"
        ")"
    )


def canonizar_humedad_inicial(agua_inicial: object) -> Decimal:
    try:
        value = Decimal(str(agua_inicial))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("La humedad inicial debe ser un valor decimal finito.") from exc
    if not value.is_finite():
        raise ValueError("La humedad inicial debe ser un valor decimal finito.")
    try:
        return value.quantize(MOISTURE_QUANTUM, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError("La humedad inicial debe ser un valor decimal finito.") from exc


def validar_humedad_inicial(agua_inicial: object, soil_type: object) -> Decimal:
    soil = validar_soil_type(soil_type)
    value = canonizar_humedad_inicial(agua_inicial)
    low, high = SOIL_WATER_LIMITS[soil]
    if not (low <= value <= high):
        raise ValueError(
            f"La humedad inicial debe estar entre {low}% y {high}% para el suelo seleccionado."
        )
    return value


def sincronizar_humedad_json(configuracion: object, agua_inicial: object) -> dict[str, Any]:
    config = dict(configuracion) if isinstance(configuracion, dict) else {}
    config["initialMoisturePercent"] = float(canonizar_humedad_inicial(agua_inicial))
    return config


class Parametro(Base):
    """Parámetros biofísicos de suelo, agua y configuración espacial JSON."""

    __tablename__ = "parametros"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    simulacion_id = Column(
        String(36),
        ForeignKey("simulaciones.id", ondelete="CASCADE"),
        nullable=False,
    )
    agua_inicial = Column(Numeric(8, 2), nullable=False)
    capacidad_suelo = Column(Numeric(8, 2), nullable=False)
    umbral_hidrico = Column(Numeric(8, 2), nullable=False)

    configuracion_json = Column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
    )
    configuracion_heredada = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    __table_args__ = (
        CheckConstraint(
            initial_moisture_check_sql(),
            name="chk_parametros_agua_inicial",
        ),
        CheckConstraint(
            "capacidad_suelo > 0",
            name="chk_parametros_capacidad_suelo",
        ),
        CheckConstraint(
            "umbral_hidrico >= 0",
            name="chk_parametros_umbral_hidrico",
        ),
        UniqueConstraint("simulacion_id"),
        Index("idx_parametros_simulacion_id", simulacion_id, unique=True),
    )

    simulacion = relationship("Simulacion", back_populates="parametro")
    historial = relationship(
        "ParametroHistorico",
        back_populates="parametro",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Parametro(id={self.id}, simulacion_id='{self.simulacion_id}')>"


@event.listens_for(Parametro, "before_insert")
@event.listens_for(Parametro, "before_update")
def _validar_humedad_inicial_orm(mapper, connection, target):
    if getattr(target, "configuracion_heredada", False):
        return
    configuracion = target.configuracion_json
    soil_type = configuracion.get("soilType") if isinstance(configuracion, dict) else None
    validar_humedad_inicial(target.agua_inicial, soil_type)
    target.configuracion_json = sincronizar_humedad_json(configuracion, target.agua_inicial)
