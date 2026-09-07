"""Pruebas de `scripts/backfill_dmc_historico.py` — idempotencia, detección
de conflictos y cálculo del rango de meses. Sin red real: `_fetch_month`
se reemplaza por un mock determinista."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backfill_dmc_historico import _months_in_range, _records_equal, run_backfill


def _payload(records: list[dict]) -> dict:
    return {
        "organismo": "DMC",
        "fechaCreacion": "07-09-2026 12:00",  # cambia entre respuestas, no debe afectar la comparación
        "datosEstaciones": {"estacion": {"codigoNacional": "330007"}, "datos": records},
    }


def _rec(momento: str, temp: float = 20.0, hr: float = 50.0, viento: float = 5.0) -> dict:
    return {"momento": momento, "temperatura": temp, "humedadRelativa": hr, "fuerzaDelViento": viento}


def test_months_in_range_spans_years_correctly() -> None:
    months = _months_in_range(date(2021, 11, 1), date(2022, 2, 1))
    assert months == [(2021, 11), (2021, 12), (2022, 1), (2022, 2)]


def test_records_equal_ignores_fechacreacion_and_order() -> None:
    a = [_rec("2026-01-01 00:00:00"), _rec("2026-01-01 00:15:00")]
    b = [_rec("2026-01-01 00:15:00"), _rec("2026-01-01 00:00:00")]  # orden distinto
    assert _records_equal(a, b)


def test_records_equal_detects_a_real_difference() -> None:
    a = [_rec("2026-01-01 00:00:00", temp=20.0)]
    b = [_rec("2026-01-01 00:00:00", temp=25.0)]  # mismo momento, temperatura distinta
    assert not _records_equal(a, b)


def test_run_backfill_writes_new_months_and_skips_identical_ones(tmp_path, monkeypatch) -> None:
    import scripts.backfill_dmc_historico as mod

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    report_path = tmp_path / "manifest.json"
    monkeypatch.setattr(mod, "RAW_DIR", raw_dir)
    monkeypatch.setattr(mod, "REPORT_PATH", report_path)
    monkeypatch.setattr(mod, "PERIOD_START", date(2021, 8, 1))
    monkeypatch.setattr(mod, "PERIOD_END", date(2021, 8, 1))  # un solo mes: 2021-08
    monkeypatch.setattr(mod, "SLEEP_BETWEEN_REQUESTS", 0)

    def fake_fetch(station, year, month):
        return _payload([_rec(f"{year}-{month:02d}-01 00:00:00")])

    monkeypatch.setattr(mod, "_fetch_month", fake_fetch)

    resultado = mod.run_backfill()
    assert resultado["meses_nuevos_ok"] == ["2021-08"]
    assert (raw_dir / "dmc_historico_330007_2021-08.json").exists()

    # segunda corrida: mismo mes, mismo contenido -> debe hacer skip, no escribir de nuevo
    resultado2 = mod.run_backfill()
    assert resultado2["meses_ya_existentes_identicos"] == ["2021-08"]
    assert resultado2["meses_nuevos_ok"] == []


def test_run_backfill_flags_a_conflict_without_overwriting(tmp_path, monkeypatch) -> None:
    import scripts.backfill_dmc_historico as mod

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    monkeypatch.setattr(mod, "RAW_DIR", raw_dir)
    monkeypatch.setattr(mod, "REPORT_PATH", tmp_path / "manifest.json")
    monkeypatch.setattr(mod, "PERIOD_START", date(2021, 8, 1))
    monkeypatch.setattr(mod, "PERIOD_END", date(2021, 8, 1))
    monkeypatch.setattr(mod, "SLEEP_BETWEEN_REQUESTS", 0)

    existing_path = raw_dir / "dmc_historico_330007_2021-08.json"
    existing_path.write_text(
        json.dumps({"330007": _payload([_rec("2021-08-01 00:00:00", temp=20.0)])}), encoding="utf-8"
    )
    original_bytes = existing_path.read_bytes()

    def fake_fetch(station, year, month):
        return _payload([_rec("2021-08-01 00:00:00", temp=99.0)])  # distinto

    monkeypatch.setattr(mod, "_fetch_month", fake_fetch)

    resultado = mod.run_backfill()
    assert len(resultado["meses_conflicto"]) == 1
    assert resultado["meses_conflicto"][0]["mes"] == "2021-08"
    # el archivo original NUNCA se sobrescribe
    assert existing_path.read_bytes() == original_bytes
    conflict_files = list(raw_dir.glob("*_conflicto_*.json"))
    assert len(conflict_files) == 1


def test_run_backfill_records_months_with_no_data(tmp_path, monkeypatch) -> None:
    import scripts.backfill_dmc_historico as mod

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    monkeypatch.setattr(mod, "RAW_DIR", raw_dir)
    monkeypatch.setattr(mod, "REPORT_PATH", tmp_path / "manifest.json")
    monkeypatch.setattr(mod, "PERIOD_START", date(2013, 1, 1))
    monkeypatch.setattr(mod, "PERIOD_END", date(2013, 1, 1))
    monkeypatch.setattr(mod, "SLEEP_BETWEEN_REQUESTS", 0)
    monkeypatch.setattr(mod, "_fetch_month", lambda station, year, month: "Sin Información")

    resultado = mod.run_backfill()
    assert resultado["meses_sin_datos"] == [{"mes": "2013-01", "respuesta": "Sin Información"}]
    assert resultado["meses_nuevos_ok"] == []


def test_run_backfill_records_failed_months_without_aborting(tmp_path, monkeypatch) -> None:
    import scripts.backfill_dmc_historico as mod

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    monkeypatch.setattr(mod, "RAW_DIR", raw_dir)
    monkeypatch.setattr(mod, "REPORT_PATH", tmp_path / "manifest.json")
    monkeypatch.setattr(mod, "PERIOD_START", date(2021, 8, 1))
    monkeypatch.setattr(mod, "PERIOD_END", date(2021, 9, 1))
    monkeypatch.setattr(mod, "SLEEP_BETWEEN_REQUESTS", 0)

    def fake_fetch(station, year, month):
        if month == 8:
            raise RuntimeError("simulated network failure")
        return _payload([_rec(f"{year}-{month:02d}-01 00:00:00")])

    monkeypatch.setattr(mod, "_fetch_month", fake_fetch)

    resultado = mod.run_backfill()
    assert len(resultado["meses_fallidos"]) == 1
    assert resultado["meses_fallidos"][0]["mes"] == "2021-08"
    # el mes que sí funcionó no se pierde por el fallo del otro
    assert resultado["meses_nuevos_ok"] == ["2021-09"]
