"""Agrupación de detecciones FIRMS en episodios (SAPI — target futuro).

Varias detecciones FIRMS pueden representar el mismo incendio: múltiples
píxeles del mismo foco, o el mismo foco visto en pasadas satelitales
sucesivas mientras sigue activo. Sin agrupar, el sistema podría "aprender"
a reconocer la misma información del mismo incendio contada varias veces
(fuga por duplicado) — el propio `scripts/exploracion_r_etiqueta_01.py` ya
detectó y excluyó este problema a mano (`n_duplicados_evento`); este módulo
lo generaliza a un mecanismo reutilizable.

Definición de "evento" (encadenamiento por cercanía al último punto del
evento, no single-linkage exhaustivo contra todo su historial — más simple
de razonar y suficiente para el volumen de datos del proyecto; documentado
así a propósito, no es un descuido):

Una detección se une a un evento abierto si está a `<= radio_km` de la
detección MÁS RECIENTE de ese evento y a `<= horas_max` de su timestamp.
Si no cumple ambas condiciones con ningún evento abierto, abre uno nuevo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

import pandas as pd

from src.geo.grid import assign_cell
from src.procesamiento.meteo_fire_joiner import ignition_timestamp
from src.procesamiento.station_catalog import haversine_km

DEFAULT_RADIUS_KM = 2.0
DEFAULT_MAX_GAP = timedelta(hours=6)


@dataclass
class _OpenEvent:
    event_id: int
    last_lat: float
    last_lon: float
    last_ts: pd.Timestamp
    detections_idx: list[int] = field(default_factory=list)


def assign_episodes(
    fires: pd.DataFrame,
    radius_km: float = DEFAULT_RADIUS_KM,
    max_gap: timedelta = DEFAULT_MAX_GAP,
) -> pd.DataFrame:
    """Agrega `event_id`, `ignition_ts` y `cell_id` a un DataFrame de
    detecciones FIRMS crudas (columnas: latitude, longitude, acq_date,
    acq_time).

    `cell_id` es `None` para detecciones fuera de la grilla canónica — se
    conservan en la salida (no se descartan acá) para que el caller decida
    si le importan; normalmente se filtran antes de construir targets.
    """
    out = fires.copy()
    out["ignition_ts"] = out.apply(
        lambda r: ignition_timestamp(str(r["acq_date"]), r["acq_time"]), axis=1
    )
    out = out.sort_values("ignition_ts", kind="stable").reset_index(drop=True)
    out["cell_id"] = out.apply(lambda r: assign_cell(float(r["latitude"]), float(r["longitude"])), axis=1)

    open_events: list[_OpenEvent] = []
    event_ids: list[int] = [0] * len(out)
    next_event_id = 1

    for i, row in out.iterrows():
        lat, lon, ts = float(row["latitude"]), float(row["longitude"]), row["ignition_ts"]

        # Cerrar eventos cuyo último punto ya excede max_gap respecto a esta
        # detección (todas las posteriores también lo excederán, por el
        # orden temporal, así que se pueden descartar de la búsqueda).
        open_events = [e for e in open_events if (ts - e.last_ts) <= max_gap]

        match = None
        for e in open_events:
            if haversine_km(lat, lon, e.last_lat, e.last_lon) <= radius_km:
                match = e
                break

        if match is None:
            match = _OpenEvent(event_id=next_event_id, last_lat=lat, last_lon=lon, last_ts=ts)
            open_events.append(match)
            next_event_id += 1
        else:
            match.last_lat, match.last_lon, match.last_ts = lat, lon, ts

        match.detections_idx.append(i)
        event_ids[i] = match.event_id

    out["event_id"] = event_ids
    return out


def first_arrival_by_cell(episodes: pd.DataFrame) -> pd.DataFrame:
    """Por cada (event_id, cell_id), el timestamp de la PRIMERA detección de
    ese evento que cayó en esa celda — no el primer timestamp global del
    evento, si se propagó entre celdas.

    Esta es la unidad que alimenta el target (ver `target_builder.py`):
    permite que un incendio que se propaga de VP-005 a VP-006 dos horas
    después cuente como "llegada nueva" en cada celda en su propio momento,
    sin recontar el mismo evento como positivo repetido en cada ventana
    sucesiva mientras sigue activo en la misma celda.
    """
    valid = episodes[episodes["cell_id"].notna()]
    if valid.empty:
        return pd.DataFrame(columns=["event_id", "cell_id", "first_arrival"])
    return (
        valid.groupby(["event_id", "cell_id"], as_index=False)["ignition_ts"]
        .min()
        .rename(columns={"ignition_ts": "first_arrival"})
    )


def build_episode_catalog(episodes: pd.DataFrame) -> pd.DataFrame:
    """Ficha por episodio: la unidad de evaluación independiente.

    Una fila por `event_id`, con lo necesario para auditar si el dataset de
    entrenamiento está dominado por pocos incendios grandes (ver
    docs/matriz-riesgo.md, auditoría del pipeline nuevo): cuántas celdas
    tocó, cuánto duró, cuántas detecciones tuvo. `affected_cells` solo
    cuenta detecciones dentro de la grilla canónica (`cell_id` no nulo);
    un episodio fuera de la grilla completa queda con `n_celdas_afectadas=0`.
    """
    if episodes.empty:
        return pd.DataFrame(
            columns=[
                "event_id",
                "episode_start",
                "episode_end",
                "n_detecciones",
                "n_celdas_afectadas",
                "celdas_afectadas",
            ]
        )

    rows: list[dict] = []
    for event_id, group in episodes.groupby("event_id"):
        celdas = sorted(group["cell_id"].dropna().unique().tolist())
        rows.append(
            {
                "event_id": event_id,
                "episode_start": group["ignition_ts"].min(),
                "episode_end": group["ignition_ts"].max(),
                "n_detecciones": len(group),
                "n_celdas_afectadas": len(celdas),
                "celdas_afectadas": celdas,
            }
        )
    return pd.DataFrame(rows).sort_values("episode_start").reset_index(drop=True)
