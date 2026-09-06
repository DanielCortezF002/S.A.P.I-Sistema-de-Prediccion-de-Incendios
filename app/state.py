"""Estado de sesión del dashboard: celda seleccionada y ciclo de vida.

Las cinco claves de `st.session_state` vivían repartidas entre `main()` y
`app/utils/cell_table.py`, inicializadas con `if "clave" not in
st.session_state` sueltos y leídas con literales en cada punto de uso. La
lógica más delicada —qué pasa con la selección cuando cambia la fecha, y por
qué la preselección se aplica una vez por ronda y no en cada rerun— estaba
escrita como comentarios dentro del cuerpo de `main()`, donde ningún test la
alcanzaba.

Acá cada transición es una función con nombre y con test.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

import streamlit as st

# Celda activa. La leen el mapa, la tabla y la ficha de detalle.
SESSION_CELL_KEY = "selected_cell_id"

# Contador que forma parte de la clave del widget de tabla. Incrementarlo
# fuerza a Streamlit a montar un widget nuevo, que es la única forma de
# limpiar los checkboxes de `st.dataframe` sin que el usuario los destilde.
SESSION_TABLE_EPOCH_KEY = "_table_epoch"

# Marca de que la preselección de la celda de mayor riesgo ya corrió en esta
# ronda (carga inicial o cambio de fecha).
SESSION_PRESELECTED_KEY = "_top_risk_preselected"

# Última fecha consultada, para detectar el cambio de fecha.
SESSION_LAST_DATE_KEY = "_last_query_date"

# Marca del precalentamiento de caché, que debe correr una vez por sesión.
SESSION_CACHE_WARMED_KEY = "cache_warmed"

# Orígenes de selección que además reinician el widget de tabla. Un clic en la
# propia tabla no lo hace: remontar el widget en medio de su propio evento
# descarta la selección que acaba de ocurrir.
_SOURCES_THAT_RESET_TABLE = frozenset({"map", "clear"})


def init_session() -> None:
    """Deja las claves de selección en un estado conocido. Idempotente."""
    st.session_state.setdefault(SESSION_CELL_KEY, None)
    st.session_state.setdefault(SESSION_TABLE_EPOCH_KEY, 0)
    st.session_state.setdefault(SESSION_PRESELECTED_KEY, False)


def selected_cell() -> Optional[str]:
    """Celda activa, o None si no hay ninguna."""
    return st.session_state.get(SESSION_CELL_KEY)


def select_cell(cell_id: Optional[str], source: str) -> None:
    """Fija la celda activa; reinicia el widget de tabla si hace falta.

    `source` distingue de dónde viene la selección porque el efecto secundario
    depende del origen: un clic en el mapa o el botón de limpiar tienen que
    destildar el checkbox de la tabla, y la única forma es remontar el widget.
    Un clic en la tabla no debe hacerlo.
    """
    st.session_state[SESSION_CELL_KEY] = cell_id
    if source in _SOURCES_THAT_RESET_TABLE:
        bump_table_epoch()


def clear_selection() -> None:
    """Deja el dashboard sin celda activa."""
    select_cell(None, "clear")


def table_epoch() -> int:
    """Generación actual del widget de tabla."""
    return int(st.session_state.get(SESSION_TABLE_EPOCH_KEY, 0))


def bump_table_epoch() -> None:
    """Fuerza el remontaje del widget de tabla en el próximo render."""
    st.session_state[SESSION_TABLE_EPOCH_KEY] = table_epoch() + 1


def reset_selection_on_date_change(selected_date: date) -> bool:
    """Limpia la selección si cambió la fecha. Devuelve si hubo cambio.

    Una celda seleccionada no sobrevive al cambio de día: el mismo `VP-038`
    existe en las dos fechas pero con otra probabilidad y otro nivel, así que
    arrastrar la selección mostraría una ficha que el usuario no pidió. Además
    se rearma la preselección, para que la nueva fecha vuelva a destacar su
    propia celda de mayor riesgo.
    """
    clave = selected_date.isoformat()
    if st.session_state.get(SESSION_LAST_DATE_KEY) == clave:
        return False

    st.session_state[SESSION_CELL_KEY] = None
    bump_table_epoch()
    st.session_state[SESSION_PRESELECTED_KEY] = False
    st.session_state[SESSION_LAST_DATE_KEY] = clave
    return True


def ensure_default_selection(top_risk: Optional[dict[str, Any]]) -> None:
    """Preselecciona la celda de mayor riesgo si no hay ninguna elegida.

    Corre una sola vez por ronda —carga inicial o cambio de fecha— y no en
    cada rerun, para que un clic o el botón de limpiar sigan mandando sobre
    esta preselección dentro de la misma ronda. Sin esto, limpiar la selección
    la volvería a poner en el rerun siguiente y el botón parecería no andar.

    Recibe el `top_risk` ya calculado para el banner en vez de recalcularlo.
    """
    if st.session_state.get(SESSION_PRESELECTED_KEY):
        return
    st.session_state[SESSION_PRESELECTED_KEY] = True
    if selected_cell() is None and top_risk is not None:
        st.session_state[SESSION_CELL_KEY] = top_risk["cell_id"]


def cache_is_warm() -> bool:
    """Si el precalentamiento de caché ya corrió en esta sesión."""
    return bool(st.session_state.get(SESSION_CACHE_WARMED_KEY))


def mark_cache_warm() -> None:
    """Registra que el precalentamiento ya corrió."""
    st.session_state[SESSION_CACHE_WARMED_KEY] = True
