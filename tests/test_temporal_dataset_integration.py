"""Pruebas de integración sobre el dataset temporal REAL (si el artefacto
existe — se salta si nadie corrió `build_temporal_dataset.py` todavía, para
no romper CI en un checkout limpio sin `data/processed/`).

Cubre, con datos reales, las propiedades que la auditoría del pipeline
nuevo pidió verificar de forma permanente: unicidad de fila, ausencia de
imputación disfrazada, y (usando los mismos bloques que
`experiment_abcd.py`) separación temporal y de episodios entre folds.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = REPO_ROOT / "data" / "processed" / "temporal_dataset_h6.parquet"
FIRES_CSV = REPO_ROOT / "data" / "processed" / "nasa_firms_2021-08-30_2026-08-30.csv"

pytestmark = pytest.mark.skipif(
    not DATASET_PATH.exists(),
    reason="temporal_dataset_h6.parquet no existe — correr scripts/build_temporal_dataset.py primero",
)


@pytest.fixture(scope="module")
def dataset() -> pd.DataFrame:
    return pd.read_parquet(DATASET_PATH)


def test_cell_forecast_time_pair_is_unique(dataset: pd.DataFrame) -> None:
    dup = dataset.groupby(["cell_id", "forecast_time"]).size()
    assert dup.max() == 1, "Hay pares (cell_id, forecast_time) repetidos"


def test_excluded_rows_are_never_negative_never_positive(dataset: pd.DataFrame) -> None:
    """La preferencia explícita de la auditoría: cooldown -> excluded=True,
    target=None. Nunca target=0 disfrazando una fila que no se evaluó."""
    excluded = dataset[dataset["excluded"]]
    if excluded.empty:
        pytest.skip("No hay filas excluidas en esta corrida")
    assert excluded["target"].isna().all()
    assert (~excluded["eligible_for_training"]).all()


def test_eligible_rows_always_have_a_defined_target(dataset: pd.DataFrame) -> None:
    eligible = dataset[dataset["eligible_for_training"]]
    assert eligible["target"].isin([0, 1]).all()


def test_missing_meteo_flags_match_real_nans(dataset: pd.DataFrame) -> None:
    from src.procesamiento.pipeline_validators import validate_missing_data_handling

    eligible = dataset[dataset["eligible_for_training"]]
    # Un flag por BLOQUE (no por variable): temp/hr/viento/regla_30_30_30
    # de un mismo lag vienen de la misma observación y faltan juntas.
    nullable = [
        ("meteo_actual_temp", "meteo_actual_missing"),
        ("meteo_lag_24h_temp", "meteo_lag_24h_missing"),
        ("meteo_lag_48h_temp", "meteo_lag_48h_missing"),
        ("dias_desde_ultimo_evento", "dias_desde_ultimo_evento_missing"),
    ]
    result = validate_missing_data_handling(eligible, nullable_features=nullable)
    assert result.status == "PASS", result.detail


def test_no_row_imputes_missing_meteo_as_zero(dataset: pd.DataFrame) -> None:
    """Ancla el bug corregido: cuando meteo_actual_missing es True, la
    columna de valor debe seguir siendo NaN, nunca 0.0."""
    missing_rows = dataset[dataset["meteo_actual_missing"] == True]  # noqa: E712
    if missing_rows.empty:
        pytest.skip("No hay filas con meteo_actual_missing en esta corrida")
    assert missing_rows["meteo_actual_temp"].isna().all()


def test_target_column_dtype_allows_real_nan_not_a_forced_int_cast(dataset: pd.DataFrame) -> None:
    """Sección 4 de la auditoría 06-09-2026: si `target` fuera un dtype
    entero, pandas/parquet no podrían representar `None` en absoluto y
    algún paso de la escritura habría tenido que convertirlo en 0 (o
    reventar). float64 con NaN real es la única forma honesta de guardar
    "no aplica" junto a 0/1 en la misma columna."""
    assert dataset["target"].dtype.kind == "f", (
        f"target tiene dtype {dataset['target'].dtype} — un entero no puede "
        "representar 'excluded' sin forzar un 0 o 1 falso"
    )


def test_target_event_id_is_nan_for_every_non_positive_row_after_roundtrip(dataset: pd.DataFrame) -> None:
    """`dataset` ya viene de un `pd.read_parquet` real (fixture de este
    archivo) — esto prueba la propiedad DESPUÉS del roundtrip a disco, no
    solo en el DataFrame en memoria de `build_temporal_dataset.py`."""
    non_positive = dataset[dataset["target"] != 1]
    assert non_positive["target_event_id"].isna().all()
    assert non_positive["target_timestamp"].isna().all()
    positive = dataset[dataset["target"] == 1]
    assert positive["target_event_id"].notna().all()
    assert positive["target_timestamp"].notna().all()


def test_forecast_times_are_reproducible_from_meteo_alone_without_touching_firms(dataset: pd.DataFrame) -> None:
    """Sección 16-17 de la auditoría 06-09-2026: `forecast_time` no puede
    estar condicionado por la existencia de una detección FIRMS futura
    (eso sería fuga de selección: solo evaluar instantes donde "algo
    interesante" iba a pasar). Se prueba recalculando el conjunto de
    `forecast_time` ÚNICAMENTE a partir de la serie meteorológica real —
    sin importar `episodes`, `arrivals` ni el CSV de FIRMS en absoluto — y
    comprobando que coincide EXACTO con los `forecast_time` del dataset."""
    from scripts.build_temporal_dataset import CANDIDATE_STEP_HOURS, STATION_ID
    from src.procesamiento.regional_meteo import load_regional_meteo_series

    meteo_series = load_regional_meteo_series(STATION_ID)
    bucketed = (
        meteo_series.set_index("momento")["temperatura"]
        .resample(f"{CANDIDATE_STEP_HOURS}h")
        .first()
        .dropna()
    )
    recomputed_times = set(bucketed.index)
    dataset_times = set(dataset["forecast_time"].unique())
    assert recomputed_times == dataset_times, (
        "forecast_time en el dataset no coincide con el recálculo puramente "
        "meteorológico — si difiere, algo distinto a la disponibilidad de "
        "clima está determinando qué instantes se evalúan."
    )


def test_folds_have_no_temporal_overlap_and_no_shared_episodes(dataset: pd.DataFrame) -> None:
    from src.procesamiento.episodes import assign_episodes

    df = dataset[dataset["eligible_for_training"]].copy()
    df["mes"] = df["forecast_time"].dt.strftime("%Y-%m")
    bloques = ["2022-01", "2022-12", "2024-02", "2025-02"]
    df = df[df["mes"].isin(bloques)]

    fires = pd.read_csv(FIRES_CSV)
    eps = assign_episodes(fires)
    eps["mes"] = eps["ignition_ts"].dt.strftime("%Y-%m")

    for i in range(1, len(bloques)):
        test_mes = bloques[i]
        train_meses = bloques[:i]
        train = df[df["mes"].isin(train_meses)]
        test = df[df["mes"] == test_mes]
        if train.empty or test.empty:
            continue

        assert train["forecast_time"].max() < test["forecast_time"].min(), f"fold {i}: train se solapa con test"

        ev_train = set(eps[eps["mes"].isin(train_meses)]["event_id"])
        ev_test = set(eps[eps["mes"] == test_mes]["event_id"])
        assert not (ev_train & ev_test), f"fold {i}: episodios compartidos entre train y test"
