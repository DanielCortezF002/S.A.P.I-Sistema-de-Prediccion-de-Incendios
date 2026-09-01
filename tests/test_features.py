"""Pruebas de feature engineering."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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


def test_lag_features_no_nulls_after_fill():
    engineer = FeatureEngineer()
    df = pd.DataFrame({"temperatura": [20.0, 22.0, 25.0, 28.0]})
    result = engineer._add_lag_features(df)
    assert result["lag_temp_24h"].isna().sum() == 0


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
