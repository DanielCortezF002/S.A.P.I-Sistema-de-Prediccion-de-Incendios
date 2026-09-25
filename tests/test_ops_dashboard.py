"""Tests del Centro de Control de solo lectura (app/pages/dashboard.py).

Fixture sintética (app/data/demo_score_synthetic.json, SYNTHETIC / DEMO).
Sin backend real: el modo en vivo se prueba con sesiones HTTP simuladas y con un
stub HTTP local (127.0.0.1) que imita el bridge; nada sale de localhost.
"""

from __future__ import annotations

import copy
import http.server
import json
import re
import socket
import threading
from pathlib import Path

import pytest
import requests

from app import control_center as launcher
from app.components import ops_dashboard as ui
from app.utils import score_contract as sc
from src.notifications.alert_payload import build_alert, render_text

FIXTURE = json.loads(sc.DEMO_FIXTURE.read_text(encoding="utf-8"))
SECRET = "SYNTH-SECRET-7f3a9c-NOT-REAL"
REPO = Path(__file__).resolve().parents[1]
PAGE = str(REPO / "app" / "pages" / "dashboard.py")
FIRMS_BLOCKED_MSG = (
    "El histórico FIRMS termina el 2026-09-10, 14 días antes de forecast_time=2026-09-24 "
    "18:00:00+00:00 (máximo 7): faltarían detecciones recientes en las features. Refrescar "
    "FIRMS (python -m src.refresh.firms_refresh refresh)."
)


def live_payload() -> dict:
    """La fixture sin sus marcas sintéticas: forma de una respuesta real del bridge."""
    p = copy.deepcopy(FIXTURE)
    p.pop("_synthetic")
    p.pop("scoring_inputs")  # el bridge actual no lo serializa
    return p


def stale_payload() -> dict:
    """FIRMS desactualizado y coherente con classify_firms_lag (T=2026-09-24)."""
    p = live_payload()
    p.update(
        firms_coverage_end="2026-09-19", firms_lag_days=5, firms_status=sc.FIRMS_STALE
    )
    return p


def live_view(payload=None) -> sc.DashboardView:
    return sc.from_payload(
        payload or live_payload(), fetched_at="2026-09-25T10:00:00+00:00"
    )


def visible_text(html: str) -> str:
    html = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    html = re.sub(r'\s(style|title|aria-label)="[^"]*"', " ", html)
    return re.sub(r"<[^>]+>", " ", html)


class FakeResponse:
    def __init__(self, status: int, body, content: bytes | None = None):
        self.status_code, self._body = status, body
        self.content = content if content is not None else b"{...}"

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    def __init__(self, response=None, exc=None):
        self.response, self.exc, self.calls = response, exc, []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url))
        if self.exc:
            raise self.exc
        return self.response


# --- Estados con ranking --------------------------------------------------------------


def test_valid_live_result_renders_operational():
    view = live_view()
    html = ui.render(view)
    assert (
        view.state == sc.LIVE_READY and view.mode == sc.MODE_LIVE and view.has_ranking
    )
    assert "OPERATIVO" in html and "DATOS DEMOSTRATIVOS" not in html
    assert "MODO: EN VIVO" in html and 'data-connection="CONNECTED"' in html
    for label in (
        "Hora de evaluación",
        "Cobertura FIRMS hasta",
        "Celdas evaluadas",
        "Modelo",
    ):
        assert f"<dt>{label}</dt>" in html
    assert "50 de 50" in html


def test_state_machine_is_explicit():
    assert sc.STATES == (
        "DEMO",
        "LOADING",
        "LIVE_READY",
        "DATA_UNAVAILABLE",
        "PROTOTYPE_UNAVAILABLE",
        "INVALID_RESULT",
        "NETWORK_ERROR",
    )
    assert set(ui.STATE_COPY) == set(sc.STATES) - {sc.LOADING}


def test_firms_metadata_rendered():
    html = ui.render(live_view())
    card = re.search(
        r'<article class="ops-src" data-source="FIRMS".*?</article>', html, re.S
    )[0]
    assert 'data-status="CURRENT"' in card
    for value in ("current", "2026-09-23", "1 día", "FIRMS AL DÍA", "AL DÍA"):
        assert value in card


def test_stale_firms_is_warning_not_blocked():
    view = live_view(stale_payload())
    html = ui.render(view)
    assert view.state == sc.LIVE_READY and view.firms_warning
    assert view.source_status()["FIRMS"] == sc.SRC_WARNING
    assert "ops-strip--warn" in html and "5 días de desfase" in visible_text(html)
    assert (
        'class="ops-top"' in html
    )  # se puntuó con aviso upstream: el ranking se muestra


