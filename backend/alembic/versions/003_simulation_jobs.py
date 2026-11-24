"""Migración 003: tabla de trabajos de ejecución de simulaciones.

Revision ID: 003_simulation_jobs
Revises: 002_metricas_hpc_nullable
Create Date: 2026-11-24 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa

revision: str = "003_simulation_jobs"
down_revision: Union[str, None] = "002_metricas_hpc_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOMBRE_TABLA = "simulation_jobs"

COLUMNAS_ESPERADAS = frozenset(
    {
        "job_id",
        "simulacion_id",
        "estado",
        "pid",
        "pgid",
        "worker_id",
        "heartbeat_at",
        "lease_expires_at",
        "progress_percent",
        "current_day",
        "cancel_requested",
        "error_message",
        "started_at",
        "finished_at",
        "attempt",
        "created_at",
        "updated_at",
    }
)
COLUMNAS_NO_NULABLES = frozenset(
    {
        "job_id",
        "simulacion_id",
        "estado",
        "cancel_requested",
        "attempt",
        "created_at",
        "updated_at",
    }
)
DEFINICIONES_INDICES = {
    "idx_simulation_jobs_estado": ("estado",),
    "idx_simulation_jobs_lease": ("lease_expires_at",),
    "idx_simulation_jobs_cancel": ("cancel_requested",),
    "idx_simulation_jobs_sim_estado": ("simulacion_id", "estado"),
    "uq_simulation_jobs_activa_por_simulacion": ("simulacion_id",),
}
INDICES_ESPERADOS = tuple(DEFINICIONES_INDICES)
RESTRICCIONES_ESPERADAS = frozenset(
    {
        "chk_simulation_jobs_estado",
        "chk_simulation_jobs_progreso",
        "chk_simulation_jobs_current_day",
        "chk_simulation_jobs_attempt",
        "chk_simulation_jobs_fechas",
    }
)


def validar_esquema(inspector: sa.Inspector) -> None:
    columnas = {columna["name"]: columna for columna in inspector.get_columns(NOMBRE_TABLA)}
    columnas_faltantes = sorted(COLUMNAS_ESPERADAS - set(columnas))
    if columnas_faltantes:
        raise RuntimeError(
            f"{NOMBRE_TABLA} existe pero faltan columnas: {', '.join(columnas_faltantes)}"
        )

    nulables_incorrectas = sorted(
        nombre
        for nombre in COLUMNAS_NO_NULABLES
        if columnas[nombre].get("nullable") is not False
    )
    if nulables_incorrectas:
        raise RuntimeError(
            f"{NOMBRE_TABLA} tiene columnas nulables incorrectamente: "
            f"{', '.join(nulables_incorrectas)}"
        )

    indices = {indice["name"]: indice for indice in inspector.get_indexes(NOMBRE_TABLA)}
    indices_faltantes = [nombre for nombre in INDICES_ESPERADOS if nombre not in indices]
    if indices_faltantes:
        raise RuntimeError(
            f"{NOMBRE_TABLA} existe pero faltan índices: {', '.join(indices_faltantes)}"
        )

    for nombre, columnas_esperadas in DEFINICIONES_INDICES.items():
        indice = indices[nombre]
        columnas_reales = tuple(indice.get("column_names") or ())
        if columnas_reales != columnas_esperadas:
            raise RuntimeError(
                f"{NOMBRE_TABLA}.{nombre} debe cubrir {', '.join(columnas_esperadas)}"
            )
        es_unico = bool(indice.get("unique"))
        if es_unico != nombre.startswith("uq_"):
            raise RuntimeError(f"{NOMBRE_TABLA}.{nombre} tiene unicidad incorrecta")

    indice_activo = indices["uq_simulation_jobs_activa_por_simulacion"]
    opciones = indice_activo.get("dialect_options") or {}
    predicado = (
        indice_activo.get("where")
        or opciones.get("postgresql_where")
        or opciones.get("sqlite_where")
    )
    texto_predicado = str(predicado)
    if predicado is None or "queued" not in texto_predicado or "running" not in texto_predicado:
        raise RuntimeError(
            f"{NOMBRE_TABLA}.uq_simulation_jobs_activa_por_simulacion debe ser parcial"
        )

    restricciones = {
        restriccion["name"]
        for restriccion in inspector.get_check_constraints(NOMBRE_TABLA)
        if restriccion.get("name")
    }
    restricciones_faltantes = sorted(RESTRICCIONES_ESPERADAS - restricciones)
    if restricciones_faltantes:
        raise RuntimeError(
            f"{NOMBRE_TABLA} existe pero faltan restricciones: "
            f"{', '.join(restricciones_faltantes)}"
        )

    primaria = inspector.get_pk_constraint(NOMBRE_TABLA).get("constrained_columns") or []
    if list(primaria) != ["job_id"]:
        raise RuntimeError(f"{NOMBRE_TABLA} debe tener job_id como clave primaria")

    foraneas = inspector.get_foreign_keys(NOMBRE_TABLA)
    foranea_simulacion = any(
        list(foranea.get("constrained_columns") or []) == ["simulacion_id"]
        and foranea.get("referred_table") == "simulaciones"
        and foranea.get("options", {}).get("ondelete") == "CASCADE"
        for foranea in foraneas
    )
    if not foranea_simulacion:
        raise RuntimeError(
            f"{NOMBRE_TABLA} debe tener una FK simulacion_id -> simulaciones ON DELETE CASCADE"
        )


def upgrade() -> None:
    bind = op.get_bind()
    tabla_existe = False

    if not context.is_offline_mode():
        inspector = sa.inspect(bind)
        tabla_existe = NOMBRE_TABLA in inspector.get_table_names()
        if tabla_existe:
            validar_esquema(inspector)

    if not tabla_existe:
        op.create_table(
            NOMBRE_TABLA,
            sa.Column("job_id", sa.Uuid(), nullable=False),
            sa.Column("simulacion_id", sa.String(length=36), nullable=False),
            sa.Column(
                "estado",
                sa.String(length=20),
                server_default=sa.text("'queued'"),
                nullable=False,
            ),
            sa.Column("pid", sa.Integer(), nullable=True),
            sa.Column("pgid", sa.Integer(), nullable=True),
            sa.Column("worker_id", sa.String(length=64), nullable=True),
            sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("progress_percent", sa.Integer(), nullable=True),
            sa.Column("current_day", sa.Integer(), nullable=True),
            sa.Column(
                "cancel_requested",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("attempt", sa.Integer(), server_default=sa.text("1"), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.CheckConstraint(
                "estado IN ('queued', 'running', 'completed', 'failed', 'canceled')",
                name="chk_simulation_jobs_estado",
            ),
            sa.CheckConstraint(
                "progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100)",
                name="chk_simulation_jobs_progreso",
            ),
            sa.CheckConstraint(
                "current_day IS NULL OR current_day >= 0",
                name="chk_simulation_jobs_current_day",
            ),
            sa.CheckConstraint("attempt > 0", name="chk_simulation_jobs_attempt"),
            sa.CheckConstraint(
                "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
                name="chk_simulation_jobs_fechas",
            ),
            sa.ForeignKeyConstraint(
                ["simulacion_id"], ["simulaciones.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("job_id"),
        )
        op.create_index(
            "idx_simulation_jobs_estado", NOMBRE_TABLA, ["estado"], unique=False
        )
        op.create_index(
            "idx_simulation_jobs_lease", NOMBRE_TABLA, ["lease_expires_at"], unique=False
        )
        op.create_index(
            "idx_simulation_jobs_cancel", NOMBRE_TABLA, ["cancel_requested"], unique=False
        )
        op.create_index(
            "idx_simulation_jobs_sim_estado",
            NOMBRE_TABLA,
            ["simulacion_id", "estado"],
            unique=False,
        )
        op.create_index(
            "uq_simulation_jobs_activa_por_simulacion",
            NOMBRE_TABLA,
            ["simulacion_id"],
            unique=True,
            postgresql_where=sa.text("estado IN ('queued', 'running')"),
            sqlite_where=sa.text("estado IN ('queued', 'running')"),
        )


def downgrade() -> None:
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        if NOMBRE_TABLA not in inspector.get_table_names():
            raise RuntimeError(f"No se puede degradar: no existe {NOMBRE_TABLA}")
        indices = {indice["name"] for indice in inspector.get_indexes(NOMBRE_TABLA)}
    else:
        indices = set(INDICES_ESPERADOS)

    for nombre in reversed(INDICES_ESPERADOS):
        if nombre in indices:
            op.drop_index(nombre, table_name=NOMBRE_TABLA)

    op.drop_table(NOMBRE_TABLA)
