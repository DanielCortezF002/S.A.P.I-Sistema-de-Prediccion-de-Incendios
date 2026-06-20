"""Pruebas de feature engineering."""

from __future__ import annotations

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
