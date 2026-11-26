"""Migración 004: rango físico de humedad inicial según tipo de suelo.

Revision ID: 004_humedad_inicial_pmp_cc
Revises: 003_simulation_jobs
Create Date: 2026-11-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "004_humedad_inicial_pmp_cc"
down_revision: Union[str, None] = "003_simulation_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHECK_SQL = (
    "configuracion_json->>'soilType' IN "
    "('franco_arenoso', 'franco_arcilloso', 'arenoso', 'franco') "
    "AND agua_inicial >= 0 AND agua_inicial <= 100 "
    "AND (CASE configuracion_json->>'soilType' "
    "WHEN 'franco_arenoso' THEN agua_inicial BETWEEN 8.20 AND 18.50 "
    "WHEN 'franco_arcilloso' THEN agua_inicial BETWEEN 17.50 AND 31.00 "
    "WHEN 'arenoso' THEN agua_inicial BETWEEN 4.80 AND 12.00 "
    "WHEN 'franco' THEN agua_inicial BETWEEN 11.00 AND 24.00 "
    "ELSE 1 = 0 END)"
)

REPAIR_SQL = """
UPDATE parametros
SET agua_inicial = CASE configuracion_json->>'soilType'
    WHEN 'franco_arenoso' THEN LEAST(GREATEST(agua_inicial, 8.20), 18.50)
    WHEN 'franco_arcilloso' THEN LEAST(GREATEST(agua_inicial, 17.50), 31.00)
    WHEN 'arenoso' THEN LEAST(GREATEST(agua_inicial, 4.80), 12.00)
    WHEN 'franco' THEN LEAST(GREATEST(agua_inicial, 11.00), 24.00)
    ELSE agua_inicial
END
WHERE configuracion_json->>'soilType' IN
    ('franco_arenoso', 'franco_arcilloso', 'arenoso', 'franco')
"""

SYNC_JSON_SQL = """
UPDATE parametros
SET configuracion_json = jsonb_set(
    configuracion_json,
    '{initialMoisturePercent}',
    to_jsonb(agua_inicial),
    true
)
"""


def upgrade() -> None:
    op.execute(REPAIR_SQL)
    op.execute(SYNC_JSON_SQL)
    op.execute("ALTER TABLE parametros DROP CONSTRAINT IF EXISTS chk_parametros_agua_inicial")
    op.execute(
        f"ALTER TABLE parametros ADD CONSTRAINT chk_parametros_agua_inicial "
        f"CHECK ({CHECK_SQL}) NOT VALID"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE parametros DROP CONSTRAINT IF EXISTS chk_parametros_agua_inicial")
    op.execute(
        "ALTER TABLE parametros ADD CONSTRAINT chk_parametros_agua_inicial "
        "CHECK (agua_inicial >= 0)"
    )
