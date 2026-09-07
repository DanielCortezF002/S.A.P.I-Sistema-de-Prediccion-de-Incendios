"""Blinda `scripts/experiment_abcd.py::MODELOS` contra fuga accidental
entre modelos (sección 9 de la auditoría del pipeline nuevo).

Si alguien agrega una feature a `experiment_abcd.py` y la pone en el
diccionario equivocado (p. ej. una feature de D que se cuela en B), este
test debe fallar — no una revisión manual.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier

from scripts.experiment_abcd import FEATURES_A, FEATURES_B, FEATURES_C, FEATURES_D, _prep_xy
from src.procesamiento.pipeline_validators import validate_feature_set_contract


def test_real_model_feature_sets_satisfy_the_containment_contract() -> None:
    result = validate_feature_set_contract(
        {"A": FEATURES_A, "B": FEATURES_B, "C": FEATURES_C, "D": FEATURES_D}
    )
    assert result.status == "PASS", result.detail


def test_d_minus_c_is_exactly_the_topography_block() -> None:
    assert set(FEATURES_D) - set(FEATURES_C) == {"elevacion", "pendiente", "orientacion"}


def test_c_minus_b_is_exactly_the_lag_block() -> None:
    esperado = {
        f"meteo_lag_{h}h_{var}"
        for h in (6, 12, 24, 48)
        for var in ("temp", "hr", "viento", "regla_30_30_30")
    }
    assert set(FEATURES_C) - set(FEATURES_B) == esperado


def test_b_minus_a_is_exactly_the_current_meteo_block() -> None:
    assert set(FEATURES_B) - set(FEATURES_A) == {
        "meteo_actual_temp",
        "meteo_actual_hr",
        "meteo_actual_viento",
        "meteo_actual_regla_30_30_30",
    }


def test_no_model_contains_cell_id_or_synthetic_features() -> None:
    for nombre, features in [("A", FEATURES_A), ("B", FEATURES_B), ("C", FEATURES_C), ("D", FEATURES_D)]:
        assert "cell_id" not in features, f"cell_id se coló en el modelo {nombre}"
        assert "ndvi" not in features, f"ndvi (sintético) se coló en el modelo {nombre}"
        assert "ignicion" not in features, f"ignicion se coló en el modelo {nombre}"


def test_prep_xy_never_imputes_nan() -> None:
    """Sección 13 de la auditoría: fixture con NaN en temperatura, humedad
    y viento -> deben SEGUIR siendo NaN después de `_prep_xy`, nunca 0.0
    ni ningún otro valor plausible. Prueba de regresión permanente — ya no
    depende de leer el código a mano."""
    df = pd.DataFrame(
        {
            "meteo_actual_temp": [20.0, np.nan, 25.0],
            "meteo_actual_hr": [50.0, np.nan, 40.0],
            "meteo_actual_viento": [10.0, np.nan, 15.0],
            "meteo_actual_regla_30_30_30": [0, np.nan, 1],
            "historial_firms_count": [0, 1, 2],
            "dias_desde_ultimo_evento": [np.nan, 5.0, 10.0],
            "target": [0, 1, 0],
        }
    )
    x, y = _prep_xy(df, FEATURES_B)

    assert x["meteo_actual_temp"].isna().tolist() == [False, True, False]
    assert x["meteo_actual_hr"].isna().tolist() == [False, True, False]
    assert x["meteo_actual_viento"].isna().tolist() == [False, True, False]
    assert x["dias_desde_ultimo_evento"].isna().tolist() == [True, False, False]
    # Ningún NaN se convirtió en 0.0 (el valor de la fila 1 sigue siendo NaN,
    # no 0.0 — comprobado explícitamente, no solo "no hay NaN").
    assert not (x["meteo_actual_temp"].fillna(-999) == 0.0).any()
    assert list(y) == [0, 1, 0]


def test_prep_xy_raises_explicitly_on_excluded_rows() -> None:
    """Sección 5 de la auditoría 06-09-2026: una fila excluded=True tiene
    target=None (cooldown) — nunca debe llegar a entrenamiento/evaluación,
    y el error debe decir POR QUÉ, no ser un ValueError genérico de pandas."""
    df = pd.DataFrame(
        {
            "historial_firms_count": [0, 1],
            "dias_desde_ultimo_evento": [1.0, 2.0],
            "target": [0, None],
            "excluded": [False, True],
        }
    )
    with pytest.raises(ValueError, match="excluded=True"):
        _prep_xy(df, FEATURES_A)


def test_prep_xy_raises_explicitly_on_ineligible_rows() -> None:
    df = pd.DataFrame(
        {
            "historial_firms_count": [0, 1],
            "dias_desde_ultimo_evento": [1.0, 2.0],
            "target": [0, 1],
            "eligible_for_training": [True, False],
        }
    )
    with pytest.raises(ValueError, match="eligible_for_training=False"):
        _prep_xy(df, FEATURES_A)


def test_prep_xy_raises_on_bare_nan_target_without_excluded_column() -> None:
    df = pd.DataFrame(
        {
            "historial_firms_count": [0, 1],
            "dias_desde_ultimo_evento": [1.0, 2.0],
            "target": [0, None],
        }
    )
    with pytest.raises(ValueError, match="target=NaN"):
        _prep_xy(df, FEATURES_A)


def test_prep_xy_still_works_on_a_clean_eligible_dataframe() -> None:
    """El guard no debe molestar al caso normal: todo eligible, sin excluded."""
    df = pd.DataFrame(
        {
            "historial_firms_count": [0, 1],
            "dias_desde_ultimo_evento": [1.0, 2.0],
            "target": [0, 1],
            "excluded": [False, False],
            "eligible_for_training": [True, True],
        }
    )
    x, y = _prep_xy(df, FEATURES_A)
    assert list(y) == [0, 1]


def test_histgradientboosting_accepts_nan_end_to_end() -> None:
    """Sección 12: confirma con un fixture real que el modelo instalado
    soporta NaN en fit() y predict_proba() sin ninguna transformación
    implícita que los reemplace."""
    x_train = pd.DataFrame(
        {
            "a": [1.0, np.nan, 3.0, 4.0, np.nan, 6.0],
            "b": [np.nan, 2.0, 3.0, np.nan, 5.0, 6.0],
        }
    )
    y_train = pd.Series([0, 0, 1, 0, 1, 1])
    clf = HistGradientBoostingClassifier(random_state=42, max_depth=2)
    clf.fit(x_train, y_train)  # no debe lanzar por los NaN

    x_test = pd.DataFrame({"a": [np.nan, 2.0], "b": [1.0, np.nan]})
    proba = clf.predict_proba(x_test)
    assert proba.shape == (2, 2)
    assert np.isfinite(proba).all()
    # El propio sklearn no modifica el DataFrame de entrada in-place.
    assert x_test["a"].isna().tolist() == [True, False]
    assert x_test["b"].isna().tolist() == [False, True]
