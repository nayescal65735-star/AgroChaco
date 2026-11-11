"""Modelo SQLAlchemy para los eventos y trazas de ejecución de las simulaciones."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class EventoEjecucion(Base):
    """Eventos y traza cronológica generada durante la ejecución de simulaciones."""

    __tablename__ = "eventos_ejecucion"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    simulacion_id = Column(
        String(36),
        ForeignKey("simulaciones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha_hora = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    nivel = Column(String(10), nullable=False)
    mensaje = Column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "nivel IN ('INFO', 'WARNING', 'ERROR', 'DEBUG', 'CRITICAL')",
            name="chk_eventos_nivel",
        ),
        Index("idx_eventos_sim_fecha", simulacion_id, fecha_hora),
    )

    simulacion = relationship("Simulacion", back_populates="eventos")

    def __repr__(self) -> str:
        return (
            f"<EventoEjecucion(id={self.id}, simulacion_id='{self.simulacion_id}', "
            f"nivel='{self.nivel}', fecha_hora='{self.fecha_hora}')>"
        )

