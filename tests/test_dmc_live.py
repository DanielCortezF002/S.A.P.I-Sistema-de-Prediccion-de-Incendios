"""Pruebas de la última observación DMC (Rodelillo, 330007) que muestra la interfaz.

Resolución D2 (F2, 30-10-2026): la interfaz ya no consulta la API de DMC; lee la última
ingesta del pipeline. Las pruebas del cliente HTTP retirado (éxito, timeout, error 500,
saneamiento de credenciales) se retiraron con ese código; las de frescura, panel y
ausencia de emojis se conservan sin cambios.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.data.dmc_live import DmcLiveSnapshot
from app.utils.dmc_live import (
    STATUS_CON_RETRASO,
    STATUS_DESACTUALIZADO,
    STATUS_NO_DISPONIBLE,
    STATUS_RECIENTE,
    _classify_freshness,
    observation_from_snapshot,
    reload_rodelillo_observation,
)

_NOW = datetime(2026, 10, 25, 15, 0, tzinfo=timezone.utc)


def _snapshot(momento: datetime | None, available: bool = True) -> DmcLiveSnapshot:
    return DmcLiveSnapshot(
        station_code="330007",
        station_label="DMC Rodelillo",
        momento=momento,
        temperatura=21.5 if available else None,
        humedad_relativa=55.0 if available else None,
        velocidad_viento_kmh=9.26 if available else None,
        direccion_viento_deg=180.0 if available else None,
        delta_temp=None,
        delta_humedad=None,
        delta_viento=None,
        source_path="data/raw/dmc_meteo_20261025.json" if available else None,
        available=available,
        detail="Sin archivo dmc_meteo_*.json en data/raw" if not available else "ok",
    )


def test_classify_freshness_thresholds() -> None:
    assert _classify_freshness(None) == STATUS_NO_DISPONIBLE
    assert _classify_freshness(0.5) == STATUS_RECIENTE
    assert _classify_freshness(2.0) == STATUS_RECIENTE
    assert _classify_freshness(2.1) == STATUS_CON_RETRASO
    assert _classify_freshness(6.0) == STATUS_CON_RETRASO
    assert _classify_freshness(6.1) == STATUS_DESACTUALIZADO
    assert _classify_freshness(24.0) == STATUS_DESACTUALIZADO


def test_observation_from_recent_snapshot() -> None:
    """La observación ingerida hace 1 h se muestra como RECIENTE, con hora UTC y Chile."""
    obs = observation_from_snapshot(
        _snapshot(datetime(2026, 10, 25, 14, 0)), now_utc=_NOW
    )
    assert obs["ok"] is True
    assert obs["status"] == STATUS_RECIENTE
    assert obs["age_hours"] == 1.0
    assert obs["temperatura_c"] == 21.5
    assert obs["humedad_pct"] == 55.0
    assert obs["viento_kmh"] == 9.3
    assert obs["viento_kt"] == 5.0
    assert obs["momento_utc"] == "25-10-2026 14:00 UTC"
    assert obs["momento_cl"].startswith("25-10-2026 11:00")
    assert obs["fuente"].startswith("Última ingesta del pipeline")


def test_observation_freshness_follows_ingested_timestamp() -> None:
    delayed = observation_from_snapshot(
        _snapshot(_NOW.replace(tzinfo=None) - timedelta(hours=4)), now_utc=_NOW
    )
    outdated = observation_from_snapshot(
        _snapshot(_NOW.replace(tzinfo=None) - timedelta(hours=30)), now_utc=_NOW
    )
    assert delayed["status"] == STATUS_CON_RETRASO
    assert outdated["status"] == STATUS_DESACTUALIZADO


def test_observation_without_ingested_file_is_not_available() -> None:
    """Sin ingesta en data/raw el estado es NO DISPONIBLE y se explica el motivo."""
    obs = observation_from_snapshot(_snapshot(None, available=False), now_utc=_NOW)
    assert obs["ok"] is False
    assert obs["status"] == STATUS_NO_DISPONIBLE
    assert obs["temperatura_c"] is None
    assert "data/raw" in obs["error"]


def test_reload_rereads_ingested_file() -> None:
    with patch("app.utils.dmc_live.load_rodelillo_snapshot") as mock_load:
        mock_load.return_value = _snapshot(datetime(2026, 10, 25, 14, 0))
        obs = reload_rodelillo_observation()
        mock_load.cache_clear.assert_called_once()
        assert obs["ok"] is True


def test_dmc_live_module_has_no_network_client() -> None:
    """D2: el módulo que alimenta la interfaz no importa clientes HTTP."""
    source = Path("app/utils/dmc_live.py").read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & {
        "requests",
        "httpx",
        "aiohttp",
        "urllib.request",
        "http.client",
    }


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
        r"[\U00010000-\U0010ffff]|[☀-➿]|[⌀-⏿]|[⭐-⭕]|[‼-⁉]",
        code,
    )
    assert emojis == [], f"Se encontraron emojis en ranking_backend_view.py: {emojis}"
