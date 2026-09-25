"""Centro de Control de SOLO LECTURA (ruta /dashboard de sapi-web).

Muestra la última evaluación que entrega el servicio de score (`GET /score`
del bridge) o, en modo demostración, una fixture sintética local claramente
rotulada. No tiene ningún control que refresque FIRMS/DMC, publique CURRENT,
envíe notificaciones ni escriba configuración: "Actualizar vista" solo vuelve
a leer el resultado. La vista previa de alerta solo muestra texto.

    streamlit run app/app.py        → http://localhost:8501/dashboard
    ...?demo=1                      → modo demostración (sin backend ni internet)
    ...?demo=1&presentation=1       → modo presentación
    SAPI_SCORE_URL=http://host:8600/score  (por defecto http://127.0.0.1:8600/score)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
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
from app.utils.score_contract import fetch_live, load_demo  # noqa: E402

DEFAULT_SCORE_URL = "http://127.0.0.1:8600/score"
MODE_LIVE, MODE_DEMO = "En vivo (servicio de score)", "Demostración (datos sintéticos)"
ORDER_RANK, ORDER_CELL = "Rank (orden del servicio)", "ID de celda"
REFRESH_HELP = "Actualizar vista no actualiza las fuentes de datos."


def _score_url() -> str:
    return os.environ.get("SAPI_SCORE_URL", DEFAULT_SCORE_URL)


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


def _alert_preview(view, presentation: bool) -> None:
    _html(
        ui.wrap(
            '<section class="ops-panel ops-section" aria-labelledby="ops-alert-h">'
            '<h2 id="ops-alert-h">Vista previa de alerta</h2>'
            '<p class="ops-sub">Texto que SAPI generaría para una notificación futura. '
            "Este panel no envía nada: no hay conexión con Telegram ni n8n.</p></section>",
            presentation,
        )
    )
    if not st.toggle("Vista previa", key="ops_alert_preview"):
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


def _technical(view, read_at: str) -> None:
    with st.expander("Detalles técnicos"):
        _html(ui.wrap(ui.technical_details(view, read_at)))
        for label, value in ui.full_hashes(view):
            st.caption(f"{label} (completo, copiable)")
            st.code(value, language=None)


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
            view = fetch_live(_score_url())
        st.session_state[cache_key] = (view, datetime.now().strftime("%H:%M:%S"))
    view, read_at = st.session_state[cache_key]

    placeholder.markdown(ui.render_overview(view, presentation), unsafe_allow_html=True)
    _html(ui.wrap(ui.data_status(view), presentation))
    if view.has_ranking and not presentation:
        _ranking(view)
    _alert_preview(view, presentation)
    _html(ui.wrap(ui.limitations(), presentation))
    if not presentation:
        _technical(view, read_at)
    st.caption(
        f"Vista leída a las {read_at} (hora local del panel). {REFRESH_HELP} "
        "Solo lectura: esta página no modifica datos ni envía notificaciones."
    )


main()
