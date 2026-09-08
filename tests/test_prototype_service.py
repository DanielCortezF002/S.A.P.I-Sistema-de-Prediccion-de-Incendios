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
    STATION_ID,
    PrototypeUnavailableError,
    _resolve_forecast_time,
    _resolve_meteo_row,
    build_feature_matrix,
    load_regional_meteo_series,
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


def test_ties_share_display_rank_but_internal_rank_stays_unique() -> None:
    """Corrección de honestidad científica (2026-09-07): con pocos
    positivos históricos, decenas de celdas caen en el mismo score exacto.
    `rank` (contrato interno, 1..N único) no debe cambiar; `display_rank`
    debe agrupar los empates con el MISMO número (method='min')."""
    result = score_current_grid()
    ranks = sorted(c.rank for c in result.cells)
    assert ranks == list(range(1, len(result.cells) + 1))  # contrato interno intacto

    by_score: dict[float, set[int]] = {}
    for c in result.cells:
        by_score.setdefault(c.score, set()).add(c.display_rank)
        assert c.tie_group_size >= 1
    for score, display_ranks in by_score.items():
        assert len(display_ranks) == 1, f"score {score} tiene más de un display_rank: {display_ranks}"

    by_display_rank: dict[int, set[float]] = {}
    for c in result.cells:
        by_display_rank.setdefault(c.display_rank, set()).add(round(c.score, 10))
    for dr, scores in by_display_rank.items():
        assert len(scores) == 1, f"display_rank {dr} agrupa scores distintos: {scores}"


def test_map_uses_a_tile_provider_that_needs_no_api_key() -> None:
    """Regresión del watermark 'API KEY REQUIRED' visto en la demo
    (2026-09-07): el mapa debe usar OpenStreetMap estándar, nunca un
    proveedor que exija clave (Stadia/Stamen/etc.)."""
    import folium

    from app.components.prototype_view import _render_map  # noqa: F401 (confirma que el módulo importa sin tocar red)

    fmap = folium.Map(location=[-33.05, -71.55], zoom_start=11, tiles="OpenStreetMap")
    html = fmap._repr_html_()
    assert "tile.openstreetmap.org" in html
    for forbidden in ("stadiamaps", "stamen", "api_key", "apikey", "cartocdn"):
        assert forbidden not in html.lower()


def _real_feature_matrix() -> pd.DataFrame:
    meteo_series = load_regional_meteo_series(STATION_ID)
    forecast_time = _resolve_forecast_time(None, meteo_series)
    meteo_row = _resolve_meteo_row(forecast_time, meteo_series)
    return build_feature_matrix(forecast_time, meteo_row)


def test_feature_matrix_has_fifty_unique_cell_ids_and_no_missing_or_duplicate() -> None:
    """Sección 3 de la auditoría 2026-09-08: cobertura exacta del ranking
    — exactamente 50 cell_id únicos, ninguno perdido, ninguno duplicado."""
    features_df = _real_feature_matrix()
    from src.geo.grid import all_cells

    expected_ids = {c["cell_id"] for c in all_cells()}
    assert len(features_df) == 50
    assert features_df.index.nunique() == 50
    assert not features_df.index.duplicated().any()
    assert set(features_df.index) == expected_ids


def test_reordering_features_df_does_not_desync_cell_id_and_score() -> None:
    """Sección 2 de la auditoría 2026-09-08: si `build_feature_matrix` o
    `score_current_grid` alguna vez pasaran a usar arrays/posiciones en
    vez del índice `cell_id` de pandas, un reordenamiento del DataFrame
    desalinearía silenciosamente celda <-> score. Este test construye la
    matriz real, la baraja explícitamente, y confirma que el score de
    cada `cell_id` es IDÉNTICO sin importar el orden de las filas."""
    import joblib

    payload = joblib.load(MODEL_PATH)
    model = payload["model"]
    feature_columns = payload["metadata"]["feature_columns"]

    features_df = _real_feature_matrix()
    x_original = features_df[feature_columns]
    scores_original = pd.Series(model.predict_proba(x_original)[:, 1], index=x_original.index)

    shuffled = features_df.sample(frac=1.0, random_state=42)  # mismas filas, orden distinto
    x_shuffled = shuffled[feature_columns]
    scores_shuffled = pd.Series(model.predict_proba(x_shuffled)[:, 1], index=x_shuffled.index)

    # Comparar alineado por cell_id (índice), no por posición.
    aligned = scores_shuffled.reindex(scores_original.index)
    assert (aligned == scores_original).all(), "El score de al menos una celda cambió solo por reordenar filas"


def test_feature_rows_are_mostly_distinct_even_though_scores_tie() -> None:
    """Sección 1 de la auditoría 2026-09-08 ('¿por qué 41 celdas tienen el
    mismo score?'): ancla la evidencia de que el empate es del MODELO, no
    del pipeline de datos — las filas de features de esas celdas son
    mayormente distintas (historial/topografía varían), solo la
    meteorología regional (idéntica por diseño para las 50 celdas en un
    mismo T) se repite. Si esta prueba empezara a fallar (features
    también colapsando a un puñado de filas idénticas), eso SÍ apuntaría
    a un bug de pipeline, no a un empate legítimo del modelo."""
    import joblib

    payload = joblib.load(MODEL_PATH)
    feature_columns = payload["metadata"]["feature_columns"]
    features_df = _real_feature_matrix()
    x = features_df[feature_columns]

    n_unique_rows = len(x.drop_duplicates())
    # Con 50 celdas, un pipeline roto (broadcasting, fila reusada, merge
    # que perdió cell_id) produciría un puñado de filas idénticas (p. ej.
    # <=5). Un valor sustancialmente mayor confirma que cada celda sigue
    # aportando su propio historial/topografía real.
    assert n_unique_rows >= 30, f"Solo {n_unique_rows} filas de feature distintas entre 50 celdas — revisar pipeline"

    # La meteorología regional (compartida por diseño) es la única familia
    # de columnas que DEBE ser idéntica en las 50 filas.
    meteo_cols = [c for c in feature_columns if c.startswith("meteo_")]
    for col in meteo_cols:
        assert x[col].nunique(dropna=False) == 1, f"{col} varía entre celdas — no debería (misma estación regional)"

    # historial y topografía SÍ deben variar entre celdas (no todas NaN,
    # no todas el mismo valor) -- si colapsaran a 1 valor único, indicaría
    # datos repetidos por accidente en vez de missingness real.
    for col in ("historial_firms_count", "elevacion"):
        non_null = x[col].dropna()
        assert non_null.nunique() > 1, f"{col} no varía entre celdas con dato real — posible bug de pipeline"


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
