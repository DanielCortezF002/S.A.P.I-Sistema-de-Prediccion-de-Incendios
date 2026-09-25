"""Tests del Centro de Control de solo lectura (app/pages/dashboard.py).

Fixture sintética (app/data/demo_score_synthetic.json, SYNTHETIC / DEMO).
Sin backend real: el modo en vivo se prueba con sesiones HTTP simuladas.
"""

from __future__ import annotations

import copy
import json
import re
import socket
from pathlib import Path

import pytest
import requests

from app.components import ops_dashboard as ui
from app.utils import score_contract as sc

FIXTURE = json.loads(sc.DEMO_FIXTURE.read_text(encoding="utf-8"))
SECRET = "SYNTH-SECRET-7f3a9c-NOT-REAL"
PAGE = str(Path(__file__).resolve().parents[1] / "app" / "pages" / "dashboard.py")
FIRMS_BLOCKED_MSG = (
    "El histórico FIRMS termina el 2026-09-10, 14 días antes de forecast_time=2026-09-24 "
    "18:00:00+00:00 (máximo 7): faltarían detecciones recientes en las features. Refrescar FIRMS "
    "(python -m src.refresh.firms_refresh refresh)."
)


def live_payload() -> dict:
    """La fixture sin sus marcas sintéticas: forma de una respuesta real del bridge."""
    p = copy.deepcopy(FIXTURE)
    p.pop("_synthetic")
    p.pop("scoring_inputs")  # el bridge actual no lo serializa
    return p


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


def test_valid_result_renders_operational():
    view = sc.from_payload(live_payload())
    html = ui.render(view)
    assert view.state == sc.READY and view.has_ranking
    assert "OPERATIVO" in html and "DATOS DEMOSTRATIVOS" not in html
    for label in (
        "Evaluación",
        "Celdas evaluadas",
        "FIRMS",
        "Meteorología DMC",
        "Modelo",
    ):
        assert f"<dt>{label}</dt>" in html
    assert "50 de 50" in html


def test_firms_metadata_rendered():
    html = ui.render(sc.from_payload(live_payload()))
    card = re.search(
        r'<article class="ops-src" data-source="FIRMS".*?</article>', html, re.S
    )[0]
    assert 'data-status="CURRENT"' in card
    for value in ("current", "2026-09-23", "1 día", "FIRMS AL DÍA", "AL DÍA"):
        assert value in card


def test_stale_firms_is_warning_not_blocked():
    p = live_payload()
    p.update(firms_status="FIRMS DESACTUALIZADO", firms_lag_days=5)
    view = sc.from_payload(p)
    html = ui.render(view)
    assert view.state == sc.READY and view.firms_warning
    assert view.source_status()["FIRMS"] == sc.SRC_WARNING
    assert "ops-strip--warn" in html and "5 días de desfase" in visible_text(html)
    assert (
        'class="ops-top"' in html
    )  # se puntuó con aviso upstream: el ranking se muestra


def test_dmc_metadata_rendered_from_response():
    html = ui.render(sc.from_payload(live_payload()))
    card = re.search(r'data-source="DMC".*?</article>', html, re.S)[0]
    assert (
        "330007 · Rodelillo" in card and "DATOS RECIENTES" in card and "0.4 h" in card
    )


def test_missing_identity_says_not_in_response():
    view = sc.from_payload(live_payload())
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
    view = sc.from_payload(p)
    assert "model_sha256" not in view.identity and "<script>" not in ui.render(view)


def test_top5_exactly_ranks_1_to_5():
    view = sc.from_payload(live_payload())
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
    assert (
        "Empate: 3 celdas" in html
        and "posición 1" in html
        and "+ 1 celda más comparte" in html
    )


def test_equal_scores_do_not_alter_ranks():
    view = sc.from_payload(live_payload())
    tied = [c for c in view.cells if c.score == view.cells[0].score]
    assert [c.rank for c in tied] == [1, 2, 3] and {c.display_rank for c in tied} == {1}
    table = ui.ranking_table(view)
    ranks = [int(r) for r in re.findall(r'<td class="num">(\d+)</td>', table)]
    assert ranks == list(range(1, 51))  # rank canónico único, sin saltos por empate