def test_dmc_metadata_rendered_from_response():
    html = ui.render(live_view())
    card = re.search(r'data-source="DMC".*?</article>', html, re.S)[0]
    assert (
        "330007 · Rodelillo" in card and "DATOS RECIENTES" in card and "0.4 h" in card
    )


def test_missing_identity_says_not_in_response():
    view = live_view()
    assert view.identity == {}
    model = re.search(r'data-source="MODELO".*?</article>', ui.render(view), re.S)[0]
    assert ui.NOT_IN_RESPONSE in model and "prototype_model_d_v1" in model


def test_identity_hashes_truncated_and_full_copyable():
    view = sc.load_demo()
    sha = FIXTURE["scoring_inputs"]["model"]["sha256"]
    assert view.identity["model_sha256"] == sha
    html = ui.render(view)
    assert sha[:12] + "…" in html and sha not in html  # truncado en pantalla
    assert ("Modelo SHA-256", sha) in ui.full_hashes(
        view
    )  # completo en st.code (copiable)
    assert ("Inputs fingerprint", FIXTURE["inputs_fingerprint"]) in ui.full_hashes(view)


def test_malformed_identity_field_is_dropped():
    p = copy.deepcopy(FIXTURE)
    p["scoring_inputs"]["model"]["sha256"] = "<script>x</script>"
    view = sc.from_payload(p, demo=True)
    assert "model_sha256" not in view.identity and "<script>" not in ui.render(view)


def test_top5_exactly_ranks_1_to_5():
    view = live_view()
    assert [c.rank for c in view.top] == [1, 2, 3, 4, 5]
    assert [c.cell_id for c in view.top] == [
        "VP-028",
        "VP-033",
        "VP-038",
        "VP-035",
        "VP-019",
    ]
    html = ui.top_list(view)
    assert html.count("<li ") == 5
    assert [int(r) for r in re.findall(r'data-rank="(\d+)"', html)] == [1, 2, 3, 4, 5]
    assert "Empate: 3 celdas" in html and "posición 1" in html
    assert "+ 1 celda más comparte" in html


def test_equal_scores_preserve_backend_ranks():
    payload = live_payload()
    view = live_view(payload)
    backend = {c["cell_id"]: (c["rank"], c["score"]) for c in payload["cells"]}
    assert {c.cell_id: (c.rank, c.score) for c in view.cells} == backend  # sin tocar
    tied = [c for c in view.cells if c.score == view.cells[0].score]
    assert [c.rank for c in tied] == [1, 2, 3] and {c.display_rank for c in tied} == {1}
    ranks = [
        int(r)
        for r in re.findall(r'<td class="num">(\d+)</td>', ui.ranking_table(view))
    ]
    assert ranks == list(range(1, 51))  # rank canónico único, sin saltos por empate


def test_full_ranking_has_50_rows_in_backend_order():
    view = live_view()
    table = ui.ranking_table(view)
    rows = re.findall(
        r'<td class="num">(\d+)</td><td class="cid">(VP-\d{3})</td>', table
    )
    assert len(rows) == 50
    expected = [c["cell_id"] for c in sorted(FIXTURE["cells"], key=lambda c: c["rank"])]
    assert [cid for _, cid in rows] == expected


def test_ranking_is_not_reordered_by_frontend():
    shuffled = live_payload()
    shuffled["cells"].reverse()
    assert [c.rank for c in live_view(shuffled).cells] == list(range(1, 51))


def test_search_and_view_order_never_change_rank():
    view = live_view()
    found = ui.filter_cells(view.cells, "28")
    assert [(c.cell_id, c.rank) for c in found] == [("VP-028", 1)]
    by_id = ui.filter_cells(view.cells, "", "cell_id")
    assert [c.cell_id for c in by_id] == sorted(sc.EXPECTED_CELL_IDS)
    assert {(c.cell_id, c.rank) for c in by_id} == {
        (c.cell_id, c.rank) for c in view.cells
    }
    assert "Ninguna celda coincide" in ui.ranking_table(
        view, ui.filter_cells(view.cells, "ZZ")
    )


def test_geo_map_uses_official_grid_with_50_cells():
    view = live_view()
    svg = ui.geo_map(view)
    tips = re.findall(
        r"<title>Celda (VP-\d{3}) · rank (\d+) · score relativo ([0-9.]+)</title>", svg
    )
    assert len(tips) == 50 and {t[0] for t in tips} == set(sc.EXPECTED_CELL_IDS)
    assert svg.count('class="cell cell--top"') == 5
    assert "-71.58°" in svg  # longitud real del borde oeste de src/geo/grid.py


