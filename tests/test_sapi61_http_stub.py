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
import requests
from streamlit.testing.v1 import AppTest

from app.components.ranking_backend_view import NOT_PROVIDED, refresh_ranking_cache
from app.utils.backend_client import (
    ERROR_KIND_CONNECTION,
    ERROR_KIND_HTTP_BACKEND,
    ERROR_KIND_INVALID_JSON,
    ERROR_KIND_INVALID_RANKING,
    ERROR_KIND_TIMEOUT,
    MAX_BODY_BYTES,
    BackendError,
    BackendRankingClient,
)
from tests.test_backend_client import (
    EXTENDED_FIELDS,
    MALICIOUS_MESSAGES,
    real_payload,
    synthetic_payload,
)

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

            def handle_error(self, *_: Any) -> None:
                return

        class Server(ThreadingHTTPServer):
            def handle_error(self, request: Any, client_address: Any) -> None:
                # El cliente aborta a propósito (límite de tamaño): el reset
                # resultante en el servidor es esperado y no debe ensuciar la salida.
                stub.server_side_errors += 1

        self.server_side_errors = 0
        self.server = Server(("127.0.0.1", 0), Handler)
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
    def respond_raw_declared(status: int, body: bytes, *, declared_length: int | None) -> Responder:
        """Cuerpo completo con un Content-Length que miente (o ausente)."""

        def responder(handler: BaseHTTPRequestHandler) -> None:
            handler.send_response(status)
            handler.send_header("Content-Type", "application/json")
            if declared_length is not None:
                handler.send_header("Content-Length", str(declared_length))
            handler.end_headers()
            try:
                handler.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                return

        return responder

    @staticmethod
    def respond_slow(delay_seconds: float) -> Responder:
        def responder(handler: BaseHTTPRequestHandler) -> None:
            time.sleep(delay_seconds)
            StubBackend.respond_json(200, real_payload())(handler)

        return responder

    @staticmethod
    def respond_stream(
        status: int,
        total_bytes: int,
        *,
        declared_length: int | None | str = "real",
        chunked: bool = False,
        piece: int = 64 * 1024,
        fill: bytes = b" ",
    ) -> Responder:
        """Cuerpo grande emitido por piezas.

        `declared_length="real"` envía el Content-Length verdadero; `None` lo
        omite (HTTP/1.0: delimitado por cierre); un entero envía un valor que
        miente; `chunked=True` usa Transfer-Encoding: chunked (HTTP/1.1).
        """

        def responder(handler: BaseHTTPRequestHandler) -> None:
            if chunked:
                handler.protocol_version = "HTTP/1.1"
            handler.send_response(status)
            handler.send_header("Content-Type", "application/json")
            if chunked:
                handler.send_header("Transfer-Encoding", "chunked")
                handler.send_header("Connection", "close")
            elif declared_length == "real":
                handler.send_header("Content-Length", str(total_bytes))
            elif declared_length is not None:
                handler.send_header("Content-Length", str(declared_length))
            handler.end_headers()
            remaining = total_bytes
            try:
                while remaining > 0:
                    data = fill * min(piece, remaining)
                    remaining -= len(data)
                    if chunked:
                        handler.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
                    else:
                        handler.wfile.write(data)
                if chunked:
                    handler.wfile.write(b"0\r\n\r\n")
            except (BrokenPipeError, ConnectionResetError):
                return  # el cliente cortó: comportamiento esperado

        return responder

    @staticmethod
    def respond_incomplete(declared_length: int, actual: bytes) -> Responder:
        """Declara más bytes de los que envía y cierra la conexión."""

        def responder(handler: BaseHTTPRequestHandler) -> None:
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(declared_length))
            handler.end_headers()
            handler.wfile.write(actual)
            handler.wfile.flush()
            handler.connection.shutdown(socket.SHUT_RDWR)
            handler.connection.close()

        return responder


