"""Test dedicado de `_fmt_nd()` — cierra el gap de REQ-15 / CA-C3.

Contexto (ver `docs/trazabilidad-current.md`, SAPI-52): el dato topográfico
(elevación/pendiente) queda `NaN` cuando una celda no tiene cobertura del
raster DEM (`dem_features.py`, ya testeado en `tests/test_dem_features.py`).
Lo que NO tenía test dedicado era la capa de presentación:
`app/components/prototype_view.py::_fmt_nd`, la función que ambos paneles
del prototipo (`_render_cells_layer` y `_render_selected_panel`) usan para
formatear `cell.elevation`/`cell.slope` antes de mostrarlos.

Estos tests ejercitan `_fmt_nd` directamente con los mismos tipos de valor
que produce el pipeline real (`None`, `float("nan")`, `pd.NA`) — no son un
espejo de la implementación: verifican la salida observable ("N/D", nunca
un cero fabricado, nunca una excepción) para exactamente los casos que
`docs/architecture-4plus1-hito1.md` (escenario S8) y
`artifacts/hito1/posthito-jira/jira-ticket-specs.md` (CA-C3) describen.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from app.components.prototype_view import _fmt_nd


@pytest.mark.parametrize("missing_value", [None, float("nan"), pd.NA, math.nan])
def test_fmt_nd_preserves_missing_dem_as_nd(missing_value) -> None:
    """DEM sin cobertura (None/NaN/pd.NA) -> 'N/D', nunca '0' fabricado."""
    result = _fmt_nd(missing_value, " m", 0)
    assert result == "N/D"
    assert result != "0 m"


def test_fmt_nd_missing_value_never_raises() -> None:
    """Ninguna de las variantes de dato faltante debe lanzar excepción."""
    for missing_value in (None, float("nan"), pd.NA):
        _fmt_nd(missing_value, "°", 1)  # no debe lanzar


def test_fmt_nd_real_value_is_formatted_not_hidden_as_nd() -> None:
    """Un valor real (con cobertura DEM) se muestra formateado, no 'N/D'."""
    assert _fmt_nd(543.2, " m", 0) == "543 m"
    assert _fmt_nd(12.34, "°", 1) == "12.3°"


def test_fmt_nd_real_zero_is_not_confused_with_missing_data() -> None:
    """Un 0 real (p.ej. pendiente plana) se muestra como '0', no como 'N/D'.

    Caso límite explícito del CA: la función nunca debe inventar un 0 para
    un dato faltante, pero tampoco debe ocultar un 0 que sí es un valor
    topográfico real y válido.
    """
    assert _fmt_nd(0.0, " m", 0) == "0 m"
    assert _fmt_nd(0.0, " m", 0) != "N/D"


def test_fmt_nd_default_arguments() -> None:
    """Sin unidad ni decimales explícitos, sigue distinguiendo N/D de dato real."""
    assert _fmt_nd(None) == "N/D"
    assert _fmt_nd(10.0) == "10"
