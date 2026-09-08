"""Pruebas de descubrimiento de archivos de `load_regional_meteo_series`
(Fase 3, 2026-09-07): excluir explícitamente los `*_conflicto_*.json` que
deja `scripts/backfill_dmc_historico.py`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.procesamiento.regional_meteo import load_regional_meteo_series

STATION = "330007"


def _write_historico(dir_path: Path, filename: str, momentos: list[str]) -> None:
    payload = {
        STATION: {
            "datosEstaciones": {
                "datos": [
                    {"momento": m, "temperatura": "20.0 °C", "humedadRelativa": "50 %", "fuerzaDelViento": "5 kt"}
                    for m in momentos
                ]
            }
        }
    }
    (dir_path / filename).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_loads_a_real_historico_file(tmp_path: Path) -> None:
    _write_historico(tmp_path, f"dmc_historico_{STATION}_2021-08.json", ["2021-08-01 00:00:00"])
    series = load_regional_meteo_series(STATION, raw_dir=tmp_path)
    assert len(series) == 1
    assert series.iloc[0]["station_id"] == STATION


def test_ignores_conflict_files_left_by_the_backfill_script(tmp_path: Path) -> None:
    """Auditoría Fase 3: un archivo `_conflicto_` es evidencia para revisión
    manual, nunca datos a mezclar en silencio con el archivo original."""
    _write_historico(tmp_path, f"dmc_historico_{STATION}_2021-08.json", ["2021-08-01 00:00:00"])
    _write_historico(
        tmp_path, f"dmc_historico_{STATION}_2021-08_conflicto_2026-09-07.json", ["2021-08-01 12:00:00"]
    )
    series = load_regional_meteo_series(STATION, raw_dir=tmp_path)
    # Solo el momento del archivo original -- el del archivo de conflicto
    # NUNCA debe aparecer en la serie cargada.
    assert len(series) == 1
    assert str(series.iloc[0]["momento"]).startswith("2021-08-01 00:00:00")


def test_multiple_months_are_combined_and_sorted(tmp_path: Path) -> None:
    _write_historico(tmp_path, f"dmc_historico_{STATION}_2021-09.json", ["2021-09-01 00:00:00"])
    _write_historico(tmp_path, f"dmc_historico_{STATION}_2021-08.json", ["2021-08-01 00:00:00"])
    series = load_regional_meteo_series(STATION, raw_dir=tmp_path)
    assert len(series) == 2
    assert list(series["momento"]) == sorted(series["momento"])