class RecordingSession(requests.Session):
    """Sesión real que recuerda la última respuesta para probar `close()`."""

    def __init__(self) -> None:
        super().__init__()
        self.last_response: requests.Response | None = None

    def get(self, *args: Any, **kwargs: Any) -> requests.Response:
        response = super().get(*args, **kwargs)
        self.last_response = response
        return response


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
    assert not hasattr(info.value, "backend_message")


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


# ── HTTP_STUB: límite de cuerpo en streaming (Astra MAJOR 1) ─────────────────

OVERSIZED = MAX_BODY_BYTES + 256 * 1024


def _fetch_recorded(
    stub: StubBackend, read_timeout: float = 10.0
) -> tuple[BackendError, RecordingSession]:
    session = RecordingSession()
    client = BackendRankingClient(
        stub.base_url, connect_timeout=2.0, read_timeout=read_timeout, session=session
    )
    started = time.monotonic()
    with pytest.raises(BackendError) as info:
        client.fetch_ranking()
    assert time.monotonic() - started < 5.0, "el aborto por tamaño debe ser inmediato"
    assert session.last_response is not None
    assert session.last_response.raw.closed, "response.close() debe liberar la conexión"
    return info.value, session


def test_200_oversized_with_content_length_over_the_wire(stub: StubBackend) -> None:
    stub.responder = StubBackend.respond_stream(200, OVERSIZED)
    err, session = _fetch_recorded(stub)
    assert err.kind == ERROR_KIND_INVALID_RANKING
    assert "supera" in err.detail  # falló temprano por Content-Length
    assert session.last_response._content_consumed is False  # nunca se materializó


def test_200_oversized_without_content_length_over_the_wire(stub: StubBackend) -> None:
    stub.responder = StubBackend.respond_stream(200, OVERSIZED, declared_length=None)
    err, session = _fetch_recorded(stub)
    assert err.kind == ERROR_KIND_INVALID_RANKING
    assert "mayor a" in err.detail  # cortado durante la lectura
    assert session.last_response._content_consumed is False


def test_200_oversized_chunked_over_the_wire(stub: StubBackend) -> None:
    stub.responder = StubBackend.respond_stream(200, OVERSIZED, chunked=True)
    err, session = _fetch_recorded(stub)
    assert err.kind == ERROR_KIND_INVALID_RANKING
    assert session.last_response.headers.get("Transfer-Encoding") == "chunked"
    assert session.last_response._content_consumed is False


def test_503_oversized_chunked_error_body_is_controlled(stub: StubBackend) -> None:
    stub.responder = StubBackend.respond_stream(503, OVERSIZED, chunked=True, fill=b"x")
    err, session = _fetch_recorded(stub)
    assert err.kind == ERROR_KIND_HTTP_BACKEND
    assert err.http_status == 503
    assert err.error_type is None
    assert session.last_response._content_consumed is False


def test_503_oversized_without_content_length_is_controlled(stub: StubBackend) -> None:
    stub.responder = StubBackend.respond_stream(503, OVERSIZED, declared_length=None, fill=b"x")
    err, _ = _fetch_recorded(stub)
    assert err.kind == ERROR_KIND_HTTP_BACKEND and err.http_status == 503


def test_lying_small_content_length_fails_closed(stub: StubBackend) -> None:
    # Declara 40 bytes y envía el ranking completo: el cliente lee 40 → JSON truncado.
    body = json.dumps(real_payload()).encode("utf-8")
    stub.responder = StubBackend.respond_raw_declared(200, body, declared_length=40)
    err, _ = _fetch_recorded(stub)
    assert err.kind == ERROR_KIND_INVALID_JSON


def test_lying_huge_content_length_with_small_body_fails_early(stub: StubBackend) -> None:
    body = json.dumps(real_payload()).encode("utf-8")
    stub.responder = StubBackend.respond_raw_declared(200, body, declared_length=OVERSIZED)
    err, session = _fetch_recorded(stub)
    assert err.kind == ERROR_KIND_INVALID_RANKING and "supera" in err.detail
    assert session.last_response._content_consumed is False


