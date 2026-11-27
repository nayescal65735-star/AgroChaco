"""Migración 004: integridad histórica del rango físico de humedad inicial.

Revision ID: 004_humedad_inicial_pmp_cc
Revises: 003_simulation_jobs
Create Date: 2026-11-26 10:00:00.000000

La revisión original modificaba agua_inicial y configuracion_json de corridas con
resultados históricos. Esta versión conserva los parámetros originales, registra
una instantánea auditable y marca las configuraciones heredadas como no ejecutables.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "004_humedad_inicial_pmp_cc"
down_revision: Union[str, None] = "003_simulation_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REVISION = revision

CHECK_SQL = (
    "configuracion_heredada OR ("
    "configuracion_json->>'soilType' IS NOT NULL "
    "AND configuracion_json->>'soilType' IN "
    "('franco_arenoso', 'franco_arcilloso', 'arenoso', 'franco') "
    "AND agua_inicial >= 0 AND agua_inicial <= 100 "
    "AND (CASE configuracion_json->>'soilType' "
    "WHEN 'franco_arenoso' THEN agua_inicial BETWEEN 8.20 AND 18.50 "
    "WHEN 'franco_arcilloso' THEN agua_inicial BETWEEN 17.50 AND 31.00 "
    "WHEN 'arenoso' THEN agua_inicial BETWEEN 4.80 AND 12.00 "
    "WHEN 'franco' THEN agua_inicial BETWEEN 11.00 AND 24.00 "
    "ELSE 1 = 0 END)"
    ")"
)

SOIL_CONDITION = (
    "configuracion_json->>'soilType' IS NOT NULL "
    "AND configuracion_json->>'soilType' IN "
    "('franco_arenoso', 'franco_arcilloso', 'arenoso', 'franco')"
)

OUT_OF_RANGE_SQL = (
    "NOT ("
    f"{SOIL_CONDITION} "
    "AND (CASE configuracion_json->>'soilType' "
    "WHEN 'franco_arenoso' THEN agua_inicial BETWEEN 8.20 AND 18.50 "
    "WHEN 'franco_arcilloso' THEN agua_inicial BETWEEN 17.50 AND 31.00 "
    "WHEN 'arenoso' THEN agua_inicial BETWEEN 4.80 AND 12.00 "
    "WHEN 'franco' THEN agua_inicial BETWEEN 11.00 AND 24.00 "
    "ELSE 1 = 0 END)"
    ")"
)

CONFIGURACION_HEREDADA_SQL = f"""
    EXISTS (SELECT 1 FROM resultados r WHERE r.simulacion_id = p.simulacion_id)
    OR ({OUT_OF_RANGE_SQL})
"""

CREATE_SNAPSHOT_SQL = f"""
CREATE TABLE IF NOT EXISTS parametros_historico (
    id BIGSERIAL PRIMARY KEY,
    parametro_id BIGINT NOT NULL REFERENCES parametros(id) ON DELETE CASCADE,
    simulacion_id VARCHAR(36) NOT NULL REFERENCES simulaciones(id) ON DELETE CASCADE,
    agua_inicial NUMERIC(8, 2) NOT NULL,
    configuracion_json JSONB NOT NULL,
    tiene_resultado BOOLEAN NOT NULL,
    motivo TEXT NOT NULL,
    fuente TEXT NOT NULL,
    original_recuperable BOOLEAN NOT NULL DEFAULT true,
    capturado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    revision VARCHAR(64) NOT NULL,
    CONSTRAINT uq_parametros_historico_parametro_revision
        UNIQUE (parametro_id, revision)
)
"""

SNAPSHOT_SQL = f"""
INSERT INTO parametros_historico (
    parametro_id, simulacion_id, agua_inicial, configuracion_json,
    tiene_resultado, motivo, fuente, original_recuperable, revision
)
SELECT
    p.id, p.simulacion_id, p.agua_inicial, p.configuracion_json,
    EXISTS (SELECT 1 FROM resultados r WHERE r.simulacion_id = p.simulacion_id),
    CASE
        WHEN EXISTS (SELECT 1 FROM resultados r WHERE r.simulacion_id = p.simulacion_id)
            THEN 'resultado_historico'
        ELSE 'configuracion_fuera_de_rango'
    END,
    '004_pre_migracion',
    true,
    '{REVISION}'
FROM parametros p
WHERE ({CONFIGURACION_HEREDADA_SQL})
  AND NOT EXISTS (
      SELECT 1 FROM parametros_historico h
      WHERE h.parametro_id = p.id AND h.revision = '{REVISION}'
  )
"""

SYNC_CONFIG_SQL = f"""
UPDATE parametros p
SET configuracion_json = jsonb_set(
    p.configuracion_json,
    '{{initialMoisturePercent}}',
    to_jsonb(p.agua_inicial::double precision),
    true
)
WHERE ({OUT_OF_RANGE_SQL})
  AND NOT ({SOIL_CONDITION})
  AND p.configuracion_json ? 'initialMoisturePercent'
"""

MARK_SQL = f"""
UPDATE parametros p
SET configuracion_heredada = true
WHERE ({CONFIGURACION_HEREDADA_SQL})
"""


def upgrade() -> None:
    op.execute(
        "ALTER TABLE parametros ADD COLUMN IF NOT EXISTS configuracion_heredada "
        "BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(CREATE_SNAPSHOT_SQL)
    op.execute(SNAPSHOT_SQL)
    op.execute(SYNC_CONFIG_SQL)
    op.execute(MARK_SQL)
    op.execute("ALTER TABLE parametros DROP CONSTRAINT IF EXISTS chk_parametros_agua_inicial")
    op.execute(
        f"ALTER TABLE parametros ADD CONSTRAINT chk_parametros_agua_inicial "
        f"CHECK ({CHECK_SQL}) NOT VALID"
    )
    op.execute("ALTER TABLE parametros VALIDATE CONSTRAINT chk_parametros_agua_inicial")


def downgrade() -> None:
    op.execute("ALTER TABLE parametros DROP CONSTRAINT IF EXISTS chk_parametros_agua_inicial")
    op.execute(
        "ALTER TABLE parametros ADD CONSTRAINT chk_parametros_agua_inicial "
        "CHECK (agua_inicial >= 0) NOT VALID"
    )
    op.execute("DROP TABLE IF EXISTS parametros_historico")
    op.execute("ALTER TABLE parametros DROP COLUMN IF EXISTS configuracion_heredada")
