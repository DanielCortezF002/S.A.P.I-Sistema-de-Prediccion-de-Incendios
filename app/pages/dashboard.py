"""Centro de Control de SOLO LECTURA de SAPI.

Muestra la última evaluación que entrega el servicio de score (`GET /score`
del bridge) o, solo si se pide explícitamente, una fixture sintética local
claramente rotulada. No tiene ningún control que refresque FIRMS/DMC, publique
CURRENT, envíe notificaciones ni escriba configuración: "Actualizar vista" solo
vuelve a leer el resultado. La vista previa de alerta solo muestra texto.

    python -m app.control_center --demo          → demo (sin backend ni internet)
    python -m app.control_center --demo --presentation
    python -m app.control_center --live          → lee SAPI_SCORE_URL (src/config.py)

También sigue disponible como página de la app principal (`/dashboard`).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Mismo guard que app/app.py: si esta página es la primera en ejecutarse,
# app/ va delante en sys.path y `import app` resolvería app/app.py.
_REPO_ROOT_STR = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT_STR in sys.path:
    sys.path.remove(_REPO_ROOT_STR)
sys.path.insert(0, _REPO_ROOT_STR)
if "app" in sys.modules and not hasattr(sys.modules["app"], "__path__"):
    del sys.modules["app"]

import streamlit as st  # noqa: E402

from app.components import ops_dashboard as ui  # noqa: E402
from app.theme.css import build_stylesheet  # noqa: E402
from app.utils.score_contract import (  # noqa: E402
    LIVE_READY,
    fetch_live,
    load_demo,
    now_utc_iso,
)
from src import config  # noqa: E402

MODE_LIVE, MODE_DEMO = "En vivo (servicio de score)", "Demostración (datos sintéticos)"
ORDER_RANK, ORDER_CELL = "Rank (orden del servicio)", "ID de celda"
REFRESH_HELP = "Actualizar vista no actualiza las fuentes de datos."
LAST_SUCCESS_KEY = "ops_last_live_success"


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def _mode_controls(demo_param: bool, presentation: bool) -> tuple[str, bool]:
    if presentation:  # el modo queda fijado por la URL; sin controles de desarrollo
        mode = MODE_DEMO if demo_param else MODE_LIVE
        refresh = st.button("Actualizar vista", help=REFRESH_HELP)
        return mode, refresh
    left, right = st.columns([3, 1], vertical_alignment="bottom")
    with left:
        mode = st.radio(
            "Fuente de datos",
            (MODE_LIVE, MODE_DEMO),
            index=1 if demo_param else 0,
            horizontal=True,
            key="ops_mode",
        )
    with right:
        refresh = st.button(
            "Actualizar vista", use_container_width=True, help=REFRESH_HELP
        )
    if (mode == MODE_DEMO) != demo_param:
        if mode == MODE_DEMO:
            st.query_params["demo"] = "1"
        else:
            st.query_params.pop("demo", None)
    return mode, refresh


def _alert_text_drawer(view) -> None:
    """Texto completo de la notificación. Solo se muestra; nunca se envía."""
    if not st.toggle(
        "Vista previa",
        key="ops_alert_preview",
        help="Muestra el texto completo. SAPI no envía alertas desde este panel.",
    ):
        return
    if view.alert_text is None:
        st.info("No hay vista previa: la respuesta no permite construir una alerta.")
        return
    text = view.alert_text
    if view.synthetic:
        text = "[DATOS DEMOSTRATIVOS · SYNTHETIC DEMO · NO ENVIADO]\n" + text
    st.code(text, language=None, wrap_lines=True)


def _ranking(view) -> None:
    left, right = st.columns([2, 1], vertical_alignment="bottom")
    with left:
        query = st.text_input(
            "Buscar celda", placeholder="Ej.: VP-028 o 28", key="ops_q"
        )
    with right:
        order = st.selectbox(
            "Orden de la vista", (ORDER_RANK, ORDER_CELL), key="ops_order"
        )
    cells = ui.filter_cells(
        view.cells, query, "cell_id" if order == ORDER_CELL else "rank"
    )
    note = ""
    if query or order == ORDER_CELL:
        note = f" Vista filtrada/ordenada: {len(cells)} de {len(view.cells)}; el rank no cambia."
    _html(ui.wrap(ui.ranking_table(view, cells, note)))


def _technical(view, last_success: str | None) -> None:
    with st.expander("Detalles técnicos"):
        _html(ui.wrap(ui.technical_details(view, last_success=last_success)))
        for label, value in ui.full_hashes(view):
            st.caption(f"{label} (completo, copiable)")
            st.code(value, language=None)
        st.caption(
            f"{ui.N8N_IDENTITY_BOUNDARY}: el alert fingerprint todavía no coincide con "
            "notification_identity de ops/n8n/policy.js y no se usa para deduplicar."
        )


def main() -> None:
    st.set_page_config(
        page_title="S.A.P.I. · Centro de Control",
        page_icon="🔥",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _html(build_stylesheet())
    _html(ui.dashboard_css())

    demo_param = st.query_params.get("demo") == "1"
    presentation = st.query_params.get("presentation") == "1"
    mode, refresh = _mode_controls(demo_param, presentation)

    # Demo y en vivo nunca comparten caché: un fallo en vivo jamás muestra la fixture.
    cache_key = f"ops_view::{mode}"
    placeholder = st.empty()
    if refresh or cache_key not in st.session_state:
        if mode == MODE_DEMO:
            view = load_demo()
        else:
            placeholder.markdown(ui.loading(), unsafe_allow_html=True)
            view = fetch_live(config.SAPI_SCORE_URL)
            if view.state == LIVE_READY:
                st.session_state[LAST_SUCCESS_KEY] = view.fetched_at or now_utc_iso()
        st.session_state[cache_key] = view
    view = st.session_state[cache_key]
    last_success = st.session_state.get(LAST_SUCCESS_KEY) if mode == MODE_LIVE else None

    placeholder.markdown(
        ui.render_overview(view, presentation, last_success), unsafe_allow_html=True
    )
    _html(ui.wrap(ui.data_status(view, presentation), presentation))
    if view.has_ranking and not presentation:
        _ranking(view)
    _html(ui.wrap(ui.alert_section(view), presentation))
    _alert_text_drawer(view)
    _html(ui.wrap(ui.limitations(), presentation))
    if not presentation:
        _technical(view, last_success)
    st.caption(
        f"{REFRESH_HELP} La última consulta de vista no indica la frescura de los datos. "
        "Solo lectura: esta página no modifica datos ni envía notificaciones."
    )


main()
