"""Pruebas de `src.procesamiento.pipeline_validators`."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.procesamiento.pipeline_validators import (
    validate_event_independence,
    validate_feature_set_contract,
    validate_manifest_matches_dataset,
    validate_missing_data_handling,
    validate_pipeline_isolation,
)

T1 = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
T2 = pd.Timestamp("2026-01-02 12:00:00", tz="UTC")


def _dataset(rows):
    return pd.DataFrame(
        [
            {
                "cell_id": cell,
                "forecast_time": T,
                "target_window_start": T,
                "target_window_end": T + pd.Timedelta(hours=6),
                "target": target,
            }
            for cell, T, target in rows
        ]
    )


def _arrivals(rows):
    return pd.DataFrame([{"event_id": eid, "cell_id": cell, "first_arrival": ts} for eid, cell, ts in rows])


def test_event_independence_passes_when_positives_spread_across_episodes() -> None:
    ds = _dataset([("VP-001", T1, 1), ("VP-002", T2, 1)])
    arr = _arrivals([(1, "VP-001", T1 + pd.Timedelta(hours=1)), (2, "VP-002", T2 + pd.Timedelta(hours=1))])
    result = validate_event_independence(ds, arr)
    assert result.status == "PASS"


def test_event_independence_warns_when_one_episode_dominates() -> None:
    ds = _dataset([("VP-001", T1, 1), ("VP-002", T1, 1), ("VP-003", T2, 1)])
    arr = _arrivals(
        [
            (1, "VP-001", T1 + pd.Timedelta(hours=1)),
            (1, "VP-002", T1 + pd.Timedelta(hours=1)),
            (2, "VP-003", T2 + pd.Timedelta(hours=1)),
        ]
    )
    result = validate_event_independence(ds, arr)
    assert result.status == "WARN"
    assert result.evidence["largest_episode_fraction"] == 2 / 3


def test_event_independence_never_fails() -> None:
    """La concentración de episodios es una propiedad de la muestra, no un bug de código."""
    ds = _dataset([("VP-001", T1, 1)])
    arr = _arrivals([(1, "VP-001", T1 + pd.Timedelta(hours=1))])
    result = validate_event_independence(ds, arr)
    assert result.status in ("PASS", "WARN")


def test_missing_data_fails_without_flag_column() -> None:
    ds = pd.DataFrame({"meteo_actual_temp": [20.0, None, 22.0]})
    result = validate_missing_data_handling(ds, nullable_features=["meteo_actual_temp"])
    assert result.status == "FAIL"


def test_missing_data_passes_with_consistent_flag() -> None:
    ds = pd.DataFrame(
        {
            "meteo_actual_temp": [20.0, None, 22.0],
            "meteo_actual_temp_missing": [False, True, False],
        }
    )
    result = validate_missing_data_handling(ds, nullable_features=["meteo_actual_temp"])
    assert result.status == "PASS"


def test_missing_data_accepts_explicit_pairs_one_flag_for_several_columns() -> None:
    """El caso real: temp/hr/viento de un mismo lag comparten un solo flag
    porque vienen de la misma observación (o ninguna, si no hubo match)."""
    ds = pd.DataFrame(
        {
            "meteo_actual_temp": [20.0, None, 22.0],
            "meteo_actual_hr": [50.0, None, 60.0],
            "meteo_actual_missing": [False, True, False],
        }
    )
    result = validate_missing_data_handling(
        ds,
        nullable_features=[("meteo_actual_temp", "meteo_actual_missing"), ("meteo_actual_hr", "meteo_actual_missing")],
    )
    assert result.status == "PASS"


def test_missing_data_fails_when_flag_disagrees_with_real_nans() -> None:
    ds = pd.DataFrame(
        {
            "meteo_actual_temp": [20.0, None, 22.0],
            "meteo_actual_temp_missing": [False, False, False],  # miente sobre la fila 1
        }
    )
    result = validate_missing_data_handling(ds, nullable_features=["meteo_actual_temp"])
    assert result.status == "FAIL"


def test_feature_contract_passes_for_proper_nested_sets() -> None:
    sets = {"A": ["x"], "B": ["x", "y"], "C": ["x", "y", "z"]}
    result = validate_feature_set_contract(sets)
    assert result.status == "PASS"


def test_feature_contract_fails_when_a_is_not_subset_of_b() -> None:
    sets = {"A": ["x", "w"], "B": ["x", "y"]}  # 'w' no está en B
    result = validate_feature_set_contract(sets)
    assert result.status == "FAIL"


def test_feature_contract_fails_on_cell_id() -> None:
    sets = {"A": ["cell_id", "x"]}
    result = validate_feature_set_contract(sets)
    assert result.status == "FAIL"


def test_feature_contract_fails_on_ndvi() -> None:
    sets = {"A": ["x"], "D": ["x", "ndvi"]}
    result = validate_feature_set_contract(sets)
    assert result.status == "FAIL"


def test_pipeline_isolation_passes_on_a_clean_file(tmp_path: Path) -> None:
    clean = tmp_path / "clean.py"
    clean.write_text("import pandas as pd\ndef f(): return pd.DataFrame()\n", encoding="utf-8")
    result = validate_pipeline_isolation([clean])
    assert result.status == "PASS"


def test_pipeline_isolation_fails_on_legacy_import(tmp_path: Path) -> None:
    dirty = tmp_path / "dirty.py"
    dirty.write_text("from src.modelo.baseline import BaselineModel\n", encoding="utf-8")
    result = validate_pipeline_isolation([dirty])
    assert result.status == "FAIL"


def test_pipeline_isolation_fails_on_dataset_valparaiso_reference(tmp_path: Path) -> None:
    dirty = tmp_path / "dirty2.py"
    dirty.write_text("path = 'data/processed/dataset_valparaiso.parquet'\n", encoding="utf-8")
    result = validate_pipeline_isolation([dirty])
    assert result.status == "FAIL"


def test_pipeline_isolation_on_the_real_new_pipeline_files() -> None:
    """El chequeo real sobre los módulos del pipeline nuevo, hoy.

    `pipeline_validators.py` queda deliberadamente fuera de esta lista: su
    propio código cita los nombres prohibidos como texto (para poder
    buscarlos), lo que dispararía un falso positivo — no es una
    dependencia real, es el propio detector.
    """
    repo_root = Path(__file__).resolve().parent.parent
    files = [
        repo_root / "src" / "procesamiento" / "regional_meteo.py",
        repo_root / "src" / "procesamiento" / "episodes.py",
        repo_root / "src" / "procesamiento" / "target_builder.py",
        repo_root / "src" / "procesamiento" / "temporal_features.py",
        repo_root / "src" / "procesamiento" / "causality_validator.py",
        repo_root / "src" / "procesamiento" / "episode_evaluation.py",
        repo_root / "src" / "procesamiento" / "row_explainer.py",
        repo_root / "scripts" / "build_temporal_dataset.py",
        repo_root / "scripts" / "build_event_traceability_table.py",
        repo_root / "scripts" / "megaevento_report.py",
        repo_root / "scripts" / "experiment_abcd.py",
    ]
    result = validate_pipeline_isolation(files)
    assert result.status == "PASS", result.detail


def _manifest_dataset_fixture():
    ds = pd.DataFrame(
        {
            "cell_id": ["VP-001", "VP-001", "VP-002", "VP-002"],
            "forecast_time": [T1, T2, T1, T2],
            "target_window_end": [T1 + pd.Timedelta(hours=6), T2 + pd.Timedelta(hours=6),
                                   T1 + pd.Timedelta(hours=6), T2 + pd.Timedelta(hours=6)],
            "excluded": [False, False, False, True],
            "target": [1, 0, 0, None],
            "target_event_id": [7, None, None, None],
            "meteo_actual_missing": [False, True, False, False],
        }
    )
    manifest = {
        "n_rows": 4,
        "n_excluded": 1,
        "n_rows_eligible": 3,
        "n_positive_rows": 1,
        "n_negative_rows": 2,
        "n_positive_raw_episodes": 1,
        "n_celdas": 2,
        "n_timestamps": 2,
        "forecast_horizon_hours": 6.0,
        "meteo_age_hours_stats": {"n_sin_meteo_actual": 1},
    }
    return manifest, ds


def test_manifest_matches_dataset_passes_when_every_number_is_reproducible() -> None:
    manifest, ds = _manifest_dataset_fixture()
    result = validate_manifest_matches_dataset(manifest, ds)
    assert result.status == "PASS", result.detail


def test_manifest_matches_dataset_fails_on_a_single_wrong_number() -> None:
    """Sección 3 de la auditoría: FAIL, no WARN, ante CUALQUIER discrepancia
    — un manifest desactualizado no es una advertencia menor."""
    manifest, ds = _manifest_dataset_fixture()
    manifest["n_positive_rows"] = 99  # mentira deliberada
    result = validate_manifest_matches_dataset(manifest, ds)
    assert result.status == "FAIL"
    assert "n_positive_rows" in result.detail


def test_manifest_matches_dataset_fails_on_stale_raw_episode_count() -> None:
    manifest, ds = _manifest_dataset_fixture()
    manifest["n_positive_raw_episodes"] = 5
    result = validate_manifest_matches_dataset(manifest, ds)
    assert result.status == "FAIL"
    assert "n_positive_raw_episodes" in result.detail


def test_manifest_matches_dataset_fails_on_stale_missing_meteo_count() -> None:
    manifest, ds = _manifest_dataset_fixture()
    manifest["meteo_age_hours_stats"]["n_sin_meteo_actual"] = 0
    result = validate_manifest_matches_dataset(manifest, ds)
    assert result.status == "FAIL"


def test_manifest_matches_dataset_against_the_real_generated_dataset() -> None:
    """Auditoría 06-09-2026, sección 3: el chequeo real, no solo el fixture.
    Se salta si el dataset real todavía no fue generado en este entorno."""
    repo_root = Path(__file__).resolve().parent.parent
    parquet_path = repo_root / "data" / "processed" / "temporal_dataset_h6.parquet"
    manifest_path = repo_root / "reports" / "temporal_dataset_h6_manifest.json"
    if not parquet_path.exists() or not manifest_path.exists():
        import pytest

        pytest.skip("temporal_dataset_h6 no generado en este entorno")
    import json

    ds = pd.read_parquet(parquet_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = validate_manifest_matches_dataset(manifest, ds)
    assert result.status == "PASS", result.detail
