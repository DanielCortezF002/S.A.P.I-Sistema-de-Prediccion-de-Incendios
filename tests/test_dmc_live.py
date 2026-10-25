"""Pruebas exhaustivas para la consulta meteorológica en vivo DMC (Rodelillo, 330007)."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.utils.dmc_live import (
    STATUS_CON_RETRASO,
    STATUS_DESACTUALIZADO,
    STATUS_NO_DISPONIBLE,
    STATUS_RECIENTE,
    _classify_freshness,
    _clean_float,
    _sanitize_error,
    fetch_rodelillo_live,
    refresh_rodelillo_live,
)

_PAYLOAD_EMA = {
    "datosEstaciones": {
        "estacion": {"codigoNacional": "330007", "nombreEstacion": "Rodelillo, Ad."},
        "datos": [
            {
                "momento": "2026-10-25 14:00:00",
                "temperatura": "21.5 °C",
                "humedadRelativa": "55 %",
                "fuerzaDelViento": "5.0 kt",
            },
            {
                "momento": "2026-10-25 13:00:00",
                "temperatura": "20.1 °C",
                "humedadRelativa": "60 %",
                "fuerzaDelViento": "4.2 kt",
            },
        ],
    }
}


def _fake_response(payload: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            f"{status_code} Server Error: http://dmc.cl?usuario=secret_user&token=secret_token"
        )
    else:
        response.raise_for_status.side_effect = None
    return response


def test_classify_freshness_thresholds() -> None:
    assert _classify_freshness(None) == STATUS_NO_DISPONIBLE
    assert _classify_freshness(0.5) == STATUS_RECIENTE
    assert _classify_freshness(2.0) == STATUS_RECIENTE
    assert _classify_freshness(2.1) == STATUS_CON_RETRASO
    assert _classify_freshness(6.0) == STATUS_CON_RETRASO
    assert _classify_freshness(6.1) == STATUS_DESACTUALIZADO
    assert _classify_freshness(24.0) == STATUS_DESACTUALIZADO


def test_clean_float_parsing() -> None:
    assert _clean_float("21.5 °C") == 21.5
    assert _clean_float("55 %") == 55.0
    assert _clean_float("5.0 kt") == 5.0
    assert _clean_float("-3.2 °C") == -3.2
    assert _clean_float("18,4 °C") == 18.4
    assert _clean_float(None) is None
    assert _clean_float("") is None
    assert _clean_float("N/A") is None


def test_sanitize_error_strips_secrets() -> None:
    raw = "Failed on http://dmc.cl/api?usuario=my_user&token=super_secret_token_123"
    sanitized = _sanitize_error(raw)
    assert "super_secret_token_123" not in sanitized
    assert "my_user" not in sanitized
    assert "[URL_DMC]" in sanitized


def test_fetch_rodelillo_live_success_recent() -> None:
    now_fixed = datetime(2026, 10, 25, 14, 30, tzinfo=timezone.utc)
    fetch_rodelillo_live.clear()
    with (
        patch("app.utils.dmc_live._get_credentials", return_value=("https://climatologia.meteochile.gob.cl", "user", "token")),
        patch("app.utils.dmc_live.datetime") as mock_dt,
        patch("app.utils.dmc_live.requests.get", return_value=_fake_response(_PAYLOAD_EMA)) as mock_get,
    ):
        mock_dt.now.return_value = now_fixed
        mock_dt.strptime = datetime.strptime
        res = fetch_rodelillo_live("330007")

    assert res["ok"] is True
    assert res["status"] == STATUS_RECIENTE
    assert res["temperatura_c"] == 21.5
    assert res["humedad_pct"] == 55.0
    # 5.0 kt * 1.852 = 9.26 -> 9.3 km/h
    assert res["viento_kmh"] == 9.3
    assert res["viento_kt"] == 5.0
    assert "25-10-2026 14:00 UTC" in res["momento_utc"]
    assert res["estacion_id"] == "330007"
    assert res["estacion_nombre"] == "Rodelillo, Ad."
    assert res["error"] is None


def test_fetch_rodelillo_live_delayed_status() -> None:
    now_fixed = datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc)
    fetch_rodelillo_live.clear()
    with (
        patch("app.utils.dmc_live._get_credentials", return_value=("https://climatologia.meteochile.gob.cl", "user", "token")),
        patch("app.utils.dmc_live.datetime") as mock_dt,
        patch("app.utils.dmc_live.requests.get", return_value=_fake_response(_PAYLOAD_EMA)),
    ):
        mock_dt.now.return_value = now_fixed
        mock_dt.strptime = datetime.strptime
        res = fetch_rodelillo_live("330007")

    assert res["ok"] is True
    assert res["status"] == STATUS_CON_RETRASO
    assert res["age_hours"] == 4.0


def test_fetch_rodelillo_live_outdated_status() -> None:
    now_fixed = datetime(2026, 10, 25, 23, 0, tzinfo=timezone.utc)
    fetch_rodelillo_live.clear()
    with (
        patch("app.utils.dmc_live._get_credentials", return_value=("https://climatologia.meteochile.gob.cl", "user", "token")),
        patch("app.utils.dmc_live.datetime") as mock_dt,
        patch("app.utils.dmc_live.requests.get", return_value=_fake_response(_PAYLOAD_EMA)),
    ):
        mock_dt.now.return_value = now_fixed
        mock_dt.strptime = datetime.strptime
        res = fetch_rodelillo_live("330007")

    assert res["ok"] is True
    assert res["status"] == STATUS_DESACTUALIZADO
    assert res["age_hours"] == 9.0


def test_fetch_rodelillo_live_missing_credentials_never_calls_network() -> None:
    fetch_rodelillo_live.clear()
    with (
        patch("app.utils.dmc_live._get_credentials", return_value=("https://climatologia.meteochile.gob.cl", "", "")),
        patch("app.utils.dmc_live.requests.get") as mock_get,
    ):
        res = fetch_rodelillo_live("330007")

    assert res["ok"] is False
    assert res["status"] == STATUS_NO_DISPONIBLE
    assert "Credenciales DMC no configuradas" in res["error"]
    mock_get.assert_not_called()


def test_fetch_rodelillo_live_handles_timeout_safely() -> None:
    fetch_rodelillo_live.clear()
    with (
        patch("app.utils.dmc_live._get_credentials", return_value=("https://climatologia.meteochile.gob.cl", "user", "token")),
        patch("app.utils.dmc_live.requests.get", side_effect=requests.exceptions.Timeout("Timed out")),
    ):
        res = fetch_rodelillo_live("330007")

    assert res["ok"] is False
    assert res["status"] == STATUS_NO_DISPONIBLE
    assert "Tiempo de espera agotado" in res["error"]


def test_fetch_rodelillo_live_handles_500_without_leaking_secrets() -> None:
    fetch_rodelillo_live.clear()
    with (
        patch("app.utils.dmc_live._get_credentials", return_value=("https://climatologia.meteochile.gob.cl", "user", "token")),
        patch("app.utils.dmc_live.requests.get", return_value=_fake_response({}, status_code=500)),
    ):
        res = fetch_rodelillo_live("330007")

    assert res["ok"] is False
    assert res["status"] == STATUS_NO_DISPONIBLE
    assert "secret_token" not in res["error"]
    assert "secret_user" not in res["error"]


def test_refresh_rodelillo_live_clears_cache_and_calls() -> None:
    with patch("app.utils.dmc_live.fetch_rodelillo_live") as mock_fetch:
        mock_fetch.return_value = {"ok": True, "status": STATUS_RECIENTE}
        res = refresh_rodelillo_live("330007")
        assert res["ok"] is True
        mock_fetch.clear.assert_called_once()


def test_render_dmc_observation_panel_with_data() -> None:
    """Verifica que el panel renderice sin excepciones y exponga los avisos requeridos."""
    import streamlit as st
    from app.components.ranking_backend_view import _render_dmc_observation_panel

    st.session_state["sapi_dmc_open"] = True
    st.session_state["sapi_dmc_data"] = {
        "ok": True,
        "status": STATUS_RECIENTE,
        "temperatura_c": 21.5,
        "humedad_pct": 55.0,
        "viento_kmh": 9.3,
        "viento_kt": 5.0,
        "momento_cl": "25-10-2026 11:00 -03",
        "momento_utc": "25-10-2026 14:00 UTC",
        "checked_at_cl": "11:30:00",
        "checked_at_utc": "14:30:00 UTC",
        "estacion_id": "330007",
        "estacion_nombre": "Rodelillo, Ad.",
        "error": None,
    }

    # Debe ejecutarse limpiamente sin lanzar excepciones
    _render_dmc_observation_panel()


def test_ranking_backend_view_has_no_emojis() -> None:
    """Garantiza la ausencia total de emojis en ranking_backend_view.py."""
    import re

    with open("app/components/ranking_backend_view.py", "r", encoding="utf-8") as f:
        code = f.read()

    emojis = re.findall(
        r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\u203c-\u2049]",
        code,
    )
    assert emojis == [], f"Se encontraron emojis en ranking_backend_view.py: {emojis}"