def test_response_geometry_must_match_trusted_grid():
    p = live_payload()
    p["cells"][0]["geometry"]["min_lon"] += 0.5  # otra ubicación para la misma celda
    view = live_view(p)
    assert (
        view.state == sc.INVALID_RESULT
        and "geometry_mismatch_with_grid" in view.reasons
    )


def test_demo_is_clearly_labeled():
    view = sc.load_demo()
    html = ui.render(view)
    assert view.state == sc.DEMO and view.mode == sc.MODE_DEMO and view.synthetic
    assert (
        "DATOS DEMOSTRATIVOS" in html
        and "SYNTHETIC DEMO" in html
        and "MODO: DEMO" in html
    )
    assert "ops-band--demo" in html and ">OPERATIVO<" not in html
    assert view.connection is None and "data-connection" not in html


def test_synthetic_marker_in_live_response_is_rejected():
    view = sc.from_payload(FIXTURE)  # la fixture llegando por la vía en vivo
    assert view.state == sc.INVALID_RESULT and not view.cells
    assert "synthetic_marker_in_live_response" in view.reasons
    assert "DATOS DEMOSTRATIVOS" not in ui.render(view)


def test_presentation_mode_hides_developer_details():
    view = sc.load_demo()
    html = ui.render(view, presentation=True)
    assert "is-presentation" in html and 'class="ops-top"' in html and "<svg" in html
    assert 'class="ops-table"' not in html and 'class="ops-tech"' not in html
    for sha in [FIXTURE["inputs_fingerprint"]] + [
        v["sha256"] if "sha256" in v else v["manifest_sha256"]
        for k, v in FIXTURE["scoring_inputs"].items()
        if k != "_synthetic"
    ]:
        assert sha[:12] not in html  # sin hashes de desarrollo en presentación
    assert (
        "2026-09-23" in html
        and "no corresponde a una probabilidad calibrada" in html.lower()
    )


# --- Tiempos distintos ------------------------------------------------------------------


def _time(html: str, kind: str) -> str:
    return re.search(rf'data-time="{kind}"[^>]*>([^<]+)<', html)[1]


def test_view_fetch_scoring_and_firms_times_are_distinct():
    view = live_view()
    html = ui.render(view)
    view_t, score_t, firms_t = (_time(html, k) for k in ("view", "scoring", "firms"))
    assert view_t == "2026-09-25 10:00:00 UTC"  # hora de consulta de vista
    assert score_t == "2026-09-24 18:00 UTC"  # momento puntuado por el modelo
    assert firms_t == "2026-09-23"  # fin de cobertura FIRMS
    assert len({view_t, score_t, firms_t}) == 3
    assert (
        "Última consulta de vista" in html and "no indica la frescura" in html.lower()
    )


def test_fetch_live_records_view_time_not_scoring_time():
    session = FakeSession(FakeResponse(200, live_payload()))
    view = sc.fetch_live("http://user:pw@bridge.local:8600/score?k=v", session=session)
    assert view.fetched_at and view.fetched_at != view.scoring_time
    assert view.endpoint == "bridge.local:8600/score"  # sin credenciales ni query
    assert "pw" not in ui.technical_details(view)


# --- Estados sin ranking ------------------------------------------------------------------


@pytest.mark.parametrize(
    "error_type,state,title,message",
    [
        (
            "data_unavailable",
            sc.DATA_UNAVAILABLE,
            "DATOS NO DISPONIBLES",
            "No hay datos suficientes para generar la evaluación actual",
        ),
        (
            "prototype_unavailable",
            sc.PROTOTYPE_UNAVAILABLE,
            "EVALUACIÓN NO DISPONIBLE",
            "El servicio de evaluación no está disponible",
        ),
        (
            "internal_error",
            sc.PROTOTYPE_UNAVAILABLE,
            "EVALUACIÓN NO DISPONIBLE",
            "El servicio de evaluación no está disponible",
        ),
    ],
)
def test_unavailable_states_show_no_ranking(error_type, state, title, message):
    upstream = {
        "status": "error",
        "error_type": error_type,
        "message": "No existe el modelo en C:/interno/models/prototype_model_d.pkl",
    }
    view = sc.from_payload(upstream)
    html = ui.render(view)
    assert view.state == state and title in html and message in html
    assert (
        'class="ops-top"' not in html
        and 'class="ops-table"' not in html
        and "VP-0" not in html
    )
    assert "C:/interno" not in html  # el mensaje upstream no se muestra
    assert "no indica que la situación sea segura" in html
    assert set(view.source_status().values()) == {sc.SRC_UNKNOWN}
    assert view.connection == sc.CONN_CONNECTED  # el servicio respondió


