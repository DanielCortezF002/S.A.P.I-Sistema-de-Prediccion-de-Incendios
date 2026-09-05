"""Pruebas de la tarjeta de clima en vivo DMC (Rodelillo, 330007)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from app.utils.dmc_live import fetch_rodelillo_live

# Respuesta real (forma verificada 05-09-2026 contra la API de DMC en vivo,
# valores recortados a los campos que el parser usa).
_PAYLOAD_OK = {
    "datosEstaciones": {
        "estacion": {"codigoNacional": "330007", "nombreEstacion": "Rodelillo, Ad."},
        "datos": [
            {
                "momento": "2026-09-05 20:00:00",
                "temperatura": "22.1 °C",
                "humedadRelativa": "17 %",
                "fuerzaDelViento": "6.4 kt",
            },
            {
                "momento": "2026-09-05 19:00:00",
                "temperatura": "21.0 °C",
                "humedadRelativa": "19 %",
                "fuerzaDelViento": "5.0 kt",
            },
        ],
    }
}


def _fake_response(payload: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(f"{status_code} error")
    else:
        response.raise_for_status.side_effect = None
    return response


def test_fetch_rodelillo_live_success_returns_parsed_fields() -> None:
    """Con una respuesta 200 válida, devuelve los campos correctos ya parseados."""
    fetch_rodelillo_live.clear()
    with (
        patch("app.utils.dmc_live.DMC_USUARIO", "user_test"),
        patch("app.utils.dmc_live.DMC_TOKEN", "token_test"),
        patch("app.utils.dmc_live.requests.get", return_value=_fake_response(_PAYLOAD_OK)) as mock_get,
    ):
        resultado = fetch_rodelillo_live("330007")

    assert resultado["ok"] is True
    assert resultado["temperatura_c"] == 22.1
    assert resultado["humedad_pct"] == 17.0
    assert resultado["viento_kmh"] == round(6.4 * 1.852, 1)
    assert resultado["momento"] == "2026-09-05 20:00:00"
    # toma el primer registro (mas reciente), no el ultimo de la lista
    assert resultado["temperatura_c"] != 21.0

    called_url = mock_get.call_args.args[0]
    assert "getDatosRecientesEma/330007" in called_url
    assert mock_get.call_args.kwargs["timeout"] == 5


def test_fetch_rodelillo_live_handles_timeout_without_raising() -> None:
    """Ante timeout de red, no lanza — devuelve ok=False con mensaje claro."""
    fetch_rodelillo_live.clear()
    with (
        patch("app.utils.dmc_live.DMC_USUARIO", "user_test"),
        patch("app.utils.dmc_live.DMC_TOKEN", "token_test"),
        patch(
            "app.utils.dmc_live.requests.get",
            side_effect=requests.exceptions.Timeout("Conexión expirada"),
        ),
    ):
        resultado = fetch_rodelillo_live("330007")

    assert resultado["ok"] is False
    assert "5s" in resultado["error"] or "5" in resultado["error"]
    assert "checked_at" in resultado


def test_fetch_rodelillo_live_handles_server_error_without_raising() -> None:
    """Ante un 500 de DMC (raise_for_status), no lanza — degrada a ok=False."""
    fetch_rodelillo_live.clear()
    with (
        patch("app.utils.dmc_live.DMC_USUARIO", "user_test"),
        patch("app.utils.dmc_live.DMC_TOKEN", "token_test"),
        patch("app.utils.dmc_live.requests.get", return_value=_fake_response({}, status_code=500)),
    ):
        resultado = fetch_rodelillo_live("330007")

    assert resultado["ok"] is False
    assert "error" in resultado
    assert "checked_at" in resultado


def test_fetch_rodelillo_live_missing_credentials_degrades_without_network_call() -> None:
    """Sin DMC_USUARIO/DMC_TOKEN, no intenta la llamada de red."""
    fetch_rodelillo_live.clear()
    with (
        patch("app.utils.dmc_live.DMC_USUARIO", ""),
        patch("app.utils.dmc_live.DMC_TOKEN", ""),
        patch("app.utils.dmc_live.requests.get") as mock_get,
    ):
        resultado = fetch_rodelillo_live("330007")

    assert resultado["ok"] is False
    mock_get.assert_not_called()
