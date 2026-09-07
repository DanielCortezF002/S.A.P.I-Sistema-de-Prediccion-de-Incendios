"""Validadores del pipeline temporal, separados por tipo de riesgo.

`causality_validator.validate_temporal_causality` cubre un solo tipo de
problema (timestamps de feature vs `forecast_time`). La auditoría del
06-09-2026 encontró que eso deja sin cubrir: independencia estadística
entre filas del mismo episodio, manejo de datos faltantes, contrato de
features entre modelos A/B/C/D, y aislamiento del pipeline legacy. Cada
uno se valida por separado — un resultado agregado en uno solo ocultaría
cuál de los cinco riesgos realmente está resuelto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pandas as pd

from src.procesamiento.episode_evaluation import largest_episode_fraction

Status = Literal["PASS", "WARN", "FAIL"]

# Umbral para "un solo episodio domina la evaluación": más de la mitad de
# los positivos evaluados es el punto en que ese episodio pesa más que
# todos los demás juntos — no es arbitrario, es el punto de mayoría simple.
EVENT_CONCENTRATION_WARN_THRESHOLD = 0.5

# Nunca deben aparecer como dependencia del pipeline nuevo — confirmado su
# ausencia por auditoría manual el 06-09-2026; este validador la hace
# permanente y automática.
FORBIDDEN_LEGACY_REFERENCES = (
    "src.modelo.baseline",
    "src.modelo.optimizer",
    "from src.procesamiento.data_processor import",
    "dataset_valparaiso",
    "demo_seed",
    "generate_seed",
    "bootstrap_xgboost_model",
)


@dataclass
class ValidationResult:
    name: str
    status: Status
    detail: str
    evidence: dict = field(default_factory=dict)


def validate_event_independence(
    dataset: pd.DataFrame,
    arrivals: pd.DataFrame,
    warn_threshold: float = EVENT_CONCENTRATION_WARN_THRESHOLD,
) -> ValidationResult:
    """WARN si un solo episodio explica más de `warn_threshold` de los
    positivos del conjunto evaluado. Nunca FAIL — la concentración de
    episodios no es un bug de código, es una propiedad de la muestra que
    hay que reportar, no bloquear silenciosamente."""
    fraction, dominant_event = largest_episode_fraction(dataset, arrivals)
    n_pos = int((dataset["target"] == 1).sum())
    if n_pos == 0:
        return ValidationResult(
            "EVENT INDEPENDENCE", "WARN", "Sin positivos en el conjunto evaluado — no evaluable.",
            {"n_positivos": 0},
        )
    status: Status = "WARN" if fraction > warn_threshold else "PASS"
    return ValidationResult(
        "EVENT INDEPENDENCE",
        status,
        f"El episodio más grande (event_id={dominant_event}) explica {fraction:.1%} de los positivos.",
        {"largest_episode_fraction": fraction, "dominant_event_id": dominant_event, "n_positivos": n_pos},
    )


def validate_missing_data_handling(
    dataset: pd.DataFrame,
    nullable_features: list[str] | list[tuple[str, str]],
) -> ValidationResult:
    """FAIL si una feature nullable no tiene su columna de flag
    correspondiente, o si esa columna no coincide exactamente con los NaN
    reales (evita que un `0.0` disfrazado de "sin dato" pase inadvertido).

    `nullable_features` acepta dos formas:
    - `["col", ...]` — asume flag `f"{col}_missing"` (una feature, un flag).
    - `[("col", "flag_col"), ...]` — pares explícitos, para el caso real de
      `temporal_features.py`: varias columnas (`meteo_actual_temp/hr/viento
      /regla_30_30_30`) comparten UN solo flag por bloque
      (`meteo_actual_missing`), porque vienen de la misma observación —
      no tiene sentido pedir un flag por columna cuando las cuatro faltan
      o están presentes siempre juntas.
    """
    pairs: list[tuple[str, str]] = [
        item if isinstance(item, tuple) else (item, f"{item}_missing") for item in nullable_features
    ]
    problems = []
    for col, flag_col in pairs:
        if flag_col not in dataset.columns:
            problems.append(f"falta '{flag_col}' para la feature nullable '{col}'")
            continue
        expected = dataset[col].isna()
        actual = dataset[flag_col].astype(bool)
        if not (expected == actual).all():
            n_mismatch = int((expected != actual).sum())
            problems.append(f"'{flag_col}' no coincide con los NaN reales de '{col}' en {n_mismatch} filas")

    if problems:
        return ValidationResult("MISSING DATA", "FAIL", "; ".join(problems), {"problemas": problems})
    return ValidationResult(
        "MISSING DATA", "PASS", f"{len(pairs)} features nullable con su flag de ausencia consistente.", {}
    )


def validate_feature_set_contract(
    feature_sets: dict[str, list[str]],
    forbidden_features: tuple[str, ...] = ("cell_id", "ndvi", "ignicion"),
) -> ValidationResult:
    """FAIL si el orden A⊆B⊆C⊆D no se cumple, o si aparece una feature
    prohibida (identificador, sintética, o target) en cualquier modelo."""
    names = list(feature_sets.keys())
    problems = []

    for name, features in feature_sets.items():
        for forbidden in forbidden_features:
            if forbidden in features:
                problems.append(f"'{forbidden}' aparece en el modelo '{name}'")

    for a, b in zip(names, names[1:]):
        if not set(feature_sets[a]) <= set(feature_sets[b]):
            faltantes = set(feature_sets[a]) - set(feature_sets[b])
            problems.append(f"'{a}' no es subconjunto de '{b}' (faltan: {sorted(faltantes)})")

    if problems:
        return ValidationResult("FEATURE CONTRACT", "FAIL", "; ".join(problems), {"problemas": problems})
    return ValidationResult(
        "FEATURE CONTRACT", "PASS", f"{' ⊆ '.join(names)} verificado, sin features prohibidas.", {}
    )


def validate_pipeline_isolation(
    module_paths: list[Path],
    forbidden: tuple[str, ...] = FORBIDDEN_LEGACY_REFERENCES,
) -> ValidationResult:
    """FAIL si algún archivo del pipeline nuevo referencia texto de una
    dependencia legacy prohibida (import, nombre de archivo, etc.)."""
    problems = []
    for path in module_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                problems.append(f"{path.name} contiene referencia prohibida: '{token}'")

    if problems:
        return ValidationResult("PIPELINE ISOLATION", "FAIL", "; ".join(problems), {"problemas": problems})
    return ValidationResult(
        "PIPELINE ISOLATION", "PASS", f"{len(module_paths)} archivos revisados, sin referencias legacy.", {}
    )


def validate_manifest_matches_dataset(manifest: dict, dataset: pd.DataFrame) -> ValidationResult:
    """FAIL (nunca WARN) si CUALQUIER número que el manifest afirma no se
    puede reproducir recalculándolo directamente sobre el parquet.

    Sección 3 de la auditoría 06-09-2026: un manifest que se queda
    desactualizado tras un cambio de código es, para efectos prácticos,
    un manifest que miente. Este validador no confía en que quien generó
    el manifest lo hizo bien — recalcula cada cifra desde cero contra el
    DataFrame real y compara.
    """
    problems: list[str] = []
    checks: dict[str, tuple[object, object]] = {}

    def check(label: str, manifest_value, actual_value) -> None:
        checks[label] = (manifest_value, actual_value)
        if manifest_value != actual_value:
            problems.append(f"{label}: manifest={manifest_value!r} vs dataset={actual_value!r}")

    check("n_rows", manifest.get("n_rows"), len(dataset))

    if "excluded" in dataset.columns:
        n_excluded_real = int(dataset["excluded"].sum())
        n_eligible_real = int((~dataset["excluded"]).sum())
        check("n_excluded", manifest.get("n_excluded"), n_excluded_real)
        check("n_rows_eligible", manifest.get("n_rows_eligible"), n_eligible_real)
        eligible = dataset[~dataset["excluded"]]
    else:
        problems.append("dataset no tiene columna 'excluded' — no se puede validar n_excluded/n_rows_eligible")
        eligible = dataset

    if "target" in eligible.columns:
        check("n_positive_rows", manifest.get("n_positive_rows"), int((eligible["target"] == 1).sum()))
        check("n_negative_rows", manifest.get("n_negative_rows"), int((eligible["target"] == 0).sum()))
    else:
        problems.append("dataset no tiene columna 'target'")

    if "target_event_id" in dataset.columns and "target" in dataset.columns:
        positivos = dataset[dataset["target"] == 1]
        check(
            "n_positive_raw_episodes",
            manifest.get("n_positive_raw_episodes"),
            int(positivos["target_event_id"].dropna().nunique()),
        )
    else:
        problems.append("dataset no tiene 'target_event_id' — n_positive_raw_episodes no verificable")

    if "cell_id" in dataset.columns:
        check("n_celdas", manifest.get("n_celdas"), int(dataset["cell_id"].nunique()))
    if "forecast_time" in dataset.columns:
        check("n_timestamps", manifest.get("n_timestamps"), int(dataset["forecast_time"].nunique()))

    if "meteo_actual_missing" in dataset.columns:
        n_missing_real = int(dataset["meteo_actual_missing"].astype(bool).sum())
        n_missing_manifest = manifest.get("meteo_age_hours_stats", {}).get("n_sin_meteo_actual")
        check("meteo_age_hours_stats.n_sin_meteo_actual", n_missing_manifest, n_missing_real)

    if "forecast_time" in dataset.columns and "target_window_end" in dataset.columns:
        horas = (dataset["target_window_end"] - dataset["forecast_time"]).dt.total_seconds() / 3600.0
        if horas.nunique() == 1:
            check("forecast_horizon_hours", manifest.get("forecast_horizon_hours"), float(horas.iloc[0]))
        else:
            problems.append(f"target_window_end - forecast_time no es constante: valores {sorted(horas.unique())}")

    if problems:
        return ValidationResult("MANIFEST vs DATASET", "FAIL", "; ".join(problems), {"checks": checks})
    return ValidationResult(
        "MANIFEST vs DATASET", "PASS", f"{len(checks)} cifras del manifest reproducidas exactamente desde el parquet.",
        {"checks": checks},
    )


def format_report(results: list[ValidationResult]) -> str:
    lines = []
    width = max(len(r.name) for r in results)
    for r in results:
        lines.append(f"{r.name.ljust(width)}  {r.status:<5}  {r.detail}")
    return "\n".join(lines)
