"""Constructor del dataset temporal (cell_id, forecast_time) → target.

Orquesta, sobre datos 100% reales:
  regional_meteo (estación 330007) + episodios FIRMS + topografía DEM
    -> dataset (cell_id, forecast_time) con features "as of T" + target futuro

Deliberadamente NO incluye NDVI (sintético, ver docs/matriz-riesgo.md) ni
ninguna síntesis de `ignicion` — si una feature real no está disponible para
una fila, la fila queda con NaN en esa columna o se excluye, nunca se
inventa un valor.

Salida:
  data/processed/temporal_dataset_h{horizon_h}.parquet
  reports/temporal_dataset_h{horizon_h}_manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.geo.grid import all_cells
from src.procesamiento.causality_validator import validate_temporal_causality
from src.procesamiento.dem_features import sample_grid_topography
from src.procesamiento.episodes import assign_episodes, build_episode_catalog, first_arrival_by_cell
from src.procesamiento.pipeline_validators import validate_manifest_matches_dataset
from src.procesamiento.regional_meteo import load_regional_meteo_series
from src.procesamiento.target_builder import build_targets
from src.procesamiento.temporal_features import LAG_HOURS, build_regional_meteo_features, historial_firms_features

REPO_ROOT = Path(__file__).resolve().parent.parent
STATION_ID = "330007"
FIRES_CSV = REPO_ROOT / "data" / "processed" / "nasa_firms_2021-08-30_2026-08-30.csv"
COOLDOWN_HOURS_DEFAULT = 6
CANDIDATE_STEP_HOURS = 6  # muestreo de forecast_time — ver manifest, motivo documentado


def _load_dem_topography(grid_cells: list[dict]) -> pd.DataFrame:
    """Topografía real por celda si el DEM está procesado; si no, columnas
    en NaN (nunca la aproximación sintética que sí usa `data_processor.py`
    como fallback — acá no hay fallback, es un experimento real)."""
    terrain_dir = REPO_ROOT / "data" / "processed" / "dem_terrain"
    dem = sorted(terrain_dir.glob("*_utm19s.tif"))
    slope = sorted(terrain_dir.glob("*_slope.tif"))
    aspect = sorted(terrain_dir.glob("*_aspect.tif"))

    grid_df = pd.DataFrame(grid_cells)
    if dem and slope and aspect:
        topo = sample_grid_topography(grid_df, dem[0], slope[0], aspect[0])
        grid_df["elevacion"] = topo["altitud"]
        grid_df["pendiente"] = topo["pendiente"]
        grid_df["orientacion"] = topo["orientacion"]
        grid_df["dem_disponible"] = True
    else:
        grid_df["elevacion"] = None
        grid_df["pendiente"] = None
        grid_df["orientacion"] = None
        grid_df["dem_disponible"] = False
    return grid_df[["cell_id", "elevacion", "pendiente", "orientacion", "dem_disponible"]]


def build_dataset(horizon: timedelta, cooldown: timedelta) -> tuple[pd.DataFrame, dict]:
    grid_cells = all_cells()
    cell_ids = [c["cell_id"] for c in grid_cells]

    # 1) regional_meteo real — nunca reetiquetada por celda.
    meteo_series = load_regional_meteo_series(STATION_ID)
    if meteo_series.empty:
        raise RuntimeError(f"Sin datos reales de la estación {STATION_ID} en data/raw/")

    # Candidatos de forecast_time: uno por cada bucket de N horas que
    # contenga AL MENOS UNA lectura real — nunca un `date_range` sobre todo
    # el calendario entre la primera y la última lectura. `regional_meteo`
    # solo tiene datos densos dentro de 4 meses reales (2022-01, 2022-12,
    # 2024-02, 2025-02) más unos días de ingesta reciente; el resto del
    # rango son años de vacío. Un `date_range` ingenuo generaría miles de
    # forecast_time sin ninguna lectura real cerca (se detectó exactamente
    # así en la primera corrida: 93% de las filas quedaban con
    # `meteo_actual_temp` en NaN). Resamplear sobre la serie real evita
    # crear un candidato donde no hay dato.
    t_min, t_max = meteo_series["momento"].min(), meteo_series["momento"].max()
    bucketed = (
        meteo_series.set_index("momento")["temperatura"]
        .resample(f"{CANDIDATE_STEP_HOURS}h")
        .first()
        .dropna()
    )
    forecast_times = list(bucketed.index)

    # 2) Episodios FIRMS reales -> first_arrival por celda.
    fires = pd.read_csv(FIRES_CSV)
    episodes = assign_episodes(fires)
    arrivals = first_arrival_by_cell(episodes)
    arrivals_by_cell = {
        cell: group.sort_values().reset_index(drop=True)
        for cell, group in arrivals.groupby("cell_id")["first_arrival"]
    }

    # 3) Meteo regional + lags reales, una vez por forecast_time (se
    # comparte igual entre las 50 celdas — regla de oro de la sección 6).
    meteo_feats = build_regional_meteo_features(forecast_times, meteo_series, lag_hours=LAG_HOURS)

    # 4) Topografía real por celda (estática).
    topo = _load_dem_topography(grid_cells)

    # 5) target(cell, T, h) + exclusión por cooldown.
    targets = build_targets(arrivals, cell_ids, forecast_times, horizon, cooldown)

    # 6) Historial FIRMS "as of T" por (cell, T) — construido fila a fila a
    # propósito: cada uno trunca en su propio forecast_time, no es una tabla
    # precalculada que luego se reutiliza (eso reintroduciría el riesgo de
    # atajo tautológico que motivó separar esto del territorio estático).
    historial_rows = []
    for cell_id in cell_ids:
        arrivals_series = arrivals_by_cell.get(cell_id, pd.Series([], dtype="datetime64[ns, UTC]"))
        for T in forecast_times:
            historial_rows.append(historial_firms_features(cell_id, T, arrivals_series))
    historial = pd.DataFrame(historial_rows)

    # 7) Ensamblado final.
    dataset = targets.merge(meteo_feats, on="forecast_time", how="left")
    dataset = dataset.merge(historial, on=["cell_id", "forecast_time"], how="left")
    dataset = dataset.merge(topo, on="cell_id", how="left")

    # `meteo_age_hours`: antigüedad de la lectura "actual" respecto a T —
    # diagnóstico de frescura, no una feature del modelo todavía (sección
    # 12 de la auditoría). NaN cuando no hay meteo_actual dentro de
    # tolerancia (ya marcado en meteo_actual_missing).
    dataset["meteo_age_hours"] = (
        dataset["forecast_time"] - dataset["meteo_actual_momento"]
    ).dt.total_seconds() / 3600.0

    # Las filas excluidas por cooldown YA NO se descartan del artefacto: se
    # conservan con `excluded=True` y `eligible_for_training=False`, para
    # que sean auditables (antes desaparecían del parquet sin dejar rastro
    # de que existieron). `excluded_reason` es la única razón que hoy
    # dispara exclusión real — `meteo_missing`, `historial_insuficiente`,
    # `target_ambiguous` y `outside_data_coverage` quedan documentadas como
    # categorías posibles del esquema, pero NINGUNA fila las usa hoy: no se
    # inventan exclusiones que el código no aplica.
    dataset["eligible_for_training"] = ~dataset["excluded"]
    n_before_exclusion = len(dataset)
    excluded = dataset[dataset["excluded"]]

    # 8) Validación de causalidad — obligatoria, no opcional. Solo sobre las
    # filas elegibles: una fila excluida por cooldown tiene target=None, y
    # no tiene sentido pedirle que cumpla una regla de "target futuro".
    # `target_timestamp_col` verifica además la otra mitad del contrato que
    # antes quedaba sin comprobar automáticamente: el timestamp del target
    # (cuando existe) tiene que ser ESTRICTAMENTE posterior a `forecast_time`
    # — nunca iguala ni antecede.
    eligible = dataset[dataset["eligible_for_training"]].reset_index(drop=True)
    feature_ts_cols = [f"{('meteo_actual' if h == 0 else f'meteo_lag_{h}h')}_momento" for h in LAG_HOURS]
    feature_ts_cols.append("historial_ultimo_evento_momento")
    report = validate_temporal_causality(
        eligible,
        feature_timestamp_cols=feature_ts_cols,
        target_timestamp_col="target_timestamp",
        raise_on_violation=True,
    )

    # `event_id` de `assign_episodes()` que producen un positivo en el
    # dataset final. NOTA DE NOMENCLATURA (corregida 06-09-2026, ver
    # docs/matriz-riesgo.md): esto es "episodios crudos del algoritmo",
    # NO "incendios independientes" — un `event_id` es una construcción de
    # `assign_episodes()` (radio 2km / gap 6h), no una verdad de terreno.
    # Se probó una heurística adicional de colapso por timestamp idéntico y
    # se abandonó: el timestamp compartido resultó ser un mal proxy de
    # independencia (grupos "colapsados" con incendios hasta 112 km de
    # distancia entre sí, capturados por la misma pasada satelital, no por
    # ser el mismo fuego). No existe hoy una `evaluation_case_id` más fina
    # y defendible que `event_id` — ver `n_positive_evaluation_cases` abajo.
    #
    # Ahora se lee directamente de `target_event_id` (columna del propio
    # dataset, ver `target_builder.py`) en vez de recalcularlo con un join
    # aparte — la fila es auto-auditable, no depende de recombinar con
    # `arrivals` para saber de dónde salió su propio target.
    episode_catalog = build_episode_catalog(episodes)
    positives = eligible[eligible["target"] == 1]
    positive_event_ids: set[int] = set(positives["target_event_id"].dropna().astype(int).tolist())

    # Comprobación cruzada independiente (auditoría 06-09-2026): PARA CADA
    # FILA positiva, el `target_event_id` que trae el dataset debe estar
    # DENTRO del conjunto de eventos que un join externo contra `arrivals`
    # encuentra calificando para esa misma (cell_id, ventana) — si no está,
    # es un bug de trazabilidad real.
    #
    # Se comprueba por FILA, no comparando los dos conjuntos globales,
    # porque se verificó contra datos reales (2026-09-06) que SÍ existen
    # celdas con dos `event_id` distintos arribando a <6h uno del otro
    # (p.ej. VP-002, VP-027): en esos casos una misma fila puede tener más
    # de un evento "calificante" y `target_event_id` deliberadamente
    # registra solo el de arribo más temprano (ver docstring de
    # `target_builder.build_targets`). Comparar conjuntos globales ahí
    # produciría un falso positivo de "inconsistencia" por un choque de
    # diseño (un disparador por fila) que no es un bug.
    cross_check_ids: set[int] = set()
    rows_with_multiple_qualifying_events = 0
    for _, row in positives.iterrows():
        match = arrivals[
            (arrivals["cell_id"] == row["cell_id"])
            & (arrivals["first_arrival"] > row["target_window_start"])
            & (arrivals["first_arrival"] <= row["target_window_end"])
        ]
        qualifying_here = set(match["event_id"].tolist())
        cross_check_ids.update(qualifying_here)
        if len(qualifying_here) > 1:
            rows_with_multiple_qualifying_events += 1
        if int(row["target_event_id"]) not in qualifying_here:
            raise RuntimeError(
                "Inconsistencia de trazabilidad: la fila "
                f"(cell_id={row['cell_id']!r}, forecast_time={row['forecast_time']!r}) "
                f"trae target_event_id={row['target_event_id']!r}, pero el join "
                f"independiente contra arrivals para esa misma ventana da "
                f"{sorted(qualifying_here)}. No continuar sin corregir."
            )
    # `positive_event_ids` (única fuente: columna target_event_id) es un
    # SUBCONJUNTO válido de `cross_check_ids` (unión de TODOS los eventos
    # calificantes, incluidos los que perdieron el desempate en alguna
    # fila) — no se exige igualdad, solo se documentan ambos números.
    if not positive_event_ids.issubset(cross_check_ids):
        raise RuntimeError(
            "Inconsistencia de trazabilidad: target_event_id trae eventos que "
            f"ningún join independiente reproduce: {sorted(positive_event_ids - cross_check_ids)}."
        )

    manifest = {
        "dataset_version": "temporal_dataset_v1",
        "version_grilla": "src/geo/grid.py (canónica, unificada 06-09-2026)",
        "source_dmc": STATION_ID,
        "source_firms": str(FIRES_CSV.relative_to(REPO_ROOT)),
        "rango_temporal_regional_meteo": [str(t_min), str(t_max)],
        "forecast_horizon_hours": horizon.total_seconds() / 3600,
        "forecast_frequency_hours": CANDIDATE_STEP_HOURS,
        "cooldown_horas": cooldown.total_seconds() / 3600,
        "episode_parameters": {"radius_km": 2.0, "max_gap_hours": 6.0},
        "motivo_muestreo": (
            "Un forecast_time candidato es el primer instante real de cada "
            f"bucket de {CANDIDATE_STEP_HOURS}h que contiene AL MENOS UNA "
            "lectura real de la estación (resample sobre la serie real, no "
            "un date_range sobre todo el calendario) — evita crear "
            "candidatos en los años sin datos DMC entre los 4 meses "
            "históricos reales. (Hallazgo de la primera corrida: un "
            "date_range ingenuo dejaba 93% de las filas con meteo_actual "
            "en NaN.)"
        ),
        "definicion_target": (
            "target(cell,T,h)=1 si existe un evento (clúster espacio-temporal "
            "de detecciones FIRMS, radio 2km / gap max 6h) cuyo primer arribo "
            "a esa celda cae en (T, T+h]. Filas con T en cooldown tras un "
            "arribo previo en la misma celda quedan `excluded=True`, "
            "`eligible_for_training=False`, target=None — NUNCA 0."
        ),
        "n_celdas": len(cell_ids),
        "n_timestamps": len(forecast_times),
        "n_rows": len(dataset),
        "n_rows_eligible": len(eligible),
        "n_positive_rows": int(eligible["target"].sum()),
        "n_negative_rows": int((eligible["target"] == 0).sum()),
        "n_positive_raw_episodes": len(positive_event_ids),
        "n_positive_raw_episodes_any_qualifying": len(cross_check_ids),
        "n_positive_rows_with_multiple_qualifying_events": rows_with_multiple_qualifying_events,
        "nota_raw_episodes": (
            "n_positive_raw_episodes cuenta los event_id que quedan REGISTRADOS "
            "como target_event_id (uno por fila, el de arribo más temprano si "
            "hay empate). n_positive_raw_episodes_any_qualifying cuenta la "
            "UNIÓN de todos los event_id que calificarían para alguna fila "
            "positiva, incluidos los que perdieron el desempate — es "
            "verificablemente >= al anterior. La diferencia entre ambos "
            f"({len(cross_check_ids) - len(positive_event_ids)} evento(s)) "
            f"ocurre en {rows_with_multiple_qualifying_events} fila(s) donde dos "
            "o más eventos distintos arribaron a la misma celda con menos de "
            "`cooldown` horas de diferencia."
        ),
        "n_positive_evaluation_cases": None,
        "nota_evaluation_cases": (
            "null a propósito: se evaluó una heurística de colapso por "
            "timestamp de primera detección idéntico y se descartó — "
            "produce grupos con incendios hasta 112 km de distancia entre "
            "sí (misma pasada satelital, no el mismo fuego). Hoy no existe "
            "una unidad de evaluación más fina que `event_id` (raw episode) "
            "que sea reproducible y defendible sin una fuente externa "
            "(contorno de incendio real, reporte institucional). Reportar "
            "un número aquí sería fabricar independencia, no medirla."
        ),
        "n_excluded": int(len(excluded)),
        "excluded_reasons": excluded["excluded_reason"].value_counts().to_dict() if not excluded.empty else {},
        "excluded_reason_categories_declaradas_no_todas_en_uso": [
            "cooldown_evento_activo",
            "meteo_missing",
            "historial_insuficiente",
            "target_ambiguous",
            "outside_data_coverage",
        ],
        "n_episodios_totales_firms_backfill_completo": int(episodes["event_id"].nunique()),
        "n_celdas_con_algun_arribo_historico": int(arrivals["cell_id"].nunique()),
        "dem_disponible": bool(topo["dem_disponible"].iloc[0]) if not topo.empty else False,
        "feature_set": [c for c in dataset.columns if c not in ("excluded", "excluded_reason", "eligible_for_training")],
        "features_excluidas_deliberadamente": {
            "ndvi": "sintético incondicional en data_processor.py, no participa en experimentos reales",
            "ignicion_32_28_25": "target sintético retirado del camino de producción/experimental",
        },
        "validacion_causalidad": {
            "filas_validadas": report.n_rows,
            "violaciones": report.n_violations,
            "resultado": "OK — 0 violaciones" if report.is_valid else "FALLO",
        },
        "meteo_age_hours_stats": {
            "min": float(eligible["meteo_age_hours"].min()) if eligible["meteo_age_hours"].notna().any() else None,
            "median": float(eligible["meteo_age_hours"].median()) if eligible["meteo_age_hours"].notna().any() else None,
            "p95": float(eligible["meteo_age_hours"].quantile(0.95)) if eligible["meteo_age_hours"].notna().any() else None,
            "max": float(eligible["meteo_age_hours"].max()) if eligible["meteo_age_hours"].notna().any() else None,
            "n_sin_meteo_actual": int(eligible["meteo_actual_missing"].sum()),
            # Distribución de la ausencia — no basta el % global (sección 11
            # de la auditoría): si estuviera concentrada en un solo mes/hora
            # tendría una implicación completamente distinta de si está
            # repartida parejo.
            "por_mes": (
                eligible.assign(_mes=eligible["forecast_time"].dt.strftime("%Y-%m"))
                .groupby("_mes")["meteo_actual_missing"]
                .mean()
                .round(4)
                .to_dict()
            ),
            "por_hora_utc": (
                eligible.assign(_hora=eligible["forecast_time"].dt.hour)
                .groupby("_hora")["meteo_actual_missing"]
                .mean()
                .round(4)
                .to_dict()
            ),
            "por_celda_min_max": {
                "min_tasa_celda": float(eligible.groupby("cell_id")["meteo_actual_missing"].mean().min()),
                "max_tasa_celda": float(eligible.groupby("cell_id")["meteo_actual_missing"].mean().max()),
            },
        },
        "hash_dataset": None,  # se completa tras escribir el parquet
    }
    return dataset, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Construye el dataset temporal (cell_id, forecast_time) -> target.")
    parser.add_argument("--horizon-hours", type=float, default=6.0)
    parser.add_argument("--cooldown-hours", type=float, default=COOLDOWN_HOURS_DEFAULT)
    args = parser.parse_args()

    horizon = timedelta(hours=args.horizon_hours)
    cooldown = timedelta(hours=args.cooldown_hours)

    dataset, manifest = build_dataset(horizon, cooldown)

    out_dir = REPO_ROOT / "data" / "processed"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"temporal_dataset_h{int(args.horizon_hours)}.parquet"
    dataset.to_parquet(out_path, index=False)

    # Hash: se calcula sobre los BYTES ya escritos en disco (no sobre el
    # DataFrame en memoria) para que sea una prueba real de reproducibilidad
    # de archivo, no una propiedad del objeto Python (sección 22 de la
    # auditoría 06-09-2026).
    manifest["hash_dataset"] = hashlib.sha256(out_path.read_bytes()).hexdigest()
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    manifest_path = reports_dir / f"temporal_dataset_h{int(args.horizon_hours)}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # Verificación de reproducibilidad del hash: releer el archivo recién
    # escrito desde disco y recalcular — si no coincide, algo en la
    # escritura (compresión no determinista, encoding, etc.) invalida el
    # hash como huella del contenido.
    rehash = hashlib.sha256(out_path.read_bytes()).hexdigest()
    if rehash != manifest["hash_dataset"]:
        raise RuntimeError(
            f"hash_dataset no es reproducible: {manifest['hash_dataset']} != {rehash} al releer {out_path}"
        )

    # Autoconsistencia manifest <-> parquet (sección 3 de la auditoría
    # 06-09-2026): releer el parquet escrito (no reusar `dataset` en
    # memoria) y recalcular cada cifra del manifest contra él. FAIL, no
    # WARN — un manifest que no reproduce el archivo que describe no debe
    # publicarse.
    dataset_on_disk = pd.read_parquet(out_path)
    consistency = validate_manifest_matches_dataset(manifest, dataset_on_disk)
    if consistency.status != "PASS":
        raise RuntimeError(f"Manifest inconsistente con el parquet escrito: {consistency.detail}")

    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
    print(f"\nEscrito {out_path}")
    print(f"Escrito {manifest_path}")
    print(f"hash_dataset verificado reproducible (write -> hash -> reread -> rehash): {rehash}")
    print(f"MANIFEST vs DATASET: {consistency.status} — {consistency.detail}")


if __name__ == "__main__":
    main()
