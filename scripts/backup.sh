#!/usr/bin/env bash
# ==============================================================================
# AgroChaco - Script de Copias de Seguridad (Backup)
# Responsable: Yulenka Magne
# Motor: PostgreSQL 16 (vía Docker o Cliente Nativo)
# ==============================================================================

set -euo pipefail

# 1. Configuración de Directorios y Carga de Entorno
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -f "${PROJECT_ROOT}/.env" ]; then
    # shellcheck disable=SC2046
    export $(grep -v '^#' "${PROJECT_ROOT}/.env" | xargs -d '\n')
fi

# Variables por defecto
DB_NAME="${1:-${POSTGRES_DB:-agrochaco}}"
DB_USER="${POSTGRES_USER:-agrochaco_user}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
BACKUP_DIR="${2:-${PROJECT_ROOT}/backups}"
CONTAINER_NAME="agrochaco_db"

TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
BACKUP_FILE="${BACKUP_DIR}/backup_${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "=========================================================="
echo "   AGROCHACO - GENERADOR DE COPIAS DE SEGURIDAD (POSTGRESQL 16)"
echo "=========================================================="
echo "Base de datos a respaldar: ${DB_NAME}"
echo "Destino del respaldo:      ${BACKUP_FILE}"
echo "Fecha y hora:              $(date)"
echo "----------------------------------------------------------"

mkdir -p "${BACKUP_DIR}"

# 2. Comprobar si el contenedor Docker está activo
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[*] Detectado contenedor activo '${CONTAINER_NAME}'. Generando volcado vía Docker..."
    docker exec "${CONTAINER_NAME}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists | gzip > "${BACKUP_FILE}"
elif command -v pg_dump >/dev/null 2>&1; then
    echo "[*] Utilizando cliente nativo pg_dump..."
    PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists | gzip > "${BACKUP_FILE}"
else
    echo "[ERROR] No se encontró el contenedor Docker '${CONTAINER_NAME}' ni el comando nativo 'pg_dump'."
    exit 1
fi

# 3. Verificación de Integridad
if [ -s "${BACKUP_FILE}" ]; then
    FILE_SIZE="$(du -h "${BACKUP_FILE}" | cut -f1)"
    echo "----------------------------------------------------------"
    echo "[OK] Respaldo generado con éxito."
    echo "Archivo: ${BACKUP_FILE}"
    echo "Tamaño:  ${FILE_SIZE}"
    echo "=========================================================="
else
    echo "[ERROR] El archivo de respaldo se creó vacío o falló la ejecución."
    rm -f "${BACKUP_FILE}"
    exit 1
fi

