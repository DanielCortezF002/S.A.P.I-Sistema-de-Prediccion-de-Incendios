"""Pruebas de tabla y selección de celdas."""

from __future__ import annotations

import geopandas as gpd
from shapely.geometry import Point

from app.utils.cell_table import (
    build_display_dataframe,
    cell_id_from_folium_output,
    row_index_for_cell,
    top_risk_cell,
)


def test_build_display_dataframe_columns():
    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-049", "VP-001"],
            "probabilidad": [0.9, 0.2],
            "nivel_riesgo": ["alto", "bajo"],
            "temperatura": [32.0, 18.0],
            "humedad_relativa": [25.0, 70.0],
            "velocidad_viento": [35.0, 10.0],
            "regla_30_30_30": [1, 0],
        },
        geometry=[Point(-71.44, -33.04), Point(-71.58, -33.05)],
        crs="EPSG:4326",
    )
    df = build_display_dataframe(gdf)
    assert list(df.columns)[0] == "#"
    assert df.iloc[0]["cell_id"] == "VP-001"
    assert "zona" in df.columns


def test_build_display_dataframe_formats_invalid_regla_value() -> None:
    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001"],
            "probabilidad": [0.5],
            "nivel_riesgo": ["medio"],
            "temperatura": [20.0],
            "humedad_relativa": [50.0],
            "velocidad_viento": [10.0],
            "regla_30_30_30": ["invalido"],
        },
        geometry=[Point(-71.58, -33.05)],
        crs="EPSG:4326",
    )
    df = build_display_dataframe(gdf)
    assert df.iloc[0]["regla 30-30-30"] == "invalido"


def test_cell_id_from_tooltip():
    valid = {"VP-038", "VP-049"}
    output = {"last_object_clicked_tooltip": "VP-038"}
    assert cell_id_from_folium_output(output, valid) == "VP-038"


def test_cell_id_from_empty_output():
    assert cell_id_from_folium_output(None, {"VP-001"}) is None


def test_cell_id_from_popup():
    valid = {"VP-049"}
    output = {"last_object_clicked_popup": "<b>Celda:</b> VP-049"}
    assert cell_id_from_folium_output(output, valid) == "VP-049"


def test_cell_id_from_coordinates_out_of_range():
    gdf = gpd.GeoDataFrame(
        {"cell_id": ["VP-001"]},
        geometry=[Point(-71.58, -33.05)],
        crs="EPSG:4326",
    )
    output = {"last_object_clicked": {"lat": 0.0, "lng": 0.0}}
    assert cell_id_from_folium_output(output, {"VP-001"}, gdf) is None


def test_cell_id_skips_cells_not_in_valid_set():
    gdf = gpd.GeoDataFrame(
        {"cell_id": ["VP-001", "VP-002"]},
        geometry=[Point(-71.58, -33.05), Point(-71.50, -33.04)],
        crs="EPSG:4326",
    )
    output = {"last_object_clicked": {"lat": -33.04, "lng": -71.50}}
    assert cell_id_from_folium_output(output, {"VP-002"}, gdf) == "VP-002"


def test_cell_id_from_coordinates():
    gdf = gpd.GeoDataFrame(
        {"cell_id": ["VP-001", "VP-002"]},
        geometry=[Point(-71.58, -33.05), Point(-71.50, -33.04)],
        crs="EPSG:4326",
    )
    valid = {"VP-001", "VP-002"}
    output = {"last_object_clicked": {"lat": -33.05, "lng": -71.58}}
    assert cell_id_from_folium_output(output, valid, gdf) == "VP-001"


def test_row_index_for_cell():
    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001", "VP-002"],
            "probabilidad": [0.1, 0.2],
            "nivel_riesgo": ["bajo", "bajo"],
            "temperatura": [18.0, 19.0],
            "humedad_relativa": [60.0, 55.0],
            "velocidad_viento": [12.0, 14.0],
            "regla_30_30_30": [0, 0],
        },
        geometry=[Point(-71.58, -33.05), Point(-71.50, -33.04)],
        crs="EPSG:4326",
    )
    df = build_display_dataframe(gdf)
    assert row_index_for_cell(df, "VP-002") == 1
    assert row_index_for_cell(df, None) is None
    assert row_index_for_cell(df, "VP-999") is None


