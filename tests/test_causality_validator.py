"""Pruebas de `validate_temporal_causality` — el "test de no futuro".

Fixture pedido explícitamente en la auditoría: T=12:00; meteo a las 11:00
(pasado, válido), 12:00 (presente, válido) y 13:00 (futuro, jamás debe
entrar a una feature); FIRMS a las 11:30 (historia) y 12:30 (target).
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.procesamiento.causality_validator import TemporalLeakageError, validate_temporal_causality

T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")


def _row(**kwargs) -> pd.DataFrame:
    base = {"forecast_time": T}
    base.update(kwargs)
    return pd.DataFrame([base])


def test_feature_timestamp_before_forecast_time_is_valid() -> None:
    df = _row(meteo_momento=pd.Timestamp("2026-01-01 11:00:00", tz="UTC"))
    report = validate_temporal_causality(df, feature_timestamp_cols=["meteo_momento"])
    assert report.is_valid


def test_feature_timestamp_equal_to_forecast_time_is_valid() -> None:
    df = _row(meteo_momento=T)
    report = validate_temporal_causality(df, feature_timestamp_cols=["meteo_momento"])
    assert report.is_valid


def test_feature_timestamp_after_forecast_time_is_a_violation() -> None:
    """La lectura de las 13:00 (T+1h) jamás debe poder alimentar una feature en T."""
    df = _row(meteo_momento=pd.Timestamp("2026-01-01 13:00:00", tz="UTC"))
    report = validate_temporal_causality(
        df, feature_timestamp_cols=["meteo_momento"], raise_on_violation=False
    )
    assert not report.is_valid
    assert report.n_violations == 1


def test_raises_by_default_on_violation() -> None:
    df = _row(meteo_momento=pd.Timestamp("2026-01-01 13:00:00", tz="UTC"))
    with pytest.raises(TemporalLeakageError):
        validate_temporal_causality(df, feature_timestamp_cols=["meteo_momento"])


def test_target_timestamp_strictly_after_forecast_time_is_valid() -> None:
    """FIRMS a las 12:30 (T+30min) SÍ puede entrar como target."""
    df = _row(target_momento=pd.Timestamp("2026-01-01 12:30:00", tz="UTC"))
    report = validate_temporal_causality(
        df, feature_timestamp_cols=[], target_timestamp_col="target_momento"
    )
    assert report.is_valid


def test_target_timestamp_at_or_before_forecast_time_is_a_violation() -> None:
    """FIRMS a las 11:30 (T-30min) es HISTORIA, no puede ser el target de esta fila."""
    df = _row(target_momento=pd.Timestamp("2026-01-01 11:30:00", tz="UTC"))
    report = validate_temporal_causality(
        df, feature_timestamp_cols=[], target_timestamp_col="target_momento", raise_on_violation=False
    )
    assert not report.is_valid


def test_full_fixture_from_the_audit_request() -> None:
    """El fixture completo: meteo 11:00/12:00 válidas, 13:00 inválida;
    FIRMS 11:30 como historia (válida como feature), FIRMS 12:30 como target."""
    df = pd.DataFrame(
        [
            {
                "forecast_time": T,
                "meteo_actual_momento": pd.Timestamp("2026-01-01 12:00:00", tz="UTC"),
                "meteo_lag_1h_momento": pd.Timestamp("2026-01-01 11:00:00", tz="UTC"),
                "historial_ultimo_evento_momento": pd.Timestamp("2026-01-01 11:30:00", tz="UTC"),
                "target_evento_momento": pd.Timestamp("2026-01-01 12:30:00", tz="UTC"),
            }
        ]
    )
    report = validate_temporal_causality(
        df,
        feature_timestamp_cols=["meteo_actual_momento", "meteo_lag_1h_momento", "historial_ultimo_evento_momento"],
        target_timestamp_col="target_evento_momento",
    )
    assert report.is_valid


def test_full_fixture_fails_if_the_future_meteo_reading_leaks_in() -> None:
    df = pd.DataFrame(
        [
            {
                "forecast_time": T,
                "meteo_actual_momento": pd.Timestamp("2026-01-01 13:00:00", tz="UTC"),  # fuga
                "target_evento_momento": pd.Timestamp("2026-01-01 12:30:00", tz="UTC"),
            }
        ]
    )
    with pytest.raises(TemporalLeakageError):
        validate_temporal_causality(
            df,
            feature_timestamp_cols=["meteo_actual_momento"],
            target_timestamp_col="target_evento_momento",
        )


def test_missing_optional_columns_are_skipped_not_treated_as_violations() -> None:
    df = _row()
    report = validate_temporal_causality(df, feature_timestamp_cols=["columna_que_no_existe"])
    assert report.is_valid


def test_nat_values_do_not_count_as_violations() -> None:
    df = _row(meteo_momento=pd.NaT)
    report = validate_temporal_causality(df, feature_timestamp_cols=["meteo_momento"])
    assert report.is_valid
