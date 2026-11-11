-- ==============================================================================
-- AGROCHACO - Script DDL Inicial de Base de Datos
-- Módulo: Persistencia e Infraestructura (Yulenka Magne)
-- Motor: PostgreSQL 16
-- Descripción: Creación de las 6 tablas esenciales con tipos de datos estrictos,
--              integridad referencial (CASCADE), restricciones CHECK e índices.
-- ==============================================================================

-- Habilitar extensión para generación de identificadores UUID si es necesario
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================================================
-- 1. TABLA: simulaciones (Entidad Raíz)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS simulaciones (
    id VARCHAR(36) PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    fuente_datos VARCHAR(100) NOT NULL,
    escenario VARCHAR(50) NOT NULL,
    cantidad_escenarios INTEGER NOT NULL DEFAULT 1 CHECK (cantidad_escenarios > 0),
    dias INTEGER NOT NULL CHECK (dias BETWEEN 1 AND 365),
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (estado IN ('pending', 'running', 'completed', 'failed', 'paused')),
    semilla BIGINT NULL
);

-- Índices para optimizar consultas de historial y filtrado en simulaciones
CREATE INDEX IF NOT EXISTS idx_simulaciones_fecha_creacion
    ON simulaciones (fecha_creacion DESC);
CREATE INDEX IF NOT EXISTS idx_simulaciones_estado
    ON simulaciones (estado);
CREATE INDEX IF NOT EXISTS idx_simulaciones_escenario
    ON simulaciones (escenario);

-- ==============================================================================
-- 2. TABLA: parametros (Configuración biofísica, suelo y clima)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS parametros (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    simulacion_id VARCHAR(36) NOT NULL UNIQUE,
    agua_inicial NUMERIC(8, 2) NOT NULL CHECK (agua_inicial >= 0),
    capacidad_suelo NUMERIC(8, 2) NOT NULL CHECK (capacidad_suelo > 0),
    umbral_hidrico NUMERIC(8, 2) NOT NULL CHECK (umbral_hidrico >= 0),
    configuracion_json JSONB NOT NULL,
    CONSTRAINT fk_parametros_simulacion
        FOREIGN KEY (simulacion_id)
        REFERENCES simulaciones (id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_parametros_simulacion_id
    ON parametros (simulacion_id);
CREATE INDEX IF NOT EXISTS idx_parametros_configuracion_gin
    ON parametros USING GIN (configuracion_json);

-- ==============================================================================
-- 3. TABLA: resultados (Métricas finales biofísicas de estrés hídrico)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS resultados (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    simulacion_id VARCHAR(36) NOT NULL UNIQUE,
    deficit_medio NUMERIC(8, 4) NOT NULL CHECK (deficit_medio BETWEEN 0 AND 1),
    deficit_maximo NUMERIC(8, 4) NOT NULL CHECK (deficit_maximo BETWEEN 0 AND 1),
    agua_final_media NUMERIC(10, 2) NOT NULL,
    agua_minima NUMERIC(10, 2) NOT NULL,
    escenarios_con_deficit INTEGER NOT NULL DEFAULT 0 CHECK (escenarios_con_deficit >= 0),
    archivo_detalle VARCHAR(255) NULL,
    CONSTRAINT fk_resultados_simulacion
        FOREIGN KEY (simulacion_id)
        REFERENCES simulaciones (id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_resultados_simulacion_id
    ON resultados (simulacion_id);

-- ==============================================================================
-- 4. TABLA: rendimiento (Benchmarks HPC: Speedup, Eficiencia, Hilos, Procesos)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS rendimiento (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    simulacion_id VARCHAR(36) NOT NULL,
    modalidad VARCHAR(20) NOT NULL
        CHECK (modalidad IN ('secuencial', 'openmp', 'mpi', 'hibrido')),
    hilos INTEGER NOT NULL DEFAULT 1 CHECK (hilos > 0),
    procesos INTEGER NOT NULL DEFAULT 1 CHECK (procesos > 0),
    nodos INTEGER NOT NULL DEFAULT 1 CHECK (nodos > 0),
    tiempo_segundos NUMERIC(12, 4) NOT NULL CHECK (tiempo_segundos >= 0),
    speedup NUMERIC(10, 4) NOT NULL DEFAULT 1.0000 CHECK (speedup >= 0),
    eficiencia NUMERIC(8, 4) NOT NULL DEFAULT 1.0000 CHECK (eficiencia >= 0),
    repeticion INTEGER NOT NULL DEFAULT 1 CHECK (repeticion >= 1),
    CONSTRAINT fk_rendimiento_simulacion
        FOREIGN KEY (simulacion_id)
        REFERENCES simulaciones (id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rendimiento_simulacion_id
    ON rendimiento (simulacion_id);
CREATE INDEX IF NOT EXISTS idx_rendimiento_modalidad
    ON rendimiento (modalidad);

-- ==============================================================================
-- 5. TABLA: fuentes_datos (Integridad y trazabilidad de datasets meteorológicos)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS fuentes_datos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    simulacion_id VARCHAR(36) NOT NULL,
    nombre_archivo VARCHAR(255) NOT NULL,
    formato VARCHAR(20) NOT NULL
        CHECK (formato IN ('csv', 'json', 'netcdf', 'geotiff', 'txt')),
    hash_archivo VARCHAR(64) NOT NULL,
    periodo VARCHAR(50) NULL,
    descripcion TEXT NULL,
    CONSTRAINT fk_fuentes_simulacion
        FOREIGN KEY (simulacion_id)
        REFERENCES simulaciones (id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fuentes_simulacion_id
    ON fuentes_datos (simulacion_id);
CREATE INDEX IF NOT EXISTS idx_fuentes_hash
    ON fuentes_datos (hash_archivo);

-- ==============================================================================
-- 6. TABLA: eventos_ejecucion (Auditoría cronológica de logs de ejecución)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS eventos_ejecucion (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    simulacion_id VARCHAR(36) NOT NULL,
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    nivel VARCHAR(10) NOT NULL
        CHECK (nivel IN ('INFO', 'WARNING', 'ERROR', 'DEBUG', 'CRITICAL')),
    mensaje TEXT NOT NULL,
    CONSTRAINT fk_eventos_simulacion
        FOREIGN KEY (simulacion_id)
        REFERENCES simulaciones (id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_eventos_sim_fecha
    ON eventos_ejecucion (simulacion_id, fecha_hora ASC);

-- ==============================================================================
-- 7. TABLA: alembic_version (Sincronización con el sistema de migraciones Alembic)
-- ==============================================================================
-- Permite que cuando Docker inicialice la base con init.sql, Alembic reconozca
-- que la migración inicial ya fue aplicada, evitando errores de tablas duplicadas.
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

INSERT INTO alembic_version (version_num)
VALUES ('001_inicial_seis_tablas')
ON CONFLICT (version_num) DO NOTHING;
