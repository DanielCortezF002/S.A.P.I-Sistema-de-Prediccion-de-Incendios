"""Pruebas de `src.procesamiento.temporal_features`.

Demuestra, con un ejemplo concreto, exactamente la propiedad que el `.shift()`
antiguo violaba: `meteo_lag_24h_temp(T) == temperatura_estacion(T-24h)`, no
`temperatura(fila anterior)`.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from src.procesamiento.temporal_features import build_regional_meteo_features, historial_firms_features


def _series(rows: list[tuple[str, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "station_id": "330007",
                "momento": pd.Timestamp(momento, tz="UTC"),
                "temperatura": temp,
                "humedad_relativa": hr,
                "velocidad_viento_kmh": viento,
            }
            for momento, temp, hr, viento in rows
        ]
    )


def test_lag_24h_matches_the_real_reading_24h_before_not_the_row_closest_to_t() -> None:
    """El bug viejo (`temperatura.shift(1)`) habría usado la fila
    inmediatamente anterior a T EN LA TABLA — que aquí es una lectura de
    hace 1 hora, no de hace 24. El lag correcto debe ignorar esa fila (está
    fuera de tolerancia de T-24h) y usar la lectura real de hace 24h."""
    series = _series(
        [
            ("2026-01-01 12:00:00", 10.0, 80.0, 5.0),   # exactamente T-24h -> debe ser esta
            ("2026-01-02 11:00:00", 77.0, 10.0, 40.0),  # 1h antes de T -> lo que "shift(1)" habría usado
            ("2026-01-02 12:00:00", 25.0, 40.0, 15.0),  # T
        ]
    )
    T = pd.Timestamp("2026-01-02 12:00:00", tz="UTC")
    out = build_regional_meteo_features([T], series, lag_hours=(0, 24))
    row = out.iloc[0]
    assert row["meteo_actual_temp"] == 25.0
    assert row["meteo_lag_24h_temp"] == 10.0
    assert row["meteo_lag_24h_temp"] != 77.0
    assert bool(row["meteo_actual_missing"]) is False
    assert bool(row["meteo_lag_24h_missing"]) is False


def test_lag_24h_is_none_when_no_real_reading_exists_near_t_minus_24h() -> None:
    series = _series([("2026-01-01 12:00:00", 25.0, 40.0, 15.0)])  # solo T, nada 24h antes
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
    out = build_regional_meteo_features([T], series, lag_hours=(0, 24))
    row = out.iloc[0]
    assert row["meteo_actual_temp"] == 25.0
    assert pd.isna(row["meteo_lag_24h_temp"])
    assert pd.isna(row["meteo_lag_24h_momento"])
    # El NaN debe venir acompañado de su flag — nunca un 0.0 sin marcar.
    assert bool(row["meteo_actual_missing"]) is False
    assert bool(row["meteo_lag_24h_missing"]) is True


def test_lag_momento_never_exceeds_forecast_time() -> None:
    """Propiedad de causalidad a nivel de esta función: ningún `_momento`
    devuelto puede ser posterior a `forecast_time`, para cualquier lag."""
    series = _series(
        [
            ("2026-01-01 00:00:00", 10.0, 80.0, 5.0),
            ("2026-01-01 06:00:00", 15.0, 70.0, 8.0),
            ("2026-01-01 12:00:00", 20.0, 60.0, 12.0),
            ("2026-01-01 18:00:00", 30.0, 25.0, 32.0),  # posterior a T=12:00
        ]
    )
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
    out = build_regional_meteo_features([T], series, lag_hours=(0, 6, 12, 24, 48))
    row = out.iloc[0]
    for h in (0, 6, 12, 24, 48):
        label = "meteo_actual" if h == 0 else f"meteo_lag_{h}h"
        momento = row[f"{label}_momento"]
        if pd.notna(momento):
            assert momento <= T


def test_historial_firms_features_ignore_events_at_or_after_forecast_time() -> None:
    arrivals = pd.Series(
        [
            pd.Timestamp("2026-01-01 10:00:00", tz="UTC"),  # pasado, cuenta
            pd.Timestamp("2026-01-02 10:00:00", tz="UTC"),  # futuro respecto a T, NO debe contar
        ]
    )
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
    feats = historial_firms_features("VP-001", T, arrivals)
    assert feats["historial_firms_count"] == 1
    assert feats["historial_ultimo_evento_momento"] == pd.Timestamp("2026-01-01 10:00:00", tz="UTC")
    assert feats["dias_desde_ultimo_evento"] == 2 / 24  # 2 horas
    assert feats["dias_desde_ultimo_evento_missing"] is False


def test_historial_firms_features_with_no_past_events() -> None:
    arrivals = pd.Series([pd.Timestamp("2026-01-05 10:00:00", tz="UTC")])  # todo futuro
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
    feats = historial_firms_features("VP-001", T, arrivals)
    assert feats["historial_firms_count"] == 0
    assert feats["dias_desde_ultimo_evento"] is None
    assert feats["dias_desde_ultimo_evento_missing"] is True
    assert pd.isna(feats["historial_ultimo_evento_momento"])
