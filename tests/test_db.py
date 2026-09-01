"""Pruebas de conexión y observabilidad en src/db.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.db import (
    get_backend_connection,
    get_backend_engine,
    get_connection,
    get_engine,
    log_event,
)


@patch("src.db.create_engine")
@patch("src.db.DATABASE_URL", "postgresql://app@pooler:5432/sapi")
def test_get_engine_uses_serving_layer_url(mock_create_engine: MagicMock) -> None:
    engine = MagicMock()
    mock_create_engine.return_value = engine

    assert get_engine() is engine
    mock_create_engine.assert_called_once_with(
        "postgresql://app@pooler:5432/sapi",
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"connect_timeout": 1},
    )


@patch("src.db.create_engine")
@patch("src.db.get_backend_database_url", return_value="postgresql://batch@db:5432/sapi")
def test_get_backend_engine_uses_direct_url(
    mock_backend_url: MagicMock,
    mock_create_engine: MagicMock,
) -> None:
    engine = MagicMock()
    mock_create_engine.return_value = engine

    assert get_backend_engine() is engine
    mock_backend_url.assert_called_once()
    mock_create_engine.assert_called_once_with(
        "postgresql://batch@db:5432/sapi",
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"connect_timeout": 1},
    )


@patch("src.db.get_engine")
def test_get_connection_yields_active_connection(mock_get_engine: MagicMock) -> None:
    conn = MagicMock()
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn
    mock_get_engine.return_value = engine

    with get_connection() as active:
        assert active is conn

    engine.begin.assert_called_once()


@patch("src.db.get_backend_engine")
def test_get_backend_connection_yields_active_connection(mock_get_backend_engine: MagicMock) -> None:
    conn = MagicMock()
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn
    mock_get_backend_engine.return_value = engine

    with get_backend_connection() as active:
        assert active is conn


@patch("src.db.get_connection")
def test_log_event_persists_to_observability_table(mock_get_connection: MagicMock) -> None:
    conn = MagicMock()
    mock_get_connection.return_value.__enter__.return_value = conn

    log_event("ParallelIngester", "dmc_ok", "/data/raw/dmc.json", "INFO")

    conn.execute.assert_called_once()
    params = conn.execute.call_args[0][1]
    assert params["componente"] == "ParallelIngester"
    assert params["evento"] == "dmc_ok"
    assert params["nivel"] == "INFO"


@patch("src.db.get_connection", side_effect=RuntimeError("PostGIS no disponible"))
def test_log_event_swallows_connection_errors(mock_get_connection: MagicMock) -> None:
    """La ingesta no debe fallar si la tabla observability_logs no está accesible."""
    log_event("Test", "noop")