def test_full_ranking_has_50_rows_in_backend_order():
    view = sc.from_payload(live_payload())
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
    assert [c.rank for c in sc.from_payload(shuffled).cells] == list(range(1, 51))


def test_search_and_view_order_never_change_rank():
    view = sc.from_payload(live_payload())
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
    view = sc.from_payload(live_payload())
    svg = ui.geo_map(view)
    tips = re.findall(
        r"<title>Celda (VP-\d{3}) · rank (\d+) · score relativo ([0-9.]+)</title>", svg
    )
    assert len(tips) == 50 and {t[0] for t in tips} == set(sc.EXPECTED_CELL_IDS)
    assert svg.count('class="cell cell--top"') == 5
    assert "-71.58°" in svg  # longitud real del borde oeste de src/geo/grid.py
    assert "probabilidad" not in visible_text(svg).lower().replace(
        "no es una probabilidad", ""
    )


def test_demo_is_clearly_labeled():
    view = sc.load_demo()
    html = ui.render(view)
    assert view.state == sc.DEMO and view.synthetic
    assert "DATOS DEMOSTRATIVOS" in html and "SYNTHETIC DEMO" in html
    assert "ops-band--demo" in html and ">OPERATIVO<" not in html


def test_synthetic_marker_never_passes_as_operational():
    view = sc.from_payload(FIXTURE)  # marca sintética aunque llegue por "live"
    assert view.state == sc.DEMO and "DATOS DEMOSTRATIVOS" in ui.render(view)


def test_presentation_mode_hides_developer_details():
    view = sc.load_demo()
    html = ui.render(view, presentation=True)
    assert "is-presentation" in html and 'class="ops-top"' in html and "<svg" in html
    assert 'class="ops-table"' not in html and 'class="ops-tech"' not in html
    assert (
        "FIRMS AL DÍA" in html
        and "no corresponde a una probabilidad calibrada" in html.lower()
    )


# --- Estados sin ranking ------------------------------------------------------------------


@pytest.mark.parametrize(
    "error_type,state,title",
    [
        ("data_unavailable", sc.DATA_UNAVAILABLE, "DATOS NO DISPONIBLES"),
        ("prototype_unavailable", sc.PROTOTYPE_UNAVAILABLE, "EVALUACIÓN NO DISPONIBLE"),
        ("internal_error", sc.PROTOTYPE_UNAVAILABLE, "EVALUACIÓN NO DISPONIBLE"),
    ],
)
def test_unavailable_states_show_no_ranking(error_type, state, title):
    upstream = {
        "status": "error",
        "error_type": error_type,
        "message": "No existe el modelo en C:/interno/models/prototype_model_d.pkl",
    }
    view = sc.from_payload(upstream)
    html = ui.render(view)
    assert view.state == state and title in html
    assert (
        'class="ops-top"' not in html
        and 'class="ops-table"' not in html
        and "VP-0" not in html
    )
    assert "C:/interno" not in html  # el mensaje upstream no se muestra
    assert "no indica que la situación sea segura" in html
    assert set(view.source_status().values()) == {sc.SRC_UNKNOWN}


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
        (FakeResponse(200, None), sc.READY, None),
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
        (FakeResponse(200, ValueError("no json")), sc.INVALID, "response_not_json"),
        (
            FakeResponse(200, ValueError("empty"), content=b""),
            sc.INVALID,
            "empty_response",
        ),
        (FakeResponse(200, {}), sc.INVALID, "empty_response"),
        (FakeResponse(200, [1, 2]), sc.INVALID, "response_not_object"),
        (FakeResponse(404, {"detail": "Not Found"}), sc.INVALID, "http_404"),
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
    assert view.state == state
    assert reason is None or reason in view.reasons
    assert session.calls == [("GET", "http://bridge/score")]


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda p: p.pop("cells"), "missing_cells"),
        (lambda p: p["cells"].pop(), "wrong_cell_count"),
        (lambda p: p["cells"][1].update(rank=1), "duplicate_rank"),
        (
            lambda p: p["cells"][1].update(cell_id=p["cells"][0]["cell_id"]),
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
    ],
)
def test_invalid_response_fails_closed(mutate, reason):
    p = live_payload()
    mutate(p)
    view = sc.from_payload(p)
    html = ui.render(view)
    assert view.state == sc.INVALID and not view.cells and reason in view.reasons
    assert "RESULTADO INVÁLIDO" in html
    assert (
        'class="ops-top"' not in html
        and 'class="ops-table"' not in html
        and "<svg" not in html
    )


