"""Servicio de exportación de simulaciones a formatos estándar CSV y JSON.

Permite transformar registros almacenados en PostgreSQL a:
- JSON: Estructura jerárquica completa para auditoría o consumo por API/frontend.
- CSV: Formato tabular de historial general, parámetros, resultados, rendimiento y eventos.
"""

import csv
import io
import json
from decimal import Decimal
from typing import Any, Generator

from app.models import (
    EventoEjecucion,
    FuenteDatos,
    Parametro,
    Rendimiento,
    Resultado,
    Simulacion,
)


class ExportService:
    """Servicio de serialización y exportación de datos de simulación."""

    @staticmethod
    def _serializar_valor(valor: Any) -> Any:
        """Convierte tipos no serializables en JSON nativo (Decimal, datetime)."""
        if isinstance(valor, Decimal):
            return float(valor)
        if hasattr(valor, "isoformat"):
            return valor.isoformat()
        return valor

    # --------------------------------------------------------------------------
    # 1. Exportación JSON
    # --------------------------------------------------------------------------

    @classmethod
    def exportar_simulacion_json(cls, simulacion: Simulacion) -> dict[str, Any]:
        """Convierte una simulación completa con todas sus entidades satélite a un diccionario JSON."""
        if not simulacion:
            raise ValueError("No se puede exportar una simulación nula o inexistente.")

        data: dict[str, Any] = {
            "id": simulacion.id,
            "nombre": simulacion.nombre,
            "fuenteDatos": simulacion.fuente_datos,
            "escenario": simulacion.escenario,
            "cantidadEscenarios": simulacion.cantidad_escenarios,
            "dias": simulacion.dias,
            "fechaCreacion": cls._serializar_valor(simulacion.fecha_creacion),
            "estado": simulacion.estado,
            "semilla": simulacion.semilla,
            "parametros": None,
            "resultados": None,
            "rendimiento": [],
            "fuentesDatos": [],
            "eventos": [],
        }

        # Parámetros asociados
        if simulacion.parametro:
            p: Parametro = simulacion.parametro
            data["parametros"] = {
                "id": p.id,
                "aguaInicial": cls._serializar_valor(p.agua_inicial),
                "capacidadSuelo": cls._serializar_valor(p.capacidad_suelo),
                "umbralHidrico": cls._serializar_valor(p.umbral_hidrico),
                "configuracion": p.configuracion_json,
            }

        # Resultados consolidados
        if simulacion.resultado:
            r: Resultado = simulacion.resultado
            data["resultados"] = {
                "id": r.id,
                "deficitMedio": cls._serializar_valor(r.deficit_medio),
                "deficitMaximo": cls._serializar_valor(r.deficit_maximo),
                "aguaFinalMedia": cls._serializar_valor(r.agua_final_media),
                "aguaMinima": cls._serializar_valor(r.agua_minima),
                "escenariosConDeficit": r.escenarios_con_deficit,
                "archivoDetalle": r.archivo_detalle,
            }

        # Rendimientos HPC
        for rend in simulacion.rendimientos:
            data["rendimiento"].append(
                {
                    "id": rend.id,
                    "modalidad": rend.modalidad,
                    "hilos": rend.hilos,
                    "procesos": rend.procesos,
                    "nodos": rend.nodos,
                    "tiempoSegundos": cls._serializar_valor(rend.tiempo_segundos),
                    "speedup": cls._serializar_valor(rend.speedup),
                    "eficiencia": cls._serializar_valor(rend.eficiencia),
                    "repeticion": rend.repeticion,
                }
            )

        # Fuentes de datos
        for f in simulacion.fuentes_datos:
            data["fuentesDatos"].append(
                {
                    "id": f.id,
                    "nombreArchivo": f.nombre_archivo,
                    "formato": f.formato,
                    "hashArchivo": f.hash_archivo,
                    "periodo": f.periodo,
                    "descripcion": f.descripcion,
                }
            )

        # Eventos de ejecución
        for ev in simulacion.eventos:
            data["eventos"].append(
                {
                    "id": ev.id,
                    "fechaHora": cls._serializar_valor(ev.fecha_hora),
                    "nivel": ev.nivel,
                    "mensaje": ev.mensaje,
                }
            )

        return data

    @classmethod
    def exportar_simulacion_json_str(cls, simulacion: Simulacion, indent: int = 2) -> str:
        """Retorna la representación en cadena de texto JSON con codificación UTF-8."""
        data = cls.exportar_simulacion_json(simulacion)
        return json.dumps(data, indent=indent, ensure_ascii=False)

    # --------------------------------------------------------------------------
    # 2. Exportación CSV
    # --------------------------------------------------------------------------

    @classmethod
    def exportar_historial_csv(cls, simulaciones: list[Simulacion]) -> str:
        """Genera un archivo CSV tabular consolidando el historial de simulaciones."""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=",", quoting=csv.QUOTE_MINIMAL)

        # Cabecera estándar auditable
        writer.writerow(
            [
                "ID_Simulacion",
                "Nombre",
                "Fuente_Datos",
                "Escenario",
                "Cantidad_Escenarios",
                "Dias",
                "Estado",
                "Fecha_Creacion",
                "Zona",
                "Variedad_Maiz",
                "Tipo_Suelo",
                "Deficit_Medio",
                "Deficit_Maximo",
                "Agua_Final_Media_mm",
                "Modalidad_HPC",
                "Tiempo_Segundos",
                "Speedup",
            ]
        )

        for sim in simulaciones:
            # Extraer campos de configuración JSON si existen
            zona = ""
            variedad = ""
            tipo_suelo = ""
            if sim.parametro and isinstance(sim.parametro.configuracion_json, dict):
                cfg = sim.parametro.configuracion_json
                zona = cfg.get("zoneName") or cfg.get("zone") or ""
                variedad = cfg.get("cornVariety") or ""
                tipo_suelo = cfg.get("soilType") or ""

            # Extraer resultados
            def_medio = ""
            def_max = ""
            agua_fin = ""
            if sim.resultado:
                def_medio = str(sim.resultado.deficit_medio)
                def_max = str(sim.resultado.deficit_maximo)
                agua_fin = str(sim.resultado.agua_final_media)

            # Extraer rendimiento principal
            modalidad = ""
            tiempo = ""
            speedup = ""
            if sim.rendimientos:
                principal = sim.rendimientos[-1]
                modalidad = principal.modalidad
                tiempo = str(principal.tiempo_segundos)
                speedup = str(principal.speedup)

            writer.writerow(
                [
                    sim.id,
                    sim.nombre,
                    sim.fuente_datos,
                    sim.escenario,
                    sim.cantidad_escenarios,
                    sim.dias,
                    sim.estado,
                    cls._serializar_valor(sim.fecha_creacion),
                    zona,
                    variedad,
                    tipo_suelo,
                    def_medio,
                    def_max,
                    agua_fin,
                    modalidad,
                    tiempo,
                    speedup,
                ]
            )

        return output.getvalue()

    @classmethod
    def exportar_eventos_csv(cls, eventos: list[EventoEjecucion]) -> str:
        """Exporta la traza de eventos de ejecución a formato CSV."""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=",")
        writer.writerow(["ID_Evento", "ID_Simulacion", "Fecha_Hora", "Nivel", "Mensaje"])

        for ev in eventos:
            writer.writerow(
                [
                    ev.id,
                    ev.simulacion_id,
                    cls._serializar_valor(ev.fecha_hora),
                    ev.nivel,
                    ev.mensaje,
                ]
            )

        return output.getvalue()

    @classmethod
    def exportar_rendimientos_csv(cls, rendimientos: list[Rendimiento]) -> str:
        """Exporta métricas de aceleración HPC a formato CSV."""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=",")
        writer.writerow(
            [
                "ID_Rendimiento",
                "ID_Simulacion",
                "Modalidad",
                "Hilos",
                "Procesos",
                "Nodos",
                "Tiempo_Segundos",
                "Speedup",
                "Eficiencia",
                "Repeticion",
            ]
        )

        for r in rendimientos:
            writer.writerow(
                [
                    r.id,
                    r.simulacion_id,
                    r.modalidad,
                    r.hilos,
                    r.procesos,
                    r.nodos,
                    str(r.tiempo_segundos),
                    str(r.speedup),
                    str(r.eficiencia),
                    r.repeticion,
                ]
            )

        return output.getvalue()

