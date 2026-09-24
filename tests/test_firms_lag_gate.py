"""Gate de desfase FIRMS en la inferencia (SAPI-71 Fase B).

lag = fecha(forecast_time) - coverage_end: <=3 días al día, 4..7 con
aviso, >7 no se puntúa (PrototypeUnavailableError -> 503 en el puente).
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

import src.inference.prototype_service as svc
from src.procesamiento.firms_source import FirmsSource

COVERAGE_END = date(2026, 8, 30)


@pytest.mark.parametrize(
    "forecast_time,lag,status",
    [
        ("2026-08-20T00:00Z", -10, svc.FIRMS_STATUS_CURRENT),  # T histórico ya cubierto
        ("2026-08-30T18:00Z", 0, svc.FIRMS_STATUS_CURRENT),
        ("2026-09-01T00:00Z", 2, svc.FIRMS_STATUS_CURRENT),  # estado real hoy
        ("2026-09-02T23:59Z", 3, svc.FIRMS_STATUS_CURRENT),
        ("2026-09-03T00:00Z", 4, svc.FIRMS_STATUS_STALE),
        ("2026-09-06T18:00Z", 7, svc.FIRMS_STATUS_STALE),
    ],
)
def test_classify_firms_lag_thresholds(forecast_time, lag, status):
    assert svc.classify_firms_lag(pd.Timestamp(forecast_time), COVERAGE_END) == (
        lag,
        status,
    )


def test_lag_over_seven_days_is_unavailable():
    with pytest.raises(svc.PrototypeUnavailableError, match="8 días"):
        svc.classify_firms_lag(pd.Timestamp("2026-09-07T00:00Z"), COVERAGE_END)


def test_capture_refuses_stale_firms_before_reading_it(monkeypatch, tmp_path):
    """El gate corre antes de leer el CSV: con 12 días de desfase respecto
    del forecast_time del snapshot (2026-09-01) no se llega ni a abrir el
    archivo (que acá ni siquiera existe)."""
    stale = FirmsSource(
        path=tmp_path / "no_se_lee.csv",
        origin="baseline",
        coverage_start=date(2021, 8, 30),
        coverage_end=date(2026, 8, 20),
    )
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "1")
    monkeypatch.setattr(svc, "resolve_firms_source", lambda **_kwargs: stale)
    with pytest.raises(svc.PrototypeUnavailableError, match="12 días"):
        svc.capture_scoring_inputs()


def test_grid_result_firms_fields_default_to_none():
    """Campos nuevos con default: quien construya GridScoreResult sin ellos
    (tests, n8n-bridge) sigue funcionando."""
    fields = svc.GridScoreResult.__dataclass_fields__
    for name in (
        "firms_origin",
        "firms_coverage_end",
        "firms_lag_days",
        "firms_status",
    ):
        assert fields[name].default is None
