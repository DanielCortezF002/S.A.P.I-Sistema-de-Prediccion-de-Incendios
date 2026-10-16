"""Secuencias temporales causales por celda — SAPI-63.

Transforma el dataset flat (cell_id, forecast_time) → features en tensores
3D (n_samples, window_size, n_features) aptos para arquitecturas secuenciales
tipo LSTM/RNN.

Invariantes de integridad que este módulo preserva:
  1. CAUSALIDAD: la ventana [T-window, T) usa SOLO features disponibles en o
     antes de T. Nunca incluye el target de T ni información futura.
  2. SIN MEZCLA DE CELDAS: cada muestra pertenece a una sola celda. La grilla
     50-celda NO se mezcla en el eje de secuencia — las secuencias son
     temporales dentro de una celda, nunca espaciales.
  3. SIN IMPUTACIÓN ENCUBIERTA: si una celda tiene menos de `window_size`
     pasos anteriores en el período de entrenamiento, la muestra se descarta
     (no se rellena con ceros). El descarte se documenta en el report.
  4. WALK-FORWARD SIN FUGA: el split garantiza que el último timestamp de
     train < primer timestamp de test para CADA fold. No hay mezcla temporal.
  5. SOLO FILAS ELEGIBLES: filas con `eligible_for_training=False` (cooldown
     exclusions) se descartan antes de construir secuencias — nunca forman
     parte de una ventana, ni como input ni como target.

Nota sobre el desbalance real 1:3393:
  Con 107 positivos en 362 883 filas elegibles, la mayoría de las ventanas
  serán negativas. Este módulo NO aplica oversampling ni undersampling —
  eso es decisión del consumidor. El report de cada fold incluye la
  distribución real de positivos para que el consumidor la vea antes de
  entrenar.

No forma parte del pipeline de Modelo D ni lo modifica. Es un módulo
paralelo, experimental, coherente con ADR-006.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

import numpy as np
import pandas as pd

# Features numéricas que se incluyen en la secuencia. Se excluyen:
#   - columnas de timestamp (_momento, forecast_time, etc.)
#   - columnas de control (excluded, eligible_for_training, target_*)
#   - columnas de diagnóstico (meteo_age_hours, *_delta_minutos, dem_disponible)
# Se incluyen flags booleanos de missing (son información real, no imputación).
SEQUENCE_FEATURE_COLS: list[str] = [
    # Meteo actual
    "meteo_actual_temp",
    "meteo_actual_hr",
    "meteo_actual_viento",
    "meteo_actual_regla_30_30_30",
    "meteo_actual_missing",
    # Meteo lag 6h
    "meteo_lag_6h_temp",
    "meteo_lag_6h_hr",
    "meteo_lag_6h_viento",
    "meteo_lag_6h_regla_30_30_30",
    "meteo_lag_6h_missing",
    # Meteo lag 12h
    "meteo_lag_12h_temp",
    "meteo_lag_12h_hr",
    "meteo_lag_12h_viento",
    "meteo_lag_12h_regla_30_30_30",
    "meteo_lag_12h_missing",
    # Meteo lag 24h
    "meteo_lag_24h_temp",
    "meteo_lag_24h_hr",
    "meteo_lag_24h_viento",
    "meteo_lag_24h_regla_30_30_30",
    "meteo_lag_24h_missing",
    # Meteo lag 48h
    "meteo_lag_48h_temp",
    "meteo_lag_48h_hr",
    "meteo_lag_48h_viento",
    "meteo_lag_48h_regla_30_30_30",
    "meteo_lag_48h_missing",
    # Historial FIRMS (as-of T)
    "historial_firms_count",
    "dias_desde_ultimo_evento",
    "dias_desde_ultimo_evento_missing",
    # Topografía (estática por celda — igual en todos los pasos de la ventana,
    # pero se incluye para que la arquitectura pueda usar attention si lo desea)
    "elevacion",
    "pendiente",
    "orientacion",
]

N_FEATURES: int = len(SEQUENCE_FEATURE_COLS)


@dataclass(frozen=True)
class SequenceFold:
    """Un fold walk-forward con sus arrays 3D y metadatos de distribución.

    Atributos:
        fold_index: índice 0-based del fold.
        X_train: (n_train, window_size, n_features) float32.
        y_train: (n_train,) int8  — 0/1, nunca NaN (filas excluidas ya
                 descartadas antes de construir el fold).
        X_test:  (n_test,  window_size, n_features) float32.
        y_test:  (n_test,) int8.
        train_period: (inicio, fin) de forecast_time en train (UTC).
        test_period:  (inicio, fin) de forecast_time en test (UTC).
        n_positives_train: conteo real de positivos en y_train.
        n_positives_test:  conteo real de positivos en y_test.
        n_discarded_insufficient_window: muestras descartadas por falta de
            historia (celda sin suficientes pasos anteriores en train/test).
        positive_rate_train: proporción real positivos/total en train.
        positive_rate_test:  proporción real positivos/total en test.
        window_size: ventana de pasos temporales incluidos.
        n_features: número de features por paso.
    """

    fold_index: int
    X_train: np.ndarray
    y_train: np.ndarray
    X_test: np.ndarray
    y_test: np.ndarray
    train_period: tuple[pd.Timestamp, pd.Timestamp]
    test_period: tuple[pd.Timestamp, pd.Timestamp]
    n_positives_train: int
    n_positives_test: int
    n_discarded_insufficient_window: int
    positive_rate_train: float
    positive_rate_test: float
    window_size: int
    n_features: int
    n_discarded_discontinuity: int = 0

    def summary(self) -> dict:
        """Resumen serializable para reportes/notebooks."""
        return {
            "fold_index": self.fold_index,
            "train_period": [str(self.train_period[0]), str(self.train_period[1])],
            "test_period": [str(self.test_period[0]), str(self.test_period[1])],
            "X_train_shape": list(self.X_train.shape),
            "X_test_shape": list(self.X_test.shape),
            "n_positives_train": self.n_positives_train,
            "n_positives_test": self.n_positives_test,
            "n_discarded_insufficient_window": self.n_discarded_insufficient_window,
            "n_discarded_discontinuity": self.n_discarded_discontinuity,
            "positive_rate_train": round(self.positive_rate_train, 6),
            "positive_rate_test": round(self.positive_rate_test, 6),
            "imbalance_ratio_train": (
                round((1 - self.positive_rate_train) / self.positive_rate_train, 1)
                if self.positive_rate_train > 0
                else float("inf")
            ),
            "window_size": self.window_size,
            "n_features": self.n_features,
        }


def _cell_sequences(
    cell_df: pd.DataFrame,
    window_size: int,
    feature_cols: list[str],
    max_step_hours: float = 6.0,
) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Construye secuencias 3D para UNA celda, ordenadas por forecast_time.

    Para cada paso T en la serie de la celda:
      - Si hay al menos `window_size` pasos ANTERIORES a T (inclusive T-1,
        excluyendo T propio del eje secuencia), construye la secuencia de
        los `window_size` pasos anteriores.
      - Descarta secuencias con saltos temporales > max_step_hours (6h nominal)
        entre pasos consecutivos de la ventana, o entre el último registro de la
        ventana y el target T.
      - El target de la secuencia es el target de T.

    Retorna:
        X: (n_valid, window_size, n_features) float32
        y: (n_valid,) int8
        n_discarded_insufficient: muestras descartadas por falta de historia inicial
        n_discarded_discontinuity: muestras descartadas por saltos > max_step_hours
    """
    cell_df = cell_df.sort_values("forecast_time").reset_index(drop=True)
    n = len(cell_df)
    feat_array = cell_df[feature_cols].to_numpy(dtype=np.float32)
    target_array = cell_df["target"].to_numpy(dtype=np.float32)

    sequences_X = []
    sequences_y = []
    n_discarded_insufficient = 0
    n_discarded_discontinuity = 0

    if n == 0:
        return (
            np.empty((0, window_size, len(feature_cols)), dtype=np.float32),
            np.empty((0,), dtype=np.int8),
            0,
            0,
        )

    # Precomputar pasos validos (delta > 0 y delta <= max_step_hours)
    diffs = cell_df["forecast_time"].diff()
    max_delta = pd.Timedelta(hours=max_step_hours)
    # diffs[0] es NaT -> evalua a False
    valid_step = ((diffs > pd.Timedelta(0)) & (diffs <= max_delta)).to_numpy()

    for i in range(n):
        # La ventana usa los `window_size` pasos anteriores a T (índice i).
        # No incluye el paso i propio — eso sería mirar el instante actual
        # en el eje de secuencia, lo que mezclaría el contexto con el target.
        # Índices de ventana: [i - window_size, i)
        window_start = i - window_size
        if window_start < 0:
            n_discarded_insufficient += 1
            continue

        # Verifica continuidad temporal estricta de todos los pasos:
        # desde (window_start -> window_start + 1) hasta (i - 1 -> i [hacia T])
        # Rango en valid_step: [window_start + 1 : i + 1] (exactamente window_size pasos)
        if not valid_step[window_start + 1 : i + 1].all():
            n_discarded_discontinuity += 1
            continue

        window = feat_array[window_start:i]  # (window_size, n_features)
        sequences_X.append(window)
        sequences_y.append(int(target_array[i]))

    if not sequences_X:
        return (
            np.empty((0, window_size, len(feature_cols)), dtype=np.float32),
            np.empty((0,), dtype=np.int8),
            n_discarded_insufficient,
            n_discarded_discontinuity,
        )

    X = np.stack(sequences_X, axis=0).astype(np.float32)
    y = np.array(sequences_y, dtype=np.int8)
    return X, y, n_discarded_insufficient, n_discarded_discontinuity