def test_blocked_firms_is_explicit_and_shows_no_ranking():
    view = sc.from_payload(
        {
            "status": "error",
            "error_type": "prototype_unavailable",
            "message": FIRMS_BLOCKED_MSG,
        }
    )
    html = ui.render(view)
    assert view.state == sc.PROTOTYPE_UNAVAILABLE and view.firms_blocked
    card = re.search(r'data-source="FIRMS".*?</article>', html, re.S)[0]
    assert 'data-status="BLOCKED"' in card and "BLOQUEADO" in card
    assert "2026-09-10" in card and "14 días" in card
    assert "VP-0" not in html and "firms_refresh" not in html  # sin el mensaje crudo


def test_network_error_state():
    session = FakeSession(exc=requests.ConnectionError("refused"))
    view = sc.fetch_live("http://127.0.0.1:1/score", session=session)
    html = ui.render(view)
    assert view.state == sc.NETWORK_ERROR and "SERVICIO NO DISPONIBLE" in html
    assert "No fue posible consultar el servicio SAPI" in html
    assert (
        view.connection == sc.CONN_UNAVAILABLE
        and 'data-connection="UNAVAILABLE"' in html
    )
    assert set(view.source_status().values()) == {sc.SRC_UNAVAILABLE}


def test_timeout_state():
    view = sc.fetch_live(
        "http://b/score", session=FakeSession(exc=requests.ReadTimeout("slow"))
    )
    assert view.state == sc.NETWORK_ERROR and view.reasons == ("timeout",)
    assert "no respondió dentro del tiempo de espera" in ui.render(view)


@pytest.mark.parametrize(
    "response,state,reason",
    [
        (FakeResponse(200, None), sc.LIVE_READY, None),
        (
            FakeResponse(503, {"status": "error", "error_type": "data_unavailable"}),
            sc.DATA_UNAVAILABLE,
            None,
        ),
        (
            FakeResponse(
                503, {"status": "error", "error_type": "prototype_unavailable"}
            ),
            sc.PROTOTYPE_UNAVAILABLE,
            None,
        ),
        (
            FakeResponse(500, {"status": "error", "error_type": "internal_error"}),
            sc.PROTOTYPE_UNAVAILABLE,
            None,
        ),
        (
            FakeResponse(200, ValueError("no json")),
            sc.INVALID_RESULT,
            "response_not_json",
        ),
        (
            FakeResponse(200, ValueError("empty"), content=b""),
            sc.INVALID_RESULT,
            "empty_response",
        ),
        (FakeResponse(200, {}), sc.INVALID_RESULT, "empty_response"),
        (FakeResponse(200, [1, 2]), sc.INVALID_RESULT, "response_not_object"),
        (FakeResponse(404, {"detail": "Not Found"}), sc.INVALID_RESULT, "http_404"),
    ],
    ids=[
        "ok",
        "data_unavailable",
        "prototype_unavailable",
        "internal",
        "not_json",
        "empty_body",
        "empty_object",
        "array",
        "404",
    ],
)
def test_live_mode_is_get_only_and_maps_states(response, state, reason):
    if response._body is None:
        response._body = live_payload()
    session = FakeSession(response)
    view = sc.fetch_live("http://bridge/score", session=session)
    assert view.state == state and view.mode == sc.MODE_LIVE
    assert reason is None or reason in view.reasons
    assert session.calls == [("GET", "http://bridge/score")]
    if state == sc.INVALID_RESULT:
        assert view.connection == sc.CONN_INVALID


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda p: p.pop("cells"), "missing_cells"),
        (lambda p: p["cells"].pop(), "wrong_cell_count"),
        (lambda p: p["cells"][1].update(rank=1), "duplicate_rank"),
        (
            lambda p: p["cells"][1].update(
                cell_id=p["cells"][0]["cell_id"], geometry=p["cells"][0]["geometry"]
            ),
            "duplicate_cell_id",
        ),
        (lambda p: p["cells"][2].update(score=float("nan")), "invalid_score"),
        (lambda p: p["cells"][2].update(score=float("inf")), "invalid_score"),
        (lambda p: p["cells"][2].update(score=1.7), "invalid_score"),
        (lambda p: p["cells"][2].update(score="0.5"), "invalid_score"),
        (lambda p: p["cells"][4].update(rank=51), "rank_not_1_to_n"),
        (lambda p: p["cells"][4].update(cell_id="VP-999"), "unknown_cell_id"),
        (
            lambda p: p.pop("inputs_fingerprint"),
            "missing_or_invalid_inputs_fingerprint",
        ),
        (lambda p: p.pop("forecast_time"), "missing_or_invalid_scoring_time"),
        (lambda p: p.pop("firms_status"), "invalid_firms_status"),
        (lambda p: p.update(firms_status="VERDE"), "invalid_firms_status"),
        (lambda p: p.update(firms_origin="nasa"), "invalid_firms_origin"),
        (lambda p: p.update(freshness="SIEMPRE AL DÍA"), "invalid_freshness"),
        (lambda p: p.update(age_hours=float("nan")), "invalid_age_hours"),
        (lambda p: p["cells"][0].update(score=0.01), "rank_order_violation"),
        (lambda p: p["cells"][3].update(display_rank=2), "tie_metadata_inconsistent"),
        (lambda p: p.update(firms_lag_days=5), "alert:firms_lag_inconsistent"),
    ],
    ids=[
        "no_cells",
        "49_cells",
        "dup_rank",
        "dup_cell",
        "nan",
        "inf",
        "out_of_range",
        "str_score",
        "rank_gap",
        "unknown_cell",
        "no_fingerprint",
        "no_time",
        "no_firms_status",
        "bad_firms_status",
        "bad_origin",
        "bad_freshness",
        "nan_age",
        "order",
        "tie_meta",
        "firms_lag_vs_dates",
    ],
)
def test_invalid_response_refuses_ranking(mutate, reason):
    p = live_payload()
    mutate(p)
    view = live_view(p)
    html = ui.render(view)
    assert view.state == sc.INVALID_RESULT and not view.cells and reason in view.reasons
    assert "RESULTADO INVÁLIDO" in html
    assert (
        'class="ops-top"' not in html
        and 'class="ops-table"' not in html
        and "<svg" not in html
    )
    assert 'data-alert-status="READY"' not in html  # la alerta tampoco se genera


