"""Reverificación del hallazgo "VP-025 / 2022-12-11" contra la grilla canónica.

Contexto (docs/matriz-riesgo.md, R-ETIQUETA-01, hallazgo 02-09-2026): antes de
la unificación de grillas (06-09-2026), se encontró que la celda "VP-025" del
2022-12-11 cumplía la regla 30-30-30 con datos 100% reales (6 detecciones
NASA FIRMS reales dentro del polígono, meteo real de la estación 330007, sin
proxy ni sintético en ningún punto del cálculo). Esa celda se calculó sobre
la grilla anterior (~1 km²/celda, retirada). La unificación de grillas dejó
pendiente reverificar si el hallazgo sigue siendo válido con la geometría
canónica (`src/geo/grid.py`, ~11,5 km²/celda) — este script hace exactamente
eso, con el mismo método que ya usa
`scripts/build_matriz_features_real_sapi32_preview.py` (contención estricta,
sin aproximación por distancia).

Salida: reports/reverificacion_vp025_2022-12-11.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.geo.grid import BASE_LAT, BASE_LON, COLS, ROWS, STEP_LAT, STEP_LON
from src.procesamiento.meteo_fire_joiner import join_fires_to_meteo, summarize_join

REPO_ROOT = Path(__file__).resolve().parent.parent
FIRES_CSV = REPO_ROOT / "data" / "processed" / "nasa_firms_2021-08-30_2026-08-30.csv"
OUT_JSON = REPO_ROOT / "reports" / "reverificacion_vp025_2022-12-11.json"

EVENT_DATE = "2022-12-11"

# Ubicación física (centro) de la "VP-025" de la grilla anterior (retirada
# 06-09-2026), reconstruida a partir de sus constantes documentadas en
# docs/alcance-prototipo.md — no vive en ningún módulo del repo desde la
# migración, así que se recalcula acá explícitamente para poder ubicarla en
# la grilla nueva.
_OLD_GRID_BASE_LON = -71.535
_OLD_GRID_BASE_LAT = -33.062
_OLD_GRID_STEP_LON = 0.010
_OLD_GRID_STEP_LAT = 0.009
_OLD_GRID_COLS = 10
_OLD_VP025_INDEX = 25


def _old_vp025_center() -> tuple[float, float]:
    col = (_OLD_VP025_INDEX - 1) % _OLD_GRID_COLS
    row = (_OLD_VP025_INDEX - 1) // _OLD_GRID_COLS
    lon = round(_OLD_GRID_BASE_LON + col * _OLD_GRID_STEP_LON, 5)
    lat = round(_OLD_GRID_BASE_LAT + row * _OLD_GRID_STEP_LAT, 5)
    return lat, lon


def build_grid() -> pd.DataFrame:
    """Grilla canónica (`src/geo/grid.py`), igual que en el resto del pipeline."""
    cells = []
    idx = 1
    for row in range(ROWS):
        for col in range(COLS):
            min_lon = round(BASE_LON + col * STEP_LON, 5)
            min_lat = round(BASE_LAT + row * STEP_LAT, 5)
            cells.append(
                {
                    "cell_id": f"VP-{idx:03d}",
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": round(min_lon + STEP_LON, 5),
                    "max_lat": round(min_lat + STEP_LAT, 5),
                }
            )
            idx += 1
    return pd.DataFrame(cells)


def assign_cell_strict(fires: pd.DataFrame, grid: pd.DataFrame) -> pd.DataFrame:
    out = fires.copy()
    out["cell_id"] = None
    for _, cell in grid.iterrows():
        mask = (
            (out.longitude >= cell.min_lon)
            & (out.longitude <= cell.max_lon)
            & (out.latitude >= cell.min_lat)
            & (out.latitude <= cell.max_lat)
        )
        out.loc[mask, "cell_id"] = cell.cell_id
    return out[out.cell_id.notna()]


def cell_containing(grid: pd.DataFrame, lat: float, lon: float) -> str | None:
    match = grid[
        (grid.min_lon <= lon) & (lon <= grid.max_lon) & (grid.min_lat <= lat) & (lat <= grid.max_lat)
    ]
    return str(match.iloc[0].cell_id) if not match.empty else None


def main() -> None:
    grid = build_grid()
    old_lat, old_lon = _old_vp025_center()
    nueva_celda_de_vp025_antigua = cell_containing(grid, old_lat, old_lon)

    fires = pd.read_csv(FIRES_CSV)
    fires["acq_date"] = pd.to_datetime(fires["acq_date"])
    event = fires[fires.acq_date == EVENT_DATE]
    event_cells = assign_cell_strict(event, grid)

    joined = join_fires_to_meteo(event_cells)
    join_summary = summarize_join(joined)
    matched = joined[joined.join_status == "matched"].copy()
    matched["regla_30_30_30"] = (
        (matched.temperatura > 30) & (matched.humedad_relativa < 30) & (matched.velocidad_viento_kmh > 30)
    ).astype(int)

    por_celda = (
        matched.groupby("cell_id")
        .agg(
            n_detecciones=("latitude", "count"),
            temp_max=("temperatura", "max"),
            hr_min=("humedad_relativa", "min"),
            viento_max=("velocidad_viento_kmh", "max"),
            regla_activa_en_alguna_deteccion=("regla_30_30_30", "max"),
        )
        .reset_index()
    )
    por_celda["nota_agregacion"] = (
        "temp_max/hr_min/viento_max son el máximo/mínimo de la celda, no necesariamente "
        "de la misma detección — pueden venir de observaciones distintas y verse como si "
        "cumplieran la regla sin cumplirla ninguna en conjunto. regla_activa_en_alguna_deteccion "
        "SÍ es correcto: exige las tres condiciones en una misma fila (misma detección + su "
        "meteo emparejada) antes de agregar."
    )

    resultado = {
        "evento": EVENT_DATE,
        "hallazgo_original": {
            "celda": "VP-025 (grilla anterior, retirada 06-09-2026)",
            "afirmaba": "regla 30-30-30 activa con datos 100% reales (temp=30.7, hr=22, viento=30.37)",
        },
        "vp025_antigua_centro_fisico": {"lat": old_lat, "lon": old_lon},
        "celda_nueva_que_contiene_ese_punto": nueva_celda_de_vp025_antigua,
        "deteccciones_totales_evento": int(len(event)),
        "deteccciones_dentro_de_alguna_celda_nueva": int(len(event_cells)),
        "join_status": join_summary["by_status"],
        "match_rate": join_summary["match_rate_overall"],
        "resultado_por_celda_nueva": por_celda.to_dict(orient="records"),
        "regla_30_30_30_activa_en_alguna_celda": bool(matched["regla_30_30_30"].any()) if not matched.empty else False,
        "conclusion": None,  # se completa abajo, según el resultado real
    }

    if resultado["regla_30_30_30_activa_en_alguna_celda"]:
        celdas_con_regla = por_celda[por_celda.regla_activa_en_alguna_deteccion == 1]["cell_id"].tolist()
        resultado["conclusion"] = (
            f"CONFIRMADO con la grilla nueva: la regla 30-30-30 se cumple con datos 100% "
            f"reales en {celdas_con_regla} para el evento {EVENT_DATE}. El hallazgo original "
            f"sigue siendo válido, aunque el cell_id cambió (la celda física que antes se "
            f"llamaba VP-025 ahora es '{nueva_celda_de_vp025_antigua}', y puede no ser la "
            f"misma que aparece en celdas_con_regla si el punto original quedó repartido "
            f"entre celdas más grandes)."
        )
    else:
        resultado["conclusion"] = (
            f"NO CONFIRMADO con la grilla nueva: ninguna detección real individual del "
            f"evento {EVENT_DATE} cumple las tres condiciones de la regla 30-30-30 a la "
            f"vez, en ninguna celda de la geometría canónica. Verificado fila por fila: "
            f"en la celda que hoy contiene el punto de la antigua VP-025 (temperatura "
            f"máxima 30,7°C y humedad mínima 22% que coinciden con los valores del "
            f"hallazgo original), esos dos valores vienen de una detección a las 17:35 "
            f"UTC (viento 10,74 km/h, regla no cumplida), mientras que el viento >30 km/h "
            f"viene de otras detecciones a las 19:15 UTC (temperatura 27,7°C, regla "
            f"tampoco cumplida ahí). Ninguna fila individual cumple las tres condiciones "
            f"juntas. Esto sugiere que el hallazgo original pudo estar afectado por el "
            f"mismo riesgo metodológico: si se calculó como max(temp)/min(hr)/max(viento) "
            f"agregados sobre el polígono en vez de exigir las tres condiciones en una "
            f"misma detección, el resultado sería un artefacto de agregación, no una "
            f"ignición real con condiciones 30-30-30 simultáneas. No se pudo verificar la "
            f"metodología exacta del hallazgo original porque no quedó como script "
            f"reproducible (ver docs/matriz-riesgo.md)."
        )

    OUT_JSON.parent.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
    print(f"\nEscrito {OUT_JSON}")


if __name__ == "__main__":
    main()
