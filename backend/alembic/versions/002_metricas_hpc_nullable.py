"""Permitir NULL en speedup y eficiencia de rendimiento.

Revision ID: 002_metricas_hpc_nullable
Revises: 001_inicial_seis_tablas
Create Date: 2026-11-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_metricas_hpc_nullable"
down_revision: Union[str, None] = "001_inicial_seis_tablas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "rendimiento" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("rendimiento")}

    if "speedup" in column_names:
        op.alter_column(
            "rendimiento",
            "speedup",
            existing_type=sa.Numeric(precision=10, scale=4),
            nullable=True,
            server_default=None,
        )

    if "eficiencia" in column_names:
        op.alter_column(
            "rendimiento",
            "eficiencia",
            existing_type=sa.Numeric(precision=8, scale=4),
            nullable=True,
            server_default=None,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "rendimiento" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("rendimiento")}
    if "speedup" not in column_names or "eficiencia" not in column_names:
        return

    nulos = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM rendimiento "
            "WHERE speedup IS NULL OR eficiencia IS NULL"
        )
    ).scalar_one()

    if nulos:
        raise RuntimeError(
            "No es posible revertir la migración sin inventar mediciones: "
            f"hay {nulos} registros con speedup o eficiencia NULL."
        )

    op.alter_column(
        "rendimiento",
        "speedup",
        existing_type=sa.Numeric(precision=10, scale=4),
        nullable=False,
        server_default=sa.text("1.0000"),
    )
    op.alter_column(
        "rendimiento",
        "eficiencia",
        existing_type=sa.Numeric(precision=8, scale=4),
        nullable=False,
        server_default=sa.text("1.0000"),
    )
