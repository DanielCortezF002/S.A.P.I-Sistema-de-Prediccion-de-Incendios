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
import numpy
import pandas as pd
import pytest
import sklearn

from src.inference.prototype_service import (
    MODEL_PATH,
    REPRODUCIBILITY_FIRMS_CSV,
    REPRODUCIBILITY_TOPO_CSV,
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
_DMC_RAW_GLOB = f"dmc_historico_{STATION_ID}_*.json"
_HAS_RECENT_METEO = any((REPO_ROOT / "data" / "raw").glob(_DMC_RAW_GLOB))

# Auditoria 09-09-2026: models/prototype_model_d.pkl esta versionado en git
# desde esta fecha, pero score_current_grid() ADEMAS necesita meteorologia
# reciente real en data/raw/ (no versionada -- ver docs/deploy.md,
# "Reproducibilidad de datos y modelo"). Sin este segundo skip, un clon
# limpio con el modelo pero sin data/raw/ pasa de "10 tests saltados
# limpiamente" a "9 tests fallando con PrototypeUnavailableError" -- mismo
# artefacto faltante, peor experiencia de CI. Los 2 tests que solo cargan
# el modelo directamente (sin llamar score_current_grid) SI corren siempre
# que el .pkl exista.
pytestmark = pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason="models/prototype_model_d.pkl no existe — correr scripts/build_prototype_model.py primero",
)
_needs_recent_meteo = pytest.mark.skipif(
    not _HAS_RECENT_METEO,
    reason=(
        f"No hay {_DMC_RAW_GLOB} en data/raw/ — score_current_grid() necesita "
        "meteorologia reciente ademas del modelo (ver docs/deploy.md, "
        "seccion 'Reproducibilidad de datos y modelo')"
    ),
)


def test_prototype_model_loads() -> None:
    payload = joblib.load(MODEL_PATH)
    assert "model" in payload and "metadata" in payload
    assert payload["metadata"]["status"] == "PROTOTYPE / EXPLORATORY"
    assert hasattr(payload["model"], "predict_proba")


def test_environment_matches_training_environment_declared_in_metadata() -> None:
    """Guarda de reproducibilidad (migracion 09-09-2026, ver docs/deploy.md,
    seccion CURRENT). `models/prototype_model_d.pkl` es un
    HistGradientBoostingClassifier serializado con joblib: su estado interno
    incluye objetos de numpy/scikit-learn cuyo formato de pickle NO es
    compatible entre versiones mayores -- deserializarlo con un numpy/
    scikit-learn distinto al que lo entreno falla con un `ValueError` de
    numpy poco explicable (`PCG64 is not a known BitGenerator module`), no
    con un mensaje que apunte a la causa real. Esta prueba detecta la causa
    real ANTES de intentar cargar el modelo, con un mensaje explicable.

    Si este test falla: el entorno actual no coincide con el que entreno el
    artefacto commiteado. La correccion NO es "arreglar el test" -- es (a)
    instalar exactamente las versiones de
    `metadata["training_environment"]`, o (b) si se migra deliberadamente de
    version, regenerar el artefacto con
    `python scripts/build_prototype_model.py` en el nuevo entorno y
    actualizar `requirements.txt`/`requirements-dev.txt` de forma consistente
    (ver docs/deploy.md).
    """
    metadata = joblib.load(MODEL_PATH)["metadata"]
    declared = metadata.get("training_environment")
    if declared is None:
        pytest.skip(
            "El modelo commiteado no tiene 'training_environment' en su metadata "
            "(artefacto anterior a la migracion 09-09-2026) -- no hay contra que comparar."
        )

    actual = {
        "numpy_version": numpy.__version__,
        "scikit_learn_version": sklearn.__version__,
        "joblib_version": joblib.__version__,
    }
    mismatches = {
        key: (declared[key], actual[key]) for key in actual if declared[key] != actual[key]
    }
    assert not mismatches, (
        "El entorno actual no coincide con el que entreno "
        f"{MODEL_PATH.name} (declarado en su metadata):\n"
        + "\n".join(
            f"  {k}: declarado={v[0]!r} actual={v[1]!r}" for k, v in mismatches.items()
        )
        + "\nEsto puede hacer que las predicciones difieran del artefacto publicado, o "
        "que joblib.load() falle directamente. Ver docs/deploy.md, seccion CURRENT."
    )


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


