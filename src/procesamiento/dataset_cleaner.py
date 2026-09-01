"""Limpieza y normalización del dataset ignición ↔ meteo (SAPI-32)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.procesamiento.meteo_fire_joiner import (
    JOIN_STATUS_MATCHED,
    JOIN_STATUS_NO_DMC_COVERAGE,
    JOIN_STATUS_OUT_OF_TOLERANCE,
)

# Alineado con deduplicate_detections (nasa_firms_backfill): ~1.1 m en el ecuador.
DEDUP_COORD_DECIMALS = 5

JOIN_STATUS_PRIORITY = {
    JOIN_STATUS_MATCHED: 0,
    JOIN_STATUS_OUT_OF_TOLERANCE: 1,
    JOIN_STATUS_NO_DMC_COVERAGE: 2,
}

FIRMS_SOURCE_PRIORITY = {
    "VIIRS_SNPP_SP": 0,
    "VIIRS_SNPP_NRT": 1,
}

METEO_COLUMNS = ("temperatura", "humedad_relativa", "velocidad_viento_kmh")

# Recorte físico DMC / condiciones de superficie (Valparaíso, costa–precordillera).
PHYSICAL_BOUNDS: dict[str, tuple[float, float]] = {
    "temperatura": (-10.0, 50.0),
    "humedad_relativa": (0.0, 100.0),
    "velocidad_viento_kmh": (0.0, 200.0),
}

ZSCORE_THRESHOLD = 3.0


def _dedupe_keys_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Construye columnas auxiliares de clave FIRMS (misma semántica que backfill)."""
    keyed = df.copy()
    keyed["_latitude_key"] = pd.to_numeric(keyed["latitude"], errors="coerce").round(
        DEDUP_COORD_DECIMALS
    )
    keyed["_longitude_key"] = pd.to_numeric(keyed["longitude"], errors="coerce").round(
        DEDUP_COORD_DECIMALS
    )
    keyed["_time_key"] = (
        keyed["acq_time"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    )
    return keyed


def deduplicate_fires(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Elimina detecciones FIRMS repetidas; conserva la fila de mayor calidad de join."""
    if df.empty:
        return df.copy(), 0

    keyed = _dedupe_keys_frame(df)
    keyed["_join_priority"] = keyed["join_status"].map(JOIN_STATUS_PRIORITY).fillna(99)
    if "firms_source" in keyed.columns:
        keyed["_source_priority"] = keyed["firms_source"].map(
            lambda s: FIRMS_SOURCE_PRIORITY.get(s, 2) if pd.notna(s) else 2
        )
    else:
        keyed["_source_priority"] = 2
    if "delta_minutos" not in keyed.columns:
        keyed["delta_minutos"] = 999.0
    keyed["delta_minutos"] = keyed["delta_minutos"].fillna(999.0)

    keyed = keyed.sort_values(
        ["_join_priority", "delta_minutos", "_source_priority"],
        ascending=[True, True, True],
        kind="stable",
    )

    dedupe_cols = [
        "_latitude_key",
        "_longitude_key",
        "acq_date",
        "_time_key",
        "satellite",
        "instrument",
    ]
    before = len(keyed)
    deduped = keyed.drop_duplicates(subset=dedupe_cols, keep="first")
    removed = before - len(deduped)

    helper_cols = [
        "_latitude_key",
        "_longitude_key",
        "_time_key",
        "_join_priority",
        "_source_priority",
    ]
    return deduped.drop(columns=helper_cols).reset_index(drop=True), removed


def _apply_physical_bounds(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Anula valores meteo fuera de rango físico (solo matched)."""
    result = df.copy()
    clipped = 0
    matched = result["join_status"] == JOIN_STATUS_MATCHED

    for col, (low, high) in PHYSICAL_BOUNDS.items():
        if col not in result.columns:
            continue
        out_of_range = matched & ((result[col] < low) | (result[col] > high))
        clipped += int(out_of_range.sum())
        result.loc[out_of_range, col] = pd.NA

    return result, clipped


def _winsorize_zscore_matched(df: pd.DataFrame) -> tuple[pd.DataFrame, int, pd.Series, list[dict[str, Any]]]:
    """Winsoriza outliers meteo (|z|>3) a la media del subconjunto matched."""
    result = df.copy()
    winsorized = pd.Series(False, index=result.index)
    events: list[dict[str, Any]] = []
    matched = result["join_status"] == JOIN_STATUS_MATCHED
    total_winsorized = 0

    for col in METEO_COLUMNS:
        if col not in result.columns:
            continue
        series = result.loc[matched, col].astype("float64")
        valid = series.dropna()
        if valid.empty:
            continue
        mean = float(valid.mean())
        std = float(valid.std())
        if std == 0.0:
            continue
        z = (series - mean) / std
        outlier_idx = z.index[z.abs() > ZSCORE_THRESHOLD]
        for idx in outlier_idx:
            original = float(series.loc[idx])
            z_val = float(z.loc[idx])
            row = result.loc[idx]
            events.append(
                {
                    "columna": col,
                    "acq_date": str(row.get("acq_date", "")),
                    "acq_time": int(row["acq_time"]) if pd.notna(row.get("acq_time")) else None,
                    "ignition_ts": str(row["ignition_ts"]) if "ignition_ts" in row and pd.notna(row["ignition_ts"]) else None,
                    "valor_original": original,
                    "valor_corregido": mean,
                    "media_matched_mu": round(mean, 4),
                    "desviacion_std": round(std, 4),
                    "delta_abs_vs_mu": round(abs(original - mean), 4),
                    "z_score": round(z_val, 4),
                }
            )
        if len(outlier_idx):
            result.loc[outlier_idx, col] = mean
            winsorized.loc[outlier_idx] = True
            total_winsorized += len(outlier_idx)

    return result, total_winsorized, winsorized, events


def _impute_meteo_matched(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Imputa mediana de matched sobre nulos meteo en filas matched."""
    result = df.copy()
    matched = result["join_status"] == JOIN_STATUS_MATCHED
    imputed = 0

    for col in METEO_COLUMNS:
        if col not in result.columns:
            continue
        subset = result.loc[matched, col]
        if subset.isna().all():
            continue
        median = float(subset.median())
        null_mask = matched & result[col].isna()
        count = int(null_mask.sum())
        if count:
            result.loc[null_mask, col] = median
            imputed += count

    return result, imputed


def _winsorization_observations(events: list[dict[str, Any]]) -> list[str]:
    """Notas de patrón en winsorización (solo documentación, sin acción automática)."""
    if not events:
        return []

    columns = {e["columna"] for e in events}
    dates = {e["acq_date"] for e in events}
    times = sorted({e["acq_time"] for e in events if e.get("acq_time") is not None})
    notes: list[str] = []

    if len(columns) == 1:
        notes.append(
            f"Todos los valores winsorizados pertenecen a la columna `{next(iter(columns))}`."
        )
    if len(dates) == 1:
        notes.append(
            f"Concentrados en un único día de ignición: {next(iter(dates))}."
        )
    if len(times) <= 2 and times:
        hhmm = ", ".join(f"{t // 100:02d}:{t % 100:02d} UTC" for t in times)
        notes.append(f"Ventana horaria acotada: {hhmm}.")

    originals = {e["valor_original"] for e in events}
    if len(originals) == 1:
        notes.append(
            f"Mismo valor original antes de corregir: {next(iter(originals))} "
            f"(μ del mes ≈ {events[0]['media_matched_mu']}, |z| > {ZSCORE_THRESHOLD})."
        )

    if notes:
        notes.append(
            "El pico de viento winsorizado es probablemente un valor real de DMC, no un error "
            "de sensor: se corrigió por diseño estadístico (Z-score |z|>3), no porque se "
            "sospeche que el dato esté mal."
        )
        notes.append(
            "Revisar tramo DMC / igniciones de ese día si se amplía el histórico; "
            "no requiere acción inmediata en feb-2025."
        )
    return notes


def clean_fires_meteo_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Pipeline SAPI-32: dedup → recorte físico → Z-score → imputación (solo matched)."""
    summary: dict[str, Any] = {"input_rows": len(df)}

    deduped, removed = deduplicate_fires(df)
    summary["duplicates_removed"] = removed

    bounded, clipped = _apply_physical_bounds(deduped)
    summary["physical_clips"] = clipped

    winsorized_df, winsorize_count, flag, win_events = _winsorize_zscore_matched(bounded)
    winsorized_df["meteo_outlier_winsorized"] = flag
    summary["values_winsorized"] = winsorize_count
    summary["winsorization_events"] = win_events
    summary["observaciones"] = _winsorization_observations(win_events)

    cleaned, imputed = _impute_meteo_matched(winsorized_df)
    summary["nulls_imputed_matched"] = imputed
    summary["output_rows"] = len(cleaned)
    summary["by_join_status"] = cleaned["join_status"].value_counts().to_dict()

    non_matched = cleaned["join_status"] != JOIN_STATUS_MATCHED
    meteo_nulls_preserved = int(
        cleaned.loc[non_matched, list(METEO_COLUMNS)].isna().all(axis=1).sum()
    ) if non_matched.any() else 0
    summary["non_matched_rows_with_null_meteo"] = meteo_nulls_preserved

    return cleaned, summary
