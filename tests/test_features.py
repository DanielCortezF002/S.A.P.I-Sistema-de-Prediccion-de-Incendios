"""Pruebas de feature engineering."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from src.procesamiento.features import FeatureEngineer


def test_rule_30_30_30_activation():
    engineer = FeatureEngineer()
    df = pd.DataFrame(
        {
            "temperatura": [35.0, 20.0],
            "humedad_relativa": [20.0, 60.0],
            "velocidad_viento": [35.0, 10.0],
        }
    )
    result = engineer._encode_rule_30_30_30(df)
    assert result["regla_30_30_30"].iloc[0] == 1
    assert result["regla_30_30_30"].iloc[1] == 0


def test_encode_rule_30_30_30_degrades_to_zero_when_columns_missing():
    """Antes fallaba con KeyError si faltaba alguna de las 3 variables."""
    engineer = FeatureEngineer()
    df = pd.DataFrame({"cell_id": ["VP-001"]})
    result = engineer._encode_rule_30_30_30(df)
    assert result["regla_30_30_30"].iloc[0] == 0


def test_lag_features_no_nulls_after_fill():
    engineer = FeatureEngineer()
    df = pd.DataFrame({"temperatura": [20.0, 22.0, 25.0, 28.0]})
    result = engineer._add_lag_features(df)
    assert result["lag_temp_24h"].isna().sum() == 0


def test_encode_orientacion_circular_matches_known_angles():
    engineer = FeatureEngineer()
    # 0°=Norte, 90°=Este, 180°=Sur, 270°=Oeste: valores exactos de seno/coseno.
    df = pd.DataFrame({"orientacion": [0.0, 90.0, 180.0, 270.0]})
    result = engineer._encode_orientacion_circular(df)
    assert np.allclose(result["orientacion_sin"], [0.0, 1.0, 0.0, -1.0], atol=1e-9)
    assert np.allclose(result["orientacion_cos"], [1.0, 0.0, -1.0, 0.0], atol=1e-9)


def test_encode_orientacion_circular_350_and_10_degrees_are_close_in_encoded_space():
    """350° y 10° son casi el mismo rumbo físico (20° de diferencia real).

    En grados crudos están en extremos casi opuestos del rango 0-360; en
    seno/coseno, la distancia euclidiana entre ambos debe ser chica —
    prueba de que la codificación resuelve el problema de discontinuidad.
    """
    engineer = FeatureEngineer()
    df = pd.DataFrame({"orientacion": [350.0, 10.0]})
    result = engineer._encode_orientacion_circular(df)
    dx = result["orientacion_sin"].iloc[0] - result["orientacion_sin"].iloc[1]
    dy = result["orientacion_cos"].iloc[0] - result["orientacion_cos"].iloc[1]
    euclidean_distance = (dx**2 + dy**2) ** 0.5
    assert euclidean_distance < 0.4  # cercano, no en extremos opuestos (que darían ~2.0)


def test_encode_orientacion_circular_noop_when_column_absent():
    engineer = FeatureEngineer()
    df = pd.DataFrame({"temperatura": [20.0]})
    result = engineer._encode_orientacion_circular(df)
    assert "orientacion_sin" not in result.columns
    assert "orientacion_cos" not in result.columns


def test_optimize_dtypes_uses_float32():
    engineer = FeatureEngineer()
    df = pd.DataFrame({"temperatura": [20.0, 22.0], "regla_30_30_30": [0, 1]})
    result = engineer._optimize_dtypes(df)
    assert str(result["temperatura"].dtype) == "float32"


def test_smote_balance_returns_same_shape_or_more():
    engineer = FeatureEngineer()
    x = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6], "b": [2, 3, 4, 5, 6, 7]})
    y = pd.Series([0, 0, 0, 0, 1, 1])
    x_bal, y_bal = engineer.apply_smote_balance(x, y)
    assert len(x_bal) >= len(x)
    assert len(y_bal) >= len(y)


def test_smote_balance_duplicates_single_row_when_only_one_sample() -> None:
    engineer = FeatureEngineer()
    x = pd.DataFrame({"a": [1.0]})
    y = pd.Series([0])
    x_bal, y_bal = engineer.apply_smote_balance(x, y)
    assert len(x_bal) == 2
    assert set(y_bal.tolist()) == {0, 1}


def test_smote_balance_mutates_first_label_when_all_same_class() -> None:
    engineer = FeatureEngineer()
    x = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
    y = pd.Series([0, 0, 0])
    x_bal, y_bal = engineer.apply_smote_balance(x, y)
    assert len(x_bal) >= 3
    assert y_bal.nunique() == 2


@patch("src.procesamiento.features.SMOTE")
@patch("src.procesamiento.features.log_event")
def test_smote_balance_falls_back_on_smote_error(mock_log: MagicMock, mock_smote_cls: MagicMock) -> None:
    mock_instance = MagicMock()
    mock_instance.fit_resample.side_effect = RuntimeError("smote fail")
    mock_smote_cls.return_value = mock_instance

    engineer = FeatureEngineer()
    x = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 3, 4, 5]})
    y = pd.Series([0, 0, 1, 1])
    x_bal, y_bal = engineer.apply_smote_balance(x, y)
    assert len(x_bal) == len(x)
    mock_log.assert_called_once()