def test_loading_state_has_no_values():
    html = ui.loading()
    assert (
        'aria-busy="true"' in html
        and "VP-" not in html
        and "score relativo" not in html
    )


# --- Adaptador canónico: panel y alerta desde el mismo resultado --------------------------


def test_same_result_powers_dashboard_and_alert_preview():
    payload = live_payload()
    view = live_view(payload)
    canonical = sc.canonical_result(payload)
    expected = build_alert(canonical)
    assert view.alert.fingerprint == expected["alert_fingerprint"]
    assert view.alert.text == render_text(expected)
    assert view.alert.top == tuple(
        (c.rank, c.display_rank, c.cell_id, c.score) for c in view.top
    )
    panel = ui.alert_panel(view)
    assert [int(r) for r in re.findall(r'data-rank="(\d+)"', panel)] == [1, 2, 3, 4, 5]
    for c in view.top:
        assert f"Celda {c.cell_id} · score relativo {c.score:.4f}" in panel
    assert "2026-09-24 18:00 UTC" in panel and "2026-09-23" in panel
    assert "no corresponde a una probabilidad calibrada" in panel.lower()


def test_canonical_result_is_whitelisted_and_value_preserving():
    p = live_payload()
    p.update(NASA_FIRMS_API_KEY=SECRET, env={"x": SECRET})
    p["cells"][0]["debug"] = SECRET
    canonical = sc.canonical_result(p)
    assert SECRET not in json.dumps(canonical)
    assert [(c["rank"], c["cell_id"], c["score"]) for c in canonical["cells"]] == [
        (c["rank"], c["cell_id"], c["score"]) for c in live_payload()["cells"]
    ]


def test_alert_extra_fields_do_not_change_fingerprint():
    base = live_view().alert.fingerprint
    noisy = live_payload()
    noisy.update(Authorization=SECRET, unrelated={"a": 1})
    assert live_view(noisy).alert.fingerprint == base


def test_alert_fingerprint_displayed_truncated_and_copyable():
    view = live_view()
    fp = view.alert.fingerprint
    assert re.fullmatch(r"[0-9a-f]{64}", fp)
    tech = ui.technical_details(view)
    assert f"{fp[:12]}…" in tech and fp not in tech
    assert ("Alert fingerprint", fp) in ui.full_hashes(view)
    assert (
        ui.N8N_IDENTITY_BOUNDARY
        == "ALERT_IDENTITY_RECONCILIATION_REQUIRED_BEFORE_TELEGRAM"
    )
    assert ui.N8N_IDENTITY_BOUNDARY in tech


def test_alert_preview_for_unavailable_states():
    unavailable = sc.from_payload({"status": "error", "error_type": "data_unavailable"})
    assert (
        unavailable.alert.status == "UNAVAILABLE" and "segura" in unavailable.alert_text
    )
    assert 'data-alert-status="UNAVAILABLE"' in ui.alert_panel(unavailable)
    assert sc.from_payload({"status": "ok"}).alert is None


