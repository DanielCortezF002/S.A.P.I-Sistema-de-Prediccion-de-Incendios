"""SAPI F1 SAPI-43.CA8 -- cierre dinamico del hallazgo NOT VERIFIED en
ASTRA_F1_RN11_CA8_MATRIX.md: ningun test anterior levantaba realmente
docker-compose.yml + docker-compose.operational.yml y ejercitaba el gate
de procedencia en contenedores reales. Este test lo hace.

Stack aislado nuevo (proyecto Compose con sufijo unico, puertos libres
elegidos en tiempo de ejecucion). No toca contenedores, volumenes ni
redes preexistentes. Limpieza al final solo de lo creado por esta
ejecucion (sin -v: no se borran volumenes, ni los de esta corrida ni
ningun otro, consistente con el limite de autorizacion de esta sesion).

Omitido automaticamente (SKIP) si Docker no esta disponible.
"""
from __future__ import annotations

import contextlib
import http.server
import json
import pathlib
import socket
import subprocess
import threading
import time
import uuid

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "services/backend/src/test/resources/ml/predict-reproducible-2026-09-01.json"
EVIDENCE_DIR = REPO_ROOT / "artifacts/hito2/f1/ca8-dynamic-overlay"


def _docker_available() -> bool:
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=10, check=True)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _docker_available(), reason="Docker no disponible en este entorno")


def _free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


_STUB_EVENTS: list[dict[str, object]] = []
_STUB_EVENTS_LOCK = threading.Lock()


def _stub_event(kind: str, **fields: object) -> None:
    with _STUB_EVENTS_LOCK:
        _STUB_EVENTS.append({"t": round(time.time(), 3), "kind": kind, **fields})


class _StubHandler(http.server.BaseHTTPRequestHandler):
    """Stub del ML que habla HTTP/1.1 como el servicio real (uvicorn).

    El backend envia `POST /predict` con `Transfer-Encoding: chunked` y usa un
    HttpClient del JDK en HTTP/1.1 con pool de conexiones. Un stub que no
    consume el cuerpo chunked deja esos bytes en el socket: el servidor los
    interpreta como una nueva request (la linea `2` del chunk), responde 400 y
    cierra la conexion. Si ese cierre gana la carrera contra la lectura de la
    respuesta, el cliente falla con `IOException: HTTP/1.1 header parser
    received no bytes` -> MlCallException(UNAVAILABLE) -> 503
    upstream_unavailable. Eso ocurrio en CI (runs 39297368912 y 40132965231) y
    se reprodujo en aislamiento. Este stub consume el cuerpo completo y
    mantiene la conexion viva, igual que uvicorn; `requests` y `_STUB_EVENTS`
    dejan diagnostico si vuelve a fallar.
    """

    protocol_version = "HTTP/1.1"
    body: bytes = b"{}"
    requests: int = 0
    requests_lock = threading.Lock()

    def setup(self) -> None:
        super().setup()
        _stub_event("connect", peer=f"{self.client_address[0]}:{self.client_address[1]}")

    def finish(self) -> None:
        try:
            super().finish()
        finally:
            _stub_event("finish", peer=f"{self.client_address[0]}:{self.client_address[1]}")

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except Exception as ex:  # noqa: BLE001 - diagnostico del stub
            _stub_event("handler_error", error=type(ex).__name__, detail=repr(ex))
            raise
        finally:
            _stub_event(
                "request_done",
                line=getattr(self, "requestline", ""),
                raw=getattr(self, "raw_requestline", b"")[:80].decode("latin-1", "replace"),
                close=self.close_connection,
            )

    def _read_chunked_body(self) -> bytes:
        """Consume un cuerpo chunked completo (el backend Spring lo envia asi)."""
        chunks: list[bytes] = []
        while True:
            line = self.rfile.readline(65536).strip()
            size = int(line.split(b";", 1)[0], 16)
            if size == 0:
                while self.rfile.readline(65536) not in (b"\r\n", b"\n", b""):
                    pass
                return b"".join(chunks)
            chunks.append(self.rfile.read(size))
            self.rfile.read(2)  # CRLF de fin de chunk

    def do_POST(self) -> None:  # noqa: N802
        with _StubHandler.requests_lock:
            _StubHandler.requests += 1
        length = int(self.headers.get("Content-Length", "0"))
        chunked = "chunked" in (self.headers.get("Transfer-Encoding") or "").lower()
        _stub_event(
            "post", line=self.requestline, content_length=length,
            transfer_encoding=self.headers.get("Transfer-Encoding"),
            connection=self.headers.get("Connection"),
            expect=self.headers.get("Expect"),
        )
        # Leer el cuerpo segun el framing real: si queda sin consumir, el servidor
        # interpreta el chunk como una nueva request, responde 400 y cierra la
        # conexion; ese cierre compite con la lectura de la respuesta en el cliente
        # y produce el 503 intermitente (ver docstring de la clase).
        data = self._read_chunked_body() if chunked else self.rfile.read(length)
        _stub_event("body_read", requested=length, chunked=chunked, received=len(data))
        body = _StubHandler.body
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            _stub_event("response_written", sent=len(body))
        except Exception as ex:  # noqa: BLE001 - diagnostico del stub
            _stub_event("write_error", error=type(ex).__name__, detail=repr(ex))
            raise

    def log_message(self, fmt, *args) -> None:  # noqa: A002
        pass


