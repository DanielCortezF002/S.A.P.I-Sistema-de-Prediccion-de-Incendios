"""Smoke test de `app/app.py::main()` de punta a punta con `AppTest`.

El resto de la suite prueba funciones sueltas (`SapiDashboard`, componentes
individuales) pero nada ejecutaba `main()` completo — el ensamblado real de
la página nunca se verificaba. Esto quedó en evidencia al conectar "Top
zonas prioritarias" y "Tendencia del riesgo": una `main()` sin cubrir habría
dejado pasar un `NameError` o un `st.columns` mal anidado hasta producción.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parent.parent / "app" / "app.py"


@pytest.fixture(autouse=True)
def _backend_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Desde SAPI-61 el modo Prototipo (default) consulta el backend REST.
    Aquí no hay backend: se apunta a un puerto local recién cerrado para que
    la conexión sea rechazada de inmediato y de forma determinista (nunca al
    8080 real de la máquina). La integración con backend simulado vive en
    `tests/test_sapi61_http_stub.py`."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    monkeypatch.setenv("SAPI_BACKEND_BASE_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SAPI_BACKEND_CONNECT_TIMEOUT", "1")
    monkeypatch.setenv("SAPI_BACKEND_READ_TIMEOUT", "1")


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
    correr sin excepciones aunque el backend REST esté caído (SAPI-61.CA4):
    el manejo de errores vive en `render_ranking_backend_dashboard`, no en
    `main()`, y el usuario ve un mensaje controlado."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=60)
    at.run()
    assert not at.exception
    radios = at.sidebar.radio
    assert radios and radios[0].value == "Prototipo (datos reales)"
    assert at.error and "No se pudo obtener el ranking del backend" in at.error[0].value


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
