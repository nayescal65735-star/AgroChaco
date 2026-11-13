"""Modelo SQLAlchemy para métricas de rendimiento computacional (HPC)."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class Rendimiento(Base):
    """Métricas de aceleración (Speedup), eficiencia y tiempos de cómputo paralelo."""

    __tablename__ = "rendimiento"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    simulacion_id = Column(
        String(36),
        ForeignKey("simulaciones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    modalidad = Column(String(20), nullable=False, index=True)
    hilos = Column(Integer, nullable=False, default=1, server_default=text("1"))
    procesos = Column(Integer, nullable=False, default=1, server_default=text("1"))
    nodos = Column(Integer, nullable=False, default=1, server_default=text("1"))
    tiempo_segundos = Column(Numeric(12, 4), nullable=False)
    speedup = Column(
        Numeric(10, 4),
        nullable=False,
        default=1.0000,
        server_default=text("1.0000"),
    )
    eficiencia = Column(
        Numeric(8, 4),
        nullable=False,
        default=1.0000,
        server_default=text("1.0000"),
    )
    repeticion = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    __table_args__ = (
        CheckConstraint(
            "modalidad IN ('secuencial', 'openmp', 'mpi', 'hibrido')",
            name="chk_rendimiento_modalidad",
        ),
        CheckConstraint("hilos > 0", name="chk_rendimiento_hilos"),
        CheckConstraint("procesos > 0", name="chk_rendimiento_procesos"),
        CheckConstraint("nodos > 0", name="chk_rendimiento_nodos"),
        CheckConstraint(
            "tiempo_segundos >= 0",
            name="chk_rendimiento_tiempo_segundos",
        ),
        CheckConstraint("speedup >= 0", name="chk_rendimiento_speedup"),
        CheckConstraint("eficiencia >= 0", name="chk_rendimiento_eficiencia"),
        CheckConstraint("repeticion >= 1", name="chk_rendimiento_repeticion"),
    )

    simulacion = relationship("Simulacion", back_populates="rendimientos")

    def __repr__(self) -> str:
        return (
            f"<Rendimiento(id={self.id}, simulacion_id='{self.simulacion_id}', "
            f"modalidad='{self.modalidad}', tiempo_segundos={self.tiempo_segundos})>"
        )

