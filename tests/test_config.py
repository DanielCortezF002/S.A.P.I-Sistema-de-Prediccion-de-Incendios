"""Pruebas de configuración central."""

from __future__ import annotations

from unittest.mock import patch

from src.config import get_backend_database_url


@patch("src.config.DATABASE_URL_DIRECT", "postgresql://direct@db:5432/sapi")
@patch("src.config.DATABASE_URL", "postgresql://pooler@pooler:6543/sapi")
def test_get_backend_database_url_prefers_direct() -> None:
    assert get_backend_database_url() == "postgresql://direct@db:5432/sapi"


@patch("src.config.DATABASE_URL_DIRECT", "")
@patch("src.config.DATABASE_URL", "postgresql://pooler@pooler:6543/sapi")
def test_get_backend_database_url_falls_back_to_database_url() -> None:
    assert get_backend_database_url() == "postgresql://pooler@pooler:6543/sapi"
