"""Auditoría 06-09-2026, secciones 14-15: traza el NaN real (no de
fixture) desde el dataset hasta lo que efectivamente recibe el modelo, en
una corrida real de `run_fold` sobre `temporal_dataset_h6.parquet`.
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


def test_run_fold_reports_nan_diagnostics_matching_the_real_dataset() -> None:
    from scripts.experiment_abcd import FEATURES_B, run_fold
    from src.procesamiento.episodes import assign_episodes, first_arrival_by_cell

    df = pd.read_parquet(DATASET_PATH)
    df = df[df["eligible_for_training"]].reset_index(drop=True)
    df["mes"] = df["forecast_time"].dt.strftime("%Y-%m")

    fires = pd.read_csv(FIRES_CSV)
    episodes = assign_episodes(fires)
    arrivals = first_arrival_by_cell(episodes)

    train = df[df["mes"] == "2022-01"]
    test = df[df["mes"] == "2022-12"]
    assert not train.empty and not test.empty

    result = run_fold(train, test, arrivals)
    diag = result["nan_diagnostics"]["B"]

    # Verificación cruzada independiente: recalcular el NaN de FEATURES_B
    # directamente sobre train/test reales, sin pasar por run_fold.
    assert diag["n_nan_before_prep_xy_train"] == int(train[FEATURES_B].isna().sum().sum())
    assert diag["n_nan_before_prep_xy_test"] == int(test[FEATURES_B].isna().sum().sum())
    # `_prep_xy` no imputa: antes y después deben ser IDÉNTICOS.
    assert diag["n_nan_before_prep_xy_train"] == diag["n_nan_after_prep_xy_train"]
    assert diag["n_nan_before_prep_xy_test"] == diag["n_nan_after_prep_xy_test"]
    # El NaN que efectivamente ve `predict_proba` es el mismo que había
    # antes de llamarlo — ninguna imputación oculta en el camino.
    assert diag["n_nan_en_x_test_al_momento_de_predict"] == diag["n_nan_after_prep_xy_test"]
    # Al menos una columna con NaN real debe existir en meteo_actual_temp,
    # si el fold de test incluye alguna de las filas sin lectura DMC.
    assert diag["n_nan_test_por_columna"]["meteo_actual_temp"] == int(test["meteo_actual_temp"].isna().sum())