@_needs_recent_meteo
def test_inference_returns_fifty_cells() -> None:
    result = score_current_grid()
    assert len(result.cells) == 50
    assert len({c.cell_id for c in result.cells}) == 50


@_needs_recent_meteo
def test_ranks_are_one_to_n() -> None:
    result = score_current_grid()
    ranks = sorted(c.rank for c in result.cells)
    assert ranks == list(range(1, len(result.cells) + 1))
    # El orden de la lista ya debe venir por rank ascendente (rank 1 primero).
    assert [c.rank for c in result.cells] == ranks


@_needs_recent_meteo
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


@_needs_recent_meteo
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


@_needs_recent_meteo
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


@_needs_recent_meteo
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


@_needs_recent_meteo
def test_scores_are_finite() -> None:
    result = score_current_grid()
    for c in result.cells:
        assert math.isfinite(c.score)
        assert 0.0 <= c.score <= 1.0


@_needs_recent_meteo
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


@_needs_recent_meteo
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


# El test activa SAPI_REPRODUCIBILITY_MODE=1, que usa los SNAPSHOTS
# CONGELADOS (artifacts/hito1/reproducibility/{firms,dem}/), no
# data/processed/ operacional -- la condicion de skip debe verificar
# exactamente lo que el test realmente usa, o quedaria saltandose incluso
# en un clon limpio que YA tiene los snapshots versionados (bug real
# encontrado 09-09-2026 al probar esto en un clon limpio real).
_REPRODUCIBILITY_SNAPSHOTS_AVAILABLE = (
    REPRODUCIBILITY_FIRMS_CSV.exists() and REPRODUCIBILITY_TOPO_CSV.exists()
)


@pytest.mark.skipif(
    not _REPRODUCIBILITY_SNAPSHOTS_AVAILABLE,
    reason=(
        "Requiere artifacts/hito1/reproducibility/firms/*.csv y "
        "artifacts/hito1/reproducibility/dem/grid_topography.csv "
        "versionados (ver docs/deploy.md 'MODO HITO 1 REPRODUCIBLE')."
    ),
)
def test_reproducibility_mode_works_fully_offline(monkeypatch) -> None:
    """Auditoria 09-09-2026 (cierre de R3): con SAPI_REPRODUCIBILITY_MODE=1,
    el Modelo D versionado + el snapshot DMC versionado
    (artifacts/hito1/reproducibility/dmc/) deben reproducir el ranking
    oficial del Hito 1 SIN ninguna llamada de red -- ni para DMC (usa el
    snapshot, no data/raw/ ni la API en vivo) ni para ningun otro
    proposito. Si `score_current_grid()` alguna vez intentara abrir un
    socket, este test debe fallar de forma ruidosa, no silenciarlo."""
    import socket

    def _blocked_connect(*_args, **_kwargs):
        raise AssertionError(
            "score_current_grid() intento una conexion de red durante el modo "
            "de reproducibilidad offline -- esto no deberia depender de Internet."
        )

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "1")

    result = score_current_grid()

    # Invariantes oficiales del artefacto congelado -- ninguno hardcodeado
    # arbitrariamente: son exactamente los valores ya verificados y
    # documentados en artifacts/hito1/reproducibility/manifest.json contra
    # el modelo/dataset oficiales (41/50 empatadas, top VP-001).
    assert len(result.cells) == 50
    assert len({c.cell_id for c in result.cells}) == 50
    assert str(result.forecast_time) == "2026-09-01 00:00:00+00:00"
    assert result.cells[0].cell_id == "VP-001"
    assert result.cells[0].score == pytest.approx(0.13129336874795144, rel=1e-9)
    tie_sizes = sorted((c.tie_group_size for c in result.cells), reverse=True)
    # tie_group_size se repite por celda dentro del mismo grupo; el conjunto
    # de tamaños de grupo unicos debe contener 41 (el grupo dominante real).
    assert 41 in set(tie_sizes)
    # La frescura debe seguir siendo honesta: el snapshot es de 2026-09,
    # muy anterior a "hoy" en cualquier corrida futura de este test -- debe
    # clasificarse como historico, nunca como "reciente".
    assert "HIST" in result.freshness.upper()


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
