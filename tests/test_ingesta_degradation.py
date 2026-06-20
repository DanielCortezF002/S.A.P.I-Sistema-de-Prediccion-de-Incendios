"""Pruebas de degradación R-03 en ParallelIngester."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import requests

from src.ingesta.parallel_ingester import ParallelIngester


@patch("src.ingesta.parallel_ingester.ParallelIngester._download_with_retry")
def test_ingester_degrades_to_postgis_on_dmc_failure(mock_download: MagicMock, tmp_path) -> None:
    """Valida activación de fallback PostGIS ante falla de red en DMC."""
    mock_download.side_effect = requests.exceptions.Timeout("Conexión expirada en DMC remota.")

    ingester = ParallelIngester(raw_dir=tmp_path)
    df_fallback = pd.DataFrame(
        [{"id": 1, "temperatura": 32.4, "humedad_relativa": 25.0, "velocidad_viento": 30.0}]
    )
    ingester._recuperar_payload_fallback = MagicMock(return_value=df_fallback)

    result = ingester._ingest_dmc()

    assert result["status"] == "degraded"
    assert result["degraded"] is True
    assert result["path"]
    ingester._recuperar_payload_fallback.assert_called_once_with("staging_meteo")


@patch("src.ingesta.parallel_ingester.ParallelIngester._download_with_retry")
def test_ingester_fails_when_fallback_empty(mock_download: MagicMock, tmp_path) -> None:
    """Valida fallo explícito si PostGIS no tiene datos de contingencia."""
    mock_download.side_effect = requests.exceptions.ConnectionError("NASA FIRMS no disponible.")

    ingester = ParallelIngester(raw_dir=tmp_path)
    ingester._recuperar_payload_fallback = MagicMock(return_value=pd.DataFrame())

    result = ingester._ingest_nasa_firms()

    assert result["status"] == "failed"
    assert result["degraded"] is True
    assert result["path"] == ""


@patch("src.ingesta.parallel_ingester.ParallelIngester._ingest_nasa_firms")
@patch("src.ingesta.parallel_ingester.ParallelIngester._ingest_dmc")
@patch("src.ingesta.parallel_ingester.ParallelIngester._ingest_conaf")
def test_ingest_all_sources_tracks_degraded(
    mock_conaf: MagicMock,
    mock_dmc: MagicMock,
    mock_nasa: MagicMock,
    tmp_path,
) -> None:
    """Valida que ingest_all_sources registre fuentes degradadas."""
    mock_nasa.return_value = {"status": "success", "degraded": False, "path": "nasa.csv"}
    mock_dmc.return_value = {"status": "degraded", "degraded": True, "path": "dmc.json"}
    mock_conaf.return_value = {"status": "success", "degraded": False, "path": "conaf.json"}

    ingester = ParallelIngester(raw_dir=tmp_path)
    ingester._load_contingency_cache = MagicMock(return_value="contingency.geojson")

    result = ingester.ingest_all_sources()

    assert "nasa_firms" in result
    assert result["dmc_meteo"]["degraded"] is True
    assert "contingency" in result
    ingester._load_contingency_cache.assert_called_once()


@patch("src.ingesta.parallel_ingester.ParallelIngester._download_with_retry")
def test_conaf_loads_institutional_seed_on_failure(mock_download: MagicMock, tmp_path) -> None:
    mock_download.side_effect = requests.exceptions.ConnectionError("CONAF no disponible")
    ingester = ParallelIngester(raw_dir=tmp_path)
    ingester._recuperar_payload_fallback = MagicMock(return_value=pd.DataFrame())
    result = ingester._ingest_conaf()
    assert result["degraded"] is True
    assert result.get("source") == "institutional_seed" or result["path"]
