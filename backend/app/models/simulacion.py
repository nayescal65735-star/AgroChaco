"""Modelo SQLAlchemy para la tabla de simulaciones (entidad raíz)."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class Simulacion(Base):
    """Representa una corrida o experimento de simulación biofísica en AgroChaco."""

    __tablename__ = "simulaciones"

    id = Column(
        String(36),
        primary_key=True,
        doc="Identificador alfanumérico único de simulación (ej. SIM-XXXXXXXXXXXX o UUID)",
    )
    nombre = Column(String(150), nullable=False)
    fuente_datos = Column(String(100), nullable=False)
    escenario = Column(String(50), nullable=False)
    cantidad_escenarios = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    dias = Column(Integer, nullable=False)
    fecha_creacion = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    estado = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    semilla = Column(BigInteger, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "cantidad_escenarios > 0",
            name="chk_simulaciones_cantidad_escenarios",
        ),
        CheckConstraint(
            "dias >= 1 AND dias <= 365",
            name="chk_simulaciones_dias",
        ),
        CheckConstraint(
            "estado IN ('pending', 'running', 'completed', 'failed', 'paused')",
            name="chk_simulaciones_estado",
        ),
        Index("idx_simulaciones_fecha_creacion", fecha_creacion.desc()),
        Index("idx_simulaciones_estado", estado),
        Index("idx_simulaciones_escenario", escenario),
    )

    # Relaciones con eliminación en cascada (ON DELETE CASCADE)
    parametro = relationship(
        "Parametro",
        back_populates="simulacion",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    resultado = relationship(
        "Resultado",
        back_populates="simulacion",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    rendimientos = relationship(
        "Rendimiento",
        back_populates="simulacion",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    fuentes_datos = relationship(
        "FuenteDatos",
        back_populates="simulacion",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    eventos = relationship(
        "EventoEjecucion",
        back_populates="simulacion",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Simulacion(id='{self.id}', nombre='{self.nombre}', estado='{self.estado}')>"