@dataclass
class WalkForwardSplit:
    """Separación walk-forward sin fuga temporal.

    Divide el período disponible en bloques mensuales y genera folds
    train→test donde:
      - train = todos los bloques hasta el bloque i-1
      - test  = bloque i
      - max(train.forecast_time) < min(test.forecast_time)  [garantizado]

    Args:
        min_train_months: mínimo de meses en el conjunto de entrenamiento
            antes de generar el primer fold (evita folds con historia
            insignificante).
    """

    min_train_months: int = 12

    def split(
        self,
        df: pd.DataFrame,
    ) -> Iterator[tuple[pd.DataFrame, pd.DataFrame]]:
        """Genera pares (train_df, test_df) con garantía de no-solapamiento.

        El DataFrame `df` debe ser el subconjunto ELIGIBLE (eligible_for_training=True)
        — esta función no filtra por sí misma para dejar la responsabilidad
        explícita al llamador.
        """
        df = df.copy()
        df["_month"] = df["forecast_time"].dt.to_period("M")
        months = sorted(df["_month"].unique())

        for i in range(self.min_train_months, len(months)):
            train_months = months[:i]
            test_month = months[i]

            train_df = df[df["_month"].isin(train_months)].drop(columns=["_month"])
            test_df = df[df["_month"] == test_month].drop(columns=["_month"])

            if train_df.empty or test_df.empty:
                continue

            # Garantía de no-solapamiento — si falla, es un bug del código.
            assert train_df["forecast_time"].max() < test_df["forecast_time"].min(), (
                f"fold {i}: train.max={train_df['forecast_time'].max()} >= "
                f"test.min={test_df['forecast_time'].min()} — fuga temporal detectada"
            )

            yield train_df, test_df


