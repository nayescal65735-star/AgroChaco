# AgroChaco — Módulo de Base de Datos, Persistencia e Infraestructura

**Responsable:** Yulenka Magne
**Motor:** PostgreSQL 16
**ORM:** SQLAlchemy 2.x
**Migraciones:** Alembic
**Contenedores:** Docker & Docker Compose
**Rama:** `feature/database-yulenka`

---

## 1. Visión General y Arquitectura

El módulo de base de datos de **AgroChaco** proporciona la persistencia transaccional de alto rendimiento para el simulador de estrés hídrico y sequías en maíz del Gran Chaco boliviano.

```
       [ Frontend React / Vite ]
                   │
                   ▼ (HTTP JSON)
         [ Backend FastAPI ]
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
[ SimulationRepository ]  [ ExportService ]
        │                     │
        ▼                     ▼
 [ SQLAlchemy ORM ]     (CSV / JSON Streaming)
        │
        ▼ (psycopg v3)
 [ PostgreSQL 16 (Docker) ]
   ├── simulaciones (Entidad Raíz)
   ├── parametros (1:1 JSONB)
   ├── resultados (1:1 Métricas)
   ├── rendimiento (1:N HPC)
   ├── fuentes_datos (1:N Clima)
   └── eventos_ejecucion (1:N Logs)
```

---

## 2. Descripción de las Seis Tablas y Esquema

| Tabla | Clave Primaria | Clave Foránea | Restricciones / Índices Clave | Propósito |
| :--- | :--- | :--- | :--- | :--- |
| **`simulaciones`** | `id VARCHAR(36)` | Ninguna (Raíz) | `chk_simulaciones_dias` (1-365)<br>`chk_simulaciones_estado`<br>`idx_simulaciones_fecha_creacion DESC` | Registro principal de cada corrida de simulación biofísica. |
| **`parametros`** | `id BIGINT IDENTITY` | `simulacion_id -> simulaciones.id` (CASCADE) | `UNIQUE(simulacion_id)`<br>`chk_parametros_capacidad_suelo > 0`<br>`idx_parametros_configuracion_gin` (GIN) | Configuración agronómica, balance hídrico y malla espacial en `JSONB`. |
| **`resultados`** | `id BIGINT IDENTITY` | `simulacion_id -> simulaciones.id` (CASCADE) | `UNIQUE(simulacion_id)`<br>`chk_resultados_deficit_medio` [0, 1]<br>`chk_resultados_deficit_maximo` [0, 1] | Métricas agregadas de estrés hídrico, déficit y agua final. |
| **`rendimiento`** | `id BIGINT IDENTITY` | `simulacion_id -> simulaciones.id` (CASCADE) | `chk_rendimiento_modalidad`<br>`idx_rendimiento_modalidad`<br>`speedup >= 0, eficiencia >= 0` | Benchmarks HPC: hilos OpenMP, procesos MPI, nodos, Speedup y tiempo. |
| **`fuentes_datos`** | `id BIGINT IDENTITY` | `simulacion_id -> simulaciones.id` (CASCADE) | `hash_archivo VARCHAR(64)`<br>`chk_fuentes_formato` (csv, json, netcdf)<br>`idx_fuentes_hash` | Trazabilidad e integridad criptográfica (SHA-256) de datos meteorológicos. |
| **`eventos_ejecucion`** | `id BIGINT IDENTITY` | `simulacion_id -> simulaciones.id` (CASCADE) | `chk_eventos_nivel` (INFO, WARN, ERROR)<br>`idx_eventos_sim_fecha (simulacion_id, fecha_hora)` | Traza cronológica de auditoría de ejecución del motor y de la API. |

---

## 3. Configuración del Entorno y Docker

### Variables de Entorno (`.env`)
Copiar la plantilla desde `.env.example`:
```bash
cp .env.example .env
```
Contenido configurado en `.env`:
```ini
POSTGRES_DB=agrochaco
POSTGRES_USER=agrochaco_user
POSTGRES_PASSWORD=agrochaco_dev_2026
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://agrochaco_user:agrochaco_dev_2026@localhost:5432/agrochaco
POSTGRES_TEST_DB=agrochaco_test
```

