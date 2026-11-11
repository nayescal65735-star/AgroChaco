#!/usr/bin/env bash
# ==============================================================================
# AgroChaco - Script de Restauración de Base de Datos
# Responsable: Yulenka Magne
# Motor: PostgreSQL 16 (vía Docker o Cliente Nativo)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -f "${PROJECT_ROOT}/.env" ]; then
    # shellcheck disable=SC2046
    export $(grep -v '^#' "${PROJECT_ROOT}/.env" | xargs -d '\n')
fi

BACKUP_FILE="${1:-}"
TARGET_DB="${2:-}"
CONTAINER_NAME="agrochaco_db"
DB_USER="${POSTGRES_USER:-agrochaco_user}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"

echo "=========================================================="
echo "   AGROCHACO - RESTAURADOR DE BASE DE DATOS (POSTGRESQL 16)"
echo "=========================================================="

if [ -z "${BACKUP_FILE}" ] || [ -z "${TARGET_DB}" ]; then
    echo "Uso: $0 <archivo_respaldo.sql.gz> <base_datos_destino> [--confirm]"
    echo ""
    echo "Ejemplo seguro (restaurar en base de datos de pruebas):"
    echo "  $0 backups/backup_agrochaco_20261111_120000.sql.gz agrochaco_test --confirm"
    echo ""
    echo "[AVISO DE SEGURIDAD]: Para proteger los datos, nunca restaures sobre"
    echo "                      la base activa sin verificar antes el respaldo."
    exit 1
fi

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "[ERROR] El archivo de respaldo '${BACKUP_FILE}' no existe."
    exit 1
fi

CONFIRM_FLAG="${3:-}"
if [ "${CONFIRM_FLAG}" != "--confirm" ]; then
    echo "[AVISO DE SEGURIDAD]: Esta operación sobreescribirá datos en '${TARGET_DB}'."
    echo "Para proceder, ejecuta el comando añadiendo la bandera --confirm al final:"
    echo "  $0 ${BACKUP_FILE} ${TARGET_DB} --confirm"
    exit 1
fi

echo "Archivo de origen:      ${BACKUP_FILE}"
echo "Base de datos destino:  ${TARGET_DB}"
echo "Fecha y hora de inicio: $(date)"
echo "----------------------------------------------------------"

# Comprobar método de restauración
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[*] Restaurando en contenedor Docker '${CONTAINER_NAME}'..."
    # Asegurar que la base de datos de destino existe
    docker exec "${CONTAINER_NAME}" psql -U "${DB_USER}" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = '${TARGET_DB}'" | grep -q 1 || \
        docker exec "${CONTAINER_NAME}" psql -U "${DB_USER}" -d postgres -c "CREATE DATABASE ${TARGET_DB};"

    # Limpiar esquema public de forma segura para permitir recreación limpia sin colisiones de FK
    echo "[*] Limpiando esquema public previo en '${TARGET_DB}'..."
    docker exec "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${TARGET_DB}" -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"

    # Descomprimir y restaurar
    echo "[*] Aplicando volcado SQL..."
    gunzip -c "${BACKUP_FILE}" | docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${TARGET_DB}" -v ON_ERROR_STOP=1 >/dev/null
elif command -v psql >/dev/null 2>&1; then
    echo "[*] Restaurando mediante cliente nativo psql..."
    PGPASSWORD="${POSTGRES_PASSWORD:-}" gunzip -c "${BACKUP_FILE}" | psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TARGET_DB}" -v ON_ERROR_STOP=1 >/dev/null
else
    echo "[ERROR] No se encontró el contenedor Docker ni el cliente psql."
    exit 1
fi

echo "----------------------------------------------------------"
echo "[OK] Base de datos '${TARGET_DB}' restaurada exitosamente desde ${BACKUP_FILE}."
echo "=========================================================="
