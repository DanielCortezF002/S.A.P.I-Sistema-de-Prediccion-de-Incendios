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


@patch("src.query.prediction_query.fetch_available_date_range")
@patch("src.query.prediction_query.get_connection")
@patch("src.query.prediction_query.gpd.read_postgis")
def test_get_spatial_risk_map_exact_date(
    mock_read_postgis: MagicMock,
    mock_get_conn: MagicMock,
    mock_date_range: MagicMock,
) -> None:
    """Valida consulta por fecha exacta con límite GRID_MAX_CELLS."""
    mock_date_range.return_value = (date(2025, 2, 9), date(2025, 2, 15))
    mock_conn = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    mock_read_postgis.return_value = pd.DataFrame(
        {
            "cell_id": [f"VP-{i:03d}" for i in range(1, 51)],
            "fecha": [date(2025, 2, 15)] * 50,
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

    result = PredictionQuery().get_spatial_risk_map(date(2025, 2, 15))

    assert len(result) == 50
    sql_text = str(mock_read_postgis.call_args[0][0])
    assert "fecha = :fecha" in sql_text
    assert "DISTINCT ON" not in sql_text


@patch("src.query.prediction_query.fetch_available_date_range")
@patch("src.query.prediction_query.get_connection")
@patch("src.query.prediction_query.gpd.read_postgis")
def test_fetch_spatial_risk_map_engine_version(
    mock_read_postgis: MagicMock,
    mock_get_conn: MagicMock,
    mock_date_range: MagicMock,
) -> None:
    from src.query.risk_map_query import QUERY_ENGINE_VERSION, fetch_spatial_risk_map

    assert QUERY_ENGINE_VERSION == "exact-date-v1"
    mock_date_range.return_value = (date(2025, 2, 9), date(2025, 2, 15))
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
    with patch("src.query.prediction_query.log_event"):
        result = fetch_spatial_risk_map(date(2025, 1, 1))
    assert result.empty


@patch("src.query.prediction_query.fetch_available_date_range")
@patch("src.query.prediction_query.get_connection")
@patch("src.query.prediction_query.gpd.read_postgis")
def test_get_spatial_risk_map_empty_state(
    mock_read_postgis: MagicMock,
    mock_get_conn: MagicMock,
    mock_date_range: MagicMock,
) -> None:
    """Valida resiliencia cuando la consulta no retorna filas."""
    mock_date_range.return_value = (date(2025, 2, 9), date(2025, 2, 15))
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

    with patch("src.query.prediction_query.log_event"):
        service = PredictionQuery()
        result = service.get_spatial_risk_map(date(2025, 1, 1))

    assert isinstance(result, gpd.GeoDataFrame)
    assert result.empty


@patch("src.query.prediction_query.fetch_available_date_range")
@patch("src.query.prediction_query.get_connection")
@patch("src.query.prediction_query.gpd.read_postgis")
def test_fetch_spatial_risk_map_raises_on_db_error(
    mock_read_postgis: MagicMock,
    mock_get_conn: MagicMock,
    mock_date_range: MagicMock,
) -> None:
    import pytest

    from src.query.prediction_query import fetch_spatial_risk_map

    mock_date_range.return_value = (date(2025, 2, 9), date(2025, 2, 15))
    mock_get_conn.return_value.__enter__.return_value = MagicMock()
    mock_read_postgis.side_effect = RuntimeError("db down")
    with patch("src.query.prediction_query.log_event"):
        with pytest.raises(RuntimeError, match="db down"):
            fetch_spatial_risk_map(date(2025, 2, 15))


@patch("src.query.prediction_query.get_connection")
def test_fetch_available_dates(mock_get_conn: MagicMock) -> None:
    from src.query.prediction_query import fetch_available_dates

    mock_conn = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    with patch("src.query.prediction_query.pd.read_sql") as mock_read:
        mock_read.return_value = pd.DataFrame({"fecha": [date(2025, 2, 9), date(2025, 2, 15)]})
        dates = fetch_available_dates()
    assert dates == [date(2025, 2, 9), date(2025, 2, 15)]


@patch("src.query.prediction_query.get_connection")
def test_fetch_available_date_range_empty(mock_get_conn: MagicMock) -> None:
    from src.query.prediction_query import fetch_available_date_range

    mock_conn = MagicMock()
    mock_conn.execute.return_value.mappings.return_value.first.return_value = {
        "min_fecha": None,
        "max_fecha": None,
    }
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    assert fetch_available_date_range() == (None, None)


@patch("src.query.prediction_query.get_connection")
def test_fetch_available_date_range(mock_get_conn: MagicMock) -> None:
    from src.query.prediction_query import fetch_available_date_range

    mock_conn = MagicMock()
    mock_conn.execute.return_value.mappings.return_value.first.return_value = {
        "min_fecha": date(2025, 2, 9),
        "max_fecha": date(2025, 2, 15),
    }
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    min_d, max_d = fetch_available_date_range()
    assert min_d == date(2025, 2, 9)
    assert max_d == date(2025, 2, 15)


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


@patch("src.query.prediction_query.fetch_available_date_range")
def test_get_cell_detail_uses_max_fecha(mock_range: MagicMock) -> None:
    mock_range.return_value = (date(2025, 2, 9), date(2025, 2, 15))
    with patch("src.query.prediction_query.get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_conn.execute.return_value.mappings.return_value.first.return_value = {
            "cell_id": "VP-001",
            "fecha": date(2025, 2, 15),
        }
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        detail = PredictionQuery().get_cell_detail("VP-001")
    assert detail["cell_id"] == "VP-001"


@patch("src.query.prediction_query.fetch_available_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15)))
def test_prediction_query_date_helpers(mock_range: MagicMock) -> None:
    service = PredictionQuery()
    assert service.get_available_date_range() == (date(2025, 2, 9), date(2025, 2, 15))
    with patch("src.query.prediction_query.fetch_available_dates", return_value=[date(2025, 2, 15)]):
        assert service.get_available_dates() == [date(2025, 2, 15)]
