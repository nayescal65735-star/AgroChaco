"""Modelo SQLAlchemy para el registro de fuentes de datos meteorológicos y edafológicos."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class FuenteDatos(Base):
    """Fuentes de datos meteorológicos y hash de integridad auditable."""

    __tablename__ = "fuentes_datos"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    simulacion_id = Column(
        String(36),
        ForeignKey("simulaciones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nombre_archivo = Column(String(255), nullable=False)
    formato = Column(String(20), nullable=False)
    hash_archivo = Column(String(64), nullable=False, index=True)
    periodo = Column(String(50), nullable=True)
    descripcion = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "formato IN ('csv', 'json', 'netcdf', 'geotiff', 'txt')",
            name="chk_fuentes_formato",
        ),
    )

    simulacion = relationship("Simulacion", back_populates="fuentes_datos")

    def __repr__(self) -> str:
        return (
            f"<FuenteDatos(id={self.id}, simulacion_id='{self.simulacion_id}', "
            f"nombre='{self.nombre_archivo}', formato='{self.formato}')>"
        )

