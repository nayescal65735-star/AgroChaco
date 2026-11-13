"""Modelo SQLAlchemy para los resultados estadísticos y agregados de la simulación."""

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


class Resultado(Base):
    """Resultados consolidados de balance hídrico y estrés acumulado."""

    __tablename__ = "resultados"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    simulacion_id = Column(
        String(36),
        ForeignKey("simulaciones.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    deficit_medio = Column(Numeric(8, 4), nullable=False)
    deficit_maximo = Column(Numeric(8, 4), nullable=False)
    agua_final_media = Column(Numeric(10, 2), nullable=False)
    agua_minima = Column(Numeric(10, 2), nullable=False)
    escenarios_con_deficit = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    archivo_detalle = Column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "deficit_medio >= 0 AND deficit_medio <= 1",
            name="chk_resultados_deficit_medio",
        ),
        CheckConstraint(
            "deficit_maximo >= 0 AND deficit_maximo <= 1",
            name="chk_resultados_deficit_maximo",
        ),
        CheckConstraint(
            "escenarios_con_deficit >= 0",
            name="chk_resultados_escenarios_con_deficit",
        ),
    )

    simulacion = relationship("Simulacion", back_populates="resultado")

    def __repr__(self) -> str:
        return (
            f"<Resultado(id={self.id}, simulacion_id='{self.simulacion_id}', "
            f"deficit_medio={self.deficit_medio})>"
        )

