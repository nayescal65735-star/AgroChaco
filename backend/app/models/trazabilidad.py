"""Modelos de trazabilidad histórica y linaje de recalibraciones."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.db.database import Base


class ParametroHistorico(Base):
    """Instantánea inmutable de los parámetros originales de una simulación."""

    __tablename__ = "parametros_historico"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    parametro_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("parametros.id", ondelete="CASCADE"),
        nullable=False,
    )
    simulacion_id = Column(
        String(36),
        ForeignKey("simulaciones.id", ondelete="CASCADE"),
        nullable=False,
    )
    agua_inicial = Column(Numeric(8, 2), nullable=False)
    configuracion_json = Column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
    )
    tiene_resultado = Column(Boolean, nullable=False)
    motivo = Column(Text, nullable=False)
    fuente = Column(String(64), nullable=False)
    original_recuperable = Column(Boolean, nullable=False, default=True)
    capturado_en = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    revision = Column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "parametro_id", "revision", name="uq_parametros_historico_parametro_revision"
        ),
        Index("idx_parametros_historico_simulacion", simulacion_id),
    )

    parametro = relationship("Parametro", back_populates="historial")
    simulacion = relationship("Simulacion", back_populates="historial_parametros")

    def __repr__(self) -> str:
        return (
            f"<ParametroHistorico(id={self.id}, simulacion_id='{self.simulacion_id}', "
            f"fuente='{self.fuente}')>"
        )


class RecalibracionSimulacion(Base):
    """Linaje entre una simulación histórica y su versión recalibrada."""

    __tablename__ = "simulaciones_recalibraciones"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    simulacion_origen_id = Column(
        String(36),
        ForeignKey("simulaciones.id", ondelete="CASCADE"),
        nullable=False,
    )
    simulacion_destino_id = Column(
        String(36),
        ForeignKey("simulaciones.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    parametro_historico_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("parametros_historico.id", ondelete="SET NULL"),
        nullable=True,
    )
    motivo = Column(Text, nullable=False)
    creado_por = Column(String(100), nullable=False, default="sistema")
    creado_en = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "simulacion_origen_id",
            "simulacion_destino_id",
            name="uq_recalibracion_origen_destino",
        ),
    )

    origen = relationship(
        "Simulacion",
        foreign_keys=[simulacion_origen_id],
        back_populates="recalibraciones_origen",
    )
    destino = relationship(
        "Simulacion",
        foreign_keys=[simulacion_destino_id],
        back_populates="recalibracion_destino",
    )
    parametro_historico = relationship("ParametroHistorico")

    def __repr__(self) -> str:
        return (
            f"<RecalibracionSimulacion(origen='{self.simulacion_origen_id}', "
            f"destino='{self.simulacion_destino_id}')>"
        )
