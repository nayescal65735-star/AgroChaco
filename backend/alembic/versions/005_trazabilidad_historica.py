"""Migración 005: trazabilidad histórica y bloqueo de ejecuciones heredadas.

Revision ID: 005_trazabilidad_historica
Revises: 004_humedad_inicial_pmp_cc
Create Date: 2026-11-27 12:00:00.000000

Completa la revisión 004 para bases que ya hubieran sido marcadas con la versión
destructiva original, añade linaje de recalibración, normaliza estados running
huérfanos y distingue explícitamente los registros DEMO.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "005_trazabilidad_historica"
down_revision: Union[str, None] = "004_humedad_inicial_pmp_cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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

CREATE_SNAPSHOT_SQL = """
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

SNAPSHOT_POST_004_SQL = f"""
INSERT INTO parametros_historico (
    parametro_id, simulacion_id, agua_inicial, configuracion_json,
    tiene_resultado, motivo, fuente, original_recuperable, revision
)
SELECT
    p.id, p.simulacion_id, p.agua_inicial, p.configuracion_json,
    EXISTS (SELECT 1 FROM resultados r WHERE r.simulacion_id = p.simulacion_id),
    CASE
        WHEN EXISTS (SELECT 1 FROM resultados r WHERE r.simulacion_id = p.simulacion_id)
            THEN 'resultado_bajo_modelo_anterior'
        ELSE 'configuracion_fuera_de_rango'
    END,
    '005_post_004_irrecuperable',
    false,
    '005_trazabilidad_historica'
FROM parametros p
WHERE (
    EXISTS (SELECT 1 FROM resultados r WHERE r.simulacion_id = p.simulacion_id)
    OR ({OUT_OF_RANGE_SQL})
)
AND NOT EXISTS (
    SELECT 1 FROM parametros_historico h WHERE h.parametro_id = p.id
)
"""

MARK_POST_004_SQL = f"""
UPDATE parametros p
SET configuracion_heredada = true
WHERE (
    EXISTS (SELECT 1 FROM resultados r WHERE r.simulacion_id = p.simulacion_id)
    OR ({OUT_OF_RANGE_SQL})
)
AND NOT EXISTS (
    SELECT 1 FROM parametros_historico h
    WHERE h.parametro_id = p.id AND h.revision = '005_trazabilidad_historica'
)
"""

CREATE_RECALIBRACIONES_SQL = """
CREATE TABLE IF NOT EXISTS simulaciones_recalibraciones (
    id BIGSERIAL PRIMARY KEY,
    simulacion_origen_id VARCHAR(36) NOT NULL
        REFERENCES simulaciones(id) ON DELETE CASCADE,
    simulacion_destino_id VARCHAR(36) NOT NULL UNIQUE
        REFERENCES simulaciones(id) ON DELETE CASCADE,
    parametro_historico_id BIGINT NULL
        REFERENCES parametros_historico(id) ON DELETE SET NULL,
    motivo TEXT NOT NULL,
    creado_por VARCHAR(100) NOT NULL DEFAULT 'sistema',
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_recalibracion_origen_destino
        UNIQUE (simulacion_origen_id, simulacion_destino_id)
)
"""

VALIDAR_HEREDADO_FN = """
CREATE OR REPLACE FUNCTION validar_parametro_heredado() RETURNS trigger AS $$
BEGIN
    IF NEW.configuracion_heredada AND NOT EXISTS (
        SELECT 1 FROM parametros_historico h
        WHERE h.parametro_id = NEW.id AND h.simulacion_id = NEW.simulacion_id
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'configuracion_heredada requiere una instantánea en parametros_historico';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

BLOQUEAR_EJECUCION_FN = """
CREATE OR REPLACE FUNCTION bloquear_ejecucion_historica() RETURNS trigger AS $$
DECLARE
    sim_id VARCHAR(36);