### Comandos de Docker Compose
```bash
# Iniciar contenedor de base de datos
docker compose up -d db

# Comprobar salud del contenedor
docker compose ps

# Detener contenedor (conservando el volumen postgres_data)
docker compose down

# Acceso directo por consola interactiva psql
docker exec -it agrochaco_db psql -U agrochaco_user -d agrochaco
```

---

## 4. Migraciones con Alembic

Alembic gestiona el ciclo de vida del esquema de base de datos:

```bash
# Ver estado actual de la migración
alembic current

# Aplicar migraciones hasta la última versión
alembic upgrade head

# Revertir todas las migraciones (base)
alembic downgrade base

# Crear una nueva migración automática tras cambiar modelos
alembic revision --autogenerate -m "descripcion_del_cambio"
```

> [!NOTE]
> El archivo `backend/app/db/init.sql` y la migración `001_inicial_seis_tablas.py` están sincronizados mediante introspección y estampado automático en `alembic_version`, garantizando que una instalación nueva en Docker no genere errores de tablas duplicadas.

---

## 5. Capa de Repositorios (`SimulationRepository`)

Ubicación: `backend/app/db/repository.py`

### Métodos Principales:
- `crear_simulacion_con_parametros(db, datos_simulacion, datos_parametros)`:
  Inserción atómica (Unit of Work). Si falla cualquier inserción, ejecuta `db.rollback()` garantizando que no existan registros huérfanos.
- `guardar_resultados(db, simulacion_id, datos_resultados)`: Guarda o actualiza métricas biofísicas.
- `guardar_rendimiento(db, simulacion_id, datos_rendimiento)`: Inserta registros de aceleración HPC.
- `registrar_evento(db, simulacion_id, nivel, mensaje)`: Registra eventos de log.
- `registrar_fuente_datos(db, simulacion_id, ...)`: Registra datasets meteorológicos con hash SHA-256.
- `listar_historial(db, search, estado, escenario, fecha_desde, fecha_hasta, limit, offset)`:
  Consulta paginada con filtros a nivel de base de datos y ordenamiento por fecha descendente.
- `obtener_por_id(db, simulacion_id, cargar_relaciones=True)`: Recupera la simulación y precarga sus 5 relaciones satélite.
- `actualizar_estado(db, simulacion_id, nuevo_estado)`: Modifica el estado (`pending`, `running`, `completed`, `failed`).
- `eliminar_simulacion(db, simulacion_id)`: Eliminación en cascada total.

---

## 6. Datos de Prueba y Semillas (`seeds.py`)

Ubicación: `backend/app/db/seeds.py`

Genera 6 simulaciones de demostración correspondientes a los municipios del Gran Chaco:
- **Yacuiba (Tarija):** Escenario moderado SSP-245, motor híbrido MPI+OpenMP.
- **Villa Montes (Tarija):** Escenario extremo SSP-585, motor OpenMP (16 hilos).
- **Charagua (Santa Cruz):** Sequía reciente 2023, motor MPI distribuido (4 nodos).
- **Macharetí (Chuquisaca):** Simulación en estado `running`.
- **Caraparí (Tarija):** Línea base histórica monohilo secuencial ($T_1$).
- **Boyuibe (Santa Cruz):** Simulación en cola en estado `pending`.

### Ejecución de Seeds:
```bash
python -m app.db.seeds
```
*Idempotencia:* Si las simulaciones ya existen, el script detecta su presencia y no genera duplicados.

---

## 7. Servicio de Exportación (`ExportService`)

Ubicación: `backend/app/services/export_service.py`

### Exportación JSON:
```python
from app.services.export_service import ExportService

# Retorna diccionario estructurado con tipos nativos
datos_dict = ExportService.exportar_simulacion_json(simulacion)

# Retorna string JSON UTF-8
json_str = ExportService.exportar_simulacion_json_str(simulacion, indent=2)
```

