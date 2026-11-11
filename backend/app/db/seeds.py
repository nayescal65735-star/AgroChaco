"""Módulo de semillas y datos de prueba para AgroChaco.

Genera datos de demostración coherentes con las 6 zonas chaqueñas del frontend:
- Yacuiba (Tarija)
- Villa Montes (Tarija)
- Charagua (Santa Cruz)
- Macharetí (Chuquisaca)
- Caraparí (Tarija)
- Boyuibe (Santa Cruz)

Cubre los 4 motores HPC (secuencial, openmp, mpi, hibrido), parámetros biofísicos,
resultados de estrés hídrico FAO-56, fuentes meteorológicas y eventos de ejecución.
Diseñado para ser idempotente (se puede ejecutar múltiples veces sin duplicar).

AVISO CIENTÍFICO: Estos registros son exclusivamente para pruebas técnicas
y desarrollo de software. No representan calibraciones agronómicas experimentales de campo.
"""

from decimal import Decimal
import os
import sys
from pathlib import Path

# Asegurar path para imports
BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import Session
from app.db.database import SessionLocal, engine
from app.models import (
    EventoEjecucion,
    FuenteDatos,
    Parametro,
    Rendimiento,
    Resultado,
    Simulacion,
)


CHACO_SEEDS = [
    {
        "simulacion": {
            "id": "SIM-YACUIBA-001",
            "nombre": "[DEMO] Sequía Moderada Maíz Criollo Yacuiba",
            "fuente_datos": "Estación Meteorológica SENAMHI Yacuiba",
            "escenario": "moderado_ssp245",
            "cantidad_escenarios": 10,
            "dias": 120,
            "estado": "completed",
            "semilla": 1024,
        },
        "parametro": {
            "agua_inicial": Decimal("24.50"),
            "capacidad_suelo": Decimal("130.00"),
            "umbral_hidrico": Decimal("65.00"),
            "configuracion_json": {
                "zone": "yacuiba",
                "zoneName": "Yacuiba",
                "department": "Tarija",
                "soilType": "franco_arenoso",
                "cornVariety": "chaco_01_criollo",
                "gridConfig": {"rows": 100, "cols": 100, "cellSizeMeters": 50},
                "engine": "hibrido",
                "openmpThreads": 8,
                "mpiProcesses": 4,
                "nodesCount": 2,
            },
        },
        "resultado": {
            "deficit_medio": Decimal("0.2840"),
            "deficit_maximo": Decimal("0.6210"),
            "agua_final_media": Decimal("52.30"),
            "agua_minima": Decimal("22.10"),
            "escenarios_con_deficit": 4,
            "archivo_detalle": "/results/SIM-YACUIBA-001/timeline.csv",
        },
        "rendimientos": [
            {
                "modalidad": "secuencial",
                "hilos": 1,
                "procesos": 1,
                "nodos": 1,
                "tiempo_segundos": Decimal("128.4500"),
                "speedup": Decimal("1.0000"),
                "eficiencia": Decimal("1.0000"),
                "repeticion": 1,
            },
            {
                "modalidad": "hibrido",
                "hilos": 8,
                "procesos": 4,
                "nodos": 2,
                "tiempo_segundos": Decimal("5.2100"),
                "speedup": Decimal("24.6545"),
                "eficiencia": Decimal("0.7705"),
                "repeticion": 1,
            },
        ],
        "fuente_datos": {
            "nombre_archivo": "clima_historico_yacuiba_2000_2023.csv",
            "formato": "csv",
            "hash_archivo": "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
            "periodo": "2000-2023",
            "descripcion": "Serie histórica validada de precipitación y ETP diaria",
        },
        "eventos": [
            ("INFO", "Inicio de inicialización de malla espacial 100x100 en 2 nodos."),
            ("INFO", "Balance hídrico mono-capa completado para 120 días de cultivo."),
            ("INFO", "Cálculo de penalización fenológica FAO-33 concluido sin alertas."),
        ],
    },
    {
        "simulacion": {
            "id": "SIM-VILLAMONTES-002",
            "nombre": "[DEMO] Estrés Extremo Villa Montes Suelo Arenoso",
            "fuente_datos": "Red Agroclimatológica INIAF Chaco",
            "escenario": "extremo_ssp585",
            "cantidad_escenarios": 20,
            "dias": 140,
            "estado": "completed",
            "semilla": 2048,
        },
        "parametro": {
            "agua_inicial": Decimal("16.00"),
            "capacidad_suelo": Decimal("95.00"),
            "umbral_hidrico": Decimal("48.00"),
            "configuracion_json": {
                "zone": "villamontes",
                "zoneName": "Villa Montes",
                "department": "Tarija",
                "soilType": "arenoso",
                "cornVariety": "dekalb_7088",
                "gridConfig": {"rows": 150, "cols": 150, "cellSizeMeters": 30},
                "engine": "openmp",
                "openmpThreads": 16,
            },
        },
        "resultado": {
            "deficit_medio": Decimal("0.5920"),
            "deficit_maximo": Decimal("0.9150"),
            "agua_final_media": Decimal("21.40"),
            "agua_minima": Decimal("8.50"),
            "escenarios_con_deficit": 18,
            "archivo_detalle": "/results/SIM-VILLAMONTES-002/timeline.csv",
        },
        "rendimientos": [
            {
                "modalidad": "openmp",
                "hilos": 16,
                "procesos": 1,
                "nodos": 1,
                "tiempo_segundos": Decimal("18.3200"),
                "speedup": Decimal("11.8500"),
                "eficiencia": Decimal("0.7406"),
                "repeticion": 1,
            }
        ],
        "fuente_datos": {
            "nombre_archivo": "proyeccion_ssp585_villamontes.json",
            "formato": "json",
            "hash_archivo": "b2c3d4e5f6a17890123456789abcdef0123456789abcdef0123456789abcdef0",
            "periodo": "2024-2050",
            "descripcion": "Proyección climática de alta resolución modelo regional",
        },
        "eventos": [
            ("INFO", "Asignados 16 hilos OpenMP para simulación mono-nodo."),
            ("WARNING", "Umbral crítico de estrés hídrico superado en etapa de floración R1."),
            ("INFO", "Resultados consolidados y exportados correctamente."),
        ],
    },
    {
        "simulacion": {
            "id": "SIM-CHARAGUA-003",
            "nombre": "[DEMO] Sequía Reciente 2023 Charagua Iyambae",
            "fuente_datos": "Estación Charagua Autonomía Indígena",
            "escenario": "sequia_recente_2023",
            "cantidad_escenarios": 5,
            "dias": 90,
            "estado": "completed",
            "semilla": 4096,
        },
        "parametro": {
            "agua_inicial": Decimal("20.00"),
            "capacidad_suelo": Decimal("140.00"),
            "umbral_hidrico": Decimal("70.00"),
            "configuracion_json": {
                "zone": "charagua",
                "zoneName": "Charagua Iyambae",
                "department": "Santa Cruz",
                "soilType": "franco_arcilloso",
                "cornVariety": "iniaf_h1",
                "gridConfig": {"rows": 80, "cols": 80, "cellSizeMeters": 50},
                "engine": "mpi",
                "mpiProcesses": 8,
                "nodesCount": 4,
            },
        },
        "resultado": {
            "deficit_medio": Decimal("0.4180"),
            "deficit_maximo": Decimal("0.7850"),
            "agua_final_media": Decimal("38.60"),
            "agua_minima": Decimal("14.20"),
            "escenarios_con_deficit": 4,
            "archivo_detalle": "/results/SIM-CHARAGUA-003/timeline.csv",
        },
        "rendimientos": [
            {
                "modalidad": "mpi",
                "hilos": 1,
                "procesos": 8,
                "nodos": 4,
                "tiempo_segundos": Decimal("9.4500"),
                "speedup": Decimal("6.2000"),
                "eficiencia": Decimal("0.7750"),
                "repeticion": 1,
            }
        ],
        "fuente_datos": {
            "nombre_archivo": "datos_estacion_charagua_2023.csv",
            "formato": "csv",
            "hash_archivo": "c3d4e5f6a1b27890123456789abcdef0123456789abcdef0123456789abcdef0",
            "periodo": "2023",
            "descripcion": "Registro meteorológico de sequía histórica 2023",
        },
        "eventos": [
            ("INFO", "Despliegue distribuido MPI en 4 nodos de cómputo."),
            ("INFO", "Intercambio de fronteras (halo exchange) verificado."),
            ("INFO", "Simulación completada con éxito."),
        ],
    },
    {
        "simulacion": {
            "id": "SIM-MACHARETI-004",
            "nombre": "[DEMO] Simulación en Ejecución Macharetí",
            "fuente_datos": "SENAMHI Macharetí Chuquisaca",
            "escenario": "moderado_ssp245",
            "cantidad_escenarios": 8,
            "dias": 100,
            "estado": "running",
            "semilla": 8192,
        },
        "parametro": {
            "agua_inicial": Decimal("19.00"),
            "capacidad_suelo": Decimal("110.00"),
            "umbral_hidrico": Decimal("55.00"),
            "configuracion_json": {
                "zone": "machareti",
                "zoneName": "Macharetí",
                "department": "Chuquisaca",
                "soilType": "franco_arenoso",
                "cornVariety": "pioneer_30f35",
                "gridConfig": {"rows": 120, "cols": 120, "cellSizeMeters": 40},
                "engine": "hibrido",
                "openmpThreads": 4,
                "mpiProcesses": 4,
                "nodesCount": 2,
            },
        },
        "resultado": None,
        "rendimientos": [],
        "fuente_datos": {
            "nombre_archivo": "senamhi_machareti_mensual.csv",
            "formato": "csv",
            "hash_archivo": "d4e5f6a1b2c37890123456789abcdef0123456789abcdef0123456789abcdef0",
            "periodo": "2021-2023",
            "descripcion": "Datos agroclimáticos estación Macharetí",
        },
        "eventos": [
            ("INFO", "Corrida iniciada y encolada en el clúster HPC."),
            ("INFO", "Procesando día 45 de 100 (avance 45%)."),
        ],
    },
    {
        "simulacion": {
            "id": "SIM-CARAPARI-005",
            "nombre": "[DEMO] Línea Base Caraparí Humedad Óptima",
            "fuente_datos": "Estación Experimental San Alberto",
            "escenario": "historico",
            "cantidad_escenarios": 2,
            "dias": 110,
            "estado": "completed",
            "semilla": 16384,
        },
        "parametro": {
            "agua_inicial": Decimal("28.00"),
            "capacidad_suelo": Decimal("150.00"),
            "umbral_hidrico": Decimal("75.00"),
            "configuracion_json": {
                "zone": "carapari",
                "zoneName": "Caraparí",
                "department": "Tarija",
                "soilType": "franco",
                "cornVariety": "chaco_01_criollo",
                "gridConfig": {"rows": 60, "cols": 60, "cellSizeMeters": 50},
                "engine": "secuencial",
            },
        },
        "resultado": {
            "deficit_medio": Decimal("0.1120"),
            "deficit_maximo": Decimal("0.3400"),
            "agua_final_media": Decimal("72.80"),
            "agua_minima": Decimal("44.50"),
            "escenarios_con_deficit": 0,
            "archivo_detalle": "/results/SIM-CARAPARI-005/timeline.csv",
        },
        "rendimientos": [
            {
                "modalidad": "secuencial",
                "hilos": 1,
                "procesos": 1,
                "nodos": 1,
                "tiempo_segundos": Decimal("24.8000"),
                "speedup": Decimal("1.0000"),
                "eficiencia": Decimal("1.0000"),
                "repeticion": 1,
            }
        ],
        "fuente_datos": {
            "nombre_archivo": "carapari_precipitacion_pluvial.csv",
            "formato": "csv",
            "hash_archivo": "e5f6a1b2c3d47890123456789abcdef0123456789abcdef0123456789abcdef0",
            "periodo": "2015-2023",
            "descripcion": "Microclima subandino de alta pluviometría",
        },
        "eventos": [
            ("INFO", "Ejecución secuencial monohilo T1 finalizada con éxito."),
            ("INFO", "No se detectaron eventos de estrés hídrico severo."),
        ],
    },
    {
        "simulacion": {
            "id": "SIM-BOYUIBE-006",
            "nombre": "[DEMO] Corrida Pendiente Boyuibe Maíz Dekalb",
            "fuente_datos": "Estación Boyuibe Frontera Cordillera",
            "escenario": "moderado_ssp245",
            "cantidad_escenarios": 12,
            "dias": 130,
            "estado": "pending",
            "semilla": 32768,
        },
        "parametro": {
            "agua_inicial": Decimal("21.00"),
            "capacidad_suelo": Decimal("115.00"),
            "umbral_hidrico": Decimal("57.50"),
            "configuracion_json": {
                "zone": "boyuibe",
                "zoneName": "Boyuibe",
                "department": "Santa Cruz",
                "soilType": "franco_arenoso",
                "cornVariety": "dekalb_7088",
                "gridConfig": {"rows": 90, "cols": 90, "cellSizeMeters": 50},
                "engine": "openmp",
                "openmpThreads": 8,
            },
        },
        "resultado": None,
        "rendimientos": [],
        "fuente_datos": {
            "nombre_archivo": "senamhi_boyuibe_diario.csv",
            "formato": "csv",
            "hash_archivo": "f6a1b2c3d4e57890123456789abcdef0123456789abcdef0123456789abcdef0",
            "periodo": "2018-2023",
            "descripcion": "Datos de evaporación y temperatura media Boyuibe",
        },
        "eventos": [
            ("INFO", "Simulación registrada en cola de espera por operador."),
        ],
    },
]


