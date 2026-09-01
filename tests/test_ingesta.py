"""Pruebas de ingesta asíncrona."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests
from tenacity import RetryError

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


@patch("src.ingesta.parallel_ingester.requests.get")
def test_download_with_retry_recovers_after_transient_http_errors(mock_get: MagicMock) -> None:
    """Reintenta hasta 4 veces ante HTTPError transitorio antes de rendirse."""
    failing = MagicMock()
    failing.raise_for_status.side_effect = requests.HTTPError("503 Service Unavailable")

    ok = MagicMock()
    ok.raise_for_status = MagicMock()
    mock_get.side_effect = [failing, failing, ok]

    ingester = ParallelIngester()
    response = ingester._download_with_retry("https://example.com/api")
    assert response is ok
    assert mock_get.call_count == 3


@patch("src.ingesta.parallel_ingester.requests.get")
def test_download_with_retry_exhausts_all_attempts(mock_get: MagicMock) -> None:
    failing = MagicMock()
    failing.raise_for_status.side_effect = requests.ConnectionError("reset by peer")
    mock_get.return_value = failing

    ingester = ParallelIngester()
    with pytest.raises(RetryError):
        ingester._download_with_retry("https://example.com/api")
    assert mock_get.call_count == 4


@patch("src.ingesta.parallel_ingester.DMC_TOKEN", "token-test")
@patch("src.ingesta.parallel_ingester.DMC_USUARIO", "usuario-test")
@patch("src.ingesta.parallel_ingester.DMC_ESTACIONES_VALPARAISO", ["330004", "330005", "330007"])
@patch("src.ingesta.parallel_ingester.ParallelIngester._download_with_retry")
def test_ingest_dmc_keeps_stations_without_data_in_payload(
    mock_download: MagicMock,
    tmp_path,
) -> None:
    """Estaciones sin telemetría ('Información no disponible') siguen en el JSON agregado."""
    def _station_response(url: str, params: dict | None = None) -> MagicMock:
        codigo = url.rstrip("/").split("/")[-1]
        resp = MagicMock()
        if codigo in {"330004", "330005"}:
            resp.json.return_value = {"error": "Información no disponible"}
        else:
            resp.json.return_value = {
                "datosEstaciones": {
                    "datos": [
                        {
                            "momento": "2025-02-01 12:00:00",
                            "temperatura": "20.0 °C",
                            "humedadRelativa": "40 %",
                            "fuerzaDelViento": "8 kt",
                        }
                    ]
                }
            }
        return resp

    mock_download.side_effect = _station_response

    ingester = ParallelIngester(raw_dir=tmp_path)
    result = ingester._ingest_dmc()

    assert result["status"] == "success"
    assert result["degraded"] is False
    assert mock_download.call_count == 3

    payload = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert set(payload) == {"330004", "330005", "330007"}
    assert payload["330004"]["error"] == "Información no disponible"
    assert payload["330005"]["error"] == "Información no disponible"
    assert "datosEstaciones" in payload["330007"]


@patch("src.ingesta.parallel_ingester.DMC_TOKEN", "")
@patch("src.ingesta.parallel_ingester.DMC_USUARIO", "")
@patch("src.ingesta.parallel_ingester.ParallelIngester._degrade_source")
def test_ingest_dmc_missing_credentials_degrades(mock_degrade: MagicMock, tmp_path) -> None:
    mock_degrade.return_value = {"status": "failed", "degraded": True, "path": ""}
    ingester = ParallelIngester(raw_dir=tmp_path)
    result = ingester._ingest_dmc()
    mock_degrade.assert_called_once()
    assert result["degraded"] is True


@patch("src.ingesta.parallel_ingester.get_backend_connection")
def test_recuperar_payload_fallback_reads_staging(mock_conn_ctx: MagicMock, tmp_path) -> None:
    df = pd.DataFrame([{"temperatura": 25.0, "created_at": "2025-01-01"}])
    conn = MagicMock()
    mock_conn_ctx.return_value.__enter__.return_value = conn

    with patch("src.ingesta.parallel_ingester.pd.read_sql", return_value=df) as mock_read:
        ingester = ParallelIngester(raw_dir=tmp_path)
        out = ingester._recuperar_payload_fallback("staging_meteo")

    assert len(out) == 1
    mock_read.assert_called_once()


def test_recuperar_payload_fallback_denies_unknown_table(tmp_path) -> None:
    ingester = ParallelIngester(raw_dir=tmp_path)
    out = ingester._recuperar_payload_fallback("predicciones_riesgo")
    assert out.empty


@patch("src.ingesta.parallel_ingester.ParallelIngester._ingest_nasa_firms")
@patch("src.ingesta.parallel_ingester.ParallelIngester._ingest_dmc")
@patch("src.ingesta.parallel_ingester.ParallelIngester._ingest_conaf")
def test_ingest_all_sources_catches_worker_exception(
    mock_conaf: MagicMock,
    mock_dmc: MagicMock,
    mock_nasa: MagicMock,
    tmp_path,
) -> None:
    mock_nasa.return_value = {"status": "success", "degraded": False, "path": "nasa.csv"}
    mock_dmc.side_effect = RuntimeError("worker crash")
    mock_conaf.return_value = {"status": "success", "degraded": False, "path": "conaf.json"}

    ingester = ParallelIngester(raw_dir=tmp_path)
    ingester._load_contingency_cache = MagicMock(return_value="contingency.geojson")
    result = ingester.ingest_all_sources()

    assert result["dmc_meteo"]["status"] == "failed"
    assert result["dmc_meteo"]["degraded"] is True
    assert "contingency" in result


def test_degrade_source_exports_incendios_with_lat_lon_rename(tmp_path) -> None:
    ingester = ParallelIngester(raw_dir=tmp_path)
    df = pd.DataFrame([{"latitud": -33.05, "longitud": -71.55, "intensidad": 1}])
    ingester._recuperar_payload_fallback = MagicMock(return_value=df)
    out_path = tmp_path / "nasa_fallback.csv"
    exc = requests.HTTPError("timeout")

    result = ingester._degrade_source("nasa_firms", "staging_incendios", out_path, exc)

    assert result["status"] == "degraded"
    header = out_path.read_text(encoding="utf-8").splitlines()[0]
    assert header == "latitude,longitude,intensidad"


@patch("src.ingesta.parallel_ingester.NASA_FIRMS_API_KEY", "")
def test_ingest_nasa_missing_api_key_degrades(tmp_path) -> None:
    ingester = ParallelIngester(raw_dir=tmp_path)
    ingester._recuperar_payload_fallback = MagicMock(return_value=pd.DataFrame())
    result = ingester._ingest_nasa_firms()
    assert result["degraded"] is True
    assert result["status"] == "failed"


@patch("src.ingesta.parallel_ingester.NASA_FIRMS_API_KEY", "map-key-test")
@patch("src.ingesta.parallel_ingester.ParallelIngester._download_with_retry")
def test_ingest_nasa_success_writes_daily_csv(mock_download: MagicMock, tmp_path) -> None:
    mock_response = MagicMock()
    mock_response.text = "latitude,longitude,acq_date\n-33,-71,2026-01-01\n"
    mock_download.return_value = mock_response

    ingester = ParallelIngester(raw_dir=tmp_path)
    result = ingester._ingest_nasa_firms()

    assert result["status"] == "success"
    assert result["degraded"] is False
    assert Path(result["path"]).exists()
    mock_download.assert_called_once()
    assert "/map-key-test/" in mock_download.call_args[0][0]


@patch("src.ingesta.parallel_ingester.DMC_TOKEN", "token")
@patch("src.ingesta.parallel_ingester.DMC_USUARIO", "user")
@patch("src.ingesta.parallel_ingester.DMC_ESTACIONES_VALPARAISO", [])
def test_ingest_dmc_empty_station_catalog_degrades(tmp_path) -> None:
    ingester = ParallelIngester(raw_dir=tmp_path)
    ingester._recuperar_payload_fallback = MagicMock(return_value=pd.DataFrame())
    result = ingester._ingest_dmc()
    assert result["degraded"] is True
    assert result["status"] == "failed"


@patch("src.ingesta.parallel_ingester.get_backend_connection")
def test_recuperar_payload_fallback_handles_db_error(mock_conn_ctx: MagicMock, tmp_path) -> None:
    mock_conn_ctx.side_effect = RuntimeError("db down")
    ingester = ParallelIngester(raw_dir=tmp_path)
    out = ingester._recuperar_payload_fallback("staging_meteo")
    assert out.empty


@patch("src.ingesta.parallel_ingester.ParallelIngester._download_with_retry")
def test_ingest_conaf_success_when_api_reachable_without_seed(mock_download: MagicMock, tmp_path) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_download.return_value = mock_response

    ingester = ParallelIngester(raw_dir=tmp_path)
    with patch("src.ingesta.parallel_ingester.CONAF_SEED_PATH", tmp_path / "missing_seed.json"):
        result = ingester._ingest_conaf()

    assert result["status"] == "success"
    assert result["degraded"] is False
    payload = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert payload[0]["status"] == "reachable"


def test_parse_conaf_response_reads_institutional_seed(tmp_path) -> None:
    seed_path = tmp_path / "conaf_seed.json"
    seed_path.write_text('[{"evento": "demo"}]', encoding="utf-8")
    ingester = ParallelIngester(raw_dir=tmp_path)
    response = MagicMock()
    with patch("src.ingesta.parallel_ingester.CONAF_SEED_PATH", seed_path):
        payload = ingester._parse_conaf_response(response)
    assert payload == [{"evento": "demo"}]


def test_load_institutional_conaf_seed_fails_when_file_missing(tmp_path) -> None:
    ingester = ParallelIngester(raw_dir=tmp_path)
    with patch("src.ingesta.parallel_ingester.CONAF_SEED_PATH", tmp_path / "nope.json"):
        result = ingester._load_institutional_conaf_seed(tmp_path / "out.json")
    assert result["status"] == "failed"
    assert result["path"] == ""


def test_degrade_source_exports_meteo_as_json_records(tmp_path) -> None:
    ingester = ParallelIngester(raw_dir=tmp_path)
    df = pd.DataFrame([{"temperatura": 30.0, "created_at": "2025-01-01"}])
    ingester._recuperar_payload_fallback = MagicMock(return_value=df)
    out_path = tmp_path / "dmc_fallback.json"
    result = ingester._degrade_source("dmc_meteo", "staging_meteo", out_path, requests.Timeout("t"))
    assert result["status"] == "degraded"
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload[0]["temperatura"] == 30.0


@patch("src.ingesta.parallel_ingester.PredictionQuery")
def test_load_contingency_cache_writes_geojson_when_data_exists(mock_query_cls: MagicMock, tmp_path) -> None:
    import geopandas as gpd
    from shapely.geometry import Point

    gdf = gpd.GeoDataFrame(
        {"cell_id": ["VP-001"]},
        geometry=[Point(-71.5, -33.0)],
        crs="EPSG:4326",
    )
    mock_query_cls.return_value.get_contingency_cache.return_value = gdf

    ingester = ParallelIngester(raw_dir=tmp_path)
    out = ingester._load_contingency_cache()

    assert out.endswith("contingency_cache.geojson")
    assert Path(out).exists()


def test_degrade_source_exports_incendios_without_lat_lon_columns(tmp_path) -> None:
    ingester = ParallelIngester(raw_dir=tmp_path)
    df = pd.DataFrame([{"sensor": "VIIRS", "brightness": 320.0}])
    ingester._recuperar_payload_fallback = MagicMock(return_value=df)
    out_path = tmp_path / "nasa_fallback.csv"

    result = ingester._degrade_source("nasa_firms", "staging_incendios", out_path, requests.Timeout("t"))

    assert result["status"] == "degraded"
    header = out_path.read_text(encoding="utf-8").splitlines()[0]
    assert header == "sensor,brightness"


def test_degrade_source_unknown_staging_table_writes_csv(tmp_path) -> None:
    ingester = ParallelIngester(raw_dir=tmp_path)
    df = pd.DataFrame([{"valor": 1}])
    ingester._recuperar_payload_fallback = MagicMock(return_value=df)
    out_path = tmp_path / "other_fallback.csv"

    result = ingester._degrade_source("custom", "staging_custom", out_path, requests.Timeout("t"))

    assert result["status"] == "degraded"
    assert out_path.read_text(encoding="utf-8").startswith("valor")


@patch("src.ingesta.parallel_ingester.ParallelIngester._download_with_retry", side_effect=requests.Timeout("t"))
@patch("src.ingesta.parallel_ingester.ParallelIngester._degrade_source")
def test_ingest_conaf_falls_back_to_institutional_seed_when_degrade_fails(
    mock_degrade: MagicMock,
    _mock_download: MagicMock,
    tmp_path,
) -> None:
    mock_degrade.return_value = {"status": "failed", "degraded": True, "path": "", "error": "empty"}
    seed_path = tmp_path / "conaf_seed.json"
    seed_path.write_text('[{"evento": "historico"}]', encoding="utf-8")

    ingester = ParallelIngester(raw_dir=tmp_path)
    with patch("src.ingesta.parallel_ingester.CONAF_SEED_PATH", seed_path):
        result = ingester._ingest_conaf()

    assert result["status"] == "degraded"
    assert result["source"] == "institutional_seed"
    assert json.loads(Path(result["path"]).read_text(encoding="utf-8")) == [{"evento": "historico"}]
