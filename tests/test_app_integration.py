"""Smoke test de `app/app.py::main()` de punta a punta con `AppTest`.

El resto de la suite prueba funciones sueltas (`SapiDashboard`, componentes
individuales) pero nada ejecutaba `main()` completo — el ensamblado real de
la página nunca se verificaba. Esto quedó en evidencia al conectar "Top
zonas prioritarias" y "Tendencia del riesgo": una `main()` sin cubrir habría
dejado pasar un `NameError` o un `st.columns` mal anidado hasta producción.
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parent.parent / "app" / "app.py"


def _run(*, mode: str = "Demo (escenario sembrado)") -> AppTest:
    """Corre `main()` completo. Por defecto selecciona el modo Demo — todo
    este archivo prueba el escenario sembrado, que desde la iteración del
    prototipo (2026-09-07) ya no es el modo por defecto de la app."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=60)
    at.run()
    assert not at.exception, f"main() lanzó una excepción: {at.exception}"
    radios = at.sidebar.radio
    if radios and mode in radios[0].options and radios[0].value != mode:
        at = radios[0].set_value(mode).run()
        assert not at.exception, f"cambiar de modo lanzó una excepción: {at.exception}"
    return at


def test_main_runs_without_exceptions() -> None:
    _run()


def test_prototype_mode_is_the_default_and_runs_without_exceptions() -> None:
    """El modo por defecto (sin tocar el radio) debe ser Prototipo, y debe
    correr sin excepciones incluso si faltan artefactos reales — el manejo
    de errores vive en `render_prototype_dashboard`, no en `main()`."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=60)
    at.run()
    assert not at.exception
    radios = at.sidebar.radio
    assert radios and radios[0].value == "Prototipo (datos reales)"


def test_priority_zones_and_trend_sections_are_present() -> None:
    at = _run()
    titles = " ".join(m.value or "" for m in at.markdown)
    assert "TOP ZONAS PRIORITARIAS" in titles
    assert "TENDENCIA DEL RIESGO" in titles


def test_default_demo_day_has_two_priority_alerts() -> None:
    """Día pico del seed (2025-02-15): VP-038 y VP-049 en riesgo alto."""
    at = _run()
    alert_buttons = [b for b in at.button if b.key and b.key.startswith("alert_")]
    assert {b.key for b in alert_buttons} == {"alert_VP-038", "alert_VP-049"}


def test_selecting_a_priority_alert_updates_the_selected_cell() -> None:
    at = _run()
    alert_buttons = [b for b in at.button if b.key == "alert_VP-049"]
    assert alert_buttons, "No se encontró el botón de alerta para VP-049"

    at = alert_buttons[0].click().run()
    assert not at.exception, f"Seleccionar una alerta lanzó una excepción: {at.exception}"

    # VP-049 pasa a ser la celda destacada: su botón de alerta ahora es "Seleccionada".
    updated = {b.key: b.label for b in at.button if b.key and b.key.startswith("alert_")}
    assert updated["alert_VP-049"] == "Seleccionada"
