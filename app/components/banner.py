"""Banner de alcance demo, alerta de mayor riesgo y orientación geográfica."""

from __future__ import annotations

from datetime import date

import streamlit as st

from app.utils.grid import CELL_COUNT, cell_step_meters, grid_extent_km
from src.config import SAPI_DATA_MODE


def render_demo_scope_banner(min_d: date, max_d: date) -> None:
    """Banner superior: alcance demo y aclaración VP-038 / VP-049 (escenario sembrado).

    La extensión y la resolución se calculan desde `app.utils.grid` en vez de
    escribirse a mano: el banner afirmaba cubrir el corredor completo mientras
    la grilla generaba 8,4 x 4,0 km dentro de Viña del Mar.

    Las comunas nombradas reflejan evidencia real, no geometría: contención
    espacial estricta de las 348 detecciones NASA FIRMS del 2024-02-03 contra
    las 50 celdas de esta grilla, con la comuna de cada celda resultante
    verificada contra el shapefile oficial DPA 2023 (SUBDERE), 05-09-2026.
    Villa Alemana había quedado nombrada antes solo porque su coordenada cae
    dentro del bounding box de la grilla — sin ninguna detección real ahí
    verificada en ese momento. Con el dataset completo sí aparece (2 celdas,
    5 focos, 1.9% del total), junto con Valparaíso (32 focos) y Limache (17),
    que no estaban mencionadas en ningún texto anterior del proyecto. Ver
    tests/test_app.py::test_demo_banner_names_localities_with_real_detection_evidence.
    """
    step_x, _ = cell_step_meters()
    ancho_km, alto_km = grid_extent_km()
    st.info(
        f"**Demo académica** (`SAPI_DATA_MODE={SAPI_DATA_MODE}`): {CELL_COUNT} celdas de "
        f"~{step_x / 1000:.1f} km sobre el corredor de interfaz urbano-forestal de la "
        f"Región de Valparaíso ({ancho_km:.0f} × {alto_km:.0f} km) — evidencia real de "
        "detecciones NASA FIRMS (2024-02-03) principalmente en Viña del Mar y Quilpué "
        "(79% de los focos reales), con presencia menor confirmada en Valparaíso, "
        "Limache y Villa Alemana. "
        f"Ventana **{min_d.isoformat()}** a "
        f"**{max_d.isoformat()}** (escenario sembrado calibrado por zona). "
        "Los valores mostrados **no** son salida del modelo en tiempo real. "
        "En particular, **VP-038** y **VP-049** el día **2025-02-15** (riesgo alto y regla "
        "30-30-30 activa) son un **escenario sembrado** para la presentación — no predicción "
        "del XGBoost en runtime. Arquitectura lista para DMC/CONAF en producción. "
        "No sustituye alertas oficiales CONAF/SENAPRED."
    )
    from app.components.ops_layout import render_corridor_verified_note

    render_corridor_verified_note()


def render_risk_legend() -> None:
    """Orientación geográfica del corredor, oeste a este.

    El semáforo de riesgo ya no se duplica acá: vive anclado al mapa
    (`build_risk_legend_html`), donde se lee sin desviar la vista. Lo que
    queda es la única información que el mapa no da solo — qué comuna
    corresponde a cada banda climática.
    """
    st.caption(
        "Oeste → Este: costa de Viña del Mar · interfaz urbano-forestal "
        "(Quilpué) · precordillera y cerros orientales"
    )
