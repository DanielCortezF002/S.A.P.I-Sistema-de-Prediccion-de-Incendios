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
    """Ancla el hallazgo de la auditoría: si esta fracción baja de forma
    importante en una corrida futura (p.ej. tras un backfill más amplio),
    es una señal real de que vale la pena reabrir la conversación sobre
    qué tan generalizable es el rendimiento reportado — no algo que deba
    pasar inadvertido."""
    from scripts.megaevento_report import build_report

    report = build_report("2024-02-03")
    assert report["n_positive_rows_dataset_completo"] > 0
    assert report["n_positive_rows_ese_dia"] > 0
    # El día domina una fracción sustancial del dataset completo (hallazgo
    # real de esta auditoría: 50%) — el umbral de 0.3 es deliberadamente
    # laxo, solo para detectar que la concentración NO desapareció.
    assert report["fraccion_del_dataset_completo"] > 0.3
    assert report["n_raw_episodes"] > 1  # son MUCHOS event_id, no uno solo


def test_megaevento_report_on_a_day_with_no_activity_is_well_defined() -> None:
    from scripts.megaevento_report import build_report

    report = build_report("2019-01-01")  # fuera del rango de datos reales
    assert report["n_positive_rows_ese_dia"] == 0
    assert report["n_raw_episodes"] == 0