BEGIN
    IF TG_TABLE_NAME = 'simulation_jobs' THEN
        IF NEW.estado NOT IN ('queued', 'running') THEN
            RETURN NEW;
        END IF;
        sim_id := NEW.simulacion_id;
    ELSE
        IF NEW.estado <> 'running' THEN
            RETURN NEW;
        END IF;
        sim_id := NEW.id;
    END IF;

    IF EXISTS (
        SELECT 1 FROM parametros p
        WHERE p.simulacion_id = sim_id
          AND p.configuracion_heredada
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = format(
                'La simulación %s usa una configuración histórica; cree una recalibración antes de ejecutarla.',
                sim_id
            );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

SELECCIONAR_RUNNING_HUERFANOS_SQL = """
CREATE TEMP TABLE running_huerfanos_005 AS
SELECT s.id
FROM simulaciones s
WHERE s.estado = 'running'
  AND NOT EXISTS (
      SELECT 1 FROM simulation_jobs j
      WHERE j.simulacion_id = s.id AND j.estado IN ('queued', 'running')
  )
"""

RECONCILIAR_RUNNING_SQL = """
UPDATE simulaciones s
SET estado = 'paused'
WHERE s.id IN (SELECT id FROM running_huerfanos_005)
"""

REGISTRAR_RUNNING_SQL = """
INSERT INTO eventos_ejecucion (simulacion_id, nivel, mensaje)
SELECT h.id, 'WARNING',
       'Estado running sin trabajo activo; normalizado a paused por la revisión 005.'
FROM running_huerfanos_005 h
"""

Marcar_DEMO_SQL = """
UPDATE simulaciones
SET es_demo = true
WHERE nombre LIKE '[DEMO]%'
"""


def upgrade() -> None:
    op.execute(
        "ALTER TABLE parametros ADD COLUMN IF NOT EXISTS configuracion_heredada "
        "BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute("ALTER TABLE simulaciones ADD COLUMN IF NOT EXISTS es_demo BOOLEAN NOT NULL DEFAULT false")
    op.execute(CREATE_SNAPSHOT_SQL)
    op.execute(CREATE_RECALIBRACIONES_SQL)
    op.execute(SNAPSHOT_POST_004_SQL)
    op.execute(MARK_POST_004_SQL)
    op.execute(Marcar_DEMO_SQL)

    op.execute("ALTER TABLE parametros DROP CONSTRAINT IF EXISTS chk_parametros_agua_inicial")
    op.execute(
        f"ALTER TABLE parametros ADD CONSTRAINT chk_parametros_agua_inicial "
        f"CHECK ({CHECK_SQL}) NOT VALID"
    )
    op.execute("ALTER TABLE parametros VALIDATE CONSTRAINT chk_parametros_agua_inicial")

    op.execute(VALIDAR_HEREDADO_FN)
    op.execute("DROP TRIGGER IF EXISTS trg_validar_parametro_heredado ON parametros")
    op.execute(
        "CREATE TRIGGER trg_validar_parametro_heredado "
        "BEFORE INSERT OR UPDATE OF configuracion_heredada ON parametros "
        "FOR EACH ROW EXECUTE FUNCTION validar_parametro_heredado()"
    )

    op.execute(BLOQUEAR_EJECUCION_FN)
    op.execute("DROP TRIGGER IF EXISTS trg_bloquear_ejecucion_historica_jobs ON simulation_jobs")
    op.execute(
        "CREATE TRIGGER trg_bloquear_ejecucion_historica_jobs "
        "BEFORE INSERT OR UPDATE OF estado ON simulation_jobs "
        "FOR EACH ROW EXECUTE FUNCTION bloquear_ejecucion_historica()"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_bloquear_ejecucion_historica_sim ON simulaciones")
    op.execute(
        "CREATE TRIGGER trg_bloquear_ejecucion_historica_sim "
        "BEFORE INSERT OR UPDATE OF estado ON simulaciones "
        "FOR EACH ROW EXECUTE FUNCTION bloquear_ejecucion_historica()"
    )

    op.execute(SELECCIONAR_RUNNING_HUERFANOS_SQL)
    op.execute(RECONCILIAR_RUNNING_SQL)
    op.execute(REGISTRAR_RUNNING_SQL)
    op.execute("DROP TABLE running_huerfanos_005")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_bloquear_ejecucion_historica_sim ON simulaciones")
    op.execute("DROP TRIGGER IF EXISTS trg_bloquear_ejecucion_historica_jobs ON simulation_jobs")
    op.execute("DROP TRIGGER IF EXISTS trg_validar_parametro_heredado ON parametros")
    op.execute("DROP FUNCTION IF EXISTS bloquear_ejecucion_historica()")
    op.execute("DROP FUNCTION IF EXISTS validar_parametro_heredado()")
    op.execute("DROP TABLE IF EXISTS simulaciones_recalibraciones")
    op.execute("ALTER TABLE simulaciones DROP COLUMN IF EXISTS es_demo")
    op.execute("ALTER TABLE parametros DROP CONSTRAINT IF EXISTS chk_parametros_agua_inicial")
    op.execute(
        "ALTER TABLE parametros ADD CONSTRAINT chk_parametros_agua_inicial "
        "CHECK (agua_inicial >= (0)::numeric) NOT VALID"
    )
