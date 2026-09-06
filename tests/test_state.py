"""Pruebas del estado de sesión del dashboard.

Esta lógica vivía dentro del cuerpo de `main()` en `app/app.py`, donde ningún
test la alcanzaba: la única forma de ejercitarla era levantar Streamlit y
hacer clic. Lo más delicado que quedaba sin cubrir era el reinicio de la
selección al cambiar de fecha, que toca tres claves a la vez.
"""

from __future__ import annotations

from datetime import date

import pytest

from app import state


@pytest.fixture()
def sesion(monkeypatch) -> dict:
    """Un `st.session_state` limpio por test."""
    fake: dict = {}
    monkeypatch.setattr("app.state.st.session_state", fake)
    return fake


def test_init_session_leaves_every_key_in_a_known_state(sesion):
    state.init_session()

    assert sesion[state.SESSION_CELL_KEY] is None
    assert sesion[state.SESSION_TABLE_EPOCH_KEY] == 0
    assert sesion[state.SESSION_PRESELECTED_KEY] is False


def test_init_session_does_not_discard_an_existing_selection(sesion):
    """Corre en cada rerun, así que no puede pisar lo que el usuario eligió."""
    state.select_cell("VP-038", "table")
    state.init_session()

    assert state.selected_cell() == "VP-038"


def test_selecting_from_the_map_remounts_the_table_widget(sesion):
    """Un clic en el mapa tiene que destildar el checkbox de la tabla, y la
    única forma es cambiar la clave del widget."""
    state.init_session()
    state.select_cell("VP-002", "map")

    assert state.selected_cell() == "VP-002"
    assert state.table_epoch() == 1


def test_selecting_from_the_table_does_not_remount_the_table_widget(sesion):
    """Remontar el widget en medio de su propio evento descartaría la
    selección que acaba de ocurrir."""
    state.init_session()
    state.select_cell("VP-002", "table")

    assert state.selected_cell() == "VP-002"
    assert state.table_epoch() == 0


def test_clearing_the_selection_empties_it_and_remounts_the_table(sesion):
    state.init_session()
    state.select_cell("VP-002", "table")

    state.clear_selection()

    assert state.selected_cell() is None
    assert state.table_epoch() == 1


def test_first_render_registers_the_date_without_anything_to_reset(sesion):
    state.init_session()

    cambio = state.reset_selection_on_date_change(date(2025, 2, 15))

    assert cambio is True
    assert sesion[state.SESSION_LAST_DATE_KEY] == "2025-02-15"


def test_rerunning_on_the_same_date_keeps_the_selection(sesion):
    """Cada interacción dispara un rerun; si el reinicio no distinguiera
    rerun de cambio de fecha, ninguna selección sobreviviría a un clic."""
    state.init_session()
    state.reset_selection_on_date_change(date(2025, 2, 15))
    state.select_cell("VP-038", "table")

    cambio = state.reset_selection_on_date_change(date(2025, 2, 15))

    assert cambio is False
    assert state.selected_cell() == "VP-038"


def test_changing_the_date_drops_a_selection_made_on_the_previous_one(sesion):
    """La misma celda existe en las dos fechas pero con otra probabilidad y
    otro nivel, así que arrastrar la selección mostraría una ficha que el
    usuario no pidió."""
    state.init_session()
    state.reset_selection_on_date_change(date(2025, 2, 15))
    state.select_cell("VP-038", "table")
    epoch_previo = state.table_epoch()

    cambio = state.reset_selection_on_date_change(date(2025, 2, 9))

    assert cambio is True
    assert state.selected_cell() is None
    assert state.table_epoch() > epoch_previo, (
        "El widget de tabla debe remontarse, o queda un checkbox tildado de la fecha anterior"
    )
    assert sesion[state.SESSION_PRESELECTED_KEY] is False, (
        "La fecha nueva tiene que poder destacar su propia celda de mayor riesgo"
    )


def test_changing_the_date_rearms_preselection_for_the_new_day(sesion):
    """Comprobación de punta a punta del ciclo: la fecha nueva preselecciona
    su propia celda de mayor riesgo, no la de la fecha anterior."""
    state.init_session()
    state.reset_selection_on_date_change(date(2025, 2, 15))
    state.ensure_default_selection({"cell_id": "VP-038"})
    assert state.selected_cell() == "VP-038"

    state.reset_selection_on_date_change(date(2025, 2, 9))
    state.ensure_default_selection({"cell_id": "VP-049"})

    assert state.selected_cell() == "VP-049"


def test_cache_warm_flag_starts_false_and_latches(sesion):
    """El precalentamiento recorre todas las fechas del seed; correrlo en
    cada rerun haría inusable el dashboard."""
    assert state.cache_is_warm() is False

    state.mark_cache_warm()

    assert state.cache_is_warm() is True
