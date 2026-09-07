"""Pruebas de `src.procesamiento.target_builder.build_targets`."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from src.procesamiento.target_builder import build_targets

HORIZON = timedelta(hours=6)
COOLDOWN = timedelta(hours=6)


def _arrivals(rows: list[tuple[int, str, str]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["event_id", "cell_id", "first_arrival"])
    return pd.DataFrame(
        [
            {"event_id": eid, "cell_id": cell, "first_arrival": pd.Timestamp(ts, tz="UTC")}
            for eid, cell, ts in rows
        ]
    )


def test_target_is_one_when_a_new_arrival_falls_inside_the_future_window() -> None:
    arrivals = _arrivals([(1, "VP-001", "2026-01-01 15:00:00")])
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
    df = build_targets(arrivals, ["VP-001"], [T], HORIZON, COOLDOWN)
    row = df.iloc[0]
    assert row.target == 1
    assert row.excluded == False
    # Trazabilidad (auditoría 06-09-2026): la fila debe poder decir qué
    # evento y qué timestamp real la produjeron, sin recalcular nada afuera.
    assert row.target_event_id == 1
    assert row.target_timestamp == pd.Timestamp("2026-01-01 15:00:00", tz="UTC")


def test_target_event_id_is_none_when_target_is_zero() -> None:
    arrivals = _arrivals([(1, "VP-001", "2026-01-02 15:00:00")])
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
    df = build_targets(arrivals, ["VP-001"], [T], HORIZON, COOLDOWN)
    row = df.iloc[0]
    assert row.target == 0
    assert row.target_event_id is None
    assert pd.isna(row.target_timestamp)


def test_target_event_id_is_none_when_excluded() -> None:
    arrivals = _arrivals([(1, "VP-001", "2026-01-01 10:00:00")])
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")  # 2h despues del arribo -> cooldown
    df = build_targets(arrivals, ["VP-001"], [T], HORIZON, COOLDOWN)
    row = df.iloc[0]
    assert row.excluded == True
    assert row.target_event_id is None


def test_target_event_id_picks_the_earliest_qualifying_arrival_when_two_events_qualify() -> None:
    """Dos eventos distintos arriban dentro de la misma ventana futura ->
    se registra el de arribo MÁS TEMPRANO, no uno arbitrario."""
    arrivals = _arrivals(
        [
            (1, "VP-001", "2026-01-01 14:00:00"),  # mas tardio
            (2, "VP-001", "2026-01-01 13:00:00"),  # mas temprano -> este debe quedar registrado
        ]
    )
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
    df = build_targets(arrivals, ["VP-001"], [T], HORIZON, COOLDOWN)
    row = df.iloc[0]
    assert row.target == 1
    assert row.target_event_id == 2
    assert row.target_timestamp == pd.Timestamp("2026-01-01 13:00:00", tz="UTC")


def test_target_is_zero_when_no_arrival_falls_inside_the_window() -> None:
    arrivals = _arrivals([(1, "VP-001", "2026-01-02 15:00:00")])  # muy lejos
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
    df = build_targets(arrivals, ["VP-001"], [T], HORIZON, COOLDOWN)
    row = df.iloc[0]
    assert row.target == 0
    assert row.excluded == False


def test_arrival_exactly_at_forecast_time_does_not_count_as_future() -> None:
    """La ventana es (T, T+h] — abierta en T: un arribo EN T no es "futuro"."""
    arrivals = _arrivals([(1, "VP-001", "2026-01-01 12:00:00")])
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
    df = build_targets(arrivals, ["VP-001"], [T], HORIZON, COOLDOWN)
    row = df.iloc[0]
    # Un arribo en T mismo activa el cooldown (la celda ya está ardiendo en T),
    # así que la fila se excluye en vez de contar como "sin riesgo".
    assert row.excluded == True
    assert row.excluded_reason == "cooldown_evento_activo"


def test_arrival_exactly_at_window_end_counts_as_future() -> None:
    arrivals = _arrivals([(1, "VP-001", "2026-01-01 18:00:00")])  # T+6h exacto
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
    df = build_targets(arrivals, ["VP-001"], [T], HORIZON, COOLDOWN)
    assert df.iloc[0].target == 1


def test_forecast_time_within_cooldown_of_a_past_arrival_is_excluded() -> None:
    """La celda arde 2h antes de T -> T queda en cooldown, se excluye."""
    arrivals = _arrivals([(1, "VP-001", "2026-01-01 10:00:00")])
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")  # 2h despues del arribo
    df = build_targets(arrivals, ["VP-001"], [T], HORIZON, COOLDOWN)
    row = df.iloc[0]
    assert row.excluded == True
    assert row.target is None


def test_forecast_time_after_cooldown_expires_is_not_excluded() -> None:
    arrivals = _arrivals([(1, "VP-001", "2026-01-01 05:00:00")])
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")  # 7h despues, cooldown=6h ya paso
    df = build_targets(arrivals, ["VP-001"], [T], HORIZON, COOLDOWN)
    row = df.iloc[0]
    assert row.excluded == False
    assert row.target == 0


def test_a_cell_with_no_arrivals_at_all_is_always_negative_and_never_excluded() -> None:
    arrivals = _arrivals([])
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
    df = build_targets(arrivals, ["VP-001"], [T], HORIZON, COOLDOWN)
    row = df.iloc[0]
    assert row.target == 0
    assert row.excluded == False


def test_arrivals_in_other_cells_do_not_affect_this_cell() -> None:
    arrivals = _arrivals([(1, "VP-002", "2026-01-01 15:00:00")])
    T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
    df = build_targets(arrivals, ["VP-001"], [T], HORIZON, COOLDOWN)
    assert df.iloc[0].target == 0


def test_produces_one_row_per_cell_times_forecast_time() -> None:
    arrivals = _arrivals([])
    times = [pd.Timestamp("2026-01-01 12:00:00", tz="UTC"), pd.Timestamp("2026-01-01 13:00:00", tz="UTC")]
    df = build_targets(arrivals, ["VP-001", "VP-002"], times, HORIZON, COOLDOWN)
    assert len(df) == 4
