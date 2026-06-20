"""Fixtures compartidas para pruebas S.A.P.I."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from src.procesamiento.features import FeatureEngineer


@pytest.fixture
def sample_dataset() -> pd.DataFrame:
    """Dataset de muestra para modelamiento."""
    return pd.DataFrame(
        {
            "cell_id": [f"VP-{i:03d}" for i in range(1, 21)],
            "temperatura": [22 + i * 0.5 for i in range(20)],
            "humedad_relativa": [60 - i for i in range(20)],
            "velocidad_viento": [5 + i for i in range(20)],
            "altitud": [100 + i * 10 for i in range(20)],
            "pendiente": [10 + i * 0.5 for i in range(20)],
            "ndvi": [0.5 + i * 0.01 for i in range(20)],
            "min_lon": [-71.58 + i * 0.01 for i in range(20)],
            "min_lat": [-33.06 + i * 0.005 for i in range(20)],
            "max_lon": [-71.57 + i * 0.01 for i in range(20)],
            "max_lat": [-33.05 + i * 0.005 for i in range(20)],
            "ignicion": [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0],
        }
    )


@pytest.fixture
def engineered_dataset(sample_dataset: pd.DataFrame) -> pd.DataFrame:
    """Dataset con features de ingeniería aplicadas."""
    with patch("src.procesamiento.features.log_event"):
        return FeatureEngineer().compute_environmental_features(sample_dataset)
