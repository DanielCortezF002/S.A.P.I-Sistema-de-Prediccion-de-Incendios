"""Pruebas de `src.procesamiento.row_explainer` (sección 21 de la
auditoría 06-09-2026)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest

from src.procesamiento.row_explainer import RowNotFoundError, explain_row

T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")


def _fixture_row(**overrides) -> pd.DataFrame:
    base = {
        "cell_id": "VP-001",
        "forecast_time": T,
        "target_window_start": T,
        "target_window_end": T + pd.Timedelta(hours=6),
        "target": 1.0,
        "target_event_id": 42.0,
        "target_timestamp": T + pd.Timedelta(hours=2),
        "excluded": False,
        "excluded_reason": None,
        "meteo_actual_momento": T,
        "meteo_actual_delta_minutos": 0.0,
        "meteo_actual_missing": False,
        "meteo_actual_temp": 28.0,
        "meteo_actual_hr": 25.0,
        "meteo_actual_viento": 35.0,
        "meteo_actual_regla_30_30_30": 0,
        "meteo_age_hours": 0.0,
        "historial_firms_count": 2,
        "dias_desde_ultimo_evento": 5.0,
        "dias_desde_ultimo_evento_missing": False,
        "historial_ultimo_evento_momento": T - pd.Timedelta(days=5),
        "elevacion": 350.0,
        "pendiente": 12.0,
        "orientacion": 180.0,
        "dem_disponible": True,
        "eligible_for_training": True,
    }
    for h in (6, 12, 24, 48):
        base[f"meteo_lag_{h}h_momento"] = T - pd.Timedelta(hours=h)
        base[f"meteo_lag_{h}h_missing"] = False
        base[f"meteo_lag_{h}h_temp"] = 27.0
        base[f"meteo_lag_{h}h_hr"] = 26.0
        base[f"meteo_lag_{h}h_viento"] = 33.0
        base[f"meteo_lag_{h}h_regla_30_30_30"] = 0
    base.update(overrides)
    return pd.DataFrame([base])


def test_explains_a_positive_row_fully() -> None:
    ds = _fixture_row()
    result = explain_row(ds, "VP-001", T)
    assert result["target"]["target"] == 1
    assert result["target"]["target_event_id"] == 42
    assert result["target"]["target_timestamp"] == T + pd.Timedelta(hours=2)
    assert result["meteo_actual"]["temp"] == 28.0
    assert result["historial_firms"]["dias_desde_ultimo_evento"] == 5.0
    assert result["topografia"]["elevacion"] == 350.0


def test_explains_an_excluded_row_with_none_target() -> None:
    ds = _fixture_row(
        target=float("nan"), target_event_id=float("nan"), target_timestamp=pd.NaT,
        excluded=True, excluded_reason="cooldown_evento_activo", eligible_for_training=False,
    )
    result = explain_row(ds, "VP-001", T)
    assert result["target"]["target"] is None
    assert result["target"]["excluded"] is True
    assert result["target"]["excluded_reason"] == "cooldown_evento_activo"
    assert result["target"]["target_event_id"] is None


def test_raises_row_not_found_instead_of_returning_none() -> None:
    ds = _fixture_row()
    with pytest.raises(RowNotFoundError):
        explain_row(ds, "VP-999", T)


def test_raises_assertion_on_duplicate_key() -> None:
    ds = pd.concat([_fixture_row(), _fixture_row()], ignore_index=True)
    with pytest.raises(AssertionError):
        explain_row(ds, "VP-001", T)


def test_demonstrates_against_the_real_dataset_megaevento_row() -> None:
    """Auditoría 06-09-2026: demostración real, no solo con fixtures —
    explica una fila real del megaevento de 2024-02-03."""
    repo_root = Path(__file__).resolve().parent.parent
    parquet_path = repo_root / "data" / "processed" / "temporal_dataset_h6.parquet"
    if not parquet_path.exists():
        pytest.skip("temporal_dataset_h6 no generado en este entorno")
    ds = pd.read_parquet(parquet_path)
    positives = ds[ds["target"] == 1]
    row = positives.iloc[0]
    result = explain_row(ds, row["cell_id"], row["forecast_time"])
    assert result["target"]["target"] == 1
    assert result["target"]["target_event_id"] == int(row["target_event_id"])
