"""Tabla de trazabilidad de episodios crudos positivos (sección 6 de la
auditoría 06-09-2026).

Para cada `target_event_id` que dispara al menos una fila positiva en
`temporal_dataset_h6.parquet`, reporta: primer arribo real, cuántas filas
(cell_id, forecast_time) positivas dispara, qué celdas toca y en cuántos
`forecast_time` distintos aparece. No es una tabla de "incendios
independientes" — `event_id` es la construcción algorítmica de
`assign_episodes()` (radio 2km / gap 6h), ver docstring de
`src/procesamiento/episodes.py`.

Uso:
    python scripts/build_event_traceability_table.py [--dataset PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = REPO_ROOT / "data" / "processed" / "temporal_dataset_h6.parquet"
DEFAULT_OUT = REPO_ROOT / "reports" / "event_traceability_h6.csv"


def build_table(dataset: pd.DataFrame) -> pd.DataFrame:
    positives = dataset[dataset["target"] == 1].copy()
    if positives.empty:
        return pd.DataFrame(
            columns=[
                "target_event_id", "first_arrival", "n_positive_rows",
                "n_forecast_times", "n_cells", "cells", "fecha_calendario",
            ]
        )
    positives["fecha_calendario"] = positives["target_timestamp"].dt.strftime("%Y-%m-%d")
    table = (
        positives.groupby("target_event_id")
        .agg(
            first_arrival=("target_timestamp", "min"),
            n_positive_rows=("cell_id", "size"),
            n_forecast_times=("forecast_time", "nunique"),
            cells=("cell_id", lambda s: ",".join(sorted(set(s)))),
            fecha_calendario=("fecha_calendario", "first"),
        )
        .reset_index()
    )
    table["n_cells"] = table["cells"].str.count(",") + 1
    table = table.sort_values("first_arrival").reset_index(drop=True)
    return table[
        ["target_event_id", "first_arrival", "fecha_calendario", "n_positive_rows", "n_forecast_times", "n_cells", "cells"]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    dataset = pd.read_parquet(args.dataset)
    table = build_table(dataset)

    args.out.parent.mkdir(exist_ok=True)
    table.to_csv(args.out, index=False)

    print(table.to_string(index=False))
    print(f"\n{len(table)} raw episodes (target_event_id) generan {table['n_positive_rows'].sum()} filas positivas.")
    print(f"Escrito {args.out}")


if __name__ == "__main__":
    main()
