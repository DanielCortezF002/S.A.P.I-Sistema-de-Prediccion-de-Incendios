"""Controles del sidebar y métricas de cabecera."""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from app.state import SESSION_APPEARANCE_KEY, appearance, set_appearance
from app.theme.tokens import (
    APPEARANCE_CLARO,
    APPEARANCE_MODES,
    APPEARANCE_OSCURO,
)
from src.config import SAPI_DATA_MODE

def render_appearance_toggle(*, location: str = "main") -> str:
    """Interruptor ☀️ / 🌙 claro-oscuro. Devuelve el modo activo.

    Antes era un `st.radio` con las etiquetas "Claro"/"Oscuro" montado en el
    sidebar colapsado por defecto: invisible hasta que alguien lo abriera a
    propósito, y sin ninguna relación visual con lo que hace. Ahora son dos
    botones de ícono siempre visibles (pensados para vivir en el header, no
    escondidos), con el modo activo resaltado en `type="primary"`.
    """
    if SESSION_APPEARANCE_KEY not in st.session_state:
        st.session_state[SESSION_APPEARANCE_KEY] = APPEARANCE_OSCURO
    elif st.session_state[SESSION_APPEARANCE_KEY] not in APPEARANCE_MODES:
        st.session_state[SESSION_APPEARANCE_KEY] = APPEARANCE_OSCURO

    host = st.sidebar if location == "sidebar" else st
    current = appearance()
    col_sol, col_luna = host.columns(2, gap="small")
    with col_sol:
        clicked_claro = st.button(
            "☀️",
            key="sapi_theme_claro",
            use_container_width=True,
            type="primary" if current == APPEARANCE_CLARO else "secondary",
            help="Modo claro",
        )
    with col_luna:
        clicked_oscuro = st.button(
            "🌙",
            key="sapi_theme_oscuro",
            use_container_width=True,
            type="primary" if current == APPEARANCE_OSCURO else "secondary",
            help="Modo oscuro",
        )
    if clicked_claro and current != APPEARANCE_CLARO:
        set_appearance(APPEARANCE_CLARO)
        st.rerun()
    if clicked_oscuro and current != APPEARANCE_OSCURO:
        set_appearance(APPEARANCE_OSCURO)
        st.rerun()
    return appearance()

def render_data_mode_badge() -> None:
    """Badge visible en sidebar: fuente de datos del dashboard (SAPI-44)."""
    if SAPI_DATA_MODE == "demo_seed":
        st.sidebar.markdown("### 🟡 Modo Demo")
        st.sidebar.caption(
            "`SAPI_DATA_MODE=demo_seed` — probabilidades y niveles de riesgo provienen "
            "del escenario sembrado (`demo_seed`), no de inferencia XGBoost en runtime."
        )
    elif SAPI_DATA_MODE == "postgis_inference":
        st.sidebar.markdown("### 🟢 Inferencia PostGIS")
        st.sidebar.caption(
            "`SAPI_DATA_MODE=postgis_inference` — predicciones desde `predicciones_riesgo`."
        )
    else:
        st.sidebar.warning(f"Modo de datos no reconocido: `{SAPI_DATA_MODE}`")


def render_technical_details_expander(
    min_d: date,
    max_d: date,
    *,
    metrics: dict[str, Any],
    app_build: str,
    query_version: str,
    recall_target: float,
) -> None:
    """Metadata de trazabilidad técnica y métricas del informe — colapsadas
    al fondo del sidebar.

    Panel ML (Recall XGBoost, AUC-ROC, Recall RF baseline), Build/versión de
    query, rango de fechas del seed y el string crudo de SAPI_DATA_MODE no
    son información que un brigadista bajo presión necesite en los primeros
    3 segundos; siguen disponibles acá para trazabilidad académica, un clic
    más adentro. El aviso "Modo Demo" en lenguaje operativo
    (`render_data_mode_badge`) es otra cosa — honestidad sobre demo vs.
    producción — y se queda visible arriba, sin colapsar.

    Sin una corrida ML real detrás (ver metrics_loader.py, hallazgo
    2026-09-01), las métricas muestran "—" en vez de un número fabricado.
    """
    xgb = metrics.get("xgboost", {})
    rf = metrics.get("baseline", {})
    recall = xgb.get("recall")
    auc = xgb.get("auc_roc")
    rf_recall = rf.get("recall")
    with st.sidebar.expander("Detalles técnicos"):
        st.markdown("**Modelo ML (informe)**")
        if recall is None:
            st.metric("Recall XGBoost", "—", delta="sin corrida real todavía")
        else:
            st.metric(
                "Recall XGBoost",
                f"{recall:.0%}",
                delta=f"meta ≥{recall_target:.0%}",
                delta_color="normal" if recall >= recall_target else "inverse",
            )
        st.metric("AUC-ROC", f"{auc:.2f}" if auc is not None else "—")
        st.metric("Recall RF baseline", f"{rf_recall:.0%}" if rf_recall is not None else "—")
        st.caption("Validación temporal · SMOTE en train · ver `reports/metrics.json`")
        st.markdown("---")
        st.caption(f"Build: `{app_build}` · Query: `{query_version}`")
        st.caption(f"Datos disponibles: {min_d} → {max_d}")
        st.caption(f"`SAPI_DATA_MODE={SAPI_DATA_MODE}`")


def pick_demo_date(available: list[date], min_d: date, max_d: date) -> date:
    """Selector de fecha: dropdown de días disponibles + calendario acotado."""
    # Selector principal: dropdown (no scroll) de días con datos
    selected = st.sidebar.selectbox(
        "Recorrido demo (días con datos)",
        options=available,
        index=len(available) - 1,
        format_func=lambda d: d.strftime("%Y-%m-%d"),
    )

    # Calendario secundario para fecha exacta
    calendar_date = st.sidebar.date_input(
        "Calendario",
        value=selected,
        min_value=min_d,
        max_value=max_d,
    )
    if calendar_date in available:
        return calendar_date
    if calendar_date not in available:
        st.sidebar.caption("Sin predicciones en esa fecha; usa el selector de días.")
    return selected
