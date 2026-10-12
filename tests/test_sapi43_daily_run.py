"""SAPI-43 prep. TEST_FIXTURE_ONLY. OPERATIONAL_CURRENT_USED=NO.

Precondiciones de punteros, ausencia de fuente alternativa, arquitectura
del entrypoint y contrato de idempotencia ya implementado en Spring.
No abre red pública ni usa un CURRENT operacional.
"""

from __future__ import annotations

import ast
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import pytest
import requests

from app.utils.backend_client import BackendRankingClient

TEST_FIXTURE_ONLY = True
OPERATIONAL_CURRENT_USED = "NO"

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = REPO_ROOT / "scripts" / "sapi43_daily_run.py"
RANKING_FIXTURE = (
    REPO_ROOT
    / "services"
    / "backend"
    / "src"
    / "test"
    / "resources"
    / "ml"
    / "predict-reproducible-2026-09-01.json"
)
SPRING_REPOSITORY = (
    REPO_ROOT
    / "services"
    / "backend"
    / "src"
    / "main"
    / "java"
    / "cl"
    / "sapi"
    / "backend"
    / "ranking"
    / "persistence"
    / "RankingRepository.java"
)
V002 = REPO_ROOT / "db" / "migration" / "V002__create_sapi_v2_schema.sql"

_FORBIDDEN_ENTRYPOINT_TEXT = (
    "demo_seed",
    "run_daily_pipeline",
    "score_current_grid",
    "src.inference",
    "src.pipeline",
    "src.refresh",
    "src.modelo",
    "src.procesamiento",
    "model_status",
    "meteo_actual",
    "historical_count",
    "psycopg",
    "sqlalchemy",
    "INSERT INTO",
)
_FORBIDDEN_IMPORT_PREFIXES = (
    "app.utils.demo_seed",
    "src.pipeline",
    "src.inference",
    "src.refresh",
    "src.modelo",
    "src.procesamiento",
)

daily = importlib.import_module("scripts.sapi43_daily_run")


def expected_new_executions(
    already: set[tuple[str, str, str]],
    key: tuple[str, str, str],
) -> int:
    """Contrato SAPI-59: la misma clave natural no crea otra ejecución.

    No consulta PostGIS. Reproduce la regla de
    ``ON CONFLICT (forecast_time, model_version, inputs_fingerprint) DO NOTHING``.

    Args:
        already: Claves naturales ya aceptadas en esta prueba.
        key: Clave de la respuesta actual.

    Returns:
        ``0`` si la clave ya estaba; ``1`` si sería un alta.
    """
    return 0 if key in already else 1


def _ranking_payload() -> dict[str, Any]:
    return json.loads(RANKING_FIXTURE.read_text(encoding="utf-8"))


def _write_pointers(root: Path, firms: str = "{}", dmc: str = "{}") -> None:
    firms_path = daily.firms_pointer_path(root)
    dmc_path = daily.dmc_pointer_path(root)
    firms_path.parent.mkdir(parents=True, exist_ok=True)
    dmc_path.parent.mkdir(parents=True, exist_ok=True)
    firms_path.write_text(firms, encoding="utf-8")
    dmc_path.write_text(dmc, encoding="utf-8")


class _FakeResponse:
    """Respuesta mínima en streaming. No expone el cuerpo completo de golpe."""

    def __init__(self, status: int, body: bytes | str) -> None:
        self.status_code = status
        self._body = body.encode("utf-8") if isinstance(body, str) else body
        self.headers = {"Content-Length": str(len(self._body))}
        self.closed = 0

    @property
    def content(self) -> bytes:
        raise AssertionError("el entrypoint no debe leer response.content")

    def json(self) -> Any:
        raise AssertionError("el entrypoint no debe usar response.json()")

    def iter_content(self, chunk_size: int = 1) -> Any:
        offset = 0
        while offset < len(self._body):
            chunk = self._body[offset : offset + chunk_size]
            offset += len(chunk)
            yield chunk

    def close(self) -> None:
        self.closed += 1


