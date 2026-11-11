"""Capa de persistencia y repositorio transaccional para AgroChaco.

Implementa operaciones CRUD, transacciones atómicas con manejo estricto de rollback,
filtros de consulta de historial (por nombre, estado, fecha, escenario), paginación
y carga eficiente de entidades relacionadas.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    EventoEjecucion,
    FuenteDatos,
    Parametro,
    Rendimiento,
    Resultado,
    Simulacion,
)


class SimulationRepository:
    """Repositorio transaccional para la gestión del ciclo de vida de las simulaciones."""

    # --------------------------------------------------------------------------
    # 1. Creación Atómica y CRUD Base
    # --------------------------------------------------------------------------

    @staticmethod
    def crear_simulacion(
        db: Session,
        simulacion_data: dict[str, Any],
    ) -> Simulacion:
        """Crea un registro de simulación individual de forma transaccional."""
        try:
            simulacion = Simulacion(**simulacion_data)
            db.add(simulacion)
            db.commit()
            db.refresh(simulacion)
            return simulacion
        except Exception as error:
            db.rollback()
            raise RuntimeError(f"Error al crear simulación: {error}") from error

    @staticmethod
    def crear_simulacion_con_parametros(
        db: Session,
        datos_simulacion: dict[str, Any],
        datos_parametros: dict[str, Any],
    ) -> Simulacion:
        """Crea una simulación y sus parámetros asociados de forma atómica en una única transacción.

        Si ocurre algún error durante la inserción de la simulación o de los parámetros,
        se ejecuta un rollback automático, garantizando que no queden registros incompletos.
        """
        try:
            simulacion = Simulacion(**datos_simulacion)
            db.add(simulacion)
            db.flush()  # Asigna ID y valida restricciones antes de insertar dependencias

            parametro = Parametro(
                simulacion_id=simulacion.id,
                **datos_parametros,
            )
            db.add(parametro)

            # Traza cronológica inicial de auditoría
            evento = EventoEjecucion(
                simulacion_id=simulacion.id,
                nivel="INFO",
                mensaje=f"Simulación '{simulacion.nombre}' creada en estado '{simulacion.estado}'.",
            )
            db.add(evento)

            db.commit()
            db.refresh(simulacion)
            return simulacion

        except Exception as error:
            db.rollback()
            raise RuntimeError(
                f"Error al crear simulación y parámetros de forma atómica: {error}"
            ) from error

    # --------------------------------------------------------------------------
    # 2. Consultas y Recuperación por ID
    # --------------------------------------------------------------------------

    @staticmethod
    def obtener_por_id(
        db: Session,
        simulacion_id: str,
        cargar_relaciones: bool = True,
    ) -> Simulacion | None:
        """Recupera una simulación por su identificador primario (ej. SIM-XXXXXXXXXXXX)."""
        if not cargar_relaciones:
            return db.get(Simulacion, simulacion_id)

        stmt = (
            select(Simulacion)
            .where(Simulacion.id == simulacion_id)
            .options(
                joinedload(Simulacion.parametro),
                joinedload(Simulacion.resultado),
                selectinload(Simulacion.rendimientos),
                selectinload(Simulacion.fuentes_datos),
                selectinload(Simulacion.eventos),
            )
        )
        return db.execute(stmt).unique().scalar_one_or_none()

    # --------------------------------------------------------------------------
    # 3. Guardado de Entidades Relacionadas (Parámetros, Resultados, Rendimiento, etc.)
    # --------------------------------------------------------------------------

    @staticmethod
    def guardar_parametros(
        db: Session,
        simulacion_id: str,
        datos_parametros: dict[str, Any],
    ) -> Parametro:
        """Guarda o actualiza los parámetros biofísicos de una simulación."""
        try:
            parametro_existente = db.execute(
                select(Parametro).where(Parametro.simulacion_id == simulacion_id)
            ).scalar_one_or_none()

            if parametro_existente:
                for k, v in datos_parametros.items():
                    setattr(parametro_existente, k, v)
                parametro = parametro_existente
            else:
                parametro = Parametro(simulacion_id=simulacion_id, **datos_parametros)
                db.add(parametro)

            db.commit()
            db.refresh(parametro)
            return parametro
        except Exception as error:
            db.rollback()
            raise RuntimeError(
                f"Error al guardar parámetros para {simulacion_id}: {error}"
            ) from error

    @staticmethod
    def guardar_resultados(
        db: Session,
        simulacion_id: str,
        datos_resultados: dict[str, Any],
    ) -> Resultado:
        """Guarda o actualiza los resultados consolidados de una simulación."""
        try:
            resultado_existente = db.execute(
                select(Resultado).where(Resultado.simulacion_id == simulacion_id)
            ).scalar_one_or_none()

            if resultado_existente:
                for k, v in datos_resultados.items():
                    setattr(resultado_existente, k, v)
                resultado = resultado_existente
            else:
                resultado = Resultado(simulacion_id=simulacion_id, **datos_resultados)
                db.add(resultado)

            db.commit()
            db.refresh(resultado)
            return resultado
        except Exception as error:
            db.rollback()
            raise RuntimeError(
                f"Error al guardar resultados para {simulacion_id}: {error}"
            ) from error

    @staticmethod
    def guardar_rendimiento(
        db: Session,
        simulacion_id: str,
        datos_rendimiento: dict[str, Any],
    ) -> Rendimiento:
        """Registra una corrida de rendimiento HPC asociada a la simulación."""
        try:
            rendimiento = Rendimiento(simulacion_id=simulacion_id, **datos_rendimiento)
            db.add(rendimiento)
            db.commit()
            db.refresh(rendimiento)
            return rendimiento
        except Exception as error:
            db.rollback()
            raise RuntimeError(
                f"Error al registrar rendimiento para {simulacion_id}: {error}"
            ) from error

    @staticmethod
    def registrar_fuente_datos(
        db: Session,
        simulacion_id: str,
        nombre_archivo: str,
        formato: str,
        hash_archivo: str,
        periodo: str | None = None,
        descripcion: str | None = None,
    ) -> FuenteDatos:
        """Registra una fuente de datos meteorológica o agronómica auditable."""
        try:
            fuente = FuenteDatos(
                simulacion_id=simulacion_id,
                nombre_archivo=nombre_archivo,
                formato=formato,
                hash_archivo=hash_archivo,
                periodo=periodo,
                descripcion=descripcion,
            )
            db.add(fuente)
            db.commit()
            db.refresh(fuente)
            return fuente
        except Exception as error:
            db.rollback()
            raise RuntimeError(
                f"Error al registrar fuente de datos para {simulacion_id}: {error}"
            ) from error

    @staticmethod
    def registrar_evento(
        db: Session,
        simulacion_id: str,
        nivel: str,
        mensaje: str,
    ) -> EventoEjecucion:
        """Registra un evento cronológico de ejecución en la base de datos."""
        try:
            evento = EventoEjecucion(
                simulacion_id=simulacion_id,
                nivel=nivel.upper(),
                mensaje=mensaje,
            )
            db.add(evento)
            db.commit()
            db.refresh(evento)
            return evento
        except Exception as error:
            db.rollback()
            raise RuntimeError(
                f"Error al registrar evento para {simulacion_id}: {error}"
            ) from error

    # --------------------------------------------------------------------------
    # 4. Historial, Filtros y Paginación
    # --------------------------------------------------------------------------

    @staticmethod
    def listar_historial(
        db: Session,
        search: str | None = None,
        estado: str | None = None,
        escenario: str | None = None,
        fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Simulacion], int]:
        """Consulta el historial de simulaciones con filtros optimizados a nivel de base de datos.

        Retorna una tupla: (lista_de_simulaciones, total_coincidencias).
        """
        query = select(Simulacion)

        if search and search.strip():
            patron = f"%{search.strip()}%"
            query = query.where(
                (Simulacion.nombre.ilike(patron))
                | (Simulacion.id.ilike(patron))
                | (Simulacion.fuente_datos.ilike(patron))
            )

        if estado and estado != "all":
            query = query.where(Simulacion.estado == estado)

        if escenario and escenario != "all":
            query = query.where(Simulacion.escenario == escenario)

        if fecha_desde:
            query = query.where(Simulacion.fecha_creacion >= fecha_desde)

        if fecha_hasta:
            query = query.where(Simulacion.fecha_creacion <= fecha_hasta)

        # Cálculo del conteo total sin traer todas las filas a memoria
        total_stmt = select(func.count()).select_from(query.subquery())
        total = db.execute(total_stmt).scalar() or 0

        # Carga eficiente con joins para evitar problemas de N+1 queries
        stmt = (
            query.options(
                joinedload(Simulacion.parametro),
                joinedload(Simulacion.resultado),
                selectinload(Simulacion.rendimientos),
            )
            .order_by(desc(Simulacion.fecha_creacion))
            .offset(offset)
            .limit(limit)
        )

        simulaciones = db.execute(stmt).unique().scalars().all()
        return list(simulaciones), total

    # --------------------------------------------------------------------------
    # 5. Actualización y Eliminación
    # --------------------------------------------------------------------------

    @staticmethod
    def actualizar_simulacion(
        db: Session,
        simulacion_id: str,
        campos_actualizar: dict[str, Any],
    ) -> Simulacion:
        """Actualiza campos específicos de una simulación."""
        simulacion = db.get(Simulacion, simulacion_id)
        if not simulacion:
            raise ValueError(f"Simulación no encontrada: {simulacion_id}")

        try:
            for k, v in campos_actualizar.items():
                if hasattr(simulacion, k):
                    setattr(simulacion, k, v)

            db.commit()
            db.refresh(simulacion)
            return simulacion
        except Exception as error:
            db.rollback()
            raise RuntimeError(
                f"Error al actualizar la simulación {simulacion_id}: {error}"
            ) from error

    @staticmethod
    def actualizar_estado(
        db: Session,
        simulacion_id: str,
        nuevo_estado: str,
    ) -> Simulacion:
        """Actualiza el estado de la simulación y genera el evento de auditoría."""
        simulacion = db.get(Simulacion, simulacion_id)
        if not simulacion:
            raise ValueError(f"Simulación no encontrada: {simulacion_id}")

        try:
            simulacion.estado = nuevo_estado
            evento = EventoEjecucion(
                simulacion_id=simulacion.id,
                nivel="INFO",
                mensaje=f"Estado de simulación cambiado a '{nuevo_estado}'.",
            )
            db.add(evento)
            db.commit()
            db.refresh(simulacion)
            return simulacion
        except Exception as error:
            db.rollback()
            raise RuntimeError(
                f"Error al actualizar estado de {simulacion_id}: {error}"
            ) from error

    @staticmethod
    def eliminar_simulacion(
        db: Session,
        simulacion_id: str,
    ) -> bool:
        """Elimina una simulación y sus registros asociados mediante ON DELETE CASCADE."""
        simulacion = db.get(Simulacion, simulacion_id)
        if not simulacion:
            return False

        try:
            db.delete(simulacion)
            db.commit()
            return True
        except Exception as error:
            db.rollback()
            raise RuntimeError(
                f"Error al eliminar la simulación {simulacion_id}: {error}"
            ) from error

