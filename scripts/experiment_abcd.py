"""Experimento A/B/C/D — riesgo relativo de nueva detección FIRMS en T→T+h.

⚠️ RESULTADOS PRELIMINARES, NO CIENTÍFICOS. Ver `resultados["AVISO"]`.

Corrección de nomenclatura (06-09-2026, ver docs/matriz-riesgo.md): este
script decía antes "episodios independientes". Es impreciso — `event_id`
es una construcción del algoritmo de clustering (`assign_episodes`, radio
2km/gap 6h), no una verdad de terreno. Se intentó una heurística de
colapso adicional por timestamp idéntico y se DESCARTÓ: produce grupos con
incendios hasta 112 km de distancia entre sí (misma pasada satelital, no
el mismo fuego) — ver `episode_evaluation.py` para el detalle. Por eso este
script reporta `n_raw_episodes_evaluated` (lo que el algoritmo produce),
nunca "independientes", y no ofrece un tercer nivel "evaluation_case" sin
evidencia externa que lo respalde.

Pregunta científica: dada la información disponible antes de T, ¿podemos
ordenar las celdas por riesgo relativo de recibir una nueva detección FIRMS
durante (T, T+h]?

Validación: walk-forward por bloque temporal real. NO usa `train_test_split`
aleatorio.

Modelos, según diseño aprobado (sin `cell_id` como feature en ninguno):
  A = historial_firms_count + dias_desde_ultimo_evento
  B = A + meteo_actual (temp/hr/viento/regla_30_30_30)
  C = B + lags meteorológicos reales (6h/12h/24h/48h)
  D = C + topografía (elevación/pendiente/orientación)

Modelo: `HistGradientBoostingClassifier` — soporta NaN nativamente
(verificado en `tests/test_experiment_abcd_contract.py` con un fixture
real). Se eligió por esto, no por desempeño: la versión anterior
(RandomForest + `fillna(0.0)`) disfrazaba "sin dato meteorológico" como si
fuera una observación real de 0°C. `_prep_xy` no imputa nada — hay un test
de regresión permanente que lo comprueba.

Evaluación en DOS capas separadas, nunca combinadas en un número único:
  - por FILA (PR-AUC, ROC-AUC, precision@K, recall@K, Brier);
  - por EPISODIO RAW (`episode_evaluation.py`) — hit@K/rank por `event_id`.

Cada fold reporta además `event_support_status` (INSUFFICIENT/LIMITED/
ADEQUATE) — criterio metodológico del proyecto, no una ley estadística
universal (documentado en el propio umbral).

Baselines ingenuos: azar, prevalencia (climatología), historial crudo (sin
entrenar, solo el conteo histórico como score directo).

Salida: reports/experiment_abcd_h{horizon}_results.json
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from src.procesamiento.episodes import assign_episodes, first_arrival_by_cell
from src.procesamiento.episode_evaluation import evaluate_by_episode, largest_episode_fraction

warnings.filterwarnings("ignore", category=UserWarning)

REPO_ROOT = Path(__file__).resolve().parent.parent
RANDOM_STATE = 42
FIRES_CSV = REPO_ROOT / "data" / "processed" / "nasa_firms_2021-08-30_2026-08-30.csv"

# Umbrales de "soporte de evento" — NO son una ley estadística universal, son
# un criterio metodológico de ESTE proyecto (no derivado de una prueba de
# poder estadístico), documentado explícitamente porque el propio volumen
# de datos disponible no permite derivarlos con más rigor: el dataset
# completo tiene 26 raw episodes que disparan al menos una fila positiva
# por desempate (n_positive_raw_episodes) — o 31 si se cuenta la unión de
# todo evento que calificaría sin desempatar (n_positive_raw_episodes_
# any_qualifying), ver manifest de build_temporal_dataset.py. ADEQUATE es
# aspiracional: ningún fold de esta corrida lo alcanza hoy.
EVENT_SUPPORT_THRESHOLDS = {"INSUFFICIENT_MAX": 4, "LIMITED_MAX": 19}  # ADEQUATE: >= 20


def event_support_status(n_raw_episodes: int) -> str:
    if n_raw_episodes <= EVENT_SUPPORT_THRESHOLDS["INSUFFICIENT_MAX"]:
        return "INSUFFICIENT"
    if n_raw_episodes <= EVENT_SUPPORT_THRESHOLDS["LIMITED_MAX"]:
        return "LIMITED"
    return "ADEQUATE"


FEATURES_A = ["historial_firms_count", "dias_desde_ultimo_evento"]
FEATURES_B = FEATURES_A + ["meteo_actual_temp", "meteo_actual_hr", "meteo_actual_viento", "meteo_actual_regla_30_30_30"]
_LAG_COLS = []
for h in (6, 12, 24, 48):
    _LAG_COLS += [f"meteo_lag_{h}h_temp", f"meteo_lag_{h}h_hr", f"meteo_lag_{h}h_viento", f"meteo_lag_{h}h_regla_30_30_30"]
FEATURES_C = FEATURES_B + _LAG_COLS
FEATURES_D = FEATURES_C + ["elevacion", "pendiente", "orientacion"]

MODELOS = {"A": FEATURES_A, "B": FEATURES_B, "C": FEATURES_C, "D": FEATURES_D}


def _prep_xy(df: pd.DataFrame, features: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    """SIN imputación de ningún tipo — NaN entra y sale como NaN.

    `dias_desde_ultimo_evento` en NaN significa "nunca hubo arribo antes de
    T en esta celda" (información real, ver `temporal_features.py`); un NaN
    en `meteo_*` significa "sin lectura real dentro de tolerancia" (hueco de
    cobertura). Ambos se dejan como NaN — `HistGradientBoostingClassifier`
    aprende una dirección de split explícita para "falta este dato" en cada
    caso, no hay razón para tratarlos distinto acá con una constante.
    Ver `tests/test_experiment_abcd_contract.py::test_prep_xy_never_imputes_nan`.

    Sección 5 de la auditoría 06-09-2026: falla explícitamente si recibe
    filas `excluded=True` o `eligible_for_training=False` — antes de este
    guard, una fila así habría reventado más adelante con un
    `ValueError: Cannot convert non-finite values (NA or inf) to integer`
    genérico de pandas al hacer `.astype(int)` sobre un `target=NaN`
    (fallo real, pero sin decir POR QUÉ esa fila no debía estar ahí). El
    chequeo solo se aplica si esas columnas están presentes — un `df` de
    solo-features (como en los fixtures de prueba) las omite legítimamente.
    """
    if "excluded" in df.columns and df["excluded"].any():
        n = int(df["excluded"].sum())
        raise ValueError(
            f"_prep_xy recibió {n} fila(s) con excluded=True — estas filas tienen "
            "target=None (ni positivo ni negativo, celda en cooldown) y nunca deben "
            "entrar a entrenamiento ni evaluación. Filtra con "
            "df[df['eligible_for_training']] antes de llamar a _prep_xy."
        )
    if "eligible_for_training" in df.columns and not df["eligible_for_training"].all():
        n = int((~df["eligible_for_training"]).sum())
        raise ValueError(
            f"_prep_xy recibió {n} fila(s) con eligible_for_training=False. "
            "Filtra con df[df['eligible_for_training']] antes de llamar a _prep_xy."
        )
    if df["target"].isna().any():
        n = int(df["target"].isna().sum())
        raise ValueError(
            f"_prep_xy recibió {n} fila(s) con target=NaN sin columna 'excluded' para "
            "explicar por qué — esto no debería pasar nunca en el pipeline nuevo "
            "(ver target_builder.build_targets: target es 0, 1, o la fila está excluded)."
        )
    x = df[features].copy()
    y = df["target"].astype(int)
    return x, y


def _rank_metrics(y_true: np.ndarray, scores: np.ndarray, forecast_times: pd.Series, k_values=(3, 5)) -> dict:
    df = pd.DataFrame({"y": y_true, "score": scores, "T": forecast_times.values})
    result = {}
    for k in k_values:
        precisions, recalls = [], []
        for _, group in df.groupby("T"):
            if group["y"].sum() == 0:
                continue
            top_k = group.sort_values("score", ascending=False).head(k)
            hits = int(top_k["y"].sum())
            precisions.append(hits / min(k, len(group)))
            recalls.append(hits / int(group["y"].sum()))
        result[f"precision@{k}"] = float(np.mean(precisions)) if precisions else None
        result[f"recall@{k}"] = float(np.mean(recalls)) if recalls else None
        result[f"n_forecast_times_con_positivo_evaluados@{k}"] = len(precisions)
    return result


def evaluate_row_level(y_true: pd.Series, scores: np.ndarray, forecast_times: pd.Series) -> dict:
    """Resultado por FILA — "¿qué tan bien prioriza celdas individuales?".
    Categoría: RESULTADO EXPLORATORIO (ver sección 9 del pedido de auditoría),
    no evidencia de capacidad predictiva por sí solo."""
    y = y_true.values
    n_pos = int(y.sum())
    metrics: dict = {"n_test": len(y), "n_positivos_test_filas": n_pos}
    if n_pos == 0 or n_pos == len(y):
        metrics["pr_auc"] = None
        metrics["roc_auc"] = None
        metrics["nota"] = "Sin variación de clase en el test — PR-AUC/ROC-AUC NOT_EVALUABLE, no 0 ni 100%."
    else:
        metrics["pr_auc"] = float(average_precision_score(y, scores))
        metrics["roc_auc"] = float(roc_auc_score(y, scores))

    spread = scores.max() - scores.min()
    scores_01 = (scores - scores.min()) / spread if spread > 0 else np.full_like(scores, 0.5, dtype=float)
    metrics["brier_score"] = float(brier_score_loss(y, scores_01))
    metrics.update(_rank_metrics(y, scores, forecast_times))
    return metrics


def evaluate_episode_level(test: pd.DataFrame, scores: np.ndarray, arrivals: pd.DataFrame) -> dict:
    """Resultado por EPISODIO RAW (`event_id`) — nunca "por incendio
    independiente". Si no hay positivos, todos los campos quedan `None`
    (NOT_EVALUABLE), nunca 0.0 ni 1.0 inventados."""
    report = evaluate_by_episode(test, scores, arrivals, k_values=(3, 5))
    if report.n_raw_episodes_evaluated == 0:
        return {
            "n_raw_episodes_evaluated": 0,
            "n_filas_positivas": 0,
            "hit_at_k": None,
            "mean_rank": None,
            "median_rank": None,
            "event_support_status": event_support_status(0),
            "nota": "NOT_EVALUABLE — sin episodios positivos en este test.",
        }
    return {
        "n_raw_episodes_evaluated": report.n_raw_episodes_evaluated,
        "n_filas_positivas": report.n_positive_rows,
        "hit_at_k": report.hit_at_k,
        "n_episodios_hit_at_k": report.n_episodes_hit_at_k,
        "mean_rank": report.mean_rank,
        "median_rank": report.median_rank,
        "event_support_status": event_support_status(report.n_raw_episodes_evaluated),
    }


def run_fold(train: pd.DataFrame, test: pd.DataFrame, arrivals: pd.DataFrame) -> dict:
    fold_result: dict = {"fila": {}, "episodio": {}}

    fraction, dominant_event = largest_episode_fraction(test, arrivals)
    fold_result["concentracion_episodio_dominante"] = {
        "fraction": fraction,
        "dominant_event_id": dominant_event,
        "warning": fraction > 0.5,
    }

    scorers: dict[str, np.ndarray] = {}
    rng = np.random.default_rng(RANDOM_STATE)
    scorers["baseline_azar"] = rng.random(len(test))
    scorers["baseline_prevalencia"] = np.full(len(test), train["target"].mean())
    scorers["baseline_historial_crudo_sin_entrenar"] = test["historial_firms_count"].fillna(0).to_numpy(dtype=float)

    fold_result["nan_diagnostics"] = {}
    for nombre, features in MODELOS.items():
        # Sección 14-15 de la auditoría 06-09-2026: traza real (no solo de
        # fixture) del NaN antes/después de `_prep_xy` y en lo que
        # efectivamente recibe `fit`/`predict_proba`. `_prep_xy` no
        # transforma columnas de feature (solo selecciona + castea target),
        # así que n_nan_before == n_nan_after_prep_xy por construcción — se
        # reportan ambos igual para que quede verificado, no asumido.
        n_nan_before_train = int(train[features].isna().sum().sum())
        n_nan_before_test = int(test[features].isna().sum().sum())
        x_train, y_train = _prep_xy(train, features)
        x_test, _ = _prep_xy(test, features)
        fold_result["nan_diagnostics"][nombre] = {
            "n_nan_before_prep_xy_train": n_nan_before_train,
            "n_nan_after_prep_xy_train": int(x_train.isna().sum().sum()),
            "n_nan_before_prep_xy_test": n_nan_before_test,
            "n_nan_after_prep_xy_test": int(x_test.isna().sum().sum()),
            "n_nan_train_por_columna": {c: int(x_train[c].isna().sum()) for c in features},
            "n_nan_test_por_columna": {c: int(x_test[c].isna().sum()) for c in features},
        }
        if y_train.nunique() < 2:
            fold_result["fila"][f"modelo_{nombre}"] = {"error": "train sin ambas clases, no se puede entrenar"}
            fold_result["episodio"][f"modelo_{nombre}"] = {"error": "train sin ambas clases"}
            continue
        clf = HistGradientBoostingClassifier(random_state=RANDOM_STATE, max_depth=4, class_weight="balanced")
        clf.fit(x_train, y_train)
        # n_nan que efectivamente entra a predict_proba (post-fit, mismo
        # x_test de arriba — se re-lee de x_test.isna() para no asumir que
        # sklearn no lo tocó; ver test_histgradientboosting_accepts_nan_end_to_end).
        fold_result["nan_diagnostics"][nombre]["n_nan_en_x_test_al_momento_de_predict"] = int(
            x_test.isna().sum().sum()
        )
        scorers[f"modelo_{nombre}"] = clf.predict_proba(x_test)[:, 1]

    for nombre, scores in scorers.items():
        fold_result["fila"][nombre] = evaluate_row_level(test["target"], scores, test["forecast_time"])
        fold_result["episodio"][nombre] = evaluate_episode_level(test, scores, arrivals)

    return fold_result


def main() -> None:
    horizon = 6
    dataset_path = REPO_ROOT / "data" / "processed" / f"temporal_dataset_h{horizon}.parquet"
    df = pd.read_parquet(dataset_path)
    df = df[df["eligible_for_training"]].reset_index(drop=True)
    df["mes"] = df["forecast_time"].dt.strftime("%Y-%m")

    fires = pd.read_csv(FIRES_CSV)
    episodes = assign_episodes(fires)
    arrivals = first_arrival_by_cell(episodes)

    bloques = ["2022-01", "2022-12", "2024-02", "2025-02"]
    df = df[df["mes"].isin(bloques)].reset_index(drop=True)

    resultados = {
        "AVISO": (
            "PRELIMINAR — NO presentar como resultado científico. Distingue "
            "explícitamente tres tipos de resultado: (1) TÉCNICO (el código "
            "corre, causalidad verificada — ver suite de tests, no este "
            "archivo); (2) EXPLORATORIO (los números de este archivo: "
            "PR-AUC, ROC-AUC, hit@K); (3) EVIDENCIA DE CAPACIDAD PREDICTIVA "
            "— esto NO se puede leer directamente de (2); requiere el "
            "criterio de éxito acordado (≥2 particiones con mejora "
            "consistente, soporte ADEQUATE), que hoy ningún fold cumple. "
            "'event_id' es una construcción del algoritmo de clustering, "
            "NO un incendio confirmado en terreno."
        ),
        "horizon_hours": horizon,
        "bloques_temporales": bloques,
        "event_support_thresholds": EVENT_SUPPORT_THRESHOLDS,
        "folds": [],
    }

    for i in range(1, len(bloques)):
        test_mes = bloques[i]
        train_meses = bloques[:i]
        train = df[df["mes"].isin(train_meses)]
        test = df[df["mes"] == test_mes]

        n_positive_dates = test.loc[test["target"] == 1, "forecast_time"].dt.date.nunique()
        fraction, dominant_event = largest_episode_fraction(test, arrivals)

        fold = {
            "fold": i,
            "train_start": str(train["forecast_time"].min()) if not train.empty else None,
            "train_end": str(train["forecast_time"].max()) if not train.empty else None,
            "test_start": str(test["forecast_time"].min()) if not test.empty else None,
            "test_end": str(test["forecast_time"].max()) if not test.empty else None,
            "train_meses": train_meses,
            "test_mes": test_mes,
            "n_train": len(train),
            "n_test": len(test),
            "n_positivos_train_filas": int(train["target"].sum()),
            "n_positivos_test_filas": int(test["target"].sum()),
            "n_positive_dates_test": int(n_positive_dates),
            "largest_episode_fraction_test": fraction,
            "resultados": run_fold(train, test, arrivals),
        }
        resultados["folds"].append(fold)
        n_ep = fold["resultados"]["episodio"].get("modelo_D", {}).get("n_raw_episodes_evaluated", "?")
        estado = fold["resultados"]["episodio"].get("modelo_D", {}).get("event_support_status", "?")
        print(
            f"Fold {i}: train={train_meses} (n={len(train)}, pos_filas={fold['n_positivos_train_filas']}) "
            f"-> test={test_mes} (n={len(test)}, pos_filas={fold['n_positivos_test_filas']}, "
            f"raw_episodes={n_ep}, event_support={estado})"
        )

    out_path = REPO_ROOT / "reports" / f"experiment_abcd_h{horizon}_results.json"
    out_path.write_text(json.dumps(resultados, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nEscrito {out_path}")


if __name__ == "__main__":
    main()