class _FakeSession:
    """Sesión que registra el GET y no abre sockets."""

    def __init__(
        self,
        response: Optional[_FakeResponse] = None,
        exc: Optional[BaseException] = None,
    ) -> None:
        self.response = response
        self.exc = exc
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if self.exc is not None:
            raise self.exc
        assert self.response is not None
        return self.response


def _client(session: _FakeSession) -> BackendRankingClient:
    return BackendRankingClient(
        "http://backend.test:8080",
        connect_timeout=1.5,
        read_timeout=2.5,
        session=session,  # type: ignore[arg-type]
    )


def _ok_session() -> _FakeSession:
    return _FakeSession(_FakeResponse(200, json.dumps(_ranking_payload())))


def test_module_is_labeled_fixture_only() -> None:
    """La suite declara que no usa un CURRENT operacional."""
    assert TEST_FIXTURE_ONLY is True
    assert OPERATIONAL_CURRENT_USED == "NO"
    text = Path(__file__).read_text(encoding="utf-8")
    assert "TEST_FIXTURE_ONLY" in text
    assert "OPERATIONAL_CURRENT_USED=NO" in text


def test_missing_pointers_fail_closed_without_http(tmp_path: Path) -> None:
    """Sin los dos punteros no hay GET ni archivos nuevos."""
    session = _ok_session()
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    outcome = daily.execute(tmp_path, client=_client(session))
    after = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    assert outcome.code == daily.EXIT_CURRENT_MISSING
    assert outcome.natural_key is None
    assert "FIRMS ausente" in outcome.message
    assert "DMC ausente" in outcome.message
    assert session.calls == []
    assert after == before


def test_missing_current_does_not_construct_the_http_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La precondición falla antes de leer la URL del backend."""

    class _Exploding:
        @classmethod
        def from_env(cls) -> BackendRankingClient:
            raise AssertionError("no debe construir el cliente")

    monkeypatch.setattr(daily, "BackendRankingClient", _Exploding)
    outcome = daily.execute(tmp_path)
    assert outcome.code == daily.EXIT_CURRENT_MISSING


@pytest.mark.parametrize(
    "firms, dmc, expected",
    [
        ("", "{}", "FIRMS ilegible"),
        ("{", "{}", "FIRMS ilegible"),
        ("{}", "[]", "DMC ilegible"),
        ("null", "{}", "FIRMS ilegible"),
        ("{}", '"texto"', "DMC ilegible"),
    ],
)
def test_unreadable_pointer_skips_ranking(
    tmp_path: Path, firms: str, dmc: str, expected: str
) -> None:
    """Un JSON inválido o que no es objeto no autoriza el GET."""
    _write_pointers(tmp_path, firms=firms, dmc=dmc)
    session = _ok_session()
    outcome = daily.execute(tmp_path, client=_client(session))
    assert outcome.code == daily.EXIT_CURRENT_MISSING
    assert expected in outcome.message
    assert session.calls == []


def test_readable_object_without_sapi71_fields_still_requests_ranking(
    tmp_path: Path,
) -> None:
    """Un objeto JSON vacío es legible. No se exigen campos de SAPI-71."""
    _write_pointers(tmp_path)
    session = _ok_session()
    outcome = daily.execute(tmp_path, client=_client(session))
    assert outcome.code == daily.EXIT_OK
    assert len(session.calls) == 1


def test_one_missing_pointer_blocks_the_other(tmp_path: Path) -> None:
    """FIRMS legible no compensa un DMC ausente."""
    firms = daily.firms_pointer_path(tmp_path)
    firms.parent.mkdir(parents=True)
    firms.write_text("{}", encoding="utf-8")
    session = _ok_session()
    outcome = daily.execute(tmp_path, client=_client(session))
    assert outcome.code == daily.EXIT_CURRENT_MISSING
    assert "DMC ausente" in outcome.message
    assert "FIRMS" not in outcome.message
    assert session.calls == []


def test_success_uses_one_get_with_explicit_timeout(tmp_path: Path) -> None:
    """El único HTTP es GET /api/v1/ranking, con timeout y sin forecast_time."""
    _write_pointers(tmp_path)
    session = _ok_session()
    outcome = daily.execute(tmp_path, client=_client(session))
    payload = _ranking_payload()
    assert outcome.code == daily.EXIT_OK
    assert outcome.natural_key == (
        "2026-09-01T00:00:00+00:00",
        payload["model_version"],
        payload["inputs_fingerprint"],
    )
    assert "scientific_model_validation=false" in outcome.message
    assert "celdas=50" in outcome.message
    assert "model_status" not in outcome.message
    assert "meteo_actual" not in outcome.message
    assert "historical_count" not in outcome.message
    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["url"] == "http://backend.test:8080/api/v1/ranking"
    assert call["params"] is None
    assert call["headers"]["Accept"] == "application/json"
    assert call["timeout"] == (1.5, 2.5)
    assert call["stream"] is True


def test_env_client_sends_configured_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin cliente inyectado, el timeout sale de las variables ya existentes."""
    _write_pointers(tmp_path)
    monkeypatch.setenv("SAPI_BACKEND_BASE_URL", "http://backend.test:8080/")
    monkeypatch.setenv("SAPI_BACKEND_CONNECT_TIMEOUT", "1.25")
    monkeypatch.setenv("SAPI_BACKEND_READ_TIMEOUT", "9")
    session = _ok_session()
    monkeypatch.setattr(
        "app.utils.backend_client.requests.Session",
        lambda: session,
    )
    outcome = daily.execute(tmp_path)
    assert outcome.code == daily.EXIT_OK
    assert session.calls[0]["timeout"] == (1.25, 9.0)
    assert session.calls[0]["url"] == "http://backend.test:8080/api/v1/ranking"