def test_incomplete_transfer_is_a_controlled_connection_error(stub: StubBackend) -> None:
    body = json.dumps(real_payload()).encode("utf-8")
    stub.responder = StubBackend.respond_incomplete(len(body) * 3, body)
    err, _ = _fetch_recorded(stub)
    assert err.kind == ERROR_KIND_CONNECTION


def test_exact_limit_body_over_the_wire_is_read_and_fails_only_on_contract(
    stub: StubBackend,
) -> None:
    body = b"{" + b" " * (MAX_BODY_BYTES - 2) + b"}"
    stub.responder = StubBackend.respond_raw(200, body)
    err, _ = _fetch_recorded(stub)
    assert err.kind == ERROR_KIND_INVALID_RANKING and "requeridos" in err.detail


def test_limit_plus_one_over_the_wire_is_rejected_for_size(stub: StubBackend) -> None:
    body = b"{" + b" " * (MAX_BODY_BYTES - 1) + b"}"
    assert len(body) == MAX_BODY_BYTES + 1
    stub.responder = StubBackend.respond_raw(200, body)
    err, _ = _fetch_recorded(stub)
    assert err.kind == ERROR_KIND_INVALID_RANKING and "supera" in err.detail
    stub.responder = StubBackend.respond_raw_declared(200, body, declared_length=None)
    err, _ = _fetch_recorded(stub)
    assert err.kind == ERROR_KIND_INVALID_RANKING and "mayor a" in err.detail


def test_successful_response_is_closed_too(stub: StubBackend) -> None:
    session = RecordingSession()
    client = BackendRankingClient(
        stub.base_url, connect_timeout=2.0, read_timeout=10.0, session=session
    )
    assert len(client.fetch_ranking().cells) == 50
    assert session.last_response is not None and session.last_response.raw.closed


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
    assert "El servicio ML no está disponible." not in " ".join(
        e.value for e in list(at.error) + list(at.caption) + list(at.markdown)
    )
    assert "Grupo prioritario" not in markdown_blob(at)


def _everything_rendered(at: AppTest) -> str:
    parts: list[str] = []
    for collection in (at.error, at.warning, at.info, at.success, at.caption, at.markdown):
        parts.extend(str(e.value) for e in collection)
    parts.extend(str(t.value) for t in at.title)
    parts.extend(str(h.value) for h in at.header)
    parts.extend(str(s.value) for s in at.subheader)
    parts.extend(str(t.value) for t in at.text)
    return "\n".join(parts)


def test_apptest_malicious_remote_message_never_reaches_the_ui(
    stub: StubBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Astra MAJOR 2 en la app real: ningún fragmento del `message` remoto
    (rutas, hosts, credenciales, markdown, HTML, controles) llega al render."""
    combined = " | ".join(MALICIOUS_MESSAGES)
    stub.responder = StubBackend.respond_json(
        503, {"status": "error", "error_type": "C:\\Users\\private\\secret", "message": combined}
    )
    at = run_app(monkeypatch, stub.base_url)
    assert at.error and "503" in at.error[0].value
    rendered = _everything_rendered(at)
    assert "tipo reportado" not in rendered  # error_type fuera del contrato → no se muestra
    for fragment in (
        "secret",
        "private",
        "internal",
        "password",
        "postgresql",
        "**markdown**",
        "<script",
        "onerror",
        "Traceback",
        "/home/",
        "C:\\",
        "\x1b",
        "\x00",
        "127.0.0.1",
        str(stub.server.server_port),
        "/api/v1/ranking?",
    ):
        assert fragment not in rendered, f"{fragment!r} se filtró al render de Streamlit"
    for message in MALICIOUS_MESSAGES:
        assert message not in rendered


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
