"""Capa de persistencia y repositorio transaccional para AgroChaco.

Implementa operaciones CRUD, transacciones atómicas con manejo estricto de rollback,
filtros de consulta de historial (por nombre, estado, fecha, escenario), paginación
y carga eficiente de entidades relacionadas.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    EventoEjecucion,
    FuenteDatos,
    Parametro,
    Rendimiento,
    Resultado,
    Simulacion,
    SimulationJob,
)
from app.models.simulation_job import (
    ESTADOS_ACTIVOS_TRABAJO,
    ESTADOS_TERMINALES_TRABAJO,
    ESTADOS_TRABAJO,
    transiciones_permitidas_desde,
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
        commit: bool = True,
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

            if commit:
                db.commit()
                db.refresh(resultado)
            else:
                db.flush()
            return resultado
        except Exception as error:
            if commit:
                db.rollback()
            raise RuntimeError(
                f"Error al guardar resultados para {simulacion_id}: {error}"
            ) from error

    @staticmethod
    def guardar_rendimiento(
        db: Session,
        simulacion_id: str,
        datos_rendimiento: dict[str, Any],
        commit: bool = True,
    ) -> Rendimiento:
        """Registra una corrida de rendimiento HPC asociada a la simulación."""
        try:
            rendimiento = Rendimiento(simulacion_id=simulacion_id, **datos_rendimiento)
            db.add(rendimiento)
            if commit:
                db.commit()
                db.refresh(rendimiento)
            else:
                db.flush()
            return rendimiento
        except Exception as error:
            if commit:
                db.rollback()
            raise RuntimeError(
                f"Error al registrar rendimiento para {simulacion_id}: {error}"
            ) from error

    @staticmethod
    def guardar_ejecucion_completa(
        db: Session,
        simulacion_id: str,
        datos_resultados: dict[str, Any],
        datos_rendimiento: dict[str, Any],
        nuevo_estado: str = "completed",
        mensaje_evento: str | None = None,
        commit: bool = True,
    ) -> None:
        """Persiste resultados biofísicos, métricas HPC, estado y evento en una única transacción atómica."""
        try:
            SimulationRepository.guardar_resultados(
                db, simulacion_id, datos_resultados, commit=False
            )
            SimulationRepository.guardar_rendimiento(
                db, simulacion_id, datos_rendimiento, commit=False
            )
            simulacion = db.get(Simulacion, simulacion_id)
            if simulacion:
                simulacion.estado = nuevo_estado
            if mensaje_evento:
                evento = EventoEjecucion(
                    simulacion_id=simulacion_id,
                    nivel="INFO",
                    mensaje=mensaje_evento,
                )
                db.add(evento)
            if commit:
                db.commit()
        except Exception as error:
            db.rollback()
            raise RuntimeError(
                f"Error en persistencia atómica para {simulacion_id}: {error}"
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
    def actualizar_estado_simulacion(
        db: Session,
        simulacion_id: str,
        nuevo_estado: str,
        *,
        commit: bool = True,
    ) -> Simulacion | None:
        estados = ("pending", "running", "completed", "failed", "paused")
        if nuevo_estado not in estados:
            raise ValueError(f"Estado de simulación inválido: {nuevo_estado}")

        stmt = (
            update(Simulacion)
            .where(Simulacion.id == simulacion_id)
            .values(estado=nuevo_estado)
        )
        try:
            resultado = db.execute(stmt, execution_options={"synchronize_session": False})
            if commit:
                db.commit()
            if resultado.rowcount != 1:
                return None
            return db.get(Simulacion, simulacion_id)
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

    @staticmethod
    def _normalizar_job_id(job_id: UUID | str) -> UUID:
        return job_id if isinstance(job_id, UUID) else UUID(str(job_id))

    @staticmethod
    def _normalizar_fecha_utc(valor: datetime | None) -> datetime | None:
        if valor is None:
            return None
        if valor.tzinfo is None:
            return valor.replace(tzinfo=timezone.utc)
        return valor.astimezone(timezone.utc)

    @staticmethod
    def crear_trabajo(
        db: Session,
        simulacion_id: str,
        *,
        job_id: UUID | str | None = None,
        worker_id: str | None = None,
        attempt: int = 1,
    ) -> SimulationJob:
        if attempt <= 0:
            raise ValueError("attempt debe ser mayor que 0")
        if db.get(Simulacion, simulacion_id) is None:
            raise ValueError(f"Simulación no encontrada: {simulacion_id}")

        datos: dict[str, Any] = {
            "simulacion_id": simulacion_id,
            "worker_id": worker_id,
            "attempt": attempt,
        }
        if job_id is not None:
            datos["job_id"] = SimulationRepository._normalizar_job_id(job_id)

        try:
            trabajo = SimulationJob(**datos)
            db.add(trabajo)
            db.commit()
            db.refresh(trabajo)
            return trabajo
        except Exception as error:
            db.rollback()
            raise RuntimeError(f"Error al crear trabajo para {simulacion_id}: {error}") from error

    @staticmethod
    def crear_trabajo_unico(
        db: Session,
        simulacion_id: str,
        *,
        job_id: UUID | str | None = None,
    ) -> SimulationJob | None:
        if db.get(Simulacion, simulacion_id) is None:
            raise ValueError(f"Simulación no encontrada: {simulacion_id}")

        activo = db.execute(
            select(SimulationJob.job_id).where(
                SimulationJob.simulacion_id == simulacion_id,
                SimulationJob.estado.in_(ESTADOS_ACTIVOS_TRABAJO),
            )
        ).scalar_one_or_none()
        if activo is not None:
            return None

        datos: dict[str, Any] = {"simulacion_id": simulacion_id}
        if job_id is not None:
            datos["job_id"] = SimulationRepository._normalizar_job_id(job_id)

        try:
            trabajo = SimulationJob(**datos)
            db.add(trabajo)
            db.commit()
            db.refresh(trabajo)
            return trabajo
        except IntegrityError:
            db.rollback()
            return None
        except Exception as error:
            db.rollback()
            raise RuntimeError(f"Error al crear trabajo para {simulacion_id}: {error}") from error

    @staticmethod
    def obtener_trabajo(db: Session, job_id: UUID | str) -> SimulationJob | None:
        return db.get(SimulationJob, SimulationRepository._normalizar_job_id(job_id))

    @staticmethod
    def reclamar_trabajo(
        db: Session,
        job_id: UUID | str,
        worker_id: str,
        *,
        lease_seconds: int = 60,
        simulacion_id: str | None = None,
    ) -> SimulationJob | None:
        if not worker_id:
            raise ValueError("worker_id es obligatorio para reclamar un trabajo")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds debe ser mayor que 0")

        ahora = datetime.now(timezone.utc)
        condiciones = [
            SimulationJob.job_id == SimulationRepository._normalizar_job_id(job_id),
            SimulationJob.estado == "queued",
            SimulationJob.cancel_requested.is_(False),
        ]
        if simulacion_id is not None:
            condiciones.append(SimulationJob.simulacion_id == simulacion_id)

        stmt = (
            update(SimulationJob)
            .where(*condiciones)
            .values(
                estado="running",
                worker_id=worker_id,
                heartbeat_at=ahora,
                lease_expires_at=ahora + timedelta(seconds=lease_seconds),
                started_at=ahora,
                updated_at=ahora,
            )
        )
        try:
            resultado = db.execute(stmt, execution_options={"synchronize_session": False})
            db.commit()
            if resultado.rowcount != 1:
                return None
            return SimulationRepository.obtener_trabajo(db, job_id)
        except Exception as error:
            db.rollback()
            raise RuntimeError(f"Error al reclamar trabajo {job_id}: {error}") from error

    @staticmethod
    def actualizar_estado_trabajo(
        db: Session,
        job_id: UUID | str,
        nuevo_estado: str,
        *,
        estado_esperado: str | None = None,
        error_message: str | None = None,
        progress_percent: int | None = None,
        current_day: int | None = None,
        finished_at: datetime | None = None,
        worker_id: str | None = None,
        commit: bool = True,
    ) -> SimulationJob | None:
        if nuevo_estado not in ESTADOS_TRABAJO:
            raise ValueError(f"Estado de trabajo inválido: {nuevo_estado}")
        if estado_esperado is not None and estado_esperado not in ESTADOS_TRABAJO:
            raise ValueError(f"Estado esperado inválido: {estado_esperado}")
        if progress_percent is not None and not 0 <= progress_percent <= 100:
            raise ValueError("progress_percent debe estar entre 0 y 100")
        if current_day is not None and current_day < 0:
            raise ValueError("current_day no puede ser negativo")

        trabajo = SimulationRepository.obtener_trabajo(db, job_id)
        if trabajo is None:
            return None

        estado_actual = estado_esperado if estado_esperado is not None else trabajo.estado
        permitidas = transiciones_permitidas_desde(estado_actual)
        if nuevo_estado not in permitidas:
            raise ValueError(f"Transición no permitida: {estado_actual} -> {nuevo_estado}")

        ahora = datetime.now(timezone.utc)
        valores: dict[str, Any] = {"estado": nuevo_estado, "updated_at": ahora}
        if error_message is not None:
            valores["error_message"] = error_message
        if progress_percent is not None:
            valores["progress_percent"] = progress_percent
        if current_day is not None:
            valores["current_day"] = current_day
        if nuevo_estado in ESTADOS_TERMINALES_TRABAJO:
            valores["finished_at"] = finished_at or ahora
            valores["lease_expires_at"] = None

        condiciones = [
            SimulationJob.job_id == SimulationRepository._normalizar_job_id(job_id),
            SimulationJob.estado == estado_actual,
        ]
        if worker_id is not None:
            condiciones.append(SimulationJob.worker_id == worker_id)
        if estado_actual in ESTADOS_ACTIVOS_TRABAJO and nuevo_estado != "canceled":
            condiciones.append(SimulationJob.cancel_requested.is_(False))

        stmt = update(SimulationJob).where(*condiciones).values(**valores)
        try:
            resultado = db.execute(stmt, execution_options={"synchronize_session": False})
            if commit:
                db.commit()
            if resultado.rowcount != 1:
                return None
            return SimulationRepository.obtener_trabajo(db, job_id)
        except Exception as error:
            db.rollback()
            raise RuntimeError(f"Error al actualizar trabajo {job_id}: {error}") from error

    @staticmethod
    def registrar_heartbeat(
        db: Session,
        job_id: UUID | str,
        worker_id: str,
        *,
        lease_seconds: int = 60,
        progress_percent: int | None = None,
        current_day: int | None = None,
    ) -> SimulationJob | None:
        if not worker_id:
            raise ValueError("worker_id es obligatorio para registrar un heartbeat")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds debe ser mayor que 0")
        if progress_percent is not None and not 0 <= progress_percent <= 100:
            raise ValueError("progress_percent debe estar entre 0 y 100")
        if current_day is not None and current_day < 0:
            raise ValueError("current_day no puede ser negativo")

        trabajo = SimulationRepository.obtener_trabajo(db, job_id)
        if trabajo is None or trabajo.estado != "running":
            return None

        ahora = datetime.now(timezone.utc)
        condiciones = [
            SimulationJob.job_id == SimulationRepository._normalizar_job_id(job_id),
            SimulationJob.estado == "running",
            SimulationJob.worker_id == worker_id,
            or_(
                SimulationJob.lease_expires_at.is_(None),
                SimulationJob.lease_expires_at >= ahora,
            ),
        ]
        if progress_percent is not None:
            condiciones.append(
                or_(
                    SimulationJob.progress_percent.is_(None),
                    SimulationJob.progress_percent <= progress_percent,
                )
            )
        if current_day is not None:
            condiciones.append(
                or_(
                    SimulationJob.current_day.is_(None),
                    SimulationJob.current_day <= current_day,
                )
            )

        valores: dict[str, Any] = {
            "heartbeat_at": ahora,
            "lease_expires_at": ahora + timedelta(seconds=lease_seconds),
            "updated_at": ahora,
        }
        if progress_percent is not None:
            valores["progress_percent"] = progress_percent
        if current_day is not None:
            valores["current_day"] = current_day

        stmt = update(SimulationJob).where(*condiciones).values(**valores)
        try:
            resultado = db.execute(stmt, execution_options={"synchronize_session": False})
            db.commit()
            if resultado.rowcount != 1:
                return None
            return SimulationRepository.obtener_trabajo(db, job_id)
        except Exception as error:
            db.rollback()
            raise RuntimeError(f"Error al registrar heartbeat de {job_id}: {error}") from error

    @staticmethod
    def registrar_proceso_trabajo(
        db: Session,
        job_id: UUID | str,
        worker_id: str,
        *,
        pid: int,
        pgid: int,
    ) -> SimulationJob | None:
        """Registra PID/PGID del proceso del dueño actual del trabajo."""
        if not worker_id:
            raise ValueError("worker_id es obligatorio para registrar el proceso")
        if pid <= 0 or pgid <= 0:
            raise ValueError("pid y pgid deben ser mayores que 0")

        ahora = datetime.now(timezone.utc)
        stmt = (
            update(SimulationJob)
            .where(
                SimulationJob.job_id == SimulationRepository._normalizar_job_id(job_id),
                SimulationJob.estado == "running",
                SimulationJob.worker_id == worker_id,
                or_(
                    SimulationJob.lease_expires_at.is_(None),
                    SimulationJob.lease_expires_at >= ahora,
                ),
            )
            .values(pid=pid, pgid=pgid, updated_at=ahora)
        )
        try:
            resultado = db.execute(stmt, execution_options={"synchronize_session": False})
            db.commit()
            if resultado.rowcount != 1:
                return None
            return SimulationRepository.obtener_trabajo(db, job_id)
        except Exception as error:
            db.rollback()
            raise RuntimeError(f"Error al registrar proceso de {job_id}: {error}") from error

    @staticmethod
    def verificar_propiedad_para_publicacion(
        db: Session,
        job_id: UUID | str,
        worker_id: str,
    ) -> SimulationJob | None:
        """Bloquea condicionalmente el trabajo del dueño actual antes de publicar resultados."""
        if not worker_id:
            raise ValueError("worker_id es obligatorio para publicar resultados")

        ahora = datetime.now(timezone.utc)
        stmt = (
            update(SimulationJob)
            .where(
                SimulationJob.job_id == SimulationRepository._normalizar_job_id(job_id),
                SimulationJob.estado == "running",
                SimulationJob.worker_id == worker_id,
                SimulationJob.cancel_requested.is_(False),
                or_(
                    SimulationJob.lease_expires_at.is_(None),
                    SimulationJob.lease_expires_at >= ahora,
                ),
            )
            .values(updated_at=ahora)
        )
        resultado = db.execute(stmt, execution_options={"synchronize_session": False})
        if resultado.rowcount != 1:
            return None
        return SimulationRepository.obtener_trabajo(db, job_id)

    @staticmethod
    def tiene_resultados(db: Session, simulacion_id: str) -> bool:
        """Indica si la simulación ya tiene resultados persistidos, para no duplicarlos."""
        stmt = (
            select(Resultado.id)
            .where(Resultado.simulacion_id == simulacion_id)
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none() is not None

    @staticmethod
    def solicitar_cancelacion(db: Session, job_id: UUID | str) -> SimulationJob | None:
        trabajo = SimulationRepository.obtener_trabajo(db, job_id)
        if trabajo is None or trabajo.estado not in ESTADOS_ACTIVOS_TRABAJO:
            return None
        if trabajo.cancel_requested:
            return trabajo

        stmt = (
            update(SimulationJob)
            .where(
                SimulationJob.job_id == SimulationRepository._normalizar_job_id(job_id),
                SimulationJob.estado == trabajo.estado,
                SimulationJob.estado.in_(ESTADOS_ACTIVOS_TRABAJO),
                SimulationJob.cancel_requested.is_(False),
            )
            .values(cancel_requested=True, updated_at=datetime.now(timezone.utc))
        )
        try:
            db.execute(stmt, execution_options={"synchronize_session": False})
            db.commit()
            return SimulationRepository.obtener_trabajo(db, job_id)
        except Exception as error:
            db.rollback()
            raise RuntimeError(f"Error al solicitar cancelación de {job_id}: {error}") from error

    @staticmethod
    def recuperar_trabajo_abandonado(
        db: Session,
        job_id: UUID | str,
        worker_id: str,
        *,
        lease_seconds: int = 60,
        worker_id_anterior: str | None = None,
    ) -> SimulationJob | None:
        if not worker_id:
            raise ValueError("worker_id es obligatorio para recuperar un trabajo")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds debe ser mayor que 0")

        ahora = datetime.now(timezone.utc)
        actual = SimulationRepository.obtener_trabajo(db, job_id)
        if actual is None or actual.estado != "running" or actual.cancel_requested:
            return None
        if worker_id_anterior is not None and actual.worker_id != worker_id_anterior:
            return None
        lease_actual = SimulationRepository._normalizar_fecha_utc(actual.lease_expires_at)
        if lease_actual is not None and lease_actual >= ahora:
            return None

        condiciones = [
            SimulationJob.job_id == SimulationRepository._normalizar_job_id(job_id),
            SimulationJob.estado == "running",
            SimulationJob.cancel_requested.is_(False),
            or_(
                SimulationJob.lease_expires_at.is_(None),
                SimulationJob.lease_expires_at < ahora,
            ),
        ]
        if actual.worker_id is None:
            condiciones.append(SimulationJob.worker_id.is_(None))
        else:
            condiciones.append(SimulationJob.worker_id == actual.worker_id)
        stmt = (
            update(SimulationJob)
            .where(*condiciones)
            .values(
                worker_id=worker_id,
                heartbeat_at=ahora,
                lease_expires_at=ahora + timedelta(seconds=lease_seconds),
                started_at=ahora,
                updated_at=ahora,
                pid=None,
                pgid=None,
                attempt=SimulationJob.attempt + 1,
            )
        )
        try:
            resultado = db.execute(stmt, execution_options={"synchronize_session": False})
            db.commit()
            if resultado.rowcount != 1:
                return None
            return SimulationRepository.obtener_trabajo(db, job_id)
        except Exception as error:
            db.rollback()
            raise RuntimeError(f"Error al recuperar trabajo {job_id}: {error}") from error

    @staticmethod
    def listar_trabajos_pendientes(db: Session, limit: int = 50) -> list[SimulationJob]:
        if limit <= 0:
            return []

        stmt = (
            select(SimulationJob)
            .where(SimulationJob.estado == "queued")
            .order_by(SimulationJob.created_at, SimulationJob.job_id)
            .limit(limit)
        )
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def listar_trabajos_abandonados(
        db: Session,
        *,
        ahora: datetime | None = None,
        limit: int = 50,
    ) -> list[SimulationJob]:
        if limit <= 0:
            return []

        referencia = ahora or datetime.now(timezone.utc)
        stmt = (
            select(SimulationJob)
            .where(
                SimulationJob.estado == "running",
                or_(
                    SimulationJob.lease_expires_at.is_(None),
                    SimulationJob.lease_expires_at < referencia,
                ),
            )
            .order_by(SimulationJob.updated_at, SimulationJob.job_id)
            .limit(limit)
        )
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        return list(db.execute(stmt).scalars().all())

