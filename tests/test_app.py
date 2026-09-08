"""Pruebas de la aplicación Streamlit y contratos de componentes."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from app.app import SapiDashboard
from app.utils.demo_seed import get_all_demo_dates


def test_export_report_pdf():
    dashboard = SapiDashboard()
    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001", "VP-002"],
            "probabilidad": [0.8, 0.2],
            "nivel_riesgo": ["alto", "bajo"],
            "regla_30_30_30": [1, 0],
        },
        geometry=[box(-71.58, -33.05, -71.57, -33.04), box(-71.57, -33.05, -71.56, -33.04)],
        crs="EPSG:4326",
    )

    # Este reporte es siempre sobre el escenario demo (gdf_precargado demo) —
    # se fija SAPI_DATA_MODE explícito para la prueba en vez de depender del
    # default global del dashboard (que desde la iteración del prototipo es
    # "prototype", no "demo_seed").
    with (
        patch("app.app._cached_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15))),
        patch("app.app.SAPI_DATA_MODE", "demo_seed"),
    ):
        report = dashboard.export_report_pdf(date(2025, 2, 15), gdf_precargado=gdf)

    content = report.decode("utf-8")
    assert "S.A.P.I." in content
    assert "Riesgo alto" in content
    assert "Recall XGBoost" in content
    assert "AUC-ROC" in content
    assert "data_source=demo_seed" in content
    assert "SAPI_DATA_MODE=demo_seed" in content


def test_export_report_empty():
    dashboard = SapiDashboard()
    empty = gpd.GeoDataFrame(
        columns=["cell_id", "probabilidad", "nivel_riesgo"],
        geometry=[],
        crs="EPSG:4326",
    )
    with patch("app.app._cached_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15))):
        report = dashboard.export_report_pdf(date(2025, 2, 9), gdf_precargado=empty)
    assert b"Celdas analizadas: 0" in report
    assert b"data_source=demo_seed" in report


@patch("app.components.controls.st.sidebar")
def test_render_data_mode_badge_demo_seed(mock_sidebar: MagicMock) -> None:
    from app.components.controls import render_data_mode_badge

    with patch("app.components.controls.SAPI_DATA_MODE", "demo_seed"):
        render_data_mode_badge()
    mock_sidebar.markdown.assert_called_once()
    caption = mock_sidebar.caption.call_args[0][0]
    assert "demo_seed" in caption
    assert "no de inferencia XGBoost" in caption


@patch("app.components.controls.st.sidebar")
def test_render_data_mode_badge_prototype(mock_sidebar: MagicMock) -> None:
    """Desde la iteración del prototipo (2026-09-07), 'prototype' es un
    modo reconocido — no debe caer en la rama de advertencia genérica."""
    from app.components.controls import render_data_mode_badge

    with patch("app.components.controls.SAPI_DATA_MODE", "prototype"):
        render_data_mode_badge()
    mock_sidebar.markdown.assert_called_once()
    mock_sidebar.warning.assert_not_called()
    caption = mock_sidebar.caption.call_args[0][0]
    assert "prototype" in caption


@patch("app.components.banner.st.info")
def test_render_demo_scope_banner_mentions_vp049(mock_info: MagicMock) -> None:
    from app.components.banner import render_demo_scope_banner

    render_demo_scope_banner(date(2025, 2, 9), date(2025, 2, 15))
    mock_info.assert_called_once()
    text = mock_info.call_args[0][0]
    assert "VP-049" in text
    assert "escenario sembrado" in text
    assert "no" in text.lower() and "modelo" in text.lower()


@patch("app.app._cached_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15)))
@patch("app.app.st_folium")
@patch("app.app._build_folium_map")
@patch("app.app.get_demo_gdf")
def test_render_folium_map_fetches_gdf_when_missing(
    mock_get_demo_gdf, mock_build_map, mock_st_folium, _mock_range
):
    mock_build_map.return_value = MagicMock()
    mock_st_folium.return_value = {}
    gdf = gpd.GeoDataFrame(
        {"cell_id": ["VP-001"], "probabilidad": [0.5], "nivel_riesgo": ["medio"]},
        geometry=[box(-71.58, -33.05, -71.57, -33.04)],
        crs="EPSG:4326",
    )
    mock_get_demo_gdf.return_value = gdf
    dashboard = SapiDashboard()
    dashboard.render_folium_map(date(2025, 2, 15))

    mock_get_demo_gdf.assert_called_once_with(date(2025, 2, 15))
    mock_build_map.assert_called_once_with(date(2025, 2, 15))
    mock_st_folium.assert_called_once()


@patch("app.app._cached_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15)))
@patch("app.app.st_folium")
@patch("app.app._build_folium_map")
def test_render_folium_map_method(mock_build_map, mock_st_folium, _mock_range):
    mock_build_map.return_value = MagicMock()
    mock_st_folium.return_value = {"last_object_clicked_tooltip": "VP-001"}
    gdf = gpd.GeoDataFrame(
        {"cell_id": ["VP-001"], "probabilidad": [0.5], "nivel_riesgo": ["medio"]},
        geometry=[box(-71.58, -33.05, -71.57, -33.04)],
        crs="EPSG:4326",
    )
    dashboard = SapiDashboard()
    output = dashboard.render_folium_map(date(2025, 2, 15), gdf=gdf)

    mock_build_map.assert_called_once_with(date(2025, 2, 15))
    mock_st_folium.assert_called_once()
    assert output["last_object_clicked_tooltip"] == "VP-001"


def test_dashboard_init():
    dashboard = SapiDashboard()
    assert dashboard.query is not None


@patch("app.components.banner.st.info")
def test_demo_banner_names_localities_with_real_detection_evidence(mock_info: MagicMock) -> None:
    """El banner nombra comunas por evidencia real de detecciones, no por
    geometría de la grilla.

    Reemplaza test_demo_banner_only_names_localities_the_grid_covers, que
    verificaba que una coordenada cayera dentro del bounding box de la
    grilla ancha — y por eso institucionalizó nombrar Villa Alemana ahí sin
    ninguna detección real verificada en ese momento (hallazgo 05-09-2026).

    La contención espacial estricta de las 348 detecciones NASA FIRMS del
    2024-02-03 (app/data/incendio_2024-02-03.csv) contra las 50 celdas de la
    grilla ancha, seguida del point-in-polygon oficial contra el shapefile
    DPA 2023 (SUBDERE), da esta distribución real: Viña del Mar 120 focos,
    Quilpué 89, Valparaíso 32, Limache 17, Villa Alemana 5 — las cinco con
    evidencia real, ninguna en cero. El test es simétrico: falla si falta
    nombrar una comuna con evidencia real, y falla igual si aparece nombrada
    una sin ninguna.
    """
    from app.components.banner import render_demo_scope_banner

    focos_reales_por_comuna = {
        "Viña del Mar": 120,
        "Quilpué": 89,
        "Valparaíso": 32,
        "Limache": 17,
        "Villa Alemana": 5,
    }
    comuna_sin_evidencia_real = "Concón"

    render_demo_scope_banner(date(2025, 2, 9), date(2025, 2, 15))
    texto = mock_info.call_args[0][0]

    for comuna in focos_reales_por_comuna:
        assert comuna in texto, f"El banner no nombra {comuna}, que sí tiene evidencia real"
    assert comuna_sin_evidencia_real not in texto, (
        f"El banner nombra {comuna_sin_evidencia_real} sin ninguna detección real verificada"
    )


@patch("app.components.banner.st.caption")
def test_render_risk_legend(mock_caption: MagicMock) -> None:
    """La leyenda de texto orienta geográficamente y no repite el semáforo."""
    from app.components.banner import render_risk_legend

    render_risk_legend()
    texto = mock_caption.call_args[0][0]
    assert "Viña del Mar" in texto
    assert "Quilpué" in texto


@patch("app.components.controls.st.metric")
@patch("app.components.controls.st.caption")
@patch("app.components.controls.st.markdown")
@patch("app.components.controls.st.sidebar")
def test_render_technical_details_expander_includes_ml_panel(
    mock_sidebar: MagicMock,
    mock_markdown: MagicMock,
    mock_caption: MagicMock,
    mock_metric: MagicMock,
) -> None:
    """El panel ML vive dentro del expander 'Detalles técnicos'."""
    from app.components.controls import render_technical_details_expander

    render_technical_details_expander(
        date(2025, 2, 9),
        date(2025, 2, 15),
        metrics={"xgboost": {"recall": 0.78, "auc_roc": 0.83}, "baseline": {"recall": 0.71}},
        app_build="demo-corredor-50cells-v9",
        query_version="exact-date-v1",
        recall_target=0.75,
    )

    mock_sidebar.expander.assert_called_once_with("Detalles técnicos")
    assert mock_metric.call_count == 3
    captions = [call.args[0] for call in mock_caption.call_args_list]
    assert any("Build" in c for c in captions)
    assert any("SAPI_DATA_MODE" in c for c in captions)


@patch("app.components.controls.st.metric")
@patch("app.components.controls.st.caption")
@patch("app.components.controls.st.markdown")
@patch("app.components.controls.st.sidebar")
def test_render_technical_details_expander_shows_dash_when_no_real_run(
    mock_sidebar: MagicMock,
    mock_markdown: MagicMock,
    mock_caption: MagicMock,
    mock_metric: MagicMock,
) -> None:
    """Sin corrida real, el panel debe mostrar '—' en vez de fabricar un número."""
    from app.components.controls import render_technical_details_expander

    render_technical_details_expander(
        date(2025, 2, 9),
        date(2025, 2, 15),
        metrics={"xgboost": {"recall": None, "auc_roc": None}, "baseline": {"recall": None}},
        app_build="demo-corredor-50cells-v9",
        query_version="exact-date-v1",
        recall_target=0.75,
    )

    assert mock_metric.call_count == 3
    displayed_values = [call.args[1] for call in mock_metric.call_args_list]
    assert displayed_values == ["—", "—", "—"]


@patch("app.components.controls.st.sidebar")
def test_pick_demo_date_uses_calendar_when_available(mock_sidebar: MagicMock) -> None:
    from app.components.controls import pick_demo_date

    available = [date(2025, 2, 9), date(2025, 2, 15)]
    mock_sidebar.selectbox.return_value = date(2025, 2, 9)
    mock_sidebar.date_input.return_value = date(2025, 2, 15)
    assert pick_demo_date(available, date(2025, 2, 9), date(2025, 2, 15)) == date(2025, 2, 15)


@patch("app.components.controls.st.sidebar")
def test_pick_demo_date_falls_back_to_slider(mock_sidebar: MagicMock) -> None:
    from app.components.controls import pick_demo_date

    available = [date(2025, 2, 9), date(2025, 2, 15)]
    mock_sidebar.selectbox.return_value = date(2025, 2, 9)
    mock_sidebar.date_input.return_value = date(2025, 2, 10)
    assert pick_demo_date(available, date(2025, 2, 9), date(2025, 2, 15)) == date(2025, 2, 9)
    mock_sidebar.caption.assert_called_once()


@patch("app.components.risk_map.cell_id_from_folium_output", return_value="VP-038")
def test_render_risk_map_returns_clicked_cell(mock_resolve: MagicMock) -> None:
    from app.components.risk_map import render_risk_map

    dashboard = MagicMock()
    dashboard.render_folium_map.return_value = {"last_object_clicked_tooltip": "VP-038"}
    gdf = gpd.GeoDataFrame(
        {"cell_id": ["VP-038"], "probabilidad": [0.9], "nivel_riesgo": ["alto"]},
        geometry=[box(-71.4, -33.0, -71.3, -32.9)],
        crs="EPSG:4326",
    )
    # Sin patch de st.caption: render_risk_map ya no imprime una propia (SAPI
    # compactación dashboard) — la caption con resolución vive en app.py.
    clicked = render_risk_map(dashboard, date(2025, 2, 15), gdf, {"VP-038"})
    assert clicked == "VP-038"
    mock_resolve.assert_called_once()


@patch("app.state.st")
def test_ensure_default_selection_shows_top_risk_ficha_on_initial_load(mock_st: MagicMock) -> None:
    """Al cargar sin selección previa, se preselecciona la celda de mayor riesgo."""
    from app.state import SESSION_CELL_KEY, ensure_default_selection
    from app.utils.cell_table import top_risk_cell

    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001", "VP-002", "VP-003"],
            "probabilidad": [0.20, 0.90, 0.55],
            "nivel_riesgo": ["bajo", "alto", "medio"],
            "regla_30_30_30": [0, 1, 0],
        },
        geometry=[
            box(-71.58, -33.05, -71.57, -33.04),
            box(-71.57, -33.05, -71.56, -33.04),
            box(-71.56, -33.05, -71.55, -33.04),
        ],
        crs="EPSG:4326",
    )
    mock_st.session_state = {}
    top_risk = top_risk_cell(gdf)

    ensure_default_selection(top_risk)

    selected_id = mock_st.session_state.get(SESSION_CELL_KEY)
    assert selected_id == "VP-002"

    selected_row = gdf.loc[gdf["cell_id"] == selected_id].iloc[0]
    assert selected_row["nivel_riesgo"] == "alto"


@patch("app.state.st")
def test_ensure_default_selection_noop_without_top_risk(mock_st: MagicMock) -> None:
    from app.state import SESSION_CELL_KEY, ensure_default_selection

    mock_st.session_state = {}
    ensure_default_selection(None)
    assert mock_st.session_state.get(SESSION_CELL_KEY) is None
    assert mock_st.session_state["_top_risk_preselected"] is True


@patch("app.state.st")
def test_ensure_default_selection_respects_explicit_click(mock_st: MagicMock) -> None:
    from app.state import SESSION_CELL_KEY, ensure_default_selection

    mock_st.session_state = {SESSION_CELL_KEY: "VP-007"}
    top_risk = {
        "cell_id": "VP-002",
        "zona": "Urbano",
        "nivel_riesgo": "alto",
        "probabilidad": 0.9,
        "regla_30_30_30": True,
    }

    ensure_default_selection(top_risk)

    assert mock_st.session_state[SESSION_CELL_KEY] == "VP-007"


@patch("app.state.st")
def test_ensure_default_selection_skips_after_limpiar(mock_st: MagicMock) -> None:
    from app.state import SESSION_CELL_KEY, ensure_default_selection

    mock_st.session_state = {SESSION_CELL_KEY: None, "_top_risk_preselected": True}
    top_risk = {
        "cell_id": "VP-002",
        "zona": "Urbano",
        "nivel_riesgo": "alto",
        "probabilidad": 0.9,
        "regla_30_30_30": True,
    }

    ensure_default_selection(top_risk)

    assert mock_st.session_state[SESSION_CELL_KEY] is None


def test_cached_date_range_from_demo_seed() -> None:
    from app.app import _cached_date_range

    _cached_date_range.clear()
    min_d, max_d = _cached_date_range()
    demo_dates = get_all_demo_dates()
    assert (min_d, max_d) == (demo_dates[0], demo_dates[-1])


def test_cached_available_dates_from_demo_seed() -> None:
    from app.app import _cached_available_dates

    _cached_available_dates.clear()
    dates = _cached_available_dates()
    assert len(dates) == 7
    assert dates == get_all_demo_dates()


def test_app_reexports_protected_banner_alias() -> None:
    """El alias con guion bajo sigue disponible para callers/tests legacy."""
    from app.app import _render_demo_scope_banner
    from app.components.banner import render_demo_scope_banner

    assert _render_demo_scope_banner is render_demo_scope_banner
