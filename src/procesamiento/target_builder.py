"""Target futuro honesto: `deteccion_firms_nueva_ventana_futura`.

Deliberadamente NO se llama `ignicion` ni `incendio_confirmado` — representa
exactamente lo que FIRMS puede observar (una detección satelital nueva),
nada más. Ver docs/matriz-riesgo.md, sección de auditoría 06-09-2026.

target(cell, T, h) = 1  ⟺  ∃ evento E con first_arrival(E, cell) ∈ (T, T+h]
target(cell, T, h) = 0  en cualquier otro caso, salvo que (cell, T) caiga en
                          el período de "cooldown" tras un arribo anterior en
                          esa celda —ahí la fila se EXCLUYE por completo (ni
                          0 ni 1), porque etiquetarla como "sin riesgo"
                          mientras la celda literalmente sigue ardiendo sería
                          tan falso como etiquetarla activa dos veces.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class TargetRow:
    cell_id: str
    forecast_time: pd.Timestamp
    target_window_start: pd.Timestamp
    target_window_end: pd.Timestamp
    target: int
    excluded: bool
    excluded_reason: str | None = None


def build_targets(
    first_arrivals: pd.DataFrame,
    cell_ids: Iterable[str],
    forecast_times: Iterable[pd.Timestamp],
    horizon: timedelta,
    cooldown: timedelta,
) -> pd.DataFrame:
    """Construye una fila `(cell_id, forecast_time)` por cada combinación,
    con su target y, si corresponde, el motivo de exclusión.

    `first_arrivals` es la salida de
    `src.procesamiento.episodes.first_arrival_by_cell` (columnas: event_id,
    cell_id, first_arrival).

    Cada fila con `target=1` lleva además `target_event_id` (el `event_id`
    de `assign_episodes()` cuyo arribo la produjo — si más de un evento
    califica en la misma ventana, se registra el de arribo más temprano,
    desempatando por `event_id` menor) y `target_timestamp` (el momento
    real de ese arribo). Sin esto, el dataset no era auto-auditable: "por
    qué esta fila es target=1" solo se podía responder recalculando
    `assign_episodes()` por fuera y cruzándolo a mano (ver auditoría
    06-09-2026, sección de trazabilidad).
    """
    if first_arrivals.empty or "cell_id" not in first_arrivals.columns:
        arrivals_by_cell: dict[str, pd.DataFrame] = {}
    else:
        arrivals_by_cell = {
            cell: group[["event_id", "first_arrival"]].sort_values("first_arrival")
            for cell, group in first_arrivals.groupby("cell_id")
        }

    _empty_arrivals = pd.DataFrame(
        {"event_id": pd.Series([], dtype="int64"), "first_arrival": pd.Series([], dtype="datetime64[ns, UTC]")}
    )
    rows: list[dict] = []
    for cell_id in cell_ids:
        cell_arrivals = arrivals_by_cell.get(cell_id, _empty_arrivals)
        arrivals = cell_arrivals["first_arrival"]
        for T in forecast_times:
            window_start, window_end = T, T + horizon

            in_cooldown = bool(((arrivals <= T) & (arrivals + cooldown > T)).any())
            if in_cooldown:
                rows.append(
                    {
                        "cell_id": cell_id,
                        "forecast_time": T,
                        "target_window_start": window_start,
                        "target_window_end": window_end,
                        "target": None,
                        "target_event_id": None,
                        "target_timestamp": pd.NaT,
                        "excluded": True,
                        "excluded_reason": "cooldown_evento_activo",
                    }
                )
                continue

            qualifying = cell_arrivals[(arrivals > window_start) & (arrivals <= window_end)]
            has_new_arrival = not qualifying.empty
            triggering = qualifying.sort_values(["first_arrival", "event_id"]).iloc[0] if has_new_arrival else None
            rows.append(
                {
                    "cell_id": cell_id,
                    "forecast_time": T,
                    "target_window_start": window_start,
                    "target_window_end": window_end,
                    "target": int(has_new_arrival),
                    "target_event_id": int(triggering["event_id"]) if triggering is not None else None,
                    "target_timestamp": triggering["first_arrival"] if triggering is not None else pd.NaT,
                    "excluded": False,
                    "excluded_reason": None,
                }
            )
    return pd.DataFrame(rows)