def test_loading_state_has_no_values():
    html = ui.loading()
    assert (
        'aria-busy="true"' in html
        and "VP-" not in html
        and "score relativo" not in html
    )


# --- Vista previa de alerta -----------------------------------------------------------------


def test_alert_preview_uses_pure_payload_module():
    from src.notifications.alert_payload import build_alert, render_text

    p = live_payload()
    assert sc.from_payload(p).alert_text == render_text(build_alert(p))
    unavailable = sc.from_payload({"status": "error", "error_type": "data_unavailable"})
    assert unavailable.alert_text and "segura" in unavailable.alert_text
    assert sc.from_payload({"status": "ok"}).alert_text is None  # INVALID: sin alerta


def test_alert_preview_does_not_touch_network(monkeypatch):
    def _no_network(*args, **kwargs):
        raise AssertionError("la vista previa intentó abrir una conexión")

    monkeypatch.setattr(socket.socket, "connect", _no_network)
    monkeypatch.setattr(requests, "post", _no_network)
    monkeypatch.setattr(requests, "get", _no_network)
    view = sc.load_demo()
    assert view.alert_text and "VP-028" in view.alert_text


# --- Lenguaje y seguridad ---------------------------------------------------------------------


def _all_renders() -> list[str]:
    stale = live_payload()
    stale.update(firms_status="FIRMS DESACTUALIZADO", firms_lag_days=5)
    views = [
        sc.from_payload(live_payload()),
        sc.load_demo(),
        sc.from_payload(stale),
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


def test_confirmed_fire_and_safety_terminology_absent():
    for html in _all_renders():
        text = visible_text(html).lower()
        for bad in (
            "incendio confirmado",
            "incendios confirmados",
            "fuego confirmado",
            "zona segura",
            "safe",
            "no fire",
            "low risk",
            "enviar",
        ):
            assert bad not in text, bad


def test_score_is_never_called_probability():
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
    html = ui.render(sc.from_payload(live_payload()))
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


def test_secret_like_fields_never_rendered():
    p = live_payload()
    p.update(
        Authorization=f"Bearer {SECRET}",
        NASA_FIRMS_API_KEY=SECRET,
        DMC_TOKEN=SECRET,
        DMC_USUARIO=SECRET,
        headers={"Authorization": SECRET},
        env={"NASA_FIRMS_API_KEY": SECRET},
        traceback=f"Traceback ... {SECRET}",
    )
    p["cells"][0]["debug"] = SECRET
    p["scoring_inputs"] = {"dmc": {"token": SECRET, "manifest_sha256": SECRET}}
    views = (
        sc.from_payload(p),
        sc.from_payload(
            {
                "status": "error",
                "error_type": "data_unavailable",
                "message": SECRET,
                "traceback": SECRET,
            }
        ),
    )
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
                "Traceback",
            ):
                assert leak not in blob, leak


def test_malicious_metadata_is_rejected_and_never_rendered():
    p = live_payload()
    p["model_version"] = "<img src=x onerror=alert(1)>"
    view = sc.from_payload(p)
    html = ui.render(view)
    assert view.state == sc.INVALID and "<img" not in html and "onerror" not in html


