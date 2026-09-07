"""Evaluación a nivel de episodio RAW — separada de la evaluación por fila.

Motivación (auditoría 06-09-2026): 23 de 46 filas positivas del dataset
`temporal_dataset_h6` vienen del mismo `event_id` (2024-02-03). Una métrica
por fila (PR-AUC, ROC-AUC fila a fila) trata esas 23 filas como si fueran
23 casos distintos.

Precisión de nomenclatura importante (corregida 06-09-2026, ver
docs/matriz-riesgo.md): "episodio" acá significa exclusivamente `event_id`
de `assign_episodes()` — una construcción del algoritmo de clustering
(radio 2km / gap 6h), NO un incendio confirmado en terreno ni una unidad
de independencia estadística verificada externamente. Se evaluó una
heurística adicional (colapsar por timestamp de primera detección
idéntico) y se descartó: produce grupos con incendios hasta 112 km de
distancia entre sí — el timestamp compartido resulta ser un mal proxy de
independencia (es solo la misma pasada satelital, no el mismo fuego). No
existe hoy una unidad más fina y defendible que `event_id`; por eso este
módulo no ofrece un tercer nivel "evaluation_case" — inventarlo sin una
fuente externa (contorno real del incendio, reporte institucional) sería
fabricar independencia, no medirla.

No reemplaza la evaluación por fila — la complementa. Reportar ambas por
separado, nunca combinarlas en un solo número (instrucción explícita).

Nota de reconciliación de cifras (auditoría 06-09-2026, sección 7-9):
`n_raw_episodes_evaluated` de este módulo cuenta TODO `event_id` que
calificaría para alguna fila positiva del conjunto evaluado — es la
semántica "any qualifying" (equivalente a
`n_positive_raw_episodes_any_qualifying` del manifest de
`build_temporal_dataset.py`, hoy 31 sobre el dataset completo), NO la
semántica "un disparador por fila" que usa la columna `target_event_id`
del dataset (`n_positive_raw_episodes`, hoy 26): en las filas donde dos
eventos califican a la vez, `target_event_id` registra solo el de arribo
más temprano, mientras que este módulo evalúa el rank de la celda para
AMBOS eventos (tiene sentido: para responder "¿el ranking hubiera
detectado a tiempo la llegada de este evento?" da igual cuál de los dos
eventos empatados se mire — ambos comparten la misma celda/rank). Por eso
`n_raw_episodes_evaluated` sobre el dataset completo puede ser mayor que
`n_positive_raw_episodes` del manifest — no es un bug, son dos preguntas
distintas y ambas están documentadas con su propio nombre.

Formato exacto de `evaluate_by_episode` (para no dejarlo a interpretación
verbal):
1. Por cada fila con `target=1`, se buscan TODOS los `event_id` de
   `arrivals` cuyo `first_arrival` cae en `(target_window_start,
   target_window_end]` para esa `cell_id` (puede haber más de uno).
2. El `rank` de esa fila es su posición por score descendente ENTRE TODAS
   las filas (positivas y negativas) que comparten su mismo
   `forecast_time` — 1 = score más alto ese instante, empates resueltos
   con `method="min"` (rank compartido = el mejor de los empatados).
3. Un mismo `event_id` puede aparecer en varias filas (varias celdas y/o
   varios `forecast_time`, si el episodio siguió generando arribos). Su
   `rank_by_episode[event_id]` es el MEJOR (menor) rank logrado en
   CUALQUIERA de esas filas — "el ranking encontró al menos una vez a
   este episodio dentro del Top-K" es la pregunta que hit@K responde, no
   "el ranking encontró cada aparición del episodio".
4. `hit_at_k[k]` = fracción de `event_id` distintos (evaluados sobre
   `rank_by_episode`, es decir, YA colapsados a 1 por episodio) cuyo mejor
   rank es `<= k`. El denominador es "episodios", nunca "filas".
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class EpisodeOutcome:
    """Una fila positiva vista desde el `event_id` (episodio raw) que la produjo."""

    event_id: int
    cell_id: str
    forecast_time: pd.Timestamp
    rank: int  # 1 = celda de mayor score entre las evaluadas en ese forecast_time
    n_cells_ranked: int
    score: float


@dataclass
class EpisodeEvaluationReport:
    """`n_raw_episodes_evaluated`: cantidad de `event_id` distintos detrás de
    los positivos evaluados — NO "incendios independientes". Ver docstring
    del módulo."""

    n_raw_episodes_evaluated: int
    n_positive_rows: int
    outcomes: list[EpisodeOutcome] = field(default_factory=list)
    hit_at_k: dict[int, float] = field(default_factory=dict)
    n_episodes_hit_at_k: dict[int, int] = field(default_factory=dict)
    mean_rank: float | None = None
    median_rank: float | None = None
    rank_by_episode: dict[int, int] = field(default_factory=dict)  # mejor rank logrado por episodio


def link_positive_rows_to_episodes(
    test_df: pd.DataFrame,
    scores: np.ndarray,
    arrivals: pd.DataFrame,
) -> list[EpisodeOutcome]:
    """Para cada fila positiva del test, encuentra el/los `event_id` reales
    que la explican (mismo criterio que `target_builder`: arrival en
    `(window_start, window_end]` para esa celda) y calcula el rank de esa
    celda dentro del ranking de su propio `forecast_time`.

    `test_df` debe traer `cell_id`, `forecast_time`, `target_window_start`,
    `target_window_end`, `target`. `scores` es un array alineado 1:1 con
    las filas de `test_df` (mismo orden, mismo largo).
    """
    df = test_df.reset_index(drop=True).copy()
    df["_score"] = scores

    # Rank dentro de cada forecast_time (1 = mayor score).
    df["_rank"] = df.groupby("forecast_time")["_score"].rank(ascending=False, method="min").astype(int)
    n_ranked = df.groupby("forecast_time")["_score"].transform("count")
    df["_n_cells_ranked"] = n_ranked

    outcomes: list[EpisodeOutcome] = []
    positives = df[df["target"] == 1]
    for _, row in positives.iterrows():
        match = arrivals[
            (arrivals["cell_id"] == row["cell_id"])
            & (arrivals["first_arrival"] > row["target_window_start"])
            & (arrivals["first_arrival"] <= row["target_window_end"])
        ]
        for event_id in match["event_id"].unique():
            outcomes.append(
                EpisodeOutcome(
                    event_id=int(event_id),
                    cell_id=str(row["cell_id"]),
                    forecast_time=row["forecast_time"],
                    rank=int(row["_rank"]),
                    n_cells_ranked=int(row["_n_cells_ranked"]),
                    score=float(row["_score"]),
                )
            )
    return outcomes


def evaluate_by_episode(
    test_df: pd.DataFrame,
    scores: np.ndarray,
    arrivals: pd.DataFrame,
    k_values: tuple[int, ...] = (3, 5),
) -> EpisodeEvaluationReport:
    """Agrega los outcomes por episodio: un episodio "acierta" en Top-K si
    ALGUNA de sus filas positivas (puede tocar más de una celda/forecast_time)
    quedó rankeada dentro de las K de mayor score en ese instante — "al
    menos una celda correctamente colocada", tal como se pidió.
    """
    outcomes = link_positive_rows_to_episodes(test_df, scores, arrivals)
    if not outcomes:
        return EpisodeEvaluationReport(n_raw_episodes_evaluated=0, n_positive_rows=0)

    best_rank_by_episode: dict[int, int] = {}
    for o in outcomes:
        best_rank_by_episode[o.event_id] = min(best_rank_by_episode.get(o.event_id, o.rank), o.rank)

    ranks = list(best_rank_by_episode.values())
    hit_at_k = {k: float(np.mean([r <= k for r in ranks])) for k in k_values}
    n_hit_at_k = {k: int(sum(r <= k for r in ranks)) for k in k_values}

    return EpisodeEvaluationReport(
        n_raw_episodes_evaluated=len(best_rank_by_episode),
        # (cell_id, forecast_time) — NO (event_id, cell_id, forecast_time).
        # Auditoría 06-09-2026: en filas donde más de un evento califica
        # dentro de la misma ventana (confirmado en datos reales: 6 filas
        # de temporal_dataset_h6), la fila sigue siendo UNA fila positiva
        # aunque `link_positive_rows_to_episodes` la reporte una vez por
        # cada event_id que calificó — contar por event_id sobrestimaría
        # n_positive_rows frente al `n_positive_rows` real del dataset.
        n_positive_rows=len({(o.cell_id, o.forecast_time) for o in outcomes}),
        outcomes=outcomes,
        hit_at_k=hit_at_k,
        n_episodes_hit_at_k=n_hit_at_k,
        mean_rank=float(np.mean(ranks)),
        median_rank=float(np.median(ranks)),
        rank_by_episode=best_rank_by_episode,
    )


def largest_episode_fraction(test_df: pd.DataFrame, arrivals: pd.DataFrame) -> tuple[float, int | None]:
    """Fracción de las filas positivas del test explicada por el episodio
    más grande — para el chequeo de "WARNING — TEST EVENT CONCENTRATION".

    Devuelve (fraccion, event_id_dominante). Si no hay positivos, (0.0, None).
    """
    positives = test_df[test_df["target"] == 1]
    if positives.empty:
        return 0.0, None

    counts: dict[int, int] = {}
    for _, row in positives.iterrows():
        match = arrivals[
            (arrivals["cell_id"] == row["cell_id"])
            & (arrivals["first_arrival"] > row["target_window_start"])
            & (arrivals["first_arrival"] <= row["target_window_end"])
        ]
        for event_id in match["event_id"].unique():
            counts[event_id] = counts.get(event_id, 0) + 1

    if not counts:
        return 0.0, None
    dominant = max(counts, key=counts.get)
    return counts[dominant] / len(positives), dominant
