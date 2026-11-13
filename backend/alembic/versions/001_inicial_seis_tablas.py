"""Migración inicial: creación de las seis tablas del modelo AgroChaco.

Revision ID: 001_inicial_seis_tablas
Revises: None
Create Date: 2026-11-11 11:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Identificadores de revisión de Alembic
revision: str = "001_inicial_seis_tablas"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Si las tablas ya fueron creadas por init.sql, no intentar recrearlas
    if "simulaciones" in existing_tables:
        return

    # 1. Tabla: simulaciones
    op.create_table(
        "simulaciones",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("fuente_datos", sa.String(length=100), nullable=False),
        sa.Column("escenario", sa.String(length=50), nullable=False),
        sa.Column("cantidad_escenarios", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("dias", sa.Integer(), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("semilla", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("cantidad_escenarios > 0", name="chk_simulaciones_cantidad_escenarios"),
        sa.CheckConstraint("dias >= 1 AND dias <= 365", name="chk_simulaciones_dias"),
        sa.CheckConstraint(
            "estado IN ('pending', 'running', 'completed', 'failed', 'paused')",
            name="chk_simulaciones_estado",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_simulaciones_fecha_creacion",
        "simulaciones",
        [sa.text("fecha_creacion DESC")],
        unique=False,
    )
    op.create_index("idx_simulaciones_estado", "simulaciones", ["estado"], unique=False)
    op.create_index("idx_simulaciones_escenario", "simulaciones", ["escenario"], unique=False)

    # 2. Tabla: parametros
    op.create_table(
        "parametros",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("simulacion_id", sa.String(length=36), nullable=False),
        sa.Column("agua_inicial", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("capacidad_suelo", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("umbral_hidrico", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column(
            "configuracion_json",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.CheckConstraint("agua_inicial >= 0", name="chk_parametros_agua_inicial"),
        sa.CheckConstraint("capacidad_suelo > 0", name="chk_parametros_capacidad_suelo"),
        sa.CheckConstraint("umbral_hidrico >= 0", name="chk_parametros_umbral_hidrico"),
        sa.ForeignKeyConstraint(["simulacion_id"], ["simulaciones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("simulacion_id"),
    )
    op.create_index("idx_parametros_simulacion_id", "parametros", ["simulacion_id"], unique=True)

    # 3. Tabla: resultados
    op.create_table(
        "resultados",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("simulacion_id", sa.String(length=36), nullable=False),
        sa.Column("deficit_medio", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("deficit_maximo", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("agua_final_media", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("agua_minima", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("escenarios_con_deficit", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("archivo_detalle", sa.String(length=255), nullable=True),
        sa.CheckConstraint("deficit_medio >= 0 AND deficit_medio <= 1", name="chk_resultados_deficit_medio"),
        sa.CheckConstraint("deficit_maximo >= 0 AND deficit_maximo <= 1", name="chk_resultados_deficit_maximo"),
        sa.CheckConstraint("escenarios_con_deficit >= 0", name="chk_resultados_escenarios_con_deficit"),
        sa.ForeignKeyConstraint(["simulacion_id"], ["simulaciones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("simulacion_id"),
    )
    op.create_index("idx_resultados_simulacion_id", "resultados", ["simulacion_id"], unique=True)

    # 4. Tabla: rendimiento
    op.create_table(
        "rendimiento",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("simulacion_id", sa.String(length=36), nullable=False),
        sa.Column("modalidad", sa.String(length=20), nullable=False),
        sa.Column("hilos", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("procesos", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("nodos", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("tiempo_segundos", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("speedup", sa.Numeric(precision=10, scale=4), server_default=sa.text("1.0000"), nullable=False),
        sa.Column("eficiencia", sa.Numeric(precision=8, scale=4), server_default=sa.text("1.0000"), nullable=False),
        sa.Column("repeticion", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "modalidad IN ('secuencial', 'openmp', 'mpi', 'hibrido')",
            name="chk_rendimiento_modalidad",
        ),
        sa.CheckConstraint("hilos > 0", name="chk_rendimiento_hilos"),
        sa.CheckConstraint("procesos > 0", name="chk_rendimiento_procesos"),
        sa.CheckConstraint("nodos > 0", name="chk_rendimiento_nodos"),
        sa.CheckConstraint("tiempo_segundos >= 0", name="chk_rendimiento_tiempo_segundos"),
        sa.CheckConstraint("speedup >= 0", name="chk_rendimiento_speedup"),
        sa.CheckConstraint("eficiencia >= 0", name="chk_rendimiento_eficiencia"),
        sa.CheckConstraint("repeticion >= 1", name="chk_rendimiento_repeticion"),
        sa.ForeignKeyConstraint(["simulacion_id"], ["simulaciones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_rendimiento_simulacion_id", "rendimiento", ["simulacion_id"], unique=False)
    op.create_index("idx_rendimiento_modalidad", "rendimiento", ["modalidad"], unique=False)

    # 5. Tabla: fuentes_datos
    op.create_table(
        "fuentes_datos",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("simulacion_id", sa.String(length=36), nullable=False),
        sa.Column("nombre_archivo", sa.String(length=255), nullable=False),
        sa.Column("formato", sa.String(length=20), nullable=False),
        sa.Column("hash_archivo", sa.String(length=64), nullable=False),
        sa.Column("periodo", sa.String(length=50), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "formato IN ('csv', 'json', 'netcdf', 'geotiff', 'txt')",
            name="chk_fuentes_formato",
        ),
        sa.ForeignKeyConstraint(["simulacion_id"], ["simulaciones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_fuentes_simulacion_id", "fuentes_datos", ["simulacion_id"], unique=False)
    op.create_index("idx_fuentes_hash", "fuentes_datos", ["hash_archivo"], unique=False)

    # 6. Tabla: eventos_ejecucion
    op.create_table(
        "eventos_ejecucion",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("simulacion_id", sa.String(length=36), nullable=False),
        sa.Column("fecha_hora", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("nivel", sa.String(length=10), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "nivel IN ('INFO', 'WARNING', 'ERROR', 'DEBUG', 'CRITICAL')",
            name="chk_eventos_nivel",
        ),
        sa.ForeignKeyConstraint(["simulacion_id"], ["simulaciones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_eventos_sim_fecha", "eventos_ejecucion", ["simulacion_id", "fecha_hora"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Eliminar en orden inverso respetando las claves foráneas
    if "eventos_ejecucion" in existing_tables:
        op.drop_index("idx_eventos_sim_fecha", table_name="eventos_ejecucion")
        op.drop_table("eventos_ejecucion")

    if "fuentes_datos" in existing_tables:
        op.drop_index("idx_fuentes_hash", table_name="fuentes_datos")
        op.drop_index("idx_fuentes_simulacion_id", table_name="fuentes_datos")
        op.drop_table("fuentes_datos")

    if "rendimiento" in existing_tables:
        op.drop_index("idx_rendimiento_modalidad", table_name="rendimiento")
        op.drop_index("idx_rendimiento_simulacion_id", table_name="rendimiento")
        op.drop_table("rendimiento")

    if "resultados" in existing_tables:
        op.drop_index("idx_resultados_simulacion_id", table_name="resultados")
        op.drop_table("resultados")

    if "parametros" in existing_tables:
        op.drop_index("idx_parametros_simulacion_id", table_name="parametros")
        op.drop_table("parametros")

    if "simulaciones" in existing_tables:
        op.drop_index("idx_simulaciones_escenario", table_name="simulaciones")
        op.drop_index("idx_simulaciones_estado", table_name="simulaciones")
        op.drop_index("idx_simulaciones_fecha_creacion", table_name="simulaciones")
        op.drop_table("simulaciones")