@pytest.mark.parametrize("status", [422, 502, 503, 504])
def test_ranking_http_errors_do_not_fall_open(tmp_path: Path, status: int) -> None:
    """Un ranking no disponible termina en el código 3, con un solo GET."""
    _write_pointers(tmp_path)
    body = json.dumps(
        {"status": "error", "error_type": "upstream_unavailable", "message": "remoto"}
    )
    session = _FakeSession(_FakeResponse(status, body))
    outcome = daily.execute(tmp_path, client=_client(session))
    assert outcome.code == daily.EXIT_RANKING_UNAVAILABLE
    assert outcome.natural_key is None
    assert "remoto" not in outcome.message
    assert len(session.calls) == 1


@pytest.mark.parametrize(
    "exc",
    [
        requests.exceptions.ConnectTimeout("t"),
        requests.exceptions.ReadTimeout("t"),
        requests.exceptions.ConnectionError("refused"),
    ],
)
def test_network_failures_are_ranking_unavailable(tmp_path: Path, exc: BaseException) -> None:
    """Timeout y conexión rechazada no inventan un ranking."""
    _write_pointers(tmp_path)
    session = _FakeSession(exc=exc)
    outcome = daily.execute(tmp_path, client=_client(session))
    assert outcome.code == daily.EXIT_RANKING_UNAVAILABLE
    assert "refused" not in outcome.message
    assert len(session.calls) == 1


def test_http_500_is_the_persistence_exit(tmp_path: Path) -> None:
    """HTTP 500 es el fallo cerrado de persistencia que publica Spring."""
    _write_pointers(tmp_path)
    body = json.dumps(
        {
            "status": "error",
            "error_type": "internal_error",
            "message": "detalle interno que no debe verse",
        }
    )
    session = _FakeSession(_FakeResponse(500, body))
    outcome = daily.execute(tmp_path, client=_client(session))
    assert outcome.code == daily.EXIT_PERSISTENCE_UNAVAILABLE
    assert outcome.code != daily.EXIT_RANKING_UNAVAILABLE
    assert "detalle interno" not in outcome.message
    assert len(session.calls) == 1