def test_alert_preview_never_sends(monkeypatch):
    def _no_network(*args, **kwargs):
        raise AssertionError("la vista previa intentó abrir una conexión")

    monkeypatch.setattr(socket.socket, "connect", _no_network)
    for verb in ("get", "post", "put", "patch", "delete"):
        monkeypatch.setattr(requests, verb, _no_network)
    view = sc.load_demo()
    html = ui.render(view)
    assert view.alert.status == "READY" and "NO ENVIADA · SOLO VISTA PREVIA" in html
    assert "telegram ni n8n" in html.lower()


# --- Lenguaje y seguridad ---------------------------------------------------------------------


def _all_views() -> list[sc.DashboardView]:
    return [
        live_view(),
        sc.load_demo(),
        live_view(stale_payload()),
        sc.from_payload({"status": "error", "error_type": "data_unavailable"}),
        sc.from_payload({"status": "error", "error_type": "prototype_unavailable"}),
        sc.from_payload(
            {
                "status": "error",
                "error_type": "prototype_unavailable",
                "message": FIRMS_BLOCKED_MSG,
            }
        ),
        sc.from_payload({"status": "ok"}),
        sc.DashboardView(sc.NETWORK_ERROR),
        sc.DashboardView(sc.NETWORK_ERROR, reasons=("timeout",)),
    ]


def _all_renders() -> list[str]:
    views = _all_views()
    out = [ui.render(v) for v in views] + [
        ui.render(views[1], presentation=True),
        ui.loading(),
    ]
    out += [ui.technical_details(v) for v in views]
    out += [v.alert_text for v in views if v.alert_text]
    return out


@pytest.mark.parametrize("phrase", ui.FORBIDDEN_PHRASES)
def test_forbidden_language_absent(phrase):
    for html in _all_renders():
        assert phrase not in visible_text(html).lower()


def test_no_confirmed_fire_or_safety_wording():
    for html in _all_renders():
        text = visible_text(html).lower()
        for bad in (
            "incendio confirmado",
            "incendios confirmados",
            "fuego confirmado",
            "zona segura",
            "no hay riesgo",
            "safe",
            "no fire",
            "low risk",
            "enviar",
        ):
            assert bad not in text, bad


def test_no_probability_wording():
    for html in _all_renders():
        text = visible_text(html).lower()
        for match in re.finditer(r"probabilidad", text):
            window = text[max(0, match.start() - 30) : match.end() + 12]
            assert (
                "no corresponde a una probabilidad" in window
                or "no es una probabilidad" in window
                or "probabilidad calibrada" in window
            ), window
        assert not re.search(
            r"score[^.]{0,30}\d\s*%", text
        )  # ningún score como porcentaje
    assert "prioridad relativa" in visible_text(_all_renders()[0])
    assert "SCORE RELATIVO" in visible_text(_all_renders()[0]).upper()


def test_no_risk_semaphore_thresholds():
    html = ui.render(live_view())
    for leak in (
        "33%",
        "66%",
        "Alto",
        "Medio",
        "Bajo",
        "vigilancia rutinaria",
        "HIGH",
        "MEDIUM",
        "LOW",
    ):
        assert leak not in visible_text(html)


def test_secrets_ignored():
    p = live_payload()
    p.update(
        Authorization=f"Bearer {SECRET}",
        NASA_FIRMS_API_KEY=SECRET,
        DMC_TOKEN=SECRET,
        DMC_USUARIO=SECRET,
        Cookie=f"session={SECRET}",
        headers={"Authorization": SECRET},
        env={"NASA_FIRMS_API_KEY": SECRET},
        traceback=f"Traceback ... {SECRET}",
    )
    p["cells"][0]["debug"] = SECRET
    p["scoring_inputs"] = {"dmc": {"token": SECRET, "manifest_sha256": SECRET}}
    views = (
        live_view(p),
        sc.from_payload(
            {
                "status": "error",
                "error_type": "data_unavailable",
                "message": SECRET,
                "traceback": SECRET,
            }
        ),
    )
    assert (
        views[0].state == sc.LIVE_READY
    )  # los extras se ignoran, no rompen el resultado
    for view in views:
        blobs = [ui.render(view), ui.technical_details(view), view.alert_text or ""]
        blobs += [v for _, v in ui.full_hashes(view)]
        for blob in blobs:
            for leak in (
                SECRET,
                "NASA_FIRMS_API_KEY",
                "Authorization",
                "DMC_TOKEN",
                "DMC_USUARIO",
                "Cookie",
                "Traceback",
            ):
                assert leak not in blob, leak