def test_page_has_no_write_controls():
    source = (
        Path(PAGE).read_text(encoding="utf-8")
        + Path(sc.__file__).read_text(encoding="utf-8")
        + Path(ui.__file__).read_text(encoding="utf-8")
    ).lower()
    for forbidden in (
        ".post(",
        ".put(",
        ".delete(",
        ".patch(",
        "api.telegram",
        "sendmessage",
        "firms_refresh import",
        "dmc_refresh",
        "current.json",
        "subprocess",
        "os.environ[",
    ):
        assert forbidden not in source, forbidden
    assert "enviar" not in Path(PAGE).read_text(encoding="utf-8").lower()


# --- Página Streamlit real (AppTest) ----------------------------------------------------------


def _markdown(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _app(monkeypatch=None, **params):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(PAGE, default_timeout=30)
    for k, v in params.items():
        at.query_params[k] = v
    return at


def test_page_demo_mode_renders_without_backend(monkeypatch):
    def _no_network(*args, **kwargs):
        raise AssertionError("demo intentó usar la red")

    monkeypatch.setattr(requests, "get", _no_network)
    at = _app(demo="1")
    at.run()
    assert not at.exception
    html = _markdown(at)
    assert "DATOS DEMOSTRATIVOS" in html
    assert html.count('<td class="num">') == 50 and html.count("<title>Celda VP-") == 50
    assert html.count('<li data-rank="') == 5
    assert any(b.label == "Actualizar vista" for b in at.button)
    assert all("enviar" not in b.label.lower() for b in at.button)
    assert any(e.label == "Detalles técnicos" for e in at.expander)


def test_page_presentation_mode(monkeypatch):
    at = _app(demo="1", presentation="1")
    at.run()
    assert not at.exception
    html = _markdown(at)
    assert "is-presentation" in html and "DATOS DEMOSTRATIVOS" in html
    assert html.count('<li data-rank="') == 5 and '<td class="num">' not in html
    assert not at.expander and not at.radio  # sin detalles de desarrollo


def test_page_alert_preview_is_text_only(monkeypatch):
    posted = []
    monkeypatch.setattr(requests, "post", lambda *a, **k: posted.append(a))
    at = _app(demo="1")
    at.run()
    at.toggle(key="ops_alert_preview").set_value(True).run()
    assert not at.exception and not posted
    preview = [c.value for c in at.code if "Celda VP-028" in c.value]
    assert preview and preview[0].startswith("[DATOS DEMOSTRATIVOS")


def test_page_search_filters_view_without_reranking():
    at = _app(demo="1")
    at.run()
    at.text_input(key="ops_q").set_value("VP-035").run()
    html = _markdown(at)
    assert '<td class="num">4</td><td class="cid">VP-035</td>' in html
    assert html.count('<td class="num">') == 1


def test_page_live_mode_network_error(monkeypatch):
    monkeypatch.setenv("SAPI_SCORE_URL", "http://127.0.0.1:1/score")
    at = _app()
    at.run()
    assert not at.exception
    html = _markdown(at)
    assert "SERVICIO NO DISPONIBLE" in html and "VP-0" not in html
    assert "DATOS DEMOSTRATIVOS" not in html  # nunca cae a la fixture


def test_page_live_refresh_is_get_only(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(("GET", url))
        return FakeResponse(200, live_payload())

    def forbidden(*a, **k):
        raise AssertionError("escritura de red")

    monkeypatch.setenv("SAPI_SCORE_URL", "http://bridge.test/score")
    monkeypatch.setattr(requests, "get", fake_get)
    for verb in ("post", "put", "patch", "delete"):
        monkeypatch.setattr(requests, verb, forbidden)
    at = _app()
    at.run()
    assert "OPERATIVO" in _markdown(at)
    next(b for b in at.button if b.label == "Actualizar vista").click().run()
    assert not at.exception
    assert calls == [("GET", "http://bridge.test/score")] * 2


def test_page_live_failure_after_demo_does_not_show_demo_values(monkeypatch):
    monkeypatch.setenv("SAPI_SCORE_URL", "http://bridge.test/score")
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
    assert (
        "DATOS NO DISPONIBLES" in html
        and "VP-0" not in html
        and "DATOS DEMOSTRATIVOS" not in html
    )