def test_top_risk_cell_prioritizes_nivel_over_probabilidad():
    # VP-002 tiene menor probabilidad pero nivel "alto" — debe ganarle a
    # VP-001, que tiene mayor probabilidad pero nivel "medio". El nivel
    # manda; la probabilidad solo desempata dentro del mismo nivel.
    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001", "VP-002"],
            "probabilidad": [0.95, 0.40],
            "nivel_riesgo": ["medio", "alto"],
            "regla_30_30_30": [0, 1],
        },
        geometry=[Point(-71.58, -33.05), Point(-71.21, -33.02)],
        crs="EPSG:4326",
    )
    top = top_risk_cell(gdf)
    assert top["cell_id"] == "VP-002"
    assert top["nivel_riesgo"] == "alto"
    assert top["regla_30_30_30"] is True


def test_top_risk_cell_breaks_tie_by_probabilidad():
    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001", "VP-002"],
            "probabilidad": [0.70, 0.85],
            "nivel_riesgo": ["alto", "alto"],
            "regla_30_30_30": [0, 0],
        },
        geometry=[Point(-71.58, -33.05), Point(-71.50, -33.04)],
        crs="EPSG:4326",
    )
    top = top_risk_cell(gdf)
    assert top["cell_id"] == "VP-002"
    assert top["probabilidad"] == 0.85


def test_top_risk_cell_regla_inactive_when_zero():
    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001"],
            "probabilidad": [0.9],
            "nivel_riesgo": ["alto"],
            "regla_30_30_30": [0],
        },
        geometry=[Point(-71.58, -33.05)],
        crs="EPSG:4326",
    )
    assert top_risk_cell(gdf)["regla_30_30_30"] is False


def test_top_risk_cell_invalid_regla_value_falls_back_to_false():
    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001"],
            "probabilidad": [0.9],
            "nivel_riesgo": ["alto"],
            "regla_30_30_30": ["invalido"],
        },
        geometry=[Point(-71.58, -33.05)],
        crs="EPSG:4326",
    )
    assert top_risk_cell(gdf)["regla_30_30_30"] is False


def test_top_risk_cell_maps_short_zona_label():
    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-008"],
            "probabilidad": [0.6],
            "nivel_riesgo": ["medio"],
            "regla_30_30_30": [0],
        },
        geometry=[Point(-71.21, -33.02)],
        crs="EPSG:4326",
    )
    assert top_risk_cell(gdf)["zona"] == "Precordillera"


def test_top_risk_cell_empty_or_none_gdf_returns_none():
    empty = gpd.GeoDataFrame(
        {"cell_id": [], "probabilidad": [], "nivel_riesgo": [], "regla_30_30_30": []},
        geometry=[],
        crs="EPSG:4326",
    )
    assert top_risk_cell(empty) is None
    assert top_risk_cell(None) is None


def test_set_selected_cell_increments_epoch_on_map(monkeypatch):
    from datetime import date

    from app.utils.cell_table import (
        SESSION_CELL_KEY,
        SESSION_TABLE_EPOCH_KEY,
        set_selected_cell,
        table_widget_key,
    )

    state: dict = {"_table_epoch": 0}

    class FakeSessionState(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    fake = FakeSessionState(state)
    # El estado de sesión vive en `app.state`; `cell_table` solo reexporta los
    # nombres que ya consumían app.py y estos tests.
    monkeypatch.setattr("app.state.st.session_state", fake)

    set_selected_cell("VP-002", "map")
    assert fake[SESSION_CELL_KEY] == "VP-002"
    assert fake[SESSION_TABLE_EPOCH_KEY] == 1
    assert table_widget_key(date(2025, 2, 15)) == "cell_detail_2025-02-15_1"

    set_selected_cell("VP-001", "table")
    assert fake[SESSION_TABLE_EPOCH_KEY] == 1
