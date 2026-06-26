"""Pruebas de tabla y selección de celdas."""

from __future__ import annotations

import geopandas as gpd
from shapely.geometry import Point

from app.utils.cell_table import (
    build_display_dataframe,
    cell_id_from_folium_output,
    row_index_for_cell,
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
    monkeypatch.setattr("app.utils.cell_table.st.session_state", fake)

    set_selected_cell("VP-002", "map")
    assert fake[SESSION_CELL_KEY] == "VP-002"
    assert fake[SESSION_TABLE_EPOCH_KEY] == 1
    assert table_widget_key(date(2025, 2, 15)) == "cell_detail_2025-02-15_1"

    set_selected_cell("VP-001", "table")
    assert fake[SESSION_TABLE_EPOCH_KEY] == 1