def poblar_semillas(db: Session | None = None) -> int:
    """Inserta los registros de prueba en la base de datos de manera idempotente."""
    cierre_propio = False
    if db is None:
        db = SessionLocal()
        cierre_propio = True

    registros_insertados = 0

    try:
        for seed in CHACO_SEEDS:
            sim_data = seed["simulacion"]
            sim_id = sim_data["id"]

            # Comprobar si ya existe
            simulacion_existente = db.get(Simulacion, sim_id)
            if simulacion_existente is not None:
                continue

            # Crear simulación
            simulacion = Simulacion(**sim_data)
            db.add(simulacion)
            db.flush()

            # Parámetro asociado
            param_data = seed["parametro"]
            parametro = Parametro(simulacion_id=sim_id, **param_data)
            db.add(parametro)

            # Resultado (si aplica)
            if seed["resultado"]:
                resultado = Resultado(simulacion_id=sim_id, **seed["resultado"])
                db.add(resultado)

            # Rendimientos HPC (si aplica)
            for rend_data in seed["rendimientos"]:
                rendimiento = Rendimiento(simulacion_id=sim_id, **rend_data)
                db.add(rendimiento)

            # Fuente de datos
            fuente_data = seed["fuente_datos"]
            fuente = FuenteDatos(simulacion_id=sim_id, **fuente_data)
            db.add(fuente)

            # Eventos de ejecución
            for nivel, mensaje in seed["eventos"]:
                evento = EventoEjecucion(
                    simulacion_id=sim_id,
                    nivel=nivel,
                    mensaje=mensaje,
                )
                db.add(evento)

            registros_insertados += 1

        db.commit()
        return registros_insertados

    except Exception as error:
        db.rollback()
        raise RuntimeError(f"Error al poblar datos de prueba: {error}") from error

    finally:
        if cierre_propio:
            db.close()


if __name__ == "__main__":
    print("[AGROCHACO] Inicializando población de semillas de prueba...")
    insertados = poblar_semillas()
    print(f"[OK] Proceso finalizado. Simulaciones nuevas insertadas: {insertados}.")

