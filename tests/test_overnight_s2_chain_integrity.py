"""Cadena ML -> backend -> Streamlit e integridad científica (OCC-NIGHTSHIFT-S2).

Clasificación de cada prueba (ver docs/closeout/sprint2-overnight-20261020/):

- ESTÁTICA: rutas declaradas en los contratos y textos científicos.
- INTEGRACIÓN: FastAPI real (`TestClient`, Modelo D real en modo reproducible).
- E2E CON STUB: FastAPI real -> relevo HTTP que SUSTITUYE a Spring Boot ->
  `BackendRankingClient` -> `app/app.py` con `AppTest`. NO acredita el sistema
  completo: Spring Boot, PostGIS y Docker no participan (eso es SAPI-66 real).

El relevo traduce `GET /api/v1/ranking` a `POST /predict` con las reglas de
`RankingService.interpret` (200 tal cual, 503 con `error_type` propagado). No
valida persistencia ni la política de procedencia.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

import pytest
import yaml
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

import services.ml_api.main as ml_api
from app.components.ranking_backend_view import refresh_ranking_cache
from src.inference.prototype_service import PrototypeUnavailableError

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "app" / "app.py"
ML_CONTRACT = ROOT / "contracts" / "openapi" / "ml-service.v0.yaml"
BACKEND_CONTRACT = ROOT / "contracts" / "openapi" / "backend.v0.yaml"
METADATA = ROOT / "models" / "prototype_model_d_metadata.json"

ml = TestClient(ml_api.app)


@pytest.fixture
def reproducible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "1")


# ── ESTÁTICAS: rutas reales y textos científicos ────────────────────────────


def _paths(contract: Path) -> set[str]:
    return set(yaml.safe_load(contract.read_text(encoding="utf-8"))["paths"])


def test_static_ml_contract_exposes_predict_not_infer() -> None:
    assert _paths(ML_CONTRACT) == {"/health", "/predict"}


def test_static_backend_contract_exposes_ranking_only_not_predict_or_infer() -> None:
    assert _paths(BACKEND_CONTRACT) == {"/health", "/api/v1/ranking"}


def test_static_streamlit_client_targets_backend_ranking_path_only() -> None:
    from app.utils import backend_client

    assert backend_client.RANKING_PATH == "/api/v1/ranking"
    source = (ROOT / "app" / "utils" / "backend_client.py").read_text(encoding="utf-8")
    assert "/predict" not in source.replace("`/predict`", "")
    assert "/infer" not in source


def test_static_scientific_warning_in_metadata_and_fallback() -> None:
    aviso = json.loads(METADATA.read_text(encoding="utf-8"))["aviso"]
    for text in (aviso, ml_api._FALLBACK_DISCLAIMER):
        assert "PROTOTIPO EXPLORATORIO" in text
        assert "ranking relativo" in text
        assert "NO una probabilidad calibrada" in text
        assert "No usar para decisiones" in text


# ── INTEGRACIÓN: ML real ────────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/infer", "/api/v1/ranking", "/api/v1/infer"])
def test_integration_ml_has_no_other_routes(path: str) -> None:
    assert ml.post(path, json={}).status_code == 404
    assert ml.get(path).status_code == 404


def test_integration_predict_is_post_only(reproducible: None) -> None:
    assert ml.get("/predict").status_code == 405


def test_integration_real_model_carries_scientific_flags(reproducible: None) -> None:
    body = ml.post("/predict", json={}).json()
    assert body["scientific_model_validation"] is False
    assert body["score_semantics"] == "relative_rank"
    assert "NO una probabilidad calibrada" in body["disclaimer"]


# ── E2E CON STUB: ML real -> relevo (sustituto de Spring) -> Streamlit ──────


class _Relay(BaseHTTPRequestHandler):
    """Sustituto de Spring Boot: reenvía al FastAPI real vía TestClient."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?")[0] != "/api/v1/ranking":
            self.send_error(404)
            return
        upstream = ml.post("/predict", json={})
        body = upstream.content
        self.send_response(upstream.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        pass


@pytest.fixture
def relay() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Relay)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _run_app(monkeypatch: pytest.MonkeyPatch, base_url: str) -> AppTest:
    monkeypatch.setenv("SAPI_BACKEND_BASE_URL", base_url)
    monkeypatch.setenv("SAPI_BACKEND_CONNECT_TIMEOUT", "5")
    monkeypatch.setenv("SAPI_BACKEND_READ_TIMEOUT", "30")
    monkeypatch.delenv("SAPI_UI_LEGACY_MODES", raising=False)
    refresh_ranking_cache()
    at = AppTest.from_file(str(APP_PATH), default_timeout=90)
    at.run()
    assert not at.exception, at.exception
    return at


def _everything(at: AppTest) -> str:
    parts = [m.value or "" for m in at.markdown]
    parts += [e.value or "" for e in at.error]
    parts += [w.value or "" for w in at.warning]
    parts += [i.value or "" for i in at.info]
    parts += [c.value or "" for c in at.caption]
    return "\n".join(parts)


def test_e2e_stub_real_ml_ranking_reaches_streamlit_with_warnings(
    reproducible: None, relay: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    truth = ml.post("/predict", json={}).json()
    at = _run_app(monkeypatch, relay)
    text = _everything(at)

    assert truth["inputs_fingerprint"] in text
    assert "PROTOTIPO EXPLORATORIO" in text
    assert "NO una probabilidad calibrada" in text
    cell_selector = [s for s in at.selectbox if s.label == "Celda"][0]
    assert cell_selector.options == [c["cell_id"] for c in truth["cells"]]
    assert not at.error


def test_e2e_stub_ml_unavailable_is_controlled_and_hides_internals(
    reproducible: None, relay: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(**_kwargs: object) -> None:
        raise PrototypeUnavailableError("C:\\secret\\path\\dmc.json faltante")

    monkeypatch.setattr(ml_api, "score_current_grid", boom)
    at = _run_app(monkeypatch, relay)
    text = _everything(at)

    assert at.error, "debe mostrarse un estado de error visible"
    assert "secret" not in text and "dmc.json" not in text
    assert "Traceback" not in text
    assert [s for s in at.selectbox if s.label == "Celda"] == []


def test_e2e_stub_unexpected_ml_failure_never_renders_a_ranking(
    reproducible: None, relay: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(**_kwargs: object) -> None:
        raise RuntimeError("fallo interno /srv/ml/internal.py")

    monkeypatch.setattr(ml_api, "score_current_grid", boom)
    at = _run_app(monkeypatch, relay)
    text = _everything(at)

    assert at.error
    assert "/srv/ml" not in text and "internal.py" not in text
    assert [s for s in at.selectbox if s.label == "Celda"] == []
