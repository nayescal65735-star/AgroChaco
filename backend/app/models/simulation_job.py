"""Modelo SQLAlchemy para trabajos de ejecución asíncrona de simulaciones."""

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base

ESTADOS_TRABAJO = ("queued", "running", "completed", "failed", "canceled")
ESTADOS_ACTIVOS_TRABAJO = ("queued", "running")
ESTADOS_TERMINALES_TRABAJO = ("completed", "failed", "canceled")
TRANSICIONES_TRABAJO = {
    "queued": ("running", "failed", "canceled"),
    "running": ("completed", "failed", "canceled"),
    "completed": (),
    "failed": (),
    "canceled": (),
}


def transiciones_permitidas_desde(estado: str) -> tuple[str, ...]:
    return TRANSICIONES_TRABAJO.get(estado, ())


class SimulationJob(Base):
    """Representa una unidad de ejecución persistente asociada a una simulación."""

    __tablename__ = "simulation_jobs"

    job_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    simulacion_id = Column(
        String(36),
        ForeignKey("simulaciones.id", ondelete="CASCADE"),
        nullable=False,
    )
    estado = Column(
        String(20),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
    )
    pid = Column(Integer, nullable=True)
    pgid = Column(Integer, nullable=True)
    worker_id = Column(String(64), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    progress_percent = Column(Integer, nullable=True)
    current_day = Column(Integer, nullable=True)
    cancel_requested = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    attempt = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "estado IN ('queued', 'running', 'completed', 'failed', 'canceled')",
            name="chk_simulation_jobs_estado",
        ),
        CheckConstraint(
            "progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100)",
            name="chk_simulation_jobs_progreso",
        ),
        CheckConstraint(
            "current_day IS NULL OR current_day >= 0",
            name="chk_simulation_jobs_current_day",
        ),
        CheckConstraint("attempt > 0", name="chk_simulation_jobs_attempt"),
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="chk_simulation_jobs_fechas",
        ),
        Index("idx_simulation_jobs_estado", estado),
        Index("idx_simulation_jobs_lease", lease_expires_at),
        Index("idx_simulation_jobs_cancel", cancel_requested),
        Index("idx_simulation_jobs_sim_estado", simulacion_id, estado),
        Index(
            "uq_simulation_jobs_activa_por_simulacion",
            simulacion_id,
            unique=True,
            postgresql_where=text("estado IN ('queued', 'running')"),
            sqlite_where=text("estado IN ('queued', 'running')"),
        ),
    )

    simulacion = relationship("Simulacion", back_populates="trabajos")

    def __repr__(self) -> str:
        return (
            f"<SimulationJob(job_id='{self.job_id}', simulacion_id='{self.simulacion_id}', "
            f"estado='{self.estado}', attempt={self.attempt})>"
        )