def build_sequence_folds(
    dataset: pd.DataFrame,
    window_size: int = 4,
    feature_cols: list[str] | None = None,
    min_train_months: int = 12,
    max_step_hours: float = 6.0,
) -> list[SequenceFold]:
    """Construye todos los folds walk-forward con arrays 3D.

    Args:
        dataset: el DataFrame del parquet temporal (todas las filas, incluyendo
            las no elegibles — se filtran internamente).
        window_size: número de pasos temporales en la ventana de contexto.
            Con frecuencia de 6h, window_size=4 → 24h de contexto.
        feature_cols: lista de columnas a incluir como features. Por defecto
            usa SEQUENCE_FEATURE_COLS definido en este módulo.
        min_train_months: ver WalkForwardSplit.
        max_step_hours: intervalo temporal máximo permitido entre pasos (6h).

    Returns:
        Lista de SequenceFold, uno por mes de test (con historia suficiente).
    """
    if feature_cols is None:
        feature_cols = SEQUENCE_FEATURE_COLS

    # Solo filas elegibles para construcción de secuencias.
    eligible = dataset[dataset["eligible_for_training"]].copy()
    eligible = eligible.sort_values(["cell_id", "forecast_time"]).reset_index(drop=True)

    splitter = WalkForwardSplit(min_train_months=min_train_months)
    folds: list[SequenceFold] = []

    for fold_idx, (train_df, test_df) in enumerate(splitter.split(eligible)):
        fold_X_train, fold_y_train, train_insuf, train_gap = _build_split_sequences(
            train_df, window_size, feature_cols, max_step_hours=max_step_hours
        )
        fold_X_test, fold_y_test, test_insuf, test_gap = _build_split_sequences(
            test_df, window_size, feature_cols, max_step_hours=max_step_hours
        )

        n_disc_insuf = train_insuf + test_insuf
        n_disc_gap = train_gap + test_gap
        n_pos_train = int(fold_y_train.sum()) if len(fold_y_train) > 0 else 0
        n_pos_test = int(fold_y_test.sum()) if len(fold_y_test) > 0 else 0
        rate_train = n_pos_train / len(fold_y_train) if len(fold_y_train) > 0 else 0.0
        rate_test = n_pos_test / len(fold_y_test) if len(fold_y_test) > 0 else 0.0

        folds.append(
            SequenceFold(
                fold_index=fold_idx,
                X_train=fold_X_train,
                y_train=fold_y_train,
                X_test=fold_X_test,
                y_test=fold_y_test,
                train_period=(
                    train_df["forecast_time"].min(),
                    train_df["forecast_time"].max(),
                ),
                test_period=(
                    test_df["forecast_time"].min(),
                    test_df["forecast_time"].max(),
                ),
                n_positives_train=n_pos_train,
                n_positives_test=n_pos_test,
                n_discarded_insufficient_window=n_disc_insuf,
                n_discarded_discontinuity=n_disc_gap,
                positive_rate_train=rate_train,
                positive_rate_test=rate_test,
                window_size=window_size,
                n_features=len(feature_cols),
            )
        )

    return folds


def _build_split_sequences(
    split_df: pd.DataFrame,
    window_size: int,
    feature_cols: list[str],
    max_step_hours: float = 6.0,
) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Construye secuencias 3D para un split (train o test), celda por celda."""
    all_X: list[np.ndarray] = []
    all_y: list[np.ndarray] = []
    total_insufficient = 0
    total_discontinuity = 0

    for cell_id, cell_df in split_df.groupby("cell_id"):
        X, y, n_insuf, n_disc = _cell_sequences(
            cell_df, window_size, feature_cols, max_step_hours=max_step_hours
        )
        all_X.append(X)
        all_y.append(y)
        total_insufficient += n_insuf
        total_discontinuity += n_disc

    if not all_X or all(len(x) == 0 for x in all_X):
        n_f = len(feature_cols)
        return (
            np.empty((0, window_size, n_f), dtype=np.float32),
            np.empty((0,), dtype=np.int8),
            total_insufficient,
            total_discontinuity,
        )

    X_out = np.concatenate([x for x in all_X if len(x) > 0], axis=0)
    y_out = np.concatenate([y for y in all_y if len(y) > 0], axis=0)
    return X_out, y_out, total_insufficient, total_discontinuity
