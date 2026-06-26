"""Pruebas de zonas climáticas por celda."""

from __future__ import annotations

from app.utils.cell_zones import zone_for_cell_id, zone_label_for_cell


def test_zone_costa() -> None:
    assert zone_for_cell_id("VP-001") == "urbano"
    assert zone_for_cell_id("VP-003") == "urbano"


def test_zone_urbano() -> None:
    assert zone_for_cell_id("VP-004") == "urbano"
    assert zone_for_cell_id("VP-015") == "urbano"


def test_zone_precordillera() -> None:
    assert zone_for_cell_id("VP-038") == "precordillera"
    assert zone_for_cell_id("VP-049") == "precordillera"


def test_zone_label() -> None:
    assert "Precordillera" in zone_label_for_cell("VP-049")
