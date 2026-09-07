"""Pruebas de `scripts/megaevento_report.py` (sección 10 de la auditoría
06-09-2026)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = REPO_ROOT / "data" / "processed" / "temporal_dataset_h6.parquet"

pytestmark = pytest.mark.skipif(
    not DATASET_PATH.exists(),
    reason="temporal_dataset_h6.parquet no existe — correr scripts/build_temporal_dataset.py primero",
)


def test_megaevento_report_reproduces_known_concentration() -> None:
    """Ancla el hallazgo de la auditoría — actualizado tras el backfill DMC
    de Fase 3 (2026-09-07): antes del backfill el 2024-02-03 explicaba 50%
    de los positivos de TODO el dataset (23/46); con ~5 años continuos de
    datos reales, esa misma cifra absoluta (23 filas) ahora es 21.5%
    (23/107) — la concentración bajó porque hay MUCHA más señal positiva
    real en otros períodos, no porque el día se haya vuelto menos
    importante en sí mismo. Si esta fracción vuelve a subir por encima de
    ~0.3 en una corrida futura, es señal de que el dataset se redujo o de
    que algo vuelve a depender de un solo día — vale la pena revisar."""
    from scripts.megaevento_report import build_report

    report = build_report("2024-02-03")
    assert report["n_positive_rows_dataset_completo"] > 0
    assert report["n_positive_rows_ese_dia"] == 23  # cifra absoluta, no cambia con el backfill
    assert report["fraccion_del_dataset_completo"] < 0.3  # ya no domina como antes del backfill
    assert report["fraccion_del_dataset_completo"] > 0.1  # pero sigue siendo una fracción real, no despreciable
    assert report["n_raw_episodes"] > 1  # son MUCHOS event_id, no uno solo


def test_megaevento_report_on_a_day_with_no_activity_is_well_defined() -> None:
    from scripts.megaevento_report import build_report

    report = build_report("2019-01-01")  # fuera del rango de datos reales
    assert report["n_positive_rows_ese_dia"] == 0
    assert report["n_raw_episodes"] == 0