def _error_type(body: bytes) -> str:
    """Extrae solo el tipo de error contractual para un diagnostico seguro de CI."""
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "[respuesta no JSON]"
    if not isinstance(payload, dict):
        return "[no objeto]"
    return str(payload.get("error_type", "[ausente]"))


def _ranking_with(forecast_time: str, fingerprint: str, firms_origin: str) -> bytes:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["forecast_time"] = forecast_time
    data["inputs_fingerprint"] = fingerprint
    data["firms_origin"] = firms_origin
    return json.dumps(data).encode("utf-8")


def _psql(db_container: str, sql: str) -> str:
    result = subprocess.run(
        ["docker", "exec", db_container, "psql", "-U", "sapi", "-d", "sapi_v2", "-t", "-A", "-c", sql],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return result.stdout.strip()


def _count_rows(db_container: str, table: str) -> int:
    return int(_psql(db_container, f"SELECT COUNT(*) FROM {table};"))


def _http(url: str) -> tuple[int, bytes]:
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read()


def _http_ready(url: str) -> tuple[int, bytes] | None:
    """Como _http, pero None (en vez de excepcion) si el servidor aun no acepta conexiones."""
    try:
        return _http(url)
    except OSError:
        return None


def test_f1_operational_overlay_real_stack_enforces_current_only_gate() -> None:
    run_id = uuid.uuid4().hex[:8]
    project = f"sapi-f1-ca8-dyn-{run_id}"
    db_port, ml_port, backend_port, stub_port, probe_port = (
        _free_port(), _free_port(), _free_port(), _free_port(), _free_port(),
    )
    db_container = f"{project}-db-v2-1"
    probe_container = f"{project}-backend-probe"
    evidence = EVIDENCE_DIR / f"run-{run_id}"
    evidence.mkdir(parents=True, exist_ok=True)

    compose_env = {
        "SAPI_DB_USER": "sapi", "SAPI_DB_NAME": "sapi_v2",
        "SAPI_DB_PASSWORD": "f1-ca8-dynamic-local-only",
        "SAPI_DB_PORT": str(db_port), "SAPI_ML_PORT": str(ml_port),
        "SAPI_BACKEND_PORT": str(backend_port),
        "SAPI_ML_CONNECT_TIMEOUT": "2s", "SAPI_ML_READ_TIMEOUT": "60s",
    }
    import os
    env = {**os.environ, **compose_env}

    with _STUB_EVENTS_LOCK:
        _STUB_EVENTS.clear()
    with _StubHandler.requests_lock:
        _StubHandler.requests = 0
    stub = http.server.ThreadingHTTPServer(("0.0.0.0", stub_port), _StubHandler)
    stub_thread = threading.Thread(target=stub.serve_forever, daemon=True)
    stub_thread.start()

    # Diagnostico: se vuelca en finally aunque una asercion falle a mitad de camino.
    results: dict[str, object] = {}

    def compose(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["docker", "compose", "-p", project, "-f", "docker-compose.yml",
             "-f", "docker-compose.operational.yml", *args],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=600,
        )

    try:
        # 1) Stack real aislado: base + overlay operacional, build limpio.
        resolved = compose("config")
        (evidence / "compose_resolved.yml").write_text(resolved.stdout, encoding="utf-8")
        up = compose("up", "--build", "-d", "db-v2", "ml-api", "backend")
        (evidence / "compose_up.log").write_text(up.stdout + up.stderr, encoding="utf-8")
        assert up.returncode == 0, up.stderr

        for _ in range(60):
            health = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Health.Status}}", f"{project}-backend-1"],
                capture_output=True, text=True,
            )
            if health.stdout.strip() == "healthy":
                break
            time.sleep(2)
        else:
            pytest.fail("backend del overlay operacional no alcanzo 'healthy' a tiempo")

        # 2) Configuracion Spring efectiva current-only, leida del proceso real.
        env_dump = subprocess.run(
            ["docker", "exec", f"{project}-backend-1", "env"], capture_output=True, text=True, check=True,
        ).stdout
        (evidence / "backend_effective_env.txt").write_text(env_dump, encoding="utf-8")
        assert "SAPI_PERSISTENCE_ALLOWED_FIRMS_ORIGINS=current" in env_dump

        before_exec = _count_rows(db_container, "ejecuciones")
        before_pred = _count_rows(db_container, "predicciones_celda")

        # Contenedor-sonda: misma imagen ya construida, misma red/DB, solo SAPI_ML_BASE_URL
        # apunta al stub real en el host -- para controlar firms_origin de forma determinista
        # sin tocar el ml-api real del stack (que en modo operacional depende de datos reales).
        subprocess.run(
            ["docker", "run", "-d", "--name", probe_container,
             "--network", f"{project}_sapi-v2-net",
             "--add-host", "host.docker.internal:host-gateway",
             "-e", f"SAPI_ML_BASE_URL=http://host.docker.internal:{stub_port}",
             "-e", "SAPI_ML_CONNECT_TIMEOUT=10s",
             "-e", "SAPI_ML_READ_TIMEOUT=60s",
             "-e", "SPRING_DATASOURCE_URL=jdbc:postgresql://db-v2:5432/sapi_v2",
             "-e", "SPRING_DATASOURCE_USERNAME=sapi",
             "-e", f"SPRING_DATASOURCE_PASSWORD={compose_env['SAPI_DB_PASSWORD']}",
             "-e", "SAPI_PERSISTENCE_ENABLED=true",
             "-e", "SAPI_PERSISTENCE_ALLOWED_FIRMS_ORIGINS=current",
             "-e", "SAPI_FLYWAY_LOCATIONS=filesystem:/app/db/migration",
             "-e", "SPRING_FLYWAY_FAILONMISSINGLOCATIONS=true",
             "-v", f"{REPO_ROOT / 'db' / 'migration'}:/app/db/migration:ro",
             "-p", f"127.0.0.1:{probe_port}:8080",
             f"{project}-backend"],
            check=True, capture_output=True, text=True,
        )
        for _ in range(30):
            # /health es el liveness contractual (200 = proceso arriba). Probar
            # /api/v1/ranking aceptaba cualquier status, incluido 503, y gastaba
            # una llamada al ML antes de la primera asercion.
            ready = _http_ready(f"http://127.0.0.1:{probe_port}/health")
            if ready is not None and ready[0] == 200:
                break
            time.sleep(2)
        else:
            pytest.fail("contenedor-sonda no respondio /health=200 a tiempo")

        # 3) Rechazo baseline y reproducibility -> 500 internal_error, cero escrituras nuevas.
        reject_fingerprints = {"baseline": "aa" * 32, "reproducibility": "bb" * 32}
        for origin, fingerprint in reject_fingerprints.items():
            _StubHandler.body = _ranking_with("2026-10-14T11:00:00Z", fingerprint, origin)
            with _StubHandler.requests_lock:
                requests_before = _StubHandler.requests
            status, body = _http(f"http://127.0.0.1:{probe_port}/api/v1/ranking")
            payload = json.loads(body)
            with _StubHandler.requests_lock:
                stub_posts = _StubHandler.requests - requests_before
            results[f"reject_{origin}"] = {
                "status": status, "body": payload, "stub_posts": stub_posts,
            }
            assert stub_posts > 0, f"origin={origin}: backend no consulto el stub HTTP"
            assert status == 500, (
                f"origin={origin}, HTTP={status}, error_type={_error_type(body)}, "
                f"stub_posts={stub_posts}"
            )
            assert payload.get("error_type") == "internal_error"
            assert _count_rows(db_container, "ejecuciones") == before_exec
            assert _count_rows(db_container, "predicciones_celda") == before_pred

        # 5) Control CURRENT sintetico: 1 ejecucion, 50 predicciones.
        synthetic_fp = "f1" * 32
        _StubHandler.body = _ranking_with("2026-10-14T12:00:00Z", synthetic_fp, "current")
        with _StubHandler.requests_lock:
            requests_before = _StubHandler.requests
        status, body = _http(f"http://127.0.0.1:{probe_port}/api/v1/ranking")
        with _StubHandler.requests_lock:
            stub_posts = _StubHandler.requests - requests_before
        results["accept_current"] = {
            "status": status, "error_type": _error_type(body) if status != 200 else None,
            "stub_posts": stub_posts,
        }
        assert stub_posts > 0, "origin=current: backend no consulto el stub HTTP"
        assert status == 200, (
            f"origin=current, HTTP={status}, error_type={_error_type(body)}, "
            f"stub_posts={stub_posts}"
        )
        assert _count_rows(db_container, "ejecuciones") == before_exec + 1
        assert _count_rows(db_container, "predicciones_celda") == before_pred + 50
        stored_origin = _psql(db_container, "SELECT firms_origin FROM ejecuciones ORDER BY id DESC LIMIT 1;")
        assert stored_origin == "current"

        # 6) Replay idempotente: misma identidad, misma respuesta, sin filas nuevas.
        with _StubHandler.requests_lock:
            requests_before = _StubHandler.requests
        status2, body2 = _http(f"http://127.0.0.1:{probe_port}/api/v1/ranking")
        with _StubHandler.requests_lock:
            stub_posts = _StubHandler.requests - requests_before
        results["replay_current"] = {
            "status": status2, "error_type": _error_type(body2) if status2 != 200 else None,
            "stub_posts": stub_posts,
        }
        assert stub_posts > 0, "origin=current (replay): backend no consulto el stub HTTP"
        assert status2 == 200, (
            f"origin=current (replay), HTTP={status2}, error_type={_error_type(body2)}, "
            f"stub_posts={stub_posts}"
        )
        assert body2 == body
        assert _count_rows(db_container, "ejecuciones") == before_exec + 1
        assert _count_rows(db_container, "predicciones_celda") == before_pred + 50

        # 7) Regresion del arnes: el stub consumio cada cuerpo chunked y no
        #    interpreto bytes del cuerpo como una request. Sin esto, el 400 de
        #    cierre compite con la respuesta y el 503 intermitente reaparece.
        with _STUB_EVENTS_LOCK:
            events = list(_STUB_EVENTS)
        posts = [event for event in events if event["kind"] == "post"]
        reads = [event for event in events if event["kind"] == "body_read"]
        malformed = [
            event for event in events
            if event["kind"] == "request_done"
            and event["line"]
            and event["line"].split(" ", 1)[0] not in {
                "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS",
            }
        ]
        assert len(reads) == len(posts) and all(event["received"] > 0 for event in reads), (
            f"el stub no consumio el cuerpo chunked: {reads}"
        )
        assert not malformed, f"el stub interpreto bytes del cuerpo como request: {malformed[:2]}"

        # 8) Evidencia: SHA, config, conteos SQL, resultados.
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
        (evidence / "git_identity.txt").write_text(f"head: {head}\nproject: {project}\n", encoding="utf-8")
        (evidence / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        (evidence / "sql_counts.txt").write_text(
            f"before: ejecuciones={before_exec} predicciones={before_pred}\n"
            f"after: ejecuciones={before_exec + 1} predicciones={before_pred + 50}\n",
            encoding="utf-8",
        )
    finally:
        try:
            (evidence / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        finally:
            with _STUB_EVENTS_LOCK:
                stub_events = list(_STUB_EVENTS)
            (evidence / "stub_events.json").write_text(
                json.dumps(stub_events, indent=2), encoding="utf-8"
            )
            probe_logs = subprocess.run(
                ["docker", "logs", "--tail", "200", probe_container],
                capture_output=True, text=True,
            )
            (evidence / "probe.log").write_text(
                probe_logs.stdout + probe_logs.stderr, encoding="utf-8"
            )
            subprocess.run(["docker", "rm", "-f", probe_container], capture_output=True)
            stub.shutdown()
            stub.server_close()
            down = compose("down")
            (evidence / "compose_down.log").write_text(down.stdout + down.stderr, encoding="utf-8")