def test_malicious_metadata_is_rejected_and_never_rendered():
    p = live_payload()
    p["model_version"] = "<img src=x onerror=alert(1)>"
    view = live_view(p)
    html = ui.render(view)
    assert (
        view.state == sc.INVALID_RESULT and "<img" not in html and "onerror" not in html
    )


# --- Solo lectura: sin rutas ni acciones de escritura ------------------------------------------


def _feature_sources() -> str:
    files = [PAGE, sc.__file__, ui.__file__, launcher.__file__]
    return "\n".join(Path(f).read_text(encoding="utf-8") for f in files).lower()


def test_no_write_route_introduced():
    source = _feature_sources()
    for forbidden in (
        ".post(",
        ".put(",
        ".delete(",
        ".patch(",
        "api.telegram",
        "sendmessage",
        "requesthandler",
        "add_route",
        "@app.post",
        "@app.put",
        "@app.delete",
        "firms_refresh import",
        "dmc_refresh",
        "current.json",
        "docker compose",
        "n8n_bridge.app",
        "attempt2",
        "os.environ[",
    ):
        assert forbidden not in source, forbidden
    assert "enviar" not in Path(PAGE).read_text(encoding="utf-8").lower()


def test_launcher_console_output_is_ascii():
    """La consola de Windows (cp1252) no puede codificar símbolos como la flecha."""
    import ast

    source = Path(launcher.__file__).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print":
            assert ast.get_source_segment(source, node).isascii()


def test_launcher_serves_page_at_root_and_starts_nothing_else():
    cmd = launcher.build_command(8599)
    assert cmd[:4] == [launcher.sys.executable, "-m", "streamlit", "run"]
    assert Path(cmd[4]) == Path(PAGE)  # la página es el script principal → ruta "/"
    assert "127.0.0.1" in cmd
    joined = " ".join(cmd).lower()
    for other in ("bridge", "n8n", "docker", "refresh", "uvicorn", "operator"):
        assert other not in joined, other
    assert launcher.page_query(True, True) == "?demo=1&presentation=1"
    assert launcher.page_query(False, False) == ""
    with pytest.raises(SystemExit):
        launcher.parse_args([])  # el modo siempre es explícito
    with pytest.raises(SystemExit):
        launcher.parse_args(["--demo", "--live"])


# --- Stub local del bridge (solo 127.0.0.1) ----------------------------------------------------


class _StubBridge(http.server.BaseHTTPRequestHandler):
    status, body = 200, b"{}"
    methods: list = []

    def do_GET(self):  # noqa: N802
        type(self).methods.append(("GET", self.path))
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass


@pytest.fixture
def stub_bridge():
    def start(status: int, payload) -> str:
        handler = type(
            "H",
            (_StubBridge,),
            {
                "status": status,
                "methods": [],
                "body": json.dumps(payload).encode("utf-8"),
            },
        )
        server = http.server.HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}/score", handler

    servers: list = []
    yield start
    for s in servers:
        s.shutdown()


def test_live_stub_bridge_valid_result(stub_bridge):
    url, handler = stub_bridge(200, live_payload())
    view = sc.fetch_live(url)
    assert view.state == sc.LIVE_READY and len(view.cells) == 50
    assert [c.rank for c in view.top] == [1, 2, 3, 4, 5]
    assert handler.methods == [("GET", "/score")]


def test_live_stub_bridge_unavailable(stub_bridge):
    url, _ = stub_bridge(503, {"status": "error", "error_type": "data_unavailable"})
    view = sc.fetch_live(url)
    assert view.state == sc.DATA_UNAVAILABLE and not view.cells


# --- Página Streamlit real (AppTest) ----------------------------------------------------------


