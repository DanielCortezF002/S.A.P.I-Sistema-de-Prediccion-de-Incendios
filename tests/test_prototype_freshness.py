"""Pruebas del indicador de frescura de la meteorología (corrección UX/
semántica, 2026-09-07): `forecast_time=None` correctamente no inventa
clima futuro, pero la UI no puede insinuar que un ranking calculado sobre
una lectura de hace varios días es un pronóstico vigente de "las próximas
6 horas de hoy". Cubre solo esto — no reabre la auditoría del pipeline
temporal.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.inference.prototype_service import (
    FRESHNESS_DELAYED,
    FRESHNESS_HISTORICAL,
    FRESHNESS_RECENT,
    GridScoreResult,
    classify_freshness,
)


def _fake_result(freshness: str, age_hours: float) -> GridScoreResult:
    forecast_time = pd.Timestamp("2026-09-07 12:00:00", tz="UTC")
    weather_ts = forecast_time - pd.Timedelta(hours=age_hours)
    return GridScoreResult(
        forecast_time=forecast_time,
        horizon_hours=6,
        station_id="330007",
        station_name="Rodelillo",
        weather_timestamp=weather_ts,
        age_hours=age_hours,
        freshness=freshness,
        model_version="prototype_model_d_v1",
        model_status="PROTOTYPE / EXPLORATORY",
        meteo_actual={
            "temperatura": 20.0,
            "humedad_relativa": 50.0,
            "velocidad_viento_kmh": 5.0,
            "regla_30_30_30": False,
            "momento_observacion": weather_ts,
        },
        cells=[],
    )


def _markdown_blob(mock_st: MagicMock) -> str:
    return "\n".join(
        str(call.args[0]) for call in mock_st.markdown.call_args_list if call.args
    )


def _mock_expander(mock_st: MagicMock) -> None:
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    mock_st.expander.return_value = ctx


# ---- clasificación de freshness (pura, sin Streamlit) ----


def test_freshness_recent_up_to_twelve_hours() -> None:
    assert classify_freshness(0.0) == FRESHNESS_RECENT
    assert classify_freshness(6.0) == FRESHNESS_RECENT
    assert classify_freshness(12.0) == FRESHNESS_RECENT


def test_freshness_delayed_between_twelve_and_twentyfour_hours() -> None:
    assert classify_freshness(12.01) == FRESHNESS_DELAYED
    assert classify_freshness(18.0) == FRESHNESS_DELAYED
    assert classify_freshness(24.0) == FRESHNESS_DELAYED


def test_freshness_historical_beyond_twentyfour_hours() -> None:
    assert classify_freshness(24.01) == FRESHNESS_HISTORICAL
    assert classify_freshness(156.9) == FRESHNESS_HISTORICAL  # caso real observado 2026-09-07
    assert classify_freshness(10_000.0) == FRESHNESS_HISTORICAL


# ---- banner de datos históricos (solo debe aparecer con freshness=HISTORICAL) ----


@patch("app.components.prototype_view.st")
def test_stale_banner_appears_only_when_historical(mock_st: MagicMock) -> None:
    from app.components.prototype_view import _render_stale_data_banner

    _render_stale_data_banner(_fake_result(FRESHNESS_RECENT, 1.0))
    mock_st.warning.assert_not_called()

    _render_stale_data_banner(_fake_result(FRESHNESS_DELAYED, 18.0))
    mock_st.warning.assert_not_called()

    _render_stale_data_banner(_fake_result(FRESHNESS_HISTORICAL, 150.0))
    mock_st.warning.assert_called_once()
    banner_text = mock_st.warning.call_args[0][0]
    assert "DATOS HIST" in banner_text
    assert "NO representa el riesgo actual" in banner_text


@patch("app.components.prototype_view.st")
def test_stale_banner_shows_the_real_weather_timestamp(mock_st: MagicMock) -> None:
    """El timestamp ISO de la observación queda en Información técnica,
    no en el warning compacto del cuerpo principal."""
    from app.components.prototype_view import (
        _render_stale_data_banner,
        _render_tech_expander,
    )

    result = _fake_result(FRESHNESS_HISTORICAL, 150.0)
    _render_stale_data_banner(result)
    banner_text = mock_st.warning.call_args[0][0]
    assert f"{result.age_hours:.0f} h" in banner_text
    assert result.weather_timestamp.strftime("%d/%m/%Y %H:%M") not in banner_text

    _mock_expander(mock_st)
    _render_tech_expander(result)
    tech_text = _markdown_blob(mock_st)
    assert str(result.weather_timestamp) in tech_text
    assert "Forecast time:" in tech_text
    assert "Ventana evaluada:" in tech_text


# ---- nunca etiquetar como "actual" una inferencia >24h antigua ----


@patch("app.components.prototype_view.st")
def test_header_never_labels_a_stale_inference_as_proximas_horas(mock_st: MagicMock) -> None:
    """Con freshness != RECIENTE el header usa la ventana humana T → T+h,
    nunca "próximas N horas" ni timestamps ISO en el cuerpo principal."""
    from app.components.prototype_view import _render_header

    _render_header(_fake_result(FRESHNESS_HISTORICAL, 150.0))
    header_text = _markdown_blob(mock_st)
    assert "próximas" not in header_text.lower()
    assert "Forecast time:" not in header_text
    assert "Ventana evaluada:" not in header_text
    assert "12:00 → 18:00 UTC" in header_text
    assert "DATOS HISTÓRICOS / DESACTUALIZADOS" not in header_text
    assert header_text.count("DATOS HISTÓRICOS") == 1
    assert "PROTOTIPO EXPLORATORIO" in header_text


@patch("app.components.prototype_view.st")
def test_header_never_labels_delayed_data_as_proximas_horas(mock_st: MagicMock) -> None:
    from app.components.prototype_view import _render_header

    _render_header(_fake_result(FRESHNESS_DELAYED, 18.0))
    header_text = _markdown_blob(mock_st)
    assert "próximas" not in header_text.lower()
    assert "Forecast time:" not in header_text
    assert "Ventana evaluada:" not in header_text
    assert "12:00 → 18:00 UTC" in header_text
    assert "DATOS HISTÓRICOS" not in header_text


@patch("app.components.prototype_view.st")
def test_header_uses_human_window_when_data_is_recent(mock_st: MagicMock) -> None:
    from app.components.prototype_view import _render_header

    _render_header(_fake_result(FRESHNESS_RECENT, 1.0))
    header_text = _markdown_blob(mock_st)
    assert "Forecast time:" not in header_text
    assert "12:00 → 18:00 UTC" in header_text
    assert "DMC Rodelillo · 330007" in header_text
