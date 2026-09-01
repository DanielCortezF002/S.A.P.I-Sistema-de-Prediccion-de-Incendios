"""Pruebas del catálogo DMC y selección espacial por Haversine."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.procesamiento.station_catalog import (
    DmcStation,
    default_station_catalog,
    haversine_km,
    select_nearest_station,
)


def test_default_station_catalog_loads_known_stations_from_config():
    with patch(
        "src.procesamiento.station_catalog.DMC_ESTACIONES_VALPARAISO",
        ["330004", "330005", "330007"],
    ):
        catalog = default_station_catalog()

    assert set(catalog) == {"330004", "330005", "330007"}
    rodelillo = catalog["330007"]
    assert rodelillo.nombre == "Rodelillo, Ad."
    assert rodelillo.latitud == pytest.approx(-33.06528)
    assert rodelillo.longitud == pytest.approx(-71.55639)


def test_default_station_catalog_ignores_codes_without_catastro_coords():
    """Códigos en .env sin coordenadas validadas no entran al catálogo (evita join a ciegas)."""
    with patch(
        "src.procesamiento.station_catalog.DMC_ESTACIONES_VALPARAISO",
        ["330007", "999999"],
    ):
        catalog = default_station_catalog()

    assert list(catalog) == ["330007"]
    assert "999999" not in catalog


def test_select_nearest_station_skips_candidates_missing_from_catalog():
    catalog = {
        "330007": DmcStation("330007", "Rodelillo", -33.06528, -71.55639),
    }
    codigo, dist = select_nearest_station(
        -33.06528,
        -71.55639,
        ["999999", "330007"],
        catalog,
    )
    assert codigo == "330007"
    assert dist == pytest.approx(0.0, abs=1e-6)


def test_select_nearest_station_raises_when_no_catalog_entries_match():
    catalog = {"330007": DmcStation("330007", "Rodelillo", -33.06528, -71.55639)}
    with pytest.raises(ValueError, match="candidate_codes vacío o sin entradas en catálogo"):
        select_nearest_station(-33.0, -71.0, ["888888"], catalog)


def test_haversine_km_same_point_is_zero():
    assert haversine_km(-33.05, -71.55, -33.05, -71.55) == 0.0