def test_scientific_validation_true_is_rejected(tmp_path: Path) -> None:
    """Un ranking con validación científica en true no se acepta."""
    _write_pointers(tmp_path)
    payload = _ranking_payload()
    payload["scientific_model_validation"] = True
    session = _FakeSession(_FakeResponse(200, json.dumps(payload)))
    outcome = daily.execute(tmp_path, client=_client(session))
    assert outcome.code == daily.EXIT_RANKING_UNAVAILABLE
    assert outcome.natural_key is None


def test_repeated_natural_key_expects_zero_new_executions(tmp_path: Path) -> None:
    """Misma clave natural: el entrypoint no inserta y el contrato espera 0 altas.

    El conteo esperado mira la regla de Spring, no una base viva.
    """
    _write_pointers(tmp_path)
    repository = SPRING_REPOSITORY.read_text(encoding="utf-8")
    schema = V002.read_text(encoding="utf-8")
    assert "ON CONFLICT (forecast_time, model_version, inputs_fingerprint) DO NOTHING" in repository
    assert (
        "CONSTRAINT ejecuciones_clave_natural "
        "UNIQUE (forecast_time, model_version, inputs_fingerprint)" in schema
    )
    assert "scientific_model_validation = false" in schema

    session = _ok_session()
    client = _client(session)
    seen: set[tuple[str, str, str]] = set()
    first = daily.execute(tmp_path, client=client)
    assert first.code == daily.EXIT_OK
    assert first.natural_key is not None
    assert expected_new_executions(seen, first.natural_key) == 1
    seen.add(first.natural_key)

    second = daily.execute(tmp_path, client=client)
    assert second.code == daily.EXIT_OK
    assert second.natural_key == first.natural_key
    assert expected_new_executions(seen, second.natural_key) == 0
    assert len(session.calls) == 2
    assert {call["url"] for call in session.calls} == {"http://backend.test:8080/api/v1/ranking"}


def test_entrypoint_source_has_no_forbidden_paths() -> None:
    """El entrypoint no importa scoring, sembrado, pipeline legado ni SQL."""
    source = ENTRYPOINT.read_text(encoding="utf-8")
    for token in _FORBIDDEN_ENTRYPOINT_TEXT:
        assert token not in source, token
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    for name in imported:
        for prefix in _FORBIDDEN_IMPORT_PREFIXES:
            assert not (name == prefix or name.startswith(prefix + ".")), name


def test_import_does_not_load_scoring_or_legacy_pipeline() -> None:
    """Importar el entrypoint en un proceso limpio no carga inferencia."""
    probe = (
        "import sys; before = set(sys.modules); "
        "import scripts.sapi43_daily_run; "
        "after = set(sys.modules); "
        "print('\\n'.join(sorted(after - before)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    loaded = set(result.stdout.splitlines())
    forbidden = {
        "src.inference",
        "src.pipeline",
        "src.pipeline.run_daily",
        "app.utils.demo_seed",
        "sklearn",
        "joblib",
    }
    assert loaded.isdisjoint(forbidden)


def test_main_hides_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Un fallo interno no imprime traza ni la excepción original."""

    def _boom(_root: Path) -> daily.DailyRunOutcome:
        raise RuntimeError("secreto http://interno.example/ranking")

    monkeypatch.setattr(daily, "execute", _boom)
    assert daily.main([]) == daily.EXIT_INTERNAL
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "secreto" not in captured.err
    assert "http://" not in captured.err
    assert captured.out == ""


def test_main_routes_precondition_failure_to_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """La precondición sale por stderr, sin traza."""
    monkeypatch.setattr(
        daily,
        "execute",
        lambda _root: daily.DailyRunOutcome(daily.EXIT_CURRENT_MISSING, "puntero ausente"),
    )
    assert daily.main([]) == daily.EXIT_CURRENT_MISSING
    captured = capsys.readouterr()
    assert captured.err.strip() == "puntero ausente"
    assert "Traceback" not in captured.err
    assert captured.out == ""
