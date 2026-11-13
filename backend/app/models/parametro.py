"""Modelo SQLAlchemy para los parámetros agronómicos y de configuración de la simulación."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.db.database import Base


class Parametro(Base):
    """Parámetros biofísicos de suelo, agua y configuración espacial JSON."""

    __tablename__ = "parametros"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    simulacion_id = Column(
        String(36),
        ForeignKey("simulaciones.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    agua_inicial = Column(Numeric(8, 2), nullable=False)
    capacidad_suelo = Column(Numeric(8, 2), nullable=False)
    umbral_hidrico = Column(Numeric(8, 2), nullable=False)

    # JSONB para PostgreSQL, JSON genérico como fallback
    configuracion_json = Column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "agua_inicial >= 0",
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
    )

    simulacion = relationship("Simulacion", back_populates="parametro")

    def __repr__(self) -> str:
        return f"<Parametro(id={self.id}, simulacion_id='{self.simulacion_id}')>"

