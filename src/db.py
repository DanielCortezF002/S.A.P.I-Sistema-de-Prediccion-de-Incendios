"""Utilidades de conexión a base de datos."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from src.config import DATABASE_URL, get_backend_database_url


def get_engine() -> Engine:
    """Crea motor SQLAlchemy para capa de consulta (Streamlit / pooler).

    Returns:
        Engine configurado con DATABASE_URL.
    """
    return create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800)


def get_backend_engine() -> Engine:
    """Crea motor SQLAlchemy para pipeline batch e ingesta (conexión directa).

    Returns:
        Engine configurado con DATABASE_URL_DIRECT.
    """
    return create_engine(get_backend_database_url(), pool_pre_ping=True, pool_recycle=1800)


@contextmanager
def get_connection() -> Generator[Connection, None, None]:
    """Context manager para conexiones de la Serving Layer (PredictionQuery).

    Yields:
        Conexión activa a PostgreSQL vía DATABASE_URL.
    """
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


@contextmanager
def get_backend_connection() -> Generator[Connection, None, None]:
    """Context manager para operaciones batch e ingesta resilientes.

    Yields:
        Conexión activa a PostgreSQL vía DATABASE_URL_DIRECT.
    """
    engine = get_backend_engine()
    with engine.begin() as conn:
        yield conn


def log_event(componente: str, evento: str, detalle: str = "", nivel: str = "INFO") -> None:
    """Registra evento en tabla de observabilidad.

    Args:
        componente: Módulo origen del evento.
        evento: Nombre corto del evento.
        detalle: Descripción extendida.
        nivel: Nivel de log (INFO, WARN, ERROR).
    """
    try:
        with get_connection() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO observability_logs (componente, evento, detalle, nivel)
                    VALUES (:componente, :evento, :detalle, :nivel)
                    """
                ),
                {
                    "componente": componente,
                    "evento": evento,
                    "detalle": detalle,
                    "nivel": nivel,
                },
            )
    except Exception:
        pass
