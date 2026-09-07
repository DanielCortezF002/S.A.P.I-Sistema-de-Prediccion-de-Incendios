"""Diagnóstico P0 — integridad espacial y temporal de `_load_meteo()`.

Solo lee. No modifica `src/procesamiento/data_processor.py` ni ningún otro
módulo de producción. Reconstruye, con UN SOLO recorrido de los mismos
archivos crudos (mismo glob, mismo orden de iteración dentro de este
proceso), dos vistas en paralelo:

  (a) exactamente lo que `_load_meteo()` produce hoy (metadata descartada,
      cell_id asignado por posición) — replicando su lógica línea por
      línea, no llamándola por separado, para que la correspondencia
      posicional entre (a) y (b) esté garantizada por construcción y no
      dependa de que dos llamadas a `Path.glob()` devuelvan el mismo orden;
  (b) la metadata real (estación, momento) que esa lógica descarta antes de
      asignar `cell_id`.

Comparar (a) contra (b) permite responder: la celda que _load_meteo() arma,
¿corresponde a la estación/momento reales que dice representar?

Salida: reports/auditoria_integridad_datos.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.geo.grid import cell_center
from src.procesamiento.data_processor import DataProcessor
from src.procesamiento.raw_parser import parse_dmc_json
from src.procesamiento.station_catalog import default_station_catalog, haversine_km

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = REPO_ROOT / "reports" / "auditoria_integridad_datos.json"


def replay_load_meteo_with_metadata(dp: DataProcessor) -> pd.DataFrame:
    """Un solo recorrido de `dmc_meteo_*.json`, con la metadata que
    `_load_meteo()` (data_processor.py) descarta antes de flatten+groupby.
    El orden de `records` acá es idéntico, fila por fila, al que produce el
    bucle real, porque es literalmente el mismo bucle (mismo glob, sin
    ordenar) con dos columnas extra que la versión real no conserva.
    """
    rows: list[dict] = []
    for path in dp.raw_dir.glob("dmc_meteo_*.json"):
        parsed = parse_dmc_json(path)
        if parsed.empty:
            continue
        for _, row in parsed.iterrows():
            rows.append(
                {
                    "archivo_fuente": path.name,
                    "codigo_estacion_real": row["codigo_estacion"],
                    "momento_real": row["momento"],
                    "temperatura": row["temperatura"],
                    "humedad_relativa": row["humedad_relativa"],
                    "velocidad_viento": row["velocidad_viento_kmh"],
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    dp = DataProcessor()
    grid = dp._build_grid()

    with_meta = replay_load_meteo_with_metadata(dp)

    # Réplica exacta de la asignación de cell_id en _load_meteo() (mismo
    # criterio: posicional si hay <= celdas que el grid, si no, secuencial
    # VP-001..VP-NNN), aplicada sobre `with_meta` en vez de sobre records
    # sin metadata — así (a) y (b) comparten índice de fila por diseño.
    if len(with_meta) <= len(grid):
        with_meta = with_meta.copy()
        with_meta["cell_id"] = grid["cell_id"].values[: len(with_meta)]
    else:
        with_meta = with_meta.copy()
        with_meta["cell_id"] = [f"VP-{i:03d}" for i in range(1, len(with_meta) + 1)]

    # `_load_meteo()` real, sin tocar, para confirmar que produce lo mismo
    # que esta réplica en las columnas que sí conserva (control de que la
    # réplica es fiel, no una reinterpretación).
    meteo_real = dp._load_meteo()
    merged_real = grid.merge(meteo_real, how="left", on="cell_id")

    catalog = default_station_catalog()

    filas: list[dict] = []
    for i in range(len(grid)):
        cell_id = grid.iloc[i]["cell_id"]
        lat, lon = cell_center(int(cell_id.split("-")[1]))

        dists = {
            codigo: haversine_km(lat, lon, st.latitud, st.longitud)
            for codigo, st in catalog.items()
        }
        estacion_correcta = min(dists, key=dists.get) if dists else None
        dist_correcta_km = dists.get(estacion_correcta)

        real_row = merged_real.iloc[i]
        meta_row = with_meta[with_meta.cell_id == cell_id]

        fila = {
            "cell_id": cell_id,
            "celda_centro_lat": lat,
            "celda_centro_lon": lon,
            "estacion_geograficamente_correcta": estacion_correcta,
            "estacion_correcta_nombre": catalog[estacion_correcta].nombre if estacion_correcta else None,
            "distancia_a_estacion_correcta_km": round(dist_correcta_km, 2) if dist_correcta_km else None,
            "temperatura_asignada_por_load_meteo": real_row.get("temperatura"),
            "humedad_asignada_por_load_meteo": real_row.get("humedad_relativa"),
            "viento_asignado_por_load_meteo": real_row.get("velocidad_viento"),
        }

        if not meta_row.empty:
            m = meta_row.iloc[0]
            fila["temperatura_replica_coincide_con_real"] = bool(
                pd.isna(real_row.get("temperatura")) or abs(float(m["temperatura"]) - float(real_row["temperatura"])) < 1e-6
            )
            fila["estacion_realmente_usada"] = m["codigo_estacion_real"]
            fila["momento_real_de_la_lectura"] = str(m["momento_real"])
            fila["archivo_fuente"] = m["archivo_fuente"]
            est_usada = catalog.get(m["codigo_estacion_real"])
            if est_usada:
                fila["distancia_celda_a_estacion_usada_km"] = round(
                    haversine_km(lat, lon, est_usada.latitud, est_usada.longitud), 2
                )
        else:
            fila["estacion_realmente_usada"] = None
            fila["momento_real_de_la_lectura"] = None

        fila["asignacion_es_geograficamente_correcta"] = (
            fila.get("estacion_realmente_usada") == estacion_correcta
        )
        filas.append(fila)

    tabla = pd.DataFrame(filas)

    todas_misma_estacion_real = with_meta["codigo_estacion_real"].nunique() == 1 if not with_meta.empty else None
    n_estaciones_con_datos_reales = with_meta["codigo_estacion_real"].nunique() if not with_meta.empty else 0
    correctas = int(tabla["asignacion_es_geograficamente_correcta"].sum())
    replica_fiel = bool(tabla["temperatura_replica_coincide_con_real"].all())

    momentos = pd.to_datetime(tabla["momento_real_de_la_lectura"], errors="coerce")
    deltas_min = momentos.diff().dt.total_seconds().dropna() / 60.0
    delta_tipico_min = float(deltas_min.median()) if not deltas_min.empty else None

    resultado = {
        "replica_de_load_meteo_es_fiel_a_la_real": replica_fiel,
        "n_celdas_grid": len(grid),
        "n_lecturas_reales_totales_tras_flatten": len(with_meta),
        "n_estaciones_con_datos_reales_en_data_raw": n_estaciones_con_datos_reales,
        "todas_las_lecturas_reales_vienen_de_una_sola_estacion": bool(todas_misma_estacion_real),
        "estacion_unica_si_aplica": (
            with_meta["codigo_estacion_real"].iloc[0] if todas_misma_estacion_real else None
        ),
        "n_celdas_con_asignacion_geograficamente_correcta": correctas,
        "n_celdas_con_asignacion_geograficamente_incorrecta": len(grid) - correctas,
        "delta_temporal_tipico_entre_celdas_consecutivas_minutos": delta_tipico_min,
        "interpretacion": (
            "Si delta_temporal_tipico_entre_celdas_consecutivas_minutos es ~15, "
            "significa que la celda i+1 recibe la lectura HORARIA SIGUIENTE de la "
            "MISMA estación que la celda i, no una lectura de una ubicación "
            "geográfica distinta. Las '50 celdas' del dataset de producción "
            "codifican, en la práctica, instantes consecutivos de UNA sola "
            "estación (Rodelillo, 330007), no 50 ubicaciones."
        ),
        "primeras_10_celdas": tabla.head(10).to_dict(orient="records"),
        "ultimas_5_celdas": tabla.tail(5).to_dict(orient="records"),
    }

    OUT_JSON.parent.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
    print(f"\nEscrito {OUT_JSON}")


if __name__ == "__main__":
    main()
