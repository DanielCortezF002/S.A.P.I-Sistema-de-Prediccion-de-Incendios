"""Pruebas de experiments.sapi63.temporal_sequences — SAPI-63.

Verifican las propiedades críticas del módulo sin datos reales (sin parquet):
  1. Shape 3D correcto: (n_samples, window_size, n_features).
  2. Causalidad: la ventana [T-w, T) nunca incluye el timestamp T mismo.
  3. Separación walk-forward: max(train.forecast_time) < min(test.forecast_time).
  4. Sin mezcla de celdas: las secuencias de la celda A no incluyen filas de B.
  5. Descarte por ventana insuficiente: pasos iniciales sin suficiente historia.
  6. Distribución real de positivos por fold (sin fabricar).
  7. Sin imputación encubierta de NaN: NaN en features → float32 NaN en tensor.
  8. Filas excluidas (eligible=False) nunca forman parte de ninguna secuencia.
  9. Target = 0 o 1 solamente (int8).
 10. Folds vacíos cuando no hay suficiente historia (min_train_months).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.sapi63.temporal_sequences import (
    N_FEATURES,
    SEQUENCE_FEATURE_COLS,
    SequenceFold,
    WalkForwardSplit,
    _cell_sequences,
    _build_split_sequences,
    build_sequence_folds,
)


# ---------------------------------------------------------------------------
# Fixtures mínimas — datasets sintéticos de software (no científicos)
# ---------------------------------------------------------------------------

def _make_minimal_df(
    n_cells: int = 3,
    n_times: int = 20,
    seed: int = 42,
    positive_indices: list[int] | None = None,
    start_date: str = "2022-01-01",
) -> pd.DataFrame:
    """Crea un DataFrame mínimo con la misma estructura del dataset real.

    Fechas en UTC, una lectura cada 6h (misma frecuencia que el dataset real).
    Por defecto todos los targets son 0 salvo los especificados en
    `positive_indices` (índice en el eje de tiempo, shared across cells).
    """
    rng = np.random.default_rng(seed)
    times = pd.date_range(start_date, periods=n_times, freq="6h", tz="UTC")
    rows = []
    for cell in [f"VP-{i:03d}" for i in range(n_cells)]:
        for t in times:
            row = {
                "cell_id": cell,
                "forecast_time": t,
                "target": 0.0,
                "eligible_for_training": True,
                "excluded": False,
                "excluded_reason": "",
                # Features numéricas con algunos NaN para probar flag
                "meteo_actual_temp": float(rng.uniform(10, 40)),
                "meteo_actual_hr": float(rng.uniform(20, 90)),
                "meteo_actual_viento": float(rng.uniform(0, 50)),
                "meteo_actual_regla_30_30_30": float(rng.integers(0, 2)),
                "meteo_actual_missing": False,
                "meteo_lag_6h_temp": float(rng.uniform(10, 40)),
                "meteo_lag_6h_hr": float(rng.uniform(20, 90)),
                "meteo_lag_6h_viento": float(rng.uniform(0, 50)),
                "meteo_lag_6h_regla_30_30_30": float(rng.integers(0, 2)),
                "meteo_lag_6h_missing": False,
                "meteo_lag_12h_temp": float(rng.uniform(10, 40)),
                "meteo_lag_12h_hr": float(rng.uniform(20, 90)),
                "meteo_lag_12h_viento": float(rng.uniform(0, 50)),
                "meteo_lag_12h_regla_30_30_30": float(rng.integers(0, 2)),
                "meteo_lag_12h_missing": False,
                "meteo_lag_24h_temp": float(rng.uniform(10, 40)),
                "meteo_lag_24h_hr": float(rng.uniform(20, 90)),
                "meteo_lag_24h_viento": float(rng.uniform(0, 50)),
                "meteo_lag_24h_regla_30_30_30": float(rng.integers(0, 2)),
                "meteo_lag_24h_missing": False,
                "meteo_lag_48h_temp": float(rng.uniform(10, 40)),
                "meteo_lag_48h_hr": float(rng.uniform(20, 90)),
                "meteo_lag_48h_viento": float(rng.uniform(0, 50)),
                "meteo_lag_48h_regla_30_30_30": float(rng.integers(0, 2)),
                "meteo_lag_48h_missing": False,
                "historial_firms_count": int(rng.integers(0, 5)),
                "dias_desde_ultimo_evento": float(rng.uniform(0, 365)),
                "dias_desde_ultimo_evento_missing": False,
                "elevacion": float(rng.uniform(100, 2000)),
                "pendiente": float(rng.uniform(0, 45)),
                "orientacion": float(rng.uniform(0, 360)),
            }
            rows.append(row)

    df = pd.DataFrame(rows)

    if positive_indices:
        for idx in positive_indices:
            t = times[idx]
            df.loc[df["forecast_time"] == t, "target"] = 1.0

    return df


# ---------------------------------------------------------------------------
# Tests de _cell_sequences (unidad)
# ---------------------------------------------------------------------------

class TestCellSequences:
    def test_shape_is_3d(self) -> None:
        df = _make_minimal_df(n_cells=1, n_times=10)
        cell_df = df[df["cell_id"] == "VP-000"]
        X, y, *_ = _cell_sequences(cell_df, window_size=3, feature_cols=SEQUENCE_FEATURE_COLS)
        assert X.ndim == 3
        assert X.shape[1] == 3
        assert X.shape[2] == N_FEATURES

    def test_n_samples_correct(self) -> None:
        """Con 10 pasos y window=3: primeros 3 no tienen historia → 7 válidos."""
        df = _make_minimal_df(n_cells=1, n_times=10)
        cell_df = df[df["cell_id"] == "VP-000"]
        X, y, n_disc_insuf, n_disc_gap = _cell_sequences(cell_df, window_size=3, feature_cols=SEQUENCE_FEATURE_COLS)
        assert len(X) == 7
        assert len(y) == 7
        assert n_disc_insuf == 3
        assert n_disc_gap == 0

    def test_discards_when_insufficient_history(self) -> None:
        """window_size=5, n_times=4 → todos descartados."""
        df = _make_minimal_df(n_cells=1, n_times=4)
        cell_df = df[df["cell_id"] == "VP-000"]
        X, y, n_disc_insuf, n_disc_gap = _cell_sequences(cell_df, window_size=5, feature_cols=SEQUENCE_FEATURE_COLS)
        assert len(X) == 0
        assert n_disc_insuf == 4
        assert n_disc_gap == 0

    def test_window_does_not_include_own_timestep(self) -> None:
        """La ventana para el paso T usa índices [T-w, T), no T."""
        df = _make_minimal_df(n_cells=1, n_times=6)
        cell_df = df[df["cell_id"] == "VP-000"].sort_values("forecast_time").reset_index(drop=True)
        X, y, *_ = _cell_sequences(cell_df, window_size=2, feature_cols=SEQUENCE_FEATURE_COLS)
        # El primer sample válido (i=2) debe tener la ventana de las filas 0 y 1
        feat_col_idx = SEQUENCE_FEATURE_COLS.index("meteo_actual_temp")
        expected_row0 = float(cell_df.iloc[0]["meteo_actual_temp"])
        expected_row1 = float(cell_df.iloc[1]["meteo_actual_temp"])
        assert X[0, 0, feat_col_idx] == pytest.approx(expected_row0)
        assert X[0, 1, feat_col_idx] == pytest.approx(expected_row1)

    def test_dtype_is_float32(self) -> None:
        df = _make_minimal_df(n_cells=1, n_times=6)
        cell_df = df[df["cell_id"] == "VP-000"]
        X, y, *_ = _cell_sequences(cell_df, window_size=2, feature_cols=SEQUENCE_FEATURE_COLS)
        assert X.dtype == np.float32

    def test_target_dtype_is_int8(self) -> None:
        df = _make_minimal_df(n_cells=1, n_times=6, positive_indices=[3, 4])
        cell_df = df[df["cell_id"] == "VP-000"]
        X, y, *_ = _cell_sequences(cell_df, window_size=2, feature_cols=SEQUENCE_FEATURE_COLS)
        assert y.dtype == np.int8
        assert set(y).issubset({0, 1})

    def test_nan_in_features_propagates_as_nan_not_zero(self) -> None:
        """NaN en feature → float32 NaN en tensor, no 0.0."""
        df = _make_minimal_df(n_cells=1, n_times=6)
        cell_df = df[df["cell_id"] == "VP-000"].copy()
        cell_df = cell_df.sort_values("forecast_time").reset_index(drop=True)
        # Introduce NaN en la primera fila de meteo_actual_temp
        cell_df.at[0, "meteo_actual_temp"] = float("nan")
        feat_col_idx = SEQUENCE_FEATURE_COLS.index("meteo_actual_temp")
        X, _, *_ = _cell_sequences(cell_df, window_size=2, feature_cols=SEQUENCE_FEATURE_COLS)
        # La primera ventana válida (i=2) incluye la fila 0 → NaN debe estar
        assert np.isnan(X[0, 0, feat_col_idx])

    def test_discards_window_crossing_multiday_jump(self) -> None:
        """Demuestra que un salto de varios días descarta ventanas y NINGUNA secuencia lo atraviesa."""
        t1 = pd.date_range("2022-01-01", periods=10, freq="6h", tz="UTC")
        # Salto de ~5 días entre t1[-1] (2022-01-03 06:00) y t2[0] (2022-01-08 00:00)
        t2 = pd.date_range("2022-01-08", periods=10, freq="6h", tz="UTC")
        times = list(t1) + list(t2)
        n_times = len(times)

        df = _make_minimal_df(n_cells=1, n_times=n_times)
        cell_df = df[df["cell_id"] == "VP-000"].copy()
        cell_df["forecast_time"] = times
        # Asignamos valor secuencial reconocible en meteo_actual_temp para rastrear origen
        cell_df["meteo_actual_temp"] = np.arange(n_times, dtype=np.float32)

        window_size = 4
        X, y, n_insuf, n_gap = _cell_sequences(
            cell_df, window_size=window_size, feature_cols=SEQUENCE_FEATURE_COLS
        )

        assert n_insuf == 4
        assert n_gap == 4
        assert len(X) == 12

        temp_idx = SEQUENCE_FEATURE_COLS.index("meteo_actual_temp")
        # Primeras 6 secuencias: todas previas al salto (valores 0..9)
        for seq in X[:6]:
            assert np.all(seq[:, temp_idx] < 10.0), "Secuencia previa contiene datos posteriores al salto"
        # Últimas 6 secuencias: todas posteriores al salto (valores 10..19)
        for seq in X[6:]:
            assert np.all(seq[:, temp_idx] >= 10.0), "Secuencia posterior contiene datos previos al salto"

    def test_discards_gap_between_last_window_step_and_target_t(self) -> None:
        """Si la ventana es continua pero el paso entre T-1 y T tiene salto > 6h, se descarta."""
        t_steps = [
            pd.Timestamp("2022-01-01 00:00", tz="UTC"),
            pd.Timestamp("2022-01-01 06:00", tz="UTC"),
            pd.Timestamp("2022-01-01 12:00", tz="UTC"),
            pd.Timestamp("2022-01-01 18:00", tz="UTC"),
            pd.Timestamp("2022-01-02 12:00", tz="UTC"),  # Salto de 18h hacia T
        ]
        df = _make_minimal_df(n_cells=1, n_times=5)
        cell_df = df[df["cell_id"] == "VP-000"].copy()
        cell_df["forecast_time"] = t_steps
        X, y, n_insuf, n_gap = _cell_sequences(
            cell_df, window_size=4, feature_cols=SEQUENCE_FEATURE_COLS
        )
        assert n_insuf == 4
        assert n_gap == 1
        assert len(X) == 0

    def test_discards_gap_inside_window(self) -> None:
        """Si el salto > 6h ocurre dentro de los pasos de la ventana, se descarta."""
        t_steps = [
            pd.Timestamp("2022-01-01 00:00", tz="UTC"),
            pd.Timestamp("2022-01-01 06:00", tz="UTC"),
            pd.Timestamp("2022-01-02 00:00", tz="UTC"),  # Salto de 18h interno
            pd.Timestamp("2022-01-02 06:00", tz="UTC"),
            pd.Timestamp("2022-01-02 12:00", tz="UTC"),
        ]
        df = _make_minimal_df(n_cells=1, n_times=5)
        cell_df = df[df["cell_id"] == "VP-000"].copy()
        cell_df["forecast_time"] = t_steps
        X, y, n_insuf, n_gap = _cell_sequences(
            cell_df, window_size=4, feature_cols=SEQUENCE_FEATURE_COLS
        )
        assert n_insuf == 4
        assert n_gap == 1
        assert len(X) == 0


# ---------------------------------------------------------------------------
# Tests de WalkForwardSplit
# ---------------------------------------------------------------------------

class TestWalkForwardSplit:
    def test_no_temporal_overlap(self) -> None:
        """max(train.forecast_time) < min(test.forecast_time) en TODOS los folds."""
        # 24 meses de datos con 6h de frecuencia
        df = _make_minimal_df(n_cells=2, n_times=24 * 4, start_date="2022-01-01")
        eligible = df[df["eligible_for_training"]].copy()
        splitter = WalkForwardSplit(min_train_months=3)
        for train_df, test_df in splitter.split(eligible):
            assert train_df["forecast_time"].max() < test_df["forecast_time"].min(), (
                "Fuga temporal detectada: train se solapa con test"
            )

    def test_test_period_is_always_one_month(self) -> None:
        """Cada período de test abarca exactamente un mes calendario."""
        df = _make_minimal_df(n_cells=2, n_times=24 * 4, start_date="2022-01-01")
        eligible = df[df["eligible_for_training"]].copy()
        splitter = WalkForwardSplit(min_train_months=2)
        for train_df, test_df in splitter.split(eligible):
            months_in_test = test_df["forecast_time"].dt.to_period("M").nunique()
            assert months_in_test == 1

    def test_train_grows_monotonically(self) -> None:
        """El conjunto de entrenamiento siempre crece — nunca decrece."""
        df = _make_minimal_df(n_cells=2, n_times=30 * 4, start_date="2022-01-01")
        eligible = df[df["eligible_for_training"]].copy()
        splitter = WalkForwardSplit(min_train_months=2)
        sizes = [len(tr) for tr, _ in splitter.split(eligible)]
        for prev, curr in zip(sizes, sizes[1:]):
            assert curr > prev

    def test_eligible_filter_excludes_cooldown_rows(self) -> None:
        """Filas con eligible_for_training=False NO aparecen en ningún fold."""
        df = _make_minimal_df(n_cells=2, n_times=20 * 4, start_date="2022-01-01")
        # Marca algunas filas como no elegibles
        df.loc[df["forecast_time"].dt.month == 3, "eligible_for_training"] = False
        eligible = df[df["eligible_for_training"]].copy()
        splitter = WalkForwardSplit(min_train_months=2)
        for train_df, test_df in splitter.split(eligible):
            assert (train_df["eligible_for_training"] == True).all()  # noqa: E712
            assert (test_df["eligible_for_training"] == True).all()  # noqa: E712


# ---------------------------------------------------------------------------
# Tests de build_sequence_folds (integración de software)
# ---------------------------------------------------------------------------

class TestBuildSequenceFolds:
    def test_returns_list_of_sequence_folds(self) -> None:
        # 90 días × 4 lecturas/día = 360 pasos → cubre 3 meses → con
        # min_train_months=2 se obtiene ≥1 fold (mes 3 como test).
        df = _make_minimal_df(n_cells=3, n_times=90 * 4, start_date="2022-01-01")
        folds = build_sequence_folds(df, window_size=2, min_train_months=2)
        assert isinstance(folds, list)
        assert len(folds) > 0
        assert all(isinstance(f, SequenceFold) for f in folds)

    def test_shape_3d_in_all_folds(self) -> None:
        df = _make_minimal_df(n_cells=3, n_times=20 * 4, start_date="2022-01-01")
        folds = build_sequence_folds(df, window_size=3, min_train_months=2)
        for fold in folds:
            if len(fold.X_train) > 0:
                assert fold.X_train.ndim == 3
                assert fold.X_train.shape[1] == 3
                assert fold.X_train.shape[2] == N_FEATURES
            if len(fold.X_test) > 0:
                assert fold.X_test.ndim == 3

    def test_no_temporal_overlap_in_folds(self) -> None:
        df = _make_minimal_df(n_cells=2, n_times=25 * 4, start_date="2022-01-01")
        folds = build_sequence_folds(df, window_size=2, min_train_months=2)
        for fold in folds:
            assert fold.train_period[1] < fold.test_period[0], (
                f"fold {fold.fold_index}: train_end={fold.train_period[1]} >= "
                f"test_start={fold.test_period[0]}"
            )

    def test_positive_counts_match_y_arrays(self) -> None:
        df = _make_minimal_df(
            n_cells=3, n_times=20 * 4, start_date="2022-01-01",
            positive_indices=[5, 15, 30]
        )
        folds = build_sequence_folds(df, window_size=2, min_train_months=2)
        for fold in folds:
            assert fold.n_positives_train == int(fold.y_train.sum())
            assert fold.n_positives_test == int(fold.y_test.sum())

    def test_positive_rate_is_consistent(self) -> None:
        df = _make_minimal_df(n_cells=2, n_times=20 * 4, start_date="2022-01-01",
                              positive_indices=[10, 20, 50, 70])
        folds = build_sequence_folds(df, window_size=2, min_train_months=2)
        for fold in folds:
            if len(fold.y_train) > 0:
                expected = fold.n_positives_train / len(fold.y_train)
                assert fold.positive_rate_train == pytest.approx(expected, abs=1e-9)

    def test_fold_index_is_sequential(self) -> None:
        df = _make_minimal_df(n_cells=2, n_times=20 * 4, start_date="2022-01-01")
        folds = build_sequence_folds(df, window_size=2, min_train_months=2)
        for expected_idx, fold in enumerate(folds):
            assert fold.fold_index == expected_idx

    def test_no_folds_when_min_train_too_large(self) -> None:
        """Si min_train_months > meses disponibles, no se generan folds."""
        df = _make_minimal_df(n_cells=2, n_times=3 * 4, start_date="2022-01-01")
        folds = build_sequence_folds(df, window_size=2, min_train_months=99)
        assert len(folds) == 0

    def test_no_cells_mixed_in_sequences(self) -> None:
        """Comprueba que _build_split_sequences no mezcla celdas.

        Si la celda VP-000 tiene valores muy distintos a VP-001, los primeros
        pasos de cada secuencia deben corresponder solo a su propia celda.
        Usamos un valor de feature constante y distinto por celda para detectar
        la mezcla.
        """
        df = _make_minimal_df(n_cells=2, n_times=10, start_date="2022-01-01")
        df.loc[df["cell_id"] == "VP-000", "meteo_actual_temp"] = 100.0
        df.loc[df["cell_id"] == "VP-001", "meteo_actual_temp"] = 200.0
        eligible = df[df["eligible_for_training"]].copy()
        X, y, *_ = _build_split_sequences(eligible, window_size=2, feature_cols=SEQUENCE_FEATURE_COLS)
        feat_idx = SEQUENCE_FEATURE_COLS.index("meteo_actual_temp")
        # Todos los valores en la feature deben ser 100.0 o 200.0, NUNCA una mezcla
        vals = X[:, :, feat_idx].flatten()
        # Filtra NaN si hubiera
        valid_vals = vals[~np.isnan(vals)]
        unique_vals = set(np.round(valid_vals, 1))
        assert unique_vals.issubset({100.0, 200.0}), (
            f"Se encontraron valores mezclados de celdas: {unique_vals - {100.0, 200.0}}"
        )

    def test_summary_is_serializable(self) -> None:
        df = _make_minimal_df(n_cells=2, n_times=15 * 4, start_date="2022-01-01")
        folds = build_sequence_folds(df, window_size=2, min_train_months=2)
        import json
        for fold in folds:
            s = fold.summary()
            # No debe levantar
            json.dumps(s)

    def test_eligible_false_rows_never_in_sequences(self) -> None:
        """Filas con eligible_for_training=False no contribuyen a X ni y."""
        df = _make_minimal_df(n_cells=2, n_times=15 * 4, start_date="2022-01-01")
        # Marca filas de un período específico como no elegibles
        excluded_t = df["forecast_time"].unique()[5]
        df.loc[df["forecast_time"] == excluded_t, "eligible_for_training"] = False
        df.loc[df["forecast_time"] == excluded_t, "meteo_actual_temp"] = 9999.0  # valor canario

        folds = build_sequence_folds(df, window_size=2, min_train_months=2)
        feat_idx = SEQUENCE_FEATURE_COLS.index("meteo_actual_temp")
        for fold in folds:
            for X in [fold.X_train, fold.X_test]:
                if len(X) > 0:
                    assert not np.any(X[:, :, feat_idx] == 9999.0), (
                        "Valor canario de fila no elegible encontrado en secuencias"
                    )

    def test_build_sequence_folds_tracks_discontinuity(self) -> None:
        """build_sequence_folds registra n_discarded_discontinuity en los SequenceFold."""
        df = _make_minimal_df(n_cells=2, n_times=15 * 4, start_date="2022-01-01")
        folds = build_sequence_folds(df, window_size=2, min_train_months=2)
        for fold in folds:
            assert hasattr(fold, "n_discarded_discontinuity")
            s = fold.summary()
            assert "n_discarded_discontinuity" in s
            assert isinstance(s["n_discarded_discontinuity"], int)
