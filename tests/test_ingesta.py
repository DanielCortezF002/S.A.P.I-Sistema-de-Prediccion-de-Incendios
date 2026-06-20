"""Pruebas de ingesta asíncrona."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.ingesta.parallel_ingester import ParallelIngester


@patch("src.ingesta.parallel_ingester.ParallelIngester._ingest_nasa_firms")
@patch("src.ingesta.parallel_ingester.ParallelIngester._ingest_dmc")
@patch("src.ingesta.parallel_ingester.ParallelIngester._ingest_conaf")
def test_ingest_all_sources(mock_conaf, mock_dmc, mock_nasa, tmp_path) -> None:
    mock_nasa.return_value = {"status": "success", "degraded": False, "path": str(tmp_path / "nasa.csv")}
    mock_dmc.return_value = {"status": "success", "degraded": False, "path": str(tmp_path / "dmc.json")}
    mock_conaf.return_value = {
        "status": "success",
        "degraded": False,
        "path": str(tmp_path / "conaf.json"),
    }

    ingester = ParallelIngester(raw_dir=tmp_path)
    result = ingester.ingest_all_sources()

    assert "nasa_firms" in result
    assert "dmc_meteo" in result
    assert "conaf_incendios" in result
    assert result["nasa_firms"]["degraded"] is False


@patch("src.ingesta.parallel_ingester.requests.get")
def test_download_with_retry_success(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    ingester = ParallelIngester()
    response = ingester._download_with_retry("https://example.com")
    assert response is mock_response
