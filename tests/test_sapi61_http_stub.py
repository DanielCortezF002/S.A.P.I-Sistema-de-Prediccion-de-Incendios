"""SAPI-61 — HTTP_STUB y STREAMLIT_INTEGRATION (CA1, CA2, CA3, CA4, CA5).

Un `http.server` real en 127.0.0.1 (puerto efímero) hace de backend Spring
Boot: registra método, ruta y cabeceras y responde lo que cada test decide.
Sobre él corren (a) el cliente directo y (b) `app/app.py` completo con
`AppTest`. No es la prueba E2E con Docker (SAPI-66): aquí no hay Spring ni
FastAPI reales.
"""

from __future__ import annotations

import copy
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest
from streamlit.testing.v1 import AppTest

from app.components.ranking_backend_view import NOT_PROVIDED, refresh_ranking_cache
from app.utils.backend_client import (
    ERROR_KIND_CONNECTION,
    ERROR_KIND_HTTP_BACKEND,
    ERROR_KIND_INVALID_JSON,
    ERROR_KIND_INVALID_RANKING,
    ERROR_KIND_TIMEOUT,
    BackendError,
    BackendRankingClient,
)
from tests.test_backend_client import EXTENDED_FIELDS, real_payload, synthetic_payload

APP_PATH = Path(__file__).resolve().parent.parent / "app" / "app.py"
PROTOTYPE_MODE = "Prototipo (datos reales)"

Responder = Callable[[BaseHTTPRequestHandler], None]


class StubBackend:
    """Backend HTTP mínimo y programable."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.responder: Responder = self.respond_json(200, real_payload())
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 (nombre impuesto por http.server)
                stub.requests.append(
                    {
                        "method": "GET",
                        "path": self.path,
                        "accept": self.headers.get("Accept"),
                    }
                )
                stub.responder(self)

            def log_message(self, *_: Any) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def start(self) -> "StubBackend":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    @staticmethod
    def respond_json(status: int, payload: Any) -> Responder:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        def responder(handler: BaseHTTPRequestHandler) -> None:
            handler.send_response(status)
            handler.send_header("Content-Type", "application/json; charset=utf-8")
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)

        return responder

    @staticmethod
    def respond_raw(status: int, body: bytes, content_type: str = "application/json") -> Responder:
        def responder(handler: BaseHTTPRequestHandler) -> None:
            handler.send_response(status)
            handler.send_header("Content-Type", content_type)
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)

        return responder

    @staticmethod
    def respond_slow(delay_seconds: float) -> Responder:
        def responder(handler: BaseHTTPRequestHandler) -> None:
            time.sleep(delay_seconds)
            StubBackend.respond_json(200, real_payload())(handler)

        return responder


@pytest.fixture
def stub() -> Iterator[StubBackend]:
    backend = StubBackend().start()
    try:
        yield backend
    finally:
        backend.stop()


def closed_port_url() -> str:
    """URL a un puerto local que acaba de cerrarse: conexión rechazada."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"


def error_body(error_type: str, message: str) -> dict:
    return {"status": "error", "error_type": error_type, "message": message}


def client_for(stub: StubBackend, read_timeout: float = 10.0) -> BackendRankingClient:
    return BackendRankingClient(stub.base_url, connect_timeout=2.0, read_timeout=read_timeout)


def run_app(monkeypatch: pytest.MonkeyPatch, base_url: str) -> AppTest:
    monkeypatch.setenv("SAPI_BACKEND_BASE_URL", base_url)
    monkeypatch.setenv("SAPI_BACKEND_CONNECT_TIMEOUT", "2")
    monkeypatch.setenv("SAPI_BACKEND_READ_TIMEOUT", "10")
    monkeypatch.delenv("SAPI_UI_LEGACY_MODES", raising=False)
    # Los puertos efímeros pueden reutilizarse entre tests: nunca heredar cache.
    refresh_ranking_cache()
    at = AppTest.from_file(str(APP_PATH), default_timeout=60)
    at.run()
    assert not at.exception, f"main() lanzó una excepción: {at.exception}"
    return at


def markdown_blob(at: AppTest) -> str:
    return "\n".join(m.value or "" for m in at.markdown)


# ── HTTP_STUB: cliente contra servidor real ──────────────────────────────────


def test_client_issues_get_on_the_contract_path(stub: StubBackend) -> None:
    view = client_for(stub).fetch_ranking()
    assert len(view.cells) == 50
    assert stub.requests == [
        {"method": "GET", "path": "/api/v1/ranking", "accept": "application/json"}
    ]