### Exportación CSV:
```python
# Historial completo a CSV
csv_historial = ExportService.exportar_historial_csv(lista_simulaciones)

# Traza de eventos a CSV
csv_eventos = ExportService.exportar_eventos_csv(simulacion.eventos)

# Métricas de aceleración HPC a CSV
csv_rendimiento = ExportService.exportar_rendimientos_csv(simulacion.rendimientos)
```

---

## 8. Copias de Seguridad y Restauración

Ubicación: `scripts/backup.sh` y `scripts/restore.sh`

### Generar Copia de Seguridad:
```bash
./scripts/backup.sh [nombre_bd] [directorio_destino]

# Ejemplo (respalda 'agrochaco' en ./backups/):
./scripts/backup.sh
```
El archivo se guarda comprimido con marca de tiempo:
`backups/backup_agrochaco_YYYYMMDD_HHMMSS.sql.gz`

### Restaurar Copia de Seguridad:
```bash
./scripts/restore.sh <archivo.sql.gz> <bd_destino> --confirm

# Ejemplo seguro (restaurar en base de datos de prueba):
./scripts/restore.sh backups/backup_agrochaco_20261111_120000.sql.gz agrochaco_test --confirm
```

> [!CAUTION]
> Para evitar pérdidas accidentales, el script de restauración exige la bandera `--confirm` y limpia el esquema de forma controlada antes de aplicar el volcado.

---

## 9. Pruebas Automatizadas

La suite de pruebas contiene 19 pruebas distribuidas en 4 módulos:

| Archivo | Pruebas | Cobertura |
| :--- | :---: | :--- |
| `tests/test_infra_models.py` | 5 | Conexión PostgreSQL 16, catálogo de tablas, tipos, cascada y restricciones CHECK. |
| `tests/test_persistence.py` | 5 | Inserción atómica, rollback ante error, resultados, fuentes, eventos y eliminación. |
| `tests/test_history.py` | 5 | Historial completo, filtros por estado/escenario/texto, paginación y orden. |
| `tests/test_exports.py` | 4 | JSON jerárquico, CSV de historial/eventos/HPC y validación ante nulos. |

### Ejecutar Suite Completa:
```bash
pytest -v -s tests/
```

---

## 10. Guía de Integración para Nayeli Aguilar (FastAPI)

Para conectar los endpoints de FastAPI con PostgreSQL, Nayeli solo necesita reemplazar el diccionario en memoria `_simulations: dict` por el repositorio:

### Ejemplo: Crear Simulación (`POST /api/simulations`)
```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.repository import SimulationRepository

@router.post("", status_code=status.HTTP_201_CREATED)
def create_simulation(data: SimulationCreate, db: Session = Depends(get_db)):
    simulation_id = f"SIM-{uuid4().hex[:12].upper()}"
    config_dict = data.model_dump(mode="json")

    datos_sim = {
        "id": simulation_id,
        "nombre": data.name,
        "fuente_datos": f"Estación {data.zoneName}",
        "escenario": data.droughtScenario,
        "cantidad_escenarios": 1,
        "dias": data.simulationDays,
        "estado": "pending",
    }
    datos_param = {
        "agua_inicial": Decimal(str(data.initialMoisturePercent)),
        "capacidad_suelo": Decimal("100.00"),
        "umbral_hidrico": Decimal("50.00"),
        "configuracion_json": config_dict,
    }

    sim = SimulationRepository.crear_simulacion_con_parametros(db, datos_sim, datos_param)
    return {
        "id": sim.id,
        "config": config_dict,
        "status": sim.estado,
        "progressPercent": 0,
        "createdAt": sim.fecha_creacion.isoformat(),
        "completedAt": None,
    }
```

### Ejemplo: Listar Historial con Paginación (`GET /api/simulations`)
```python
@router.get("")
def list_simulations(
    search: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    sims, total = SimulationRepository.listar_historial(
        db, search=search, estado=status, limit=limit, offset=offset
    )
    return {
        "total": total,
        "simulations": [
            {
                "id": s.id,
                "config": s.parametro.configuracion_json if s.parametro else {},
                "status": s.estado,
                "progressPercent": 100 if s.estado == "completed" else 0,
                "createdAt": s.fecha_creacion.isoformat(),
                "completedAt": None,
            }
            for s in sims
        ],
    }
```