def _markdown(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _app(**params):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(PAGE, default_timeout=30)
    for k, v in params.items():
        at.query_params[k] = v
    return at


def test_page_demo_works_without_backend(monkeypatch):
    def _no_network(*args, **kwargs):
        raise AssertionError("demo intentó usar la red")

    monkeypatch.setattr(requests, "get", _no_network)
    at = _app(demo="1")
    at.run()
    assert not at.exception
    html = _markdown(at)
    assert "DATOS DEMOSTRATIVOS" in html and "MODO: DEMO" in html
    assert html.count('<td class="num">') == 50 and html.count("<title>Celda VP-") == 50
    assert (
        html.count('<li data-rank="') == 10
    )  # Top 5 + Top 5 de la vista previa de alerta
    assert {b.label for b in at.button} == {"Actualizar vista"}  # única acción: releer
    assert any(e.label == "Detalles técnicos" for e in at.expander)


def test_page_presentation_mode():
    at = _app(demo="1", presentation="1")
    at.run()
    assert not at.exception
    html = _markdown(at)
    assert "is-presentation" in html and "DATOS DEMOSTRATIVOS" in html
    assert html.count("<title>Celda VP-") == 50 and '<td class="num">' not in html
    assert not at.expander and not at.radio  # sin detalles de desarrollo


def test_page_alert_text_is_preview_only(monkeypatch):
    posted = []
    monkeypatch.setattr(requests, "post", lambda *a, **k: posted.append(a))
    at = _app(demo="1")
    at.run()
    at.toggle(key="ops_alert_preview").set_value(True).run()
    assert not at.exception and not posted
    preview = [c.value for c in at.code if "Celda VP-028" in c.value]
    assert preview and preview[0].startswith("[DATOS DEMOSTRATIVOS")


def test_page_technical_details_show_alert_fingerprint():
    at = _app(demo="1")
    at.run()
    fp = sc.load_demo().alert.fingerprint
    assert any(c.value == fp for c in at.code)  # completo y copiable (st.code)
    assert f"{fp[:12]}…" in _markdown(at)


def test_page_search_filters_view_without_reranking():
    at = _app(demo="1")
    at.run()
    at.text_input(key="ops_q").set_value("VP-035").run()
    html = _markdown(at)
    assert '<td class="num">4</td><td class="cid">VP-035</td>' in html
    assert html.count('<td class="num">') == 1


def test_page_live_unavailable_never_falls_back_to_demo(monkeypatch):
    from src import config

    monkeypatch.setattr(config, "SAPI_SCORE_URL", "http://127.0.0.1:1/score")
    at = _app()
    at.run()
    assert not at.exception
    html = _markdown(at)
    assert "SERVICIO NO DISPONIBLE" in html and "MODO: EN VIVO" in html
    assert "VP-0" not in html and "DATOS DEMOSTRATIVOS" not in html


def test_page_live_valid_result_and_refresh_is_get_only(monkeypatch):
    from src import config

    calls = []

    def fake_get(url, **kwargs):
        calls.append(("GET", url))
        return FakeResponse(200, live_payload())

    def forbidden(*a, **k):
        raise AssertionError("escritura de red")

    monkeypatch.setattr(config, "SAPI_SCORE_URL", "http://bridge.test/score")
    monkeypatch.setattr(requests, "get", fake_get)
    for verb in ("post", "put", "patch", "delete"):
        monkeypatch.setattr(requests, verb, forbidden)
    at = _app()
    at.run()
    html = _markdown(at)
    assert "OPERATIVO" in html and 'data-connection="CONNECTED"' in html
    assert html.count("<title>Celda VP-") == 50
    next(b for b in at.button if b.label == "Actualizar vista").click().run()
    assert not at.exception
    assert calls == [("GET", "http://bridge.test/score")] * 2


def test_page_live_failure_after_demo_does_not_show_demo_values(monkeypatch):
    from src import config

    monkeypatch.setattr(config, "SAPI_SCORE_URL", "http://bridge.test/score")
    monkeypatch.setattr(
        requests,
        "get",
        lambda *a, **k: FakeResponse(
            503, {"status": "error", "error_type": "data_unavailable"}
        ),
    )
    at = _app(demo="1")
    at.run()
    assert "VP-028" in _markdown(at)
    at.radio(key="ops_mode").set_value("En vivo (servicio de score)").run()
    html = _markdown(at)
    assert "DATOS NO DISPONIBLES" in html and "VP-0" not in html
    assert "DATOS DEMOSTRATIVOS" not in html


# --- Recursos del navegador (servidor real + Chromium, si está disponible) --------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.parametrize("query", ["?demo=1", "?demo=1&presentation=1", ""])
def test_application_owned_resources_do_not_404(query):
    sync_api = pytest.importorskip("playwright.sync_api")
    import subprocess
    import time

    port = _free_port()
    env = {**__import__("os").environ, "SAPI_SCORE_URL": "http://127.0.0.1:1/score"}
    proc = subprocess.Popen(
        launcher.build_command(port),
        cwd=REPO,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if requests.get(base + "/_stcore/health", timeout=1).status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(0.5)
        else:
            pytest.skip("el servidor local no arrancó")
        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as exc:  # noqa: BLE001
                pytest.skip(f"Chromium no disponible: {exc}")
            page = browser.new_page()
            failed = []
            page.on(
                "response",
                lambda r: failed.append((r.status, r.url)) if r.status >= 400 else None,
            )
            page.goto(base + "/" + query)
            page.wait_for_selector(".ops-band", timeout=60000)
            page.wait_for_timeout(1500)
            browser.close()
        assert failed == []
    finally:
        proc.terminate()
        proc.wait(timeout=20)
