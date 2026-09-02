"""Pruebas de src.modelo.inference_engine (sin tocar Postgres real).

Nota: este módulo no tenía cobertura previa. Se agregan pruebas acotadas a
las funciones puras (`_prepare_feature_matrix`, `_classify_risk`) — la
verificación de que `orientacion` llega desde Postgres hasta el modelo,
que es el cambio que motivó esto (SAPI-30).
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from src.modelo.inference_engine import FEATURE_COLUMNS, _classify_risk, _prepare_feature_matrix


def _sample_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001", "VP-002"],
            "temperatura": [30.0, 22.0],
            "humedad_relativa": [25.0, 60.0],
            "velocidad_viento": [32.0, 8.0],
            "regla_30_30_30": [1, 0],
            "altitud": [200.0, 150.0],
            "pendiente": [15.0, 10.0],
            "orientacion": [270.0, 90.0],
            "ndvi": [0.4, 0.6],
            "lag_temp_24h": [29.0, 21.0],
            "lag_temp_48h": [28.0, 20.5],
            "geometry": [box(-71.5, -33.1, -71.49, -33.09), box(-71.4, -33.0, -71.39, -32.99)],
        },
        crs="EPSG:4326",
    )


def test_feature_columns_include_orientacion_encoding() -> None:
    # FEATURE_COLUMNS = BaselineModel.FEATURE_COLUMNS: confirma que el alias
    # del módulo no quedó desincronizado del cambio real.
    assert "orientacion_sin" in FEATURE_COLUMNS
    assert "orientacion_cos" in FEATURE_COLUMNS
    assert "orientacion" not in FEATURE_COLUMNS  # nunca cruda, ver features.py


def test_prepare_feature_matrix_derives_orientacion_sin_cos_from_raw_column() -> None:
    matrix = _prepare_feature_matrix(_sample_gdf())

    assert "orientacion_sin" in matrix.columns
    assert "orientacion_cos" in matrix.columns
    # 270° -> sin=-1, cos=0 (dentro de tolerancia float32/float64 mixta)
    assert abs(matrix["orientacion_sin"].iloc[0] - (-1.0)) < 1e-6
    assert abs(matrix["orientacion_cos"].iloc[0] - 0.0) < 1e-6
    assert not matrix.isna().any().any()


def test_prepare_feature_matrix_fills_missing_columns_with_zero() -> None:
    gdf = gpd.GeoDataFrame(
        {"cell_id": ["VP-001"], "temperatura": [25.0], "geometry": [box(-71.5, -33.1, -71.49, -33.09)]},
        crs="EPSG:4326",
    )
    matrix = _prepare_feature_matrix(gdf)
    assert set(FEATURE_COLUMNS).issubset(matrix.columns)
    assert (matrix["altitud"] == 0.0).all()


def test_prepare_feature_matrix_renames_velocidad_viento_kmh() -> None:
    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001"],
            "velocidad_viento_kmh": [40.0],
            "geometry": [box(-71.5, -33.1, -71.49, -33.09)],
        },
        crs="EPSG:4326",
    )
    matrix = _prepare_feature_matrix(gdf)
    assert matrix["velocidad_viento"].iloc[0] == 40.0


def test_classify_risk_thresholds() -> None:
    assert _classify_risk(0.1) == "bajo"
    assert _classify_risk(0.5) == "medio"
    assert _classify_risk(0.9) == "alto"