def test_client_forwards_forecast_time_query(stub: StubBackend) -> None:
    client_for(stub).fetch_ranking(forecast_time="2026-10-01T18:00:00-03:00")
    assert (
        stub.requests[0]["path"] == "/api/v1/ranking?forecast_time=2026-10-01T18%3A00%3A00-03%3A00"
    )


def test_client_reads_base_url_from_environment(
    stub: StubBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SAPI_BACKEND_BASE_URL", stub.base_url + "/")
    view = BackendRankingClient.from_env().fetch_ranking()
    assert view.inputs_fingerprint == real_payload()["inputs_fingerprint"]
    assert stub.requests[0]["path"] == "/api/v1/ranking"


def test_client_preserves_scores_ranks_and_ties_over_the_wire(stub: StubBackend) -> None:
    payload = real_payload()
    view = client_for(stub).fetch_ranking()
    assert [(c.cell_id, c.score, c.rank, c.display_rank, c.tie_group_size) for c in view.cells] == [
        (c["cell_id"], c["score"], c["rank"], c["display_rank"], c["tie_group_size"])
        for c in payload["cells"]
    ]


def test_client_accepts_extended_payload_over_the_wire(stub: StubBackend) -> None:
    stub.responder = StubBackend.respond_json(
        200, {**real_payload(), **copy.deepcopy(EXTENDED_FIELDS), "campo_futuro": 1}
    )
    view = client_for(stub).fetch_ranking()
    assert view.freshness_available and view.station_id == "330007"
    assert view.missing_additive_fields == ()


def test_connection_refused_is_a_controlled_error() -> None:
    client = BackendRankingClient(closed_port_url(), connect_timeout=1.0, read_timeout=1.0)
    with pytest.raises(BackendError) as info:
        client.fetch_ranking()
    assert info.value.kind == ERROR_KIND_CONNECTION


def test_read_timeout_is_a_controlled_error(stub: StubBackend) -> None:
    stub.responder = StubBackend.respond_slow(1.5)
    with pytest.raises(BackendError) as info:
        client_for(stub, read_timeout=0.3).fetch_ranking()
    assert info.value.kind == ERROR_KIND_TIMEOUT


@pytest.mark.parametrize(
    "status, error_type",
    [
        (422, "invalid_request"),
        (500, "internal_error"),
        (502, "upstream_invalid_response"),
        (503, "upstream_unavailable"),
        (504, "upstream_timeout"),
    ],
)
def test_backend_error_statuses_are_mapped(stub: StubBackend, status: int, error_type: str) -> None:
    stub.responder = StubBackend.respond_json(status, error_body(error_type, "mensaje"))
    with pytest.raises(BackendError) as info:
        client_for(stub).fetch_ranking()
    assert info.value.kind == ERROR_KIND_HTTP_BACKEND
    assert info.value.http_status == status
    assert info.value.error_type == error_type
    assert info.value.backend_message == "mensaje"


def test_empty_body_over_the_wire(stub: StubBackend) -> None:
    stub.responder = StubBackend.respond_raw(200, b"")
    with pytest.raises(BackendError) as info:
        client_for(stub).fetch_ranking()
    assert info.value.kind == ERROR_KIND_INVALID_JSON


def test_invalid_json_over_the_wire(stub: StubBackend) -> None:
    stub.responder = StubBackend.respond_raw(200, b"<html>no json</html>", "text/html")
    with pytest.raises(BackendError) as info:
        client_for(stub).fetch_ranking()
    assert info.value.kind == ERROR_KIND_INVALID_JSON


def test_semantically_invalid_ranking_over_the_wire(stub: StubBackend) -> None:
    payload = real_payload()
    payload["cells"][0], payload["cells"][7] = payload["cells"][7], payload["cells"][0]
    stub.responder = StubBackend.respond_json(200, payload)
    with pytest.raises(BackendError) as info:
        client_for(stub).fetch_ranking()
    assert info.value.kind == ERROR_KIND_INVALID_RANKING


# ── STREAMLIT_INTEGRATION: app completa con AppTest ──────────────────────────


def test_apptest_prototype_default_renders_ranking_from_backend(
    stub: StubBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    at = run_app(monkeypatch, stub.base_url)
    radio = at.sidebar.radio[0]
    assert radio.value == PROTOTYPE_MODE
    assert "Prototipo local (legacy Hito 1)" not in radio.options
    assert stub.requests and stub.requests[0]["path"] == "/api/v1/ranking"

    text = markdown_blob(at)
    assert "PROTOTIPO EXPLORATORIO" in text and "BACKEND REST" in text
    assert "Grupo prioritario" in text and "<b>7 celdas</b> empatadas" in text
    assert "Empate real del modelo · 7 celdas" in text
    assert real_payload()["inputs_fingerprint"] in text
    selectors = [s for s in at.selectbox if s.label == "Celda"]
    assert selectors and len(selectors[0].options) == 50
    assert selectors[0].options == [c["cell_id"] for c in real_payload()["cells"]]
    assert not at.error


def test_apptest_v0_payload_never_invents_freshness_station_or_meteo(
    stub: StubBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    at = run_app(monkeypatch, stub.base_url)
    text = markdown_blob(at)
    assert "DATOS HISTÓRICOS" not in text
    assert not at.warning
    infos = " ".join(i.value for i in at.info)
    assert "no informada por el backend" in infos
    assert f"Estación meteorológica: {NOT_PROVIDED}" in text
    assert "°C" not in text and "km/h" not in text
    assert "Historial FIRMS: 0" not in text and "Historial FIRMS</span><b>0" not in text


def test_apptest_extended_payload_renders_freshness_and_traceability(
    stub: StubBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub.responder = StubBackend.respond_json(
        200, {**real_payload(), **copy.deepcopy(EXTENDED_FIELDS)}
    )
    at = run_app(monkeypatch, stub.base_url)
    text = markdown_blob(at)
    assert at.warning and "DATOS HISTÓRICOS" in at.warning[0].value
    assert "hace 157 h" in at.warning[0].value
    assert not at.info
    assert "DMC Rodelillo · 330007" in text
    assert "18.8 °C" in text and "15.7 km/h" in text
    assert "PROTOTYPE / EXPLORATORY" in text
    assert "FIRMS AL DÍA" in text


def test_apptest_selecting_a_cell_updates_the_detail_panel(
    stub: StubBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    at = run_app(monkeypatch, stub.base_url)
    selector = next(s for s in at.selectbox if s.label == "Celda")
    at = selector.set_value("VP-038").run()
    assert not at.exception
    text = markdown_blob(at)
    assert "Celda seleccionada" in text
    assert "VP-038" in text and "Prioridad #49" in text and "×2" in text


def test_apptest_map_mode_toggle_does_not_refetch_or_break(
    stub: StubBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    at = run_app(monkeypatch, stub.base_url)
    toggle = next(r for r in at.radio if r.label == "Vista del mapa")
    calls_before = len(stub.requests)
    at = toggle.set_value("Todas las celdas").run()
    assert not at.exception
    assert len(stub.requests) == calls_before  # cache: la UI no vuelve a consultar


def test_apptest_backend_down_shows_controlled_message(monkeypatch: pytest.MonkeyPatch) -> None:
    at = run_app(monkeypatch, closed_port_url())
    assert at.error, "con el backend caído debe haber un st.error visible"
    message = at.error[0].value
    assert "No se pudo obtener el ranking del backend" in message
    assert "No se pudo conectar" in message
    assert "127.0.0.1" not in message and "Traceback" not in message
    assert at.sidebar.radio[0].value == PROTOTYPE_MODE
    assert "Grupo prioritario" not in markdown_blob(at)


@pytest.mark.parametrize("status", [503, 504])
def test_apptest_backend_http_error_shows_controlled_message(
    stub: StubBackend, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    stub.responder = StubBackend.respond_json(
        status, error_body("upstream_unavailable", "El servicio ML no está disponible.")
    )
    at = run_app(monkeypatch, stub.base_url)
    assert at.error and str(status) in at.error[0].value
    captions = " ".join(c.value for c in at.caption)
    assert "upstream_unavailable" in captions
    assert "Grupo prioritario" not in markdown_blob(at)


def test_apptest_invalid_ranking_fails_closed_in_the_ui(
    stub: StubBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = synthetic_payload()
    payload["cells"].pop()
    stub.responder = StubBackend.respond_json(200, payload)
    at = run_app(monkeypatch, stub.base_url)
    assert at.error and "no cumple el contrato" in at.error[0].value
    assert "Grupo prioritario" not in markdown_blob(at)


def test_apptest_legacy_mode_only_appears_behind_the_flag(
    stub: StubBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SAPI_UI_LEGACY_MODES", "1")
    monkeypatch.setenv("SAPI_BACKEND_BASE_URL", stub.base_url)
    refresh_ranking_cache()
    at = AppTest.from_file(str(APP_PATH), default_timeout=60)
    at.run()
    assert not at.exception
    radio = at.sidebar.radio[0]
    assert radio.value == PROTOTYPE_MODE
    assert radio.options[-1] == "Prototipo local (legacy Hito 1)"
