"""Pruebas del cliente DemIngester (DEM COP30 vía OpenTopography)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import rasterio
import requests
from rasterio.transform import from_origin

from src.ingesta.dem_ingester import DemIngester, bbox_area_km2

_SMALL_BBOX = {
    "min_lon": -71.59,
    "max_lon": -71.34,
    "min_lat": -33.11,
    "max_lat": -32.96,
}
_HUGE_BBOX = {
    "min_lon": -71.75,
    "max_lon": -70.25,
    "min_lat": -33.65,
    "max_lat": -32.00,
}


def _write_fake_geotiff(path: Path, width: int = 4, height: int = 4) -> bytes:
    """Genera un GeoTIFF mínimo válido (no un mock) para que rasterio lo lea de verdad."""

    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.linspace(0, 300, width * height, dtype="float32").reshape(height, width)
    transform = from_origin(_SMALL_BBOX["min_lon"], _SMALL_BBOX["max_lat"], 0.01, 0.01)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
    ) as dataset:
        dataset.write(data, 1)
    return path.read_bytes()


def test_bbox_area_km2_matches_manual_calculation() -> None:
    area = bbox_area_km2(_SMALL_BBOX)
    assert 380 <= area <= 400


def test_client_init_requires_api_key() -> None:
    with pytest.raises(ValueError, match="OPENTOPO_API_KEY"):
        DemIngester(api_key="", bbox=_SMALL_BBOX)


def test_client_init_rejects_bbox_over_area_limit() -> None:
    with pytest.raises(ValueError, match="excede el límite"):
        DemIngester(api_key="k", bbox=_HUGE_BBOX)


def test_get_with_retry_recovers_from_429(tmp_path: Path) -> None:
    sleeps: list[float] = []
    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.headers = {"Retry-After": "1"}
    ok = MagicMock()
    ok.status_code = 200
    ok.headers = {}
    ok.raise_for_status = MagicMock()

    client = DemIngester(api_key="k", bbox=_SMALL_BBOX, raw_dir=tmp_path, sleep_fn=sleeps.append)
    client.session.get = MagicMock(side_effect=[rate_limited, ok])

    response = client._get_with_retry("https://example.test")
    assert response is ok
    assert sleeps


def test_get_with_retry_raises_after_four_failures(tmp_path: Path) -> None:
    client = DemIngester(api_key="k", bbox=_SMALL_BBOX, raw_dir=tmp_path, sleep_fn=lambda _: None)
    client.session.get = MagicMock(side_effect=requests.ConnectionError("reset"))

    with pytest.raises(RuntimeError, match="4 intentos"):
        client._get_with_retry("https://example.test")


def test_download_url_never_appears_in_retry_error(tmp_path: Path) -> None:
    """La API_Key no debe quedar expuesta en el mensaje de error final."""

    client = DemIngester(api_key="secret-key-123", bbox=_SMALL_BBOX, raw_dir=tmp_path, sleep_fn=lambda _: None)
    client.session.get = MagicMock(side_effect=requests.ConnectionError("secret-key-123 en la URL"))

    with pytest.raises(RuntimeError) as exc_info:
        client._get_with_retry(client._download_url())

    full_chain = f"{exc_info.value}{exc_info.value.__cause__}"
    assert "secret-key-123" not in full_chain
    assert "REDACTADA" in full_chain


def test_fetch_downloads_reads_and_writes_manifest(tmp_path: Path) -> None:
    client = DemIngester(api_key="k", bbox=_SMALL_BBOX, raw_dir=tmp_path, sleep_fn=lambda _: None)
    fake_tif_bytes = _write_fake_geotiff(tmp_path / "source.tif")

    response = MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "image/tiff"}
    response.content = fake_tif_bytes
    response.raise_for_status = MagicMock()
    client.session.get = MagicMock(return_value=response)

    result = client.fetch()

    assert result.cached is False
    assert result.path.exists()
    assert result.width == 4 and result.height == 4
    assert result.crs == "EPSG:4326"
    assert result.max_elevation_m > result.min_elevation_m

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["cached"] is False
    assert len(manifest["sha256"]) == 64
    assert manifest["area_km2"] == round(bbox_area_km2(_SMALL_BBOX), 2)


def test_fetch_reuses_cache_without_calling_api(tmp_path: Path) -> None:
    client = DemIngester(api_key="k", bbox=_SMALL_BBOX, raw_dir=tmp_path, sleep_fn=lambda _: None)
    fake_tif_bytes = _write_fake_geotiff(tmp_path / "source.tif")

    response = MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "image/tiff"}
    response.content = fake_tif_bytes
    response.raise_for_status = MagicMock()
    client.session.get = MagicMock(return_value=response)

    first = client.fetch()
    assert first.cached is False
    assert client.session.get.call_count == 1

    second = client.fetch()
    assert second.cached is True
    assert client.session.get.call_count == 1  # no repitió la llamada a la API


def test_fetch_force_true_bypasses_cache(tmp_path: Path) -> None:
    client = DemIngester(api_key="k", bbox=_SMALL_BBOX, raw_dir=tmp_path, sleep_fn=lambda _: None)
    fake_tif_bytes = _write_fake_geotiff(tmp_path / "source.tif")

    response = MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "image/tiff"}
    response.content = fake_tif_bytes
    response.raise_for_status = MagicMock()
    client.session.get = MagicMock(return_value=response)

    client.fetch()
    result = client.fetch(force=True)

    assert result.cached is False
    assert client.session.get.call_count == 2


def test_fetch_rejects_non_tiff_response_body(tmp_path: Path) -> None:
    client = DemIngester(api_key="k", bbox=_SMALL_BBOX, raw_dir=tmp_path, sleep_fn=lambda _: None)

    response = MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "application/json"}
    response.text = '{"error": "Invalid demtype"}'
    response.raise_for_status = MagicMock()
    client.session.get = MagicMock(return_value=response)

    with pytest.raises(RuntimeError, match="Respuesta inesperada"):
        client.fetch()
