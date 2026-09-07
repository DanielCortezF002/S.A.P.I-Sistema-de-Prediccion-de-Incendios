"""Pruebas mínimas del prototipo local (iteración 'terminar el prototipo
funcional local de S.A.P.I.', 2026-09-07). No reabre la auditoría del
pipeline temporal — solo cubre el camino nuevo: modelo -> servicio de
inferencia -> contrato de datos para el dashboard."""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import pandas as pd
import pytest

from src.inference.prototype_service import (
    MODEL_PATH,
    PrototypeUnavailableError,
    score_current_grid,
)
from src.procesamiento.pipeline_validators import FORBIDDEN_LEGACY_REFERENCES, validate_pipeline_isolation

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = REPO_ROOT / "data" / "processed" / "temporal_dataset_h6.parquet"

pytestmark = pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason="models/prototype_model_d.pkl no existe — correr scripts/build_prototype_model.py primero",
)


def test_prototype_model_loads() -> None:
    payload = joblib.load(MODEL_PATH)
    assert "model" in payload and "metadata" in payload
    assert payload["metadata"]["status"] == "PROTOTYPE / EXPLORATORY"
    assert hasattr(payload["model"], "predict_proba")


def test_feature_contract_matches_model() -> None:
    """Las columnas que el metadata declara deben ser EXACTAMENTE las que
    el modelo entrenado espera (mismo orden no es obligatorio, mismo
    conjunto sí) — si diverge, la inferencia rompería en silencio con
    columnas desalineadas."""
    payload = joblib.load(MODEL_PATH)
    model = payload["model"]
    declared = set(payload["metadata"]["feature_columns"])
    if hasattr(model, "feature_names_in_"):
        assert set(model.feature_names_in_) == declared


def test_inference_returns_fifty_cells() -> None:
    result = score_current_grid()
    assert len(result.cells) == 50
    assert len({c.cell_id for c in result.cells}) == 50


def test_ranks_are_one_to_n() -> None:
    result = score_current_grid()
    ranks = sorted(c.rank for c in result.cells)
    assert ranks == list(range(1, len(result.cells) + 1))
    # El orden de la lista ya debe venir por rank ascendente (rank 1 primero).
    assert [c.rank for c in result.cells] == ranks


def test_scores_are_finite() -> None:
    result = score_current_grid()
    for c in result.cells:
        assert math.isfinite(c.score)
        assert 0.0 <= c.score <= 1.0


def test_no_future_timestamps() -> None:
    """El forecast_time y el weather_timestamp devueltos nunca pueden ser
    posteriores al momento actual real — el servicio no inventa clima
    futuro, y forecast_time=None usa la última lectura real disponible."""
    result = score_current_grid()
    now = pd.Timestamp.now(tz="UTC")
    assert result.forecast_time <= now
    assert result.weather_timestamp <= now
    assert result.weather_timestamp <= result.forecast_time or (
        # meteo_actual_momento puede coincidir exactamente con forecast_time
        result.weather_timestamp == result.forecast_time
    )


def test_requesting_a_forecast_time_beyond_real_data_fails_explicitly() -> None:
    """No debe inventar meteorología futura: pedir un T muy posterior a la
    última lectura real debe fallar con un mensaje explicable, no con datos
    fabricados ni un stacktrace genérico."""
    with pytest.raises(PrototypeUnavailableError, match="no inventa"):
        score_current_grid(forecast_time="2099-01-01")


def test_dashboard_service_handles_missing_model_artifact(tmp_path, monkeypatch) -> None:
    import src.inference.prototype_service as svc

    monkeypatch.setattr(svc, "MODEL_PATH", tmp_path / "no_existe.pkl")
    with pytest.raises(PrototypeUnavailableError, match="build_prototype_model"):
        svc.score_current_grid()


def test_no_legacy_imports_in_prototype_modules() -> None:
    """Sección 2 de la iteración: el prototipo no puede importar nada del
    pipeline legacy (ignicion, xgboost, matriz_features/dataset_valparaiso,
    demo_seed)."""
    files = [
        REPO_ROOT / "src" / "inference" / "prototype_service.py",
        REPO_ROOT / "scripts" / "build_prototype_model.py",
    ]
    result = validate_pipeline_isolation(files, forbidden=FORBIDDEN_LEGACY_REFERENCES)
    assert result.status == "PASS", result.detail
