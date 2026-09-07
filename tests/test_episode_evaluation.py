"""Pruebas de `src.procesamiento.episode_evaluation`.

Ancla la distinción central de esta auditoría: 3 filas positivas del mismo
episodio deben contar como 1 episodio evaluado, no como 3.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.procesamiento.episode_evaluation import evaluate_by_episode, largest_episode_fraction

T1 = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
T2 = pd.Timestamp("2026-01-02 12:00:00", tz="UTC")


def _test_df(rows: list[tuple[str, pd.Timestamp, int]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cell_id": cell,
                "forecast_time": T,
                "target_window_start": T,
                "target_window_end": T + pd.Timedelta(hours=6),
                "target": target,
            }
            for cell, T, target in rows
        ]
    )


def _arrivals(rows: list[tuple[int, str, pd.Timestamp]]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"event_id": eid, "cell_id": cell, "first_arrival": ts} for eid, cell, ts in rows]
    )


def test_three_rows_from_the_same_episode_count_as_one_episode() -> None:
    """El caso central: mismo event_id detrás de varias celdas/T."""
    df = _test_df(
        [
            ("VP-001", T1, 1),
            ("VP-002", T1, 1),
            ("VP-003", T1, 1),
            ("VP-004", T1, 0),
        ]
    )
    scores = np.array([0.9, 0.8, 0.7, 0.1])
    arrivals = _arrivals(
        [
            (100, "VP-001", T1 + pd.Timedelta(hours=1)),
            (100, "VP-002", T1 + pd.Timedelta(hours=1)),
            (100, "VP-003", T1 + pd.Timedelta(hours=1)),
        ]
    )
    report = evaluate_by_episode(df, scores, arrivals)
    assert report.n_raw_episodes_evaluated == 1  # NO 3
    assert report.n_positive_rows == 3


def test_two_different_episodes_count_as_two() -> None:
    df = _test_df([("VP-001", T1, 1), ("VP-002", T2, 1)])
    scores = np.array([0.9, 0.9])
    arrivals = _arrivals(
        [
            (100, "VP-001", T1 + pd.Timedelta(hours=1)),
            (200, "VP-002", T2 + pd.Timedelta(hours=1)),
        ]
    )
    report = evaluate_by_episode(df, scores, arrivals)
    assert report.n_raw_episodes_evaluated == 2


def test_hit_at_k_uses_best_rank_across_the_episodes_rows() -> None:
    """Si un episodio toca 2 celdas y una queda en rank 1 y otra en rank 10,
    el episodio "acierta" en Top-5 (basta con UNA celda bien puesta)."""
    df = _test_df(
        [
            ("VP-001", T1, 1),  # rank 1 (mejor score)
            ("VP-002", T1, 1),  # rank peor
        ]
        + [(f"VP-{i:03d}", T1, 0) for i in range(3, 12)]  # relleno para que existan 10 celdas
    )
    scores = np.array([0.99, 0.05] + [0.5 - i * 0.01 for i in range(9)])
    arrivals = _arrivals(
        [
            (100, "VP-001", T1 + pd.Timedelta(hours=1)),
            (100, "VP-002", T1 + pd.Timedelta(hours=1)),
        ]
    )
    report = evaluate_by_episode(df, scores, arrivals, k_values=(1, 5))
    assert report.rank_by_episode[100] == 1
    assert report.hit_at_k[1] == 1.0
    assert report.hit_at_k[5] == 1.0


def test_n_positive_rows_counts_rows_not_row_event_pairs_when_two_events_qualify() -> None:
    """Auditoría 06-09-2026: una fila puede tener DOS event_id calificando
    dentro de la misma ventana (confirmado en datos reales — VP-002,
    VP-027, etc., dos arribos a <6h de diferencia en la misma celda).
    `n_positive_rows` debe seguir contando 1 fila, no 2, aunque
    `link_positive_rows_to_episodes` genere un outcome por cada event_id."""
    df = _test_df([("VP-001", T1, 1)])
    scores = np.array([0.9])
    arrivals = _arrivals(
        [
            (100, "VP-001", T1 + pd.Timedelta(hours=1)),  # dos eventos distintos
            (200, "VP-001", T1 + pd.Timedelta(hours=2)),  # califican para la MISMA fila
        ]
    )
    report = evaluate_by_episode(df, scores, arrivals)
    assert report.n_raw_episodes_evaluated == 2  # ambos eventos sí cuentan
    assert report.n_positive_rows == 1  # pero es UNA sola fila positiva


def test_no_positives_returns_empty_report() -> None:
    df = _test_df([("VP-001", T1, 0)])
    scores = np.array([0.5])
    arrivals = _arrivals([])
    report = evaluate_by_episode(df, scores, arrivals)
    assert report.n_raw_episodes_evaluated == 0
    assert report.mean_rank is None


def test_largest_episode_fraction_flags_domination() -> None:
    df = _test_df([("VP-001", T1, 1), ("VP-002", T1, 1), ("VP-003", T2, 1)])
    arrivals = _arrivals(
        [
            (100, "VP-001", T1 + pd.Timedelta(hours=1)),
            (100, "VP-002", T1 + pd.Timedelta(hours=1)),
            (200, "VP-003", T2 + pd.Timedelta(hours=1)),
        ]
    )
    fraction, dominant = largest_episode_fraction(df, arrivals)
    assert dominant == 100
    assert fraction == 2 / 3


def test_largest_episode_fraction_with_no_positives() -> None:
    df = _test_df([("VP-001", T1, 0)])
    fraction, dominant = largest_episode_fraction(df, _arrivals([]))
    assert fraction == 0.0
    assert dominant is None
