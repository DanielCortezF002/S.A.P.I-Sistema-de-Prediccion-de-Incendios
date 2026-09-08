"""Herramienta de diagnóstico por fila (sección 21 de la auditoría
06-09-2026): dado `(cell_id, forecast_time)`, reconstruye en un solo
diccionario legible TODO lo que explica esa fila — sin recalcular nada,
solo leyendo las columnas ya presentes en `temporal_dataset_h6.parquet`.

Objetivo: que cualquier fila del dataset se pueda auditar a mano, una por
una, sin tener que reconstruir el pipeline completo.
"""

from __future__ import annotations

import pandas as pd


class RowNotFoundError(KeyError):
    pass


def explain_row(dataset: pd.DataFrame, cell_id: str, forecast_time: pd.Timestamp) -> dict:
    """Devuelve un diccionario explicando la fila `(cell_id, forecast_time)`.

    Lanza `RowNotFoundError` si la combinación no existe (en vez de
    devolver `None` o una fila vacía en silencio) y `AssertionError` si
    hay más de una fila (violaría la unicidad esperada de la clave —
    ver `test_cell_forecast_time_pair_is_unique`).
    """
    match = dataset[(dataset["cell_id"] == cell_id) & (dataset["forecast_time"] == pd.Timestamp(forecast_time))]
    if match.empty:
        raise RowNotFoundError(f"No hay fila para (cell_id={cell_id!r}, forecast_time={forecast_time!r})")
    assert len(match) == 1, f"(cell_id, forecast_time) no es única: {len(match)} filas encontradas"
    row = match.iloc[0]

    return {
        "identidad": {"cell_id": row["cell_id"], "forecast_time": row["forecast_time"]},
        "target": {
            "excluded": bool(row["excluded"]),
            "excluded_reason": None if pd.isna(row["excluded_reason"]) else row["excluded_reason"],
            "eligible_for_training": bool(row["eligible_for_training"]),
            "target": None if pd.isna(row["target"]) else int(row["target"]),
            "target_window": (row["target_window_start"], row["target_window_end"]),
            "target_event_id": None if pd.isna(row["target_event_id"]) else int(row["target_event_id"]),
            "target_timestamp": None if pd.isna(row["target_timestamp"]) else row["target_timestamp"],
        },
        "meteo_actual": {
            "estacion": "330007 (Rodelillo)",
            "momento_observacion": row["meteo_actual_momento"],
            "delta_minutos_vs_forecast_time": row["meteo_actual_delta_minutos"],
            "missing": bool(row["meteo_actual_missing"]),
            "temp": row["meteo_actual_temp"],
            "hr": row["meteo_actual_hr"],
            "viento": row["meteo_actual_viento"],
            "regla_30_30_30": row["meteo_actual_regla_30_30_30"],
            "meteo_age_hours": row["meteo_age_hours"],
        },
        "meteo_lags": {
            f"{h}h": {
                "momento": row[f"meteo_lag_{h}h_momento"],
                "missing": bool(row[f"meteo_lag_{h}h_missing"]),
                "temp": row[f"meteo_lag_{h}h_temp"],
                "hr": row[f"meteo_lag_{h}h_hr"],
                "viento": row[f"meteo_lag_{h}h_viento"],
                "regla_30_30_30": row[f"meteo_lag_{h}h_regla_30_30_30"],
            }
            for h in (6, 12, 24, 48)
        },
        "historial_firms": {
            "count_previo": row["historial_firms_count"],
            "dias_desde_ultimo_evento": (
                None if pd.isna(row["dias_desde_ultimo_evento"]) else row["dias_desde_ultimo_evento"]
            ),
            "dias_desde_ultimo_evento_missing": bool(row["dias_desde_ultimo_evento_missing"]),
            "ultimo_evento_momento": (
                None if pd.isna(row["historial_ultimo_evento_momento"]) else row["historial_ultimo_evento_momento"]
            ),
        },
        "topografia": {
            "elevacion": row["elevacion"],
            "pendiente": row["pendiente"],
            "orientacion": row["orientacion"],
            "dem_disponible": bool(row["dem_disponible"]),
        },
    }


def format_explanation(explanation: dict) -> str:
    lines = []
    for section, fields in explanation.items():
        lines.append(f"[{section}]")
        if isinstance(fields, dict):
            for k, v in fields.items():
                lines.append(f"  {k}: {v}")
        else:
            lines.append(f"  {fields}")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cell_id")
    parser.add_argument("forecast_time")
    parser.add_argument("--dataset", type=Path, default=Path("data/processed/temporal_dataset_h6.parquet"))
    args = parser.parse_args()

    ds = pd.read_parquet(args.dataset)
    explanation = explain_row(ds, args.cell_id, pd.Timestamp(args.forecast_time))
    print(format_explanation(explanation))
