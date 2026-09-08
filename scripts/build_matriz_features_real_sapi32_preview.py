"""SAPI-32 — artefacto de prueba: primer puente real igniciones->celdas.

Genera data/processed/matriz_features_real_sapi32_preview.parquet a partir
del evento real del 2024-02-03 (megaincendio Valparaíso/Viña del Mar),
sobre las celdas de `src/geo/grid.py` donde detecciones NASA FIRMS reales
caen dentro del polígono de la celda (contención estricta, sin
aproximación por distancia — a diferencia del candidato VP-044/feb-2025
descartado en el diseño previo, acá sí hay contención real).

Nota sobre VP-043 (unificación de grilla, 2026-09-06): la corrida original
de este script excluía la celda VP-043 por sospecha de falso positivo
persistente (detecciones en los 12 meses de los 6 años de historial,
patrón no estacional incompatible con incendio forestal). Esa sospecha se
verificó sobre la geometría de grilla anterior (~1 km²/celda). Tras migrar
a la grilla canónica (~11,5 km²/celda, ver `src/geo/grid.py`), "VP-043" es
una zona física distinta, y se reverificó: la nueva área tiene solo 4
detecciones en 6 años, concentradas en 2 meses (feb/dic) y 2 años — patrón
estacional consistente con incendio real, no con el hallazgo original. Por
eso ya NO se excluye. La exclusión no se puede migrar entre grillas por el
solo nombre de la celda; si se sospecha de nuevo un falso positivo, hay que
reverificarlo contra la geometría vigente.

Deliberadamente NO escribe en matriz_features de producción (Postgres) —
ver R-INTEGRACION-01 en docs/matriz-riesgo.md. Es un artefacto Parquet
separado para revisión, mismo patrón que dem_terrain/ separa el
procesamiento DEM de su integración a data_processor.py.

`ignicion` queda sin setear (None/null) a propósito: si una detección real
a ~10 km justifica marcar ignicion=1 en una celda es una decisión de
etiquetado (ver R-ETIQUETA-01), no una agregación mecánica — no se infiere
acá.

Nota sobre `regla_30_30_30` (fix 06-09-2026, ver reverificación de VP-025 en
docs/matriz-riesgo.md): se evalúa POR DETECCIÓN (misma fila, misma meteo
emparejada) antes de agregar por celda, no sobre
temperatura=max/humedad=min/viento=max ya agregados. Agregar primero mezcla
valores de detecciones distintas en momentos distintos como si describieran
una sola observación real — así fue como el hallazgo de VP-025/2022-12-11
resultó ser un artefacto de agregación. Con el fix, "regla activa en la
celda" significa "alguna detección real cumplió las tres condiciones a la
vez", no "el peor valor de cada variable en la celda, sin importar cuándo
ocurrió, cumple la regla". En esta corrida (evento 2024-02-03) el resultado
no cambió (0 celdas con regla activa en ambos casos) porque el viento
agregado nunca superó 21,11 km/h — pero el método anterior sí podía producir
falsos positivos en otros eventos, como ocurrió con VP-025.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from src.geo.grid import BASE_LAT, BASE_LON, COLS, ROWS, STEP_LAT, STEP_LON
from src.procesamiento.meteo_fire_joiner import join_fires_to_meteo, summarize_join

REPO_ROOT = Path(__file__).resolve().parent.parent
FIRES_CSV = REPO_ROOT / "data" / "processed" / "nasa_firms_2021-08-30_2026-08-30.csv"
OUT_PARQUET = REPO_ROOT / "data" / "processed" / "matriz_features_real_sapi32_preview.parquet"
OUT_MANIFEST = REPO_ROOT / "data" / "processed" / "matriz_features_real_sapi32_preview_manifest.json"

EVENT_DATE = "2024-02-03"
# Vacía a propósito: ver nota sobre VP-043 en el docstring del módulo — la
# exclusión anterior era específica de la geometría de grilla previa y no
# se sostuvo al reverificarla contra la grilla canónica.
EXCLUDED_CELLS: list[str] = []


def build_grid() -> pd.DataFrame:
    """Grilla idéntica a `src/geo/grid.py` (fuente única, ver su docstring)."""
    cells = []
    idx = 1
    for row in range(ROWS):
        for col in range(COLS):
            min_lon = round(BASE_LON + col * STEP_LON, 5)
            min_lat = round(BASE_LAT + row * STEP_LAT, 5)
            max_lon = round(min_lon + STEP_LON, 5)
            max_lat = round(min_lat + STEP_LAT, 5)
            cells.append(
                {
                    "cell_id": f"VP-{idx:03d}",
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat,
                    "clon": (min_lon + max_lon) / 2,
                    "clat": (min_lat + max_lat) / 2,
                }
            )
            idx += 1
    return pd.DataFrame(cells)


def haversine_km(lon1: float, lat1: float, lon2: np.ndarray, lat2: np.ndarray) -> np.ndarray:
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def assign_cell_strict(fires: pd.DataFrame, grid: pd.DataFrame) -> pd.DataFrame:
    """Contención estricta: cell_id si el punto cae dentro del polígono, si no se descarta."""
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


def build_preview() -> tuple[pd.DataFrame, dict]:
    grid = build_grid()
    fires = pd.read_csv(FIRES_CSV)
    fires["acq_date"] = pd.to_datetime(fires["acq_date"])

    event = fires[fires.acq_date == EVENT_DATE]
    event_cells = assign_cell_strict(event, grid)
    event_cells = event_cells[~event_cells.cell_id.isin(EXCLUDED_CELLS)]

    joined = join_fires_to_meteo(event_cells)
    join_summary = summarize_join(joined)
    if join_summary["by_status"].get("matched", 0) != len(joined):
        raise RuntimeError(
            "Se esperaba 100% matched para este evento (verificado en sesión previa); "
            f"resultado real: {join_summary['by_status']}. Revisar antes de persistir."
        )

    # regla_30_30_30 se evalúa POR DETECCIÓN, antes de agregar (hallazgo
    # 06-09-2026, ver reverificación de VP-025 en docs/matriz-riesgo.md):
    # calcularla sobre temperatura=max/humedad=min/viento=max ya agregados
    # por celda mezcla valores de detecciones distintas en momentos
    # distintos como si describieran una sola observación real. Acá cada
    # fila de `joined` ya es una detección con su propia meteo emparejada
    # (misma fuente, mismo instante), así que "regla activa en la celda" se
    # define correctamente como "alguna detección real cumplió las tres
    # condiciones a la vez", con `.max()` haciendo ese OR al agregar.
    joined["regla_30_30_30"] = (
        (joined.temperatura > 30)
        & (joined.humedad_relativa < 30)
        & (joined.velocidad_viento_kmh > 30)
    ).astype(int)

    grouped = joined.groupby(["cell_id", "acq_date"])
    agg = grouped.agg(
        temperatura=("temperatura", "max"),
        humedad_relativa=("humedad_relativa", "min"),
        velocidad_viento=("velocidad_viento_kmh", "max"),
        conteo_focos_activos=("latitude", "count"),
        max_frp=("frp", "max"),
        regla_30_30_30=("regla_30_30_30", "max"),
    ).reset_index()
    agg = agg.rename(columns={"acq_date": "fecha"})

    # distancia_km_al_dato_real: acá NO es la aproximación de ~10 km del
    # candidato VP-044/feb-2025 descartado en el diseño -- es contención
    # real, así que es la distancia del centroide de la celda a la
    # detección más cercana DENTRO de esa misma celda (típicamente
    # sub-kilométrica, la mitad del ancho de una celda de ~1 km2). Se deja
    # el campo con el mismo nombre por continuidad con el diseño acordado,
    # pero el significado cambió de "proxy por proximidad" a "distancia
    # real intra-celda" -- documentado explícitamente acá para que no se
    # lea como si siguiera siendo una aproximación de 10 km.
    grid_idx = grid.set_index("cell_id")
    dist_rows = []
    n_rows = []
    for _, row in agg.iterrows():
        cell = grid_idx.loc[row.cell_id]
        cell_fires = joined[(joined.cell_id == row.cell_id) & (joined.acq_date == row.fecha)]
        d = haversine_km(cell.clon, cell.clat, cell_fires.longitude.values, cell_fires.latitude.values)
        dist_rows.append(round(float(d.min()), 4))
        n_rows.append(int(len(cell_fires)))
    agg["distancia_km_al_dato_real"] = dist_rows
    agg["n_detecciones_agregadas"] = n_rows
    agg["ignicion"] = pd.array([None] * len(agg), dtype="Int64")  # sin setear, ver R-ETIQUETA-01

    agg = agg[
        [
            "cell_id",
            "fecha",
            "temperatura",
            "humedad_relativa",
            "velocidad_viento",
            "conteo_focos_activos",
            "max_frp",
            "regla_30_30_30",
            "distancia_km_al_dato_real",
            "n_detecciones_agregadas",
            "ignicion",
        ]
    ].sort_values("cell_id")

    manifest = {
        "_metadata": (
            "Evento catastrófico histórico (megaincendio Valparaíso/Viña del Mar, "
            "feb-2024), no representativo de un día típico — FRP hasta 323.6, hasta "
            "6 focos por celda. Usar como prueba de escala del mecanismo, no como "
            "ejemplo de valores normales."
        ),
        "nota_regla_30_30_30": (
            "Evaluada por detección individual antes de agregar (fix 06-09-2026, ver "
            "docstring del script) — no sobre temperatura/humedad/viento ya agregados "
            "por celda, que puede mezclar detecciones distintas en momentos distintos."
        ),
        "evento": EVENT_DATE,
        "celdas_excluidas": EXCLUDED_CELLS,
        "nota_VP-043": (
            "Excluida en la corrida sobre la grilla anterior por sospecha de falso "
            "positivo persistente (detecciones en 12/12 meses de 6 años). Tras migrar "
            "a la grilla canónica (src/geo/grid.py), VP-043 es una zona física "
            "distinta; reverificada aquí: solo 4 detecciones en 6 años, 2 meses "
            "(feb/dic), 2 años — patrón estacional normal, ya no se excluye."
        ),
        "n_celdas": int(agg.cell_id.nunique()),
        "n_detecciones_totales_agregadas": int(agg.n_detecciones_agregadas.sum()),
        "join_status": join_summary["by_status"],
        "match_rate_overall": join_summary["match_rate_overall"],
        "ignicion": "sin setear (None) a propósito — ver R-ETIQUETA-01 en docs/matriz-riesgo.md",
        "no_persistido_en_matriz_features_produccion": (
            "Este artefacto es un Parquet de revisión, deliberadamente separado de "
            "matriz_features (Postgres) hasta confirmar el enfoque — ver "
            "R-INTEGRACION-01 en docs/matriz-riesgo.md."
        ),
        "fuente_detecciones": str(FIRES_CSV.relative_to(REPO_ROOT)),
        "fuente_meteo": "data/raw/dmc_historico_330007_2024-02.json (estación 330007, Rodelillo)",
        "reproducible_con": "scripts/build_matriz_features_real_sapi32_preview.py",
    }
    return agg, manifest


def main() -> None:
    df, manifest = build_preview()
    df.to_parquet(OUT_PARQUET, index=False)
    OUT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Escrito {OUT_PARQUET} ({len(df)} filas, {df.cell_id.nunique()} celdas)")
    print(f"Escrito {OUT_MANIFEST}")


if __name__ == "__main__":
    main()
