"""Pruebas de PredictionQuery y clasificación."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pandas as pd

from src.query.prediction_query import PredictionQuery


def test_classify_risk_levels() -> None:
    assert PredictionQuery.classify_risk(0.1) == "bajo"
    assert PredictionQuery.classify_risk(0.5) == "medio"
    assert PredictionQuery.classify_risk(0.9) == "alto"


@patch("src.query.risk_map_query.get_connection")
@patch("src.query.risk_map_query.gpd.read_postgis")
def test_get_spatial_risk_map_distinct_on_per_cell(
    mock_read_postgis: MagicMock, mock_get_conn: MagicMock
) -> None:
    """Valida consulta por celda con límite GRID_MAX_CELLS."""
    mock_conn = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    mock_read_postgis.return_value = pd.DataFrame(
        {
            "cell_id": [f"VP-{i:03d}" for i in range(1, 51)],
            "fecha": [date(2025, 6, 1)] * 50,
            "probabilidad": [0.5] * 50,
            "nivel_riesgo": ["medio"] * 50,
            "temperatura": [25.0] * 50,
            "humedad_relativa": [40.0] * 50,
            "velocidad_viento": [15.0] * 50,
            "regla_30_30_30": [0] * 50,
            "modelo_version": ["xgboost_v1.0"] * 50,
            "geom": [None] * 50,
        }
    )

    result = PredictionQuery().get_spatial_risk_map(date(2026, 6, 20))

    assert len(result) == 50
    sql_text = str(mock_read_postgis.call_args[0][0])
    assert "DISTINCT ON" in sql_text


@patch("src.query.risk_map_query.get_connection")
@patch("src.query.risk_map_query.gpd.read_postgis")
def test_fetch_spatial_risk_map_engine_version(
    mock_read_postgis: MagicMock, mock_get_conn: MagicMock
) -> None:
    from src.query.risk_map_query import QUERY_ENGINE_VERSION, fetch_spatial_risk_map

    assert QUERY_ENGINE_VERSION == "distinct-on-v2"
    mock_conn = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    mock_read_postgis.return_value = pd.DataFrame(
        columns=[
            "cell_id",
            "fecha",
            "probabilidad",
            "nivel_riesgo",
            "temperatura",
            "humedad_relativa",
            "velocidad_viento",
            "regla_30_30_30",
            "modelo_version",
            "geom",
        ]
    )
    result = fetch_spatial_risk_map(date(2026, 6, 20))
    assert result.empty


@patch("src.query.risk_map_query.get_connection")
@patch("src.query.risk_map_query.gpd.read_postgis")
def test_get_spatial_risk_map_empty_state(
    mock_read_postgis: MagicMock, mock_get_conn: MagicMock
) -> None:
    """Valida resiliencia cuando la consulta no retorna filas."""
    mock_conn = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    mock_read_postgis.return_value = pd.DataFrame(
        columns=[
            "cell_id",
            "fecha",
            "probabilidad",
            "nivel_riesgo",
            "temperatura",
            "humedad_relativa",
            "velocidad_viento",
            "regla_30_30_30",
            "modelo_version",
            "geom",
        ]
    )

    with patch("src.query.risk_map_query.log_event"):
        service = PredictionQuery()
        result = service.get_spatial_risk_map(date.today())

    assert isinstance(result, gpd.GeoDataFrame)
    assert result.empty


@patch("src.query.prediction_query.get_connection")
@patch("src.query.prediction_query.gpd.read_postgis")
def test_get_contingency_cache_returns_geodataframe(
    mock_read_postgis: MagicMock, mock_get_conn: MagicMock
) -> None:
    """Valida que contingencia retorne GeoDataFrame estructurado."""
    mock_conn = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    mock_read_postgis.return_value = pd.DataFrame(
        columns=[
            "cell_id",
            "fecha",
            "probabilidad",
            "nivel_riesgo",
            "temperatura",
            "humedad_relativa",
            "velocidad_viento",
            "regla_30_30_30",
            "modelo_version",
            "geom",
        ]
    )

    service = PredictionQuery()
    result = service.get_contingency_cache(days=7)

    assert isinstance(result, gpd.GeoDataFrame)
    assert result.crs.to_string() == "EPSG:4326"


@patch("src.query.prediction_query.get_connection")
@patch("src.query.prediction_query.pd.read_sql")
def test_get_observability_logs(mock_read_sql: MagicMock, mock_get_conn: MagicMock) -> None:
    mock_conn = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    mock_read_sql.return_value = pd.DataFrame({"componente": ["seed"], "evento": ["init"]})

    logs = PredictionQuery().get_observability_logs(limit=5)
    assert len(logs) == 1


@patch("src.query.prediction_query.get_connection")
def test_get_cell_detail_empty(mock_get_conn: MagicMock) -> None:
    mock_conn = MagicMock()
    mock_conn.execute.return_value.mappings.return_value.first.return_value = None
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    detail = PredictionQuery().get_cell_detail("VP-999")
    assert detail == {}

