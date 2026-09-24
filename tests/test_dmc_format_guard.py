"""Defensa de formato en parse_dmc_json: nunca aceptar en silencio un JSON
que no tenga la forma DMC `{codigo_estacion: respuesta}`."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from src.procesamiento.raw_parser import DmcFormatError, parse_dmc_json
from src.procesamiento.regional_meteo import load_regional_meteo_series

_VALID_RECORD = {
    "momento": "2026-09-01 00:00:00",
    "temperatura": "13.5 °C",
    "humedadRelativa": "65 %",
    "fuerzaDelViento": "0.0 kt",
}


def _dump(path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_staging_meteo_fallback_shape_is_rejected(tmp_path) -> None:
    """Forma exacta que escribe ParallelIngester._degrade_source para
    staging_meteo: `df.to_dict(orient="records")` -> LISTA en la raíz."""
    path = tmp_path / "dmc_meteo_2026-09-22.json"
    _dump(
        path,
        [
            {
                "estacion": "330007",
                "temperatura": 13.5,
                "created_at": "2026-09-22 00:00:00",
            }
        ],
    )
    with pytest.raises(DmcFormatError, match="se encontró list"):
        parse_dmc_json(path)


@pytest.mark.parametrize("root", ["texto", 42, None])
def test_non_object_root_is_rejected(tmp_path, root) -> None:
    path = tmp_path / "dmc_meteo_x.json"
    _dump(path, root)
    with pytest.raises(DmcFormatError):
        parse_dmc_json(path)


def test_station_object_without_dmc_keys_is_rejected(tmp_path) -> None:
    """P. ej. un DataFrame volcado con `to_dict()` por defecto (columna ->
    {índice: valor}): raíz dict, pero ninguna clave DMC."""
    path = tmp_path / "dmc_meteo_x.json"
    _dump(path, {"temperatura": {"0": 13.5}, "humedad_relativa": {"0": 65.0}})
    with pytest.raises(DmcFormatError, match="ninguna clave DMC"):
        parse_dmc_json(path)


def test_legitimate_shapes_still_parse(tmp_path) -> None:
    """Sin cambio de comportamiento para las formas reales ya vistas en
    data/raw/: `datosEstaciones`, `error` y valores no-objeto (p. ej. el
    texto "Sin Información" de la API) que se omiten como antes."""
    path = tmp_path / "dmc_meteo_ok.json"
    _dump(
        path,
        {
            "330007": {"datosEstaciones": {"datos": [_VALID_RECORD]}, "registros": 1},
            "330004": {"error": "Información no disponible"},
            "330005": "Sin Información",
        },
    )
    df = parse_dmc_json(path)
    assert list(df["codigo_estacion"]) == ["330007"]
    assert df.iloc[0]["temperatura"] == 13.5


def test_loader_does_not_silently_skip_incompatible_file(tmp_path) -> None:
    """Un archivo incompatible junto a uno válido hace fallar la carga de
    forma explícita, en vez de producir una serie parcial sin aviso."""
    _dump(
        tmp_path / "dmc_meteo_2026-09-01.json",
        {"330007": {"datosEstaciones": {"datos": [_VALID_RECORD]}}},
    )
    _dump(tmp_path / "dmc_meteo_2026-09-22.json", [{"estacion": "330007"}])
    with pytest.raises(DmcFormatError):
        load_regional_meteo_series("330007", raw_dir=tmp_path)


def test_score_current_grid_maps_format_error_to_unavailable(monkeypatch) -> None:
    import src.inference.prototype_service as svc

    def _raise(*_args, **_kwargs):
        raise DmcFormatError("dmc_meteo_2026-09-22.json: se esperaba un objeto")

    monkeypatch.setattr(svc, "pin_dmc", _raise)
    with pytest.raises(svc.PrototypeUnavailableError, match="formato incompatible"):
        svc.score_current_grid()


def test_valid_file_parse_is_unchanged(tmp_path) -> None:
    path = tmp_path / "dmc_historico_330007_2026-09.json"
    _dump(path, {"330007": {"datosEstaciones": {"datos": [_VALID_RECORD]}}})
    df = parse_dmc_json(path)
    assert df.iloc[0]["momento"] == pd.Timestamp("2026-09-01 00:00:00")
    assert df.iloc[0]["humedad_relativa"] == 65.0
    assert df.iloc[0]["velocidad_viento_kmh"] == 0.0
