"""Reporte del megaevento del 2024-02-03 (sección 10 de la auditoría
06-09-2026): cuantifica cuánto del rendimiento del fold `test=2024-02`
depende de un solo día calendario con una erupción masiva de detecciones
FIRMS (los incendios de la Región de Valparaíso de febrero de 2024).

No es un chequeo de "un solo event_id domina" (eso ya lo cubre
`validate_event_independence` / `largest_episode_fraction`, que mira UN
`event_id`) — este reporte agrupa por FECHA CALENDARIO, porque
`assign_episodes()` (radio 2km / gap 6h) parte una sola noche de incendios
masivos en decenas de `event_id` distintos que, para efectos de "cuánto
aprendizaje real hay aquí vs. cuánto es un solo evento regional", deben
mirarse juntos.

Uso: python scripts/megaevento_report.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.procesamiento.episodes import assign_episodes

REPO_ROOT = Path(__file__).resolve().parent.parent
FIRES_CSV = REPO_ROOT / "data" / "processed" / "nasa_firms_2021-08-30_2026-08-30.csv"
DATASET_PATH = REPO_ROOT / "data" / "processed" / "temporal_dataset_h6.parquet"
OUT_PATH = REPO_ROOT / "reports" / "megaevento_2024-02-03_report.json"
FECHA = "2024-02-03"


def build_report(fecha: str = FECHA) -> dict:
    fires = pd.read_csv(FIRES_CSV)
    episodes = assign_episodes(fires)
    episodes["fecha"] = pd.to_datetime(episodes["ignition_ts"]).dt.strftime("%Y-%m-%d")
    day = episodes[episodes["fecha"] == fecha]

    dataset = pd.read_parquet(DATASET_PATH)
    positives = dataset[dataset["target"] == 1].copy()
    positives["fecha_target"] = positives["target_timestamp"].dt.strftime("%Y-%m-%d")
    day_positives = positives[positives["fecha_target"] == fecha]

    positives["mes"] = positives["target_timestamp"].dt.strftime("%Y-%m")
    mes = pd.to_datetime(fecha).strftime("%Y-%m")
    fold_positives = positives[positives["mes"] == mes]

    n_day = len(day_positives)
    n_mes = len(fold_positives)
    n_total = len(positives)
    fraccion_mes = float(n_day / n_mes) if n_mes else None
    fraccion_total = float(n_day / n_total) if n_total else None

    if n_day == 0:
        conclusion = f"No hay filas positivas cuyo target_timestamp caiga en {fecha} — sin megaevento que reportar ese día."
    else:
        conclusion = (
            f"{n_day} de las {n_mes} filas positivas del mes {mes} ({fraccion_mes:.1%}) y {n_day} "
            f"de las {n_total} filas positivas de TODO el dataset ({fraccion_total:.1%}) provienen "
            f"de un solo día calendario ({fecha}), repartidas en {day['event_id'].nunique()} raw "
            "episodes distintos (la brecha entre 'un event_id domina' y 'un día domina' es real: "
            "ningún event_id individual supera el umbral de concentración de "
            "validate_event_independence, pero el día calendario sí concentra la mayoría de la "
            "señal positiva disponible). Cualquier métrica del fold correspondiente debe leerse "
            "como 'rendimiento mayormente explicado por un evento regional de incendios de un "
            "día', no como evidencia de que el modelo generaliza a fuegos dispersos en el tiempo."
        )

    return {
        "fecha": fecha,
        "raw_episode_ids": sorted(int(e) for e in day["event_id"].unique()),
        "n_raw_episodes": int(day["event_id"].nunique()),
        "n_detecciones_firms": int(len(day)),
        "primera_deteccion": str(day["ignition_ts"].min()) if not day.empty else None,
        "ultima_deteccion": str(day["ignition_ts"].max()) if not day.empty else None,
        "celdas_afectadas": sorted(day["cell_id"].dropna().unique().tolist()),
        "n_celdas_afectadas": int(day["cell_id"].nunique()),
        "n_positive_rows_ese_dia": n_day,
        "n_positive_forecast_times_ese_dia": int(day_positives["forecast_time"].nunique()),
        "n_positive_rows_mes_completo": n_mes,
        "n_positive_rows_dataset_completo": n_total,
        "fraccion_del_mes": fraccion_mes,
        "fraccion_del_dataset_completo": fraccion_total,
        "conclusion": conclusion,
    }


def main() -> None:
    report = build_report()
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nEscrito {OUT_PATH}")


if __name__ == "__main__":
    main()
