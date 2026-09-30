"""Tests del payload de alerta y sus vistas previas (src/notifications/*).

Fixture sintética (tests/fixtures/alert_demo, SYNTHETIC DEMO ONLY). Ningún
test envía nada: el módulo no tiene red.
"""

from __future__ import annotations

import copy
import json
import math
import socket
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

import src.notifications.alert_payload as ap
from src.notifications import alert_preview
from src.notifications.alert_payload import (
    build_alert,
    render_telegram_preview,
    render_text,
    stable_json,
)

DEMO = Path(__file__).parent / "fixtures" / "alert_demo"
GENERATED = "2026-09-25T00:00:00+00:00"
SECRET = "Bearer sk-SYNTHETIC-9f8e7d6c5b4a-NOT-REAL"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def deny(*a, **k):
        raise AssertionError("red prohibida en el renderer de alertas")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)


@pytest.fixture
def payload() -> dict:
    return json.loads((DEMO / "synthetic_score.json").read_text(encoding="utf-8"))


def reasons(alert: dict) -> set[str]:
    return set(alert.get("reasons", []))


def all_text(alert: dict) -> str:
    return "\n".join(
        [
            json.dumps(alert, ensure_ascii=False),
            render_text(alert),
            render_telegram_preview(alert)["text"],
        ]
    )


# 1. Resultado válido de 50 celdas ------------------------------------------------------


def test_valid_50_cell_result_is_ready(payload):
    alert = build_alert(payload, generated_at=GENERATED)
    assert alert["status"] == "READY" and alert["schema_version"] == ap.SCHEMA_VERSION
    assert (
        alert["summary"]["cell_count"] == 50
        and alert["summary"]["top_n"] == ap.DEFAULT_TOP_N == 5
    )
    assert [c["cell_id"] for c in alert["top_cells"]] == [
        "VP-012",
        "VP-027",
        "VP-031",
        "VP-004",
        "VP-008",
    ]
    assert (
        alert["summary"]["top_group_size"] == 3
        and alert["summary"]["ties_beyond_top_n"] == 1
    )
    assert alert["firms"] == {
        "origin": "current",
        "coverage_end": "2026-09-19",
        "lag_days": 1,
        "status": "FIRMS AL DÍA",
    }


def test_grid_score_result_object_is_accepted(payload):
    from src.inference.prototype_service import CellScore, GridScoreResult
    import pandas as pd

    cells = [
        CellScore(
            **{
                k: c[k]
                for k in (
                    "cell_id",
                    "score",
                    "rank",
                    "display_rank",
                    "tie_group_size",
                    "geometry",
                    "elevation",
                    "slope",
                    "historical_count",
                )
            }
        )
        for c in payload["cells"]
    ]
    result = GridScoreResult(
        forecast_time=pd.Timestamp(payload["forecast_time"]),
        horizon_hours=6,
        station_id="330007",
        station_name="Rodelillo",
        weather_timestamp=pd.Timestamp(payload["weather_timestamp"]),
        age_hours=0.5,
        freshness="DATOS RECIENTES",
        model_version="prototype_model_d_v1",
        model_status="PROTOTYPE / EXPLORATORY",
        meteo_actual={},
        cells=cells,
        firms_origin="current",
        firms_coverage_end=date(2026, 9, 19),
        firms_lag_days=1,
        firms_status="FIRMS AL DÍA",
        inputs_fingerprint=payload["inputs_fingerprint"],
    )
    obj, dct = build_alert(result), build_alert(payload)
    assert (
        obj["status"] == "READY"
        and obj["alert_fingerprint"] == dct["alert_fingerprint"]
    )


# 2-6, 24. Fingerprint ------------------------------------------------------------------


def test_fingerprint_deterministic_and_generated_at_excluded(payload):
    a = build_alert(payload, generated_at="2026-01-01T00:00:00+00:00")
    b = build_alert(copy.deepcopy(payload), generated_at="2030-12-31T23:59:59+00:00")
    assert (
        a["alert_fingerprint"] == b["alert_fingerprint"]
        and len(a["alert_fingerprint"]) == 64
    )
    assert stable_json(a) == stable_json(b)
    assert a["generated_at"] != b["generated_at"]


def test_unrelated_field_order_does_not_change_identity(payload):
    shuffled = dict(reversed(list(payload.items())))
    assert (
        build_alert(shuffled)["alert_fingerprint"]
        == build_alert(payload)["alert_fingerprint"]
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["cells"][3].update(
            score=0.120
        ),  # VP-004, sin empate: sigue en orden
        lambda p: p.update(inputs_fingerprint="b" * 64),
        lambda p: p.update(firms_coverage_end="2026-09-18", firms_lag_days=2),
        lambda p: p.update(model_version="prototype_model_d_v2"),
    ],
    ids=["score", "inputs_fingerprint", "firms_coverage", "model"],
)
def test_bound_fields_change_fingerprint(payload, mutate):
    base = build_alert(payload)["alert_fingerprint"]
    changed = copy.deepcopy(payload)
    mutate(changed)
    alert = build_alert(changed)
    assert alert["status"] == "READY", alert.get("reasons")
    assert alert["alert_fingerprint"] != base


def test_top_n_is_part_of_identity(payload):
    assert (
        build_alert(payload, top_n=3)["alert_fingerprint"]
        != build_alert(payload, top_n=5)["alert_fingerprint"]
    )


# 7, 25. Top-N --------------------------------------------------------------------------


def test_top_n_preserves_rank_order_even_if_input_is_shuffled(payload):
    shuffled = copy.deepcopy(payload)
    shuffled["cells"].reverse()
    alert = build_alert(shuffled, top_n=10)
    assert [c["rank"] for c in alert["top_cells"]] == list(range(1, 11))
    assert (
        alert["alert_fingerprint"]
        == build_alert(payload, top_n=10)["alert_fingerprint"]
    )


@pytest.mark.parametrize("n", [0, -1, 51, 2.5, True])
def test_top_n_bounds(payload, n):
    with pytest.raises(ValueError):
        build_alert(payload, top_n=n)


@pytest.mark.parametrize("n", [1, 50])
def test_top_n_limits_accepted(payload, n):
    assert len(build_alert(payload, top_n=n)["top_cells"]) == n


# 8-15. Fail-closed ---------------------------------------------------------------------


def _mut(payload, fn):
    p = copy.deepcopy(payload)
    fn(p)
    return build_alert(p)


@pytest.mark.parametrize(
    "fn,reason",
    [
        (lambda p: p["cells"].pop(), "wrong_cell_count"),
        (lambda p: p["cells"][1].update(cell_id="VP-012"), "duplicate_cell_id"),
        (lambda p: p["cells"][1].update(rank=1), "duplicate_rank"),
        (lambda p: p["cells"][-1].update(rank=60), "rank_gap"),
        (
            lambda p: [c.update(rank=c["rank"] + 1) for c in p["cells"]],
            "missing_rank_1",
        ),
        (lambda p: p["cells"][3].update(score=float("nan")), "non_finite_score"),
        (lambda p: p["cells"][3].update(score=float("inf")), "non_finite_score"),
        (lambda p: p["cells"][3].update(score=float("-inf")), "non_finite_score"),
        (lambda p: p["cells"][3].pop("score"), "missing_score"),
        (lambda p: p.pop("inputs_fingerprint"), "missing_inputs_fingerprint"),
        (lambda p: p.update(inputs_fingerprint="xyz"), "invalid_inputs_fingerprint"),
        (lambda p: p.pop("forecast_time"), "missing_scoring_time"),
        (
            lambda p: p.update(forecast_time="2026-09-20T12:00:00"),
            "invalid_scoring_time",
        ),
        (lambda p: p.update(firms_status="OK"), "invalid_firms_status"),
        (lambda p: p.update(firms_origin=None), "invalid_firms_origin"),
        (lambda p: p.update(firms_lag_days="1"), "invalid_firms_lag_days"),
        (lambda p: p.update(firms_lag_days=3), "firms_lag_inconsistent"),
        (
            lambda p: p.update(firms_status="FIRMS DESACTUALIZADO"),
            "firms_status_inconsistent",
        ),
        (
            lambda p: p.update(firms_coverage_end="2026-08-01", firms_lag_days=50),
            "firms_lag_exceeds_policy",
        ),
        (lambda p: p["cells"][0].update(score=0.01), "rank_order_violation"),
        (lambda p: p["cells"][4].update(display_rank=1), "display_rank_inconsistent"),
        (lambda p: p["cells"][4].update(cell_id="C99"), "cell_id_not_in_grid"),
        (lambda p: p["cells"][2].update(score=1.5), "score_out_of_range"),
        (lambda p: p.update(status="weird"), "unexpected_status"),
        (lambda p: p.update(cells=None), "missing_cells"),
    ],
)
def test_invalid_input_fails_closed(payload, fn, reason):
    alert = _mut(payload, fn)
    assert alert["status"] == "INVALID" and reason in reasons(alert), alert.get(
        "reasons"
    )
    assert "top_cells" not in alert and "summary" not in alert
    text = render_text(alert)
    assert text.startswith("SAPI — Resultado inválido") and "Celda" not in text


def test_nan_from_json_text_is_rejected(payload):
    raw = json.dumps(payload).replace('"score": 0.121', '"score": NaN')
    assert build_alert(json.loads(raw))["status"] == "INVALID"


@pytest.mark.parametrize("source", [None, "texto", 42, []])
def test_non_object_input_is_invalid(source):
    assert build_alert(source)["status"] == "INVALID"


# 16-17. No disponible ------------------------------------------------------------------


@pytest.mark.parametrize("error_type", ["data_unavailable", "prototype_unavailable"])
def test_unavailable_does_not_generate_normal_alert(error_type):
    upstream = {
        "status": "error",
        "error_type": error_type,
        "message": "C:/ruta/interna/dmc.json corrupta",
    }
    alert = build_alert(upstream)
    assert (
        alert["status"] == "UNAVAILABLE" and alert["upstream_error_type"] == error_type
    )
    assert "top_cells" not in alert
    text = all_text(alert)
    assert (
        "C:/ruta" not in text and "interna" not in text
    )  # el mensaje upstream no se copia
    assert "no significa que la situación sea segura" in render_text(alert)


def test_internal_error_is_invalid_not_unavailable():
    alert = build_alert(
        {"status": "error", "error_type": "internal_error", "message": "x"}
    )
    assert alert["status"] == "INVALID" and reasons(alert) == {"invalid_result"}


def test_non_ready_fingerprints_are_stable_and_distinct():
    a = build_alert(
        {"status": "error", "error_type": "data_unavailable"}, generated_at="1"
    )
    b = build_alert(
        {"status": "error", "error_type": "data_unavailable"}, generated_at="2"
    )
    c = build_alert({"status": "error", "error_type": "prototype_unavailable"})
    assert a["alert_fingerprint"] == b["alert_fingerprint"] != c["alert_fingerprint"]


# 18-20. Lenguaje -----------------------------------------------------------------------


def _outputs(payload):
    ready = build_alert(payload)
    return [
        ready,
        build_alert({"status": "error", "error_type": "data_unavailable"}),
        _mut(payload, lambda p: p["cells"].pop()),
    ]


@pytest.mark.parametrize(
    "phrase",
    [
        "probabilidad de incendio",
        "% de probabilidad",
        "incendio confirmado",
        "incendio detectado",
        "predicción confirmada",
        "certeza",
        "riesgo bajo",
        "sin incendios",
        "todo normal",
    ],
)
def test_no_forbidden_claims_in_any_output(payload, phrase):
    for alert in _outputs(payload):
        assert ap._fold(phrase) not in ap._fold(all_text(alert))


def test_score_is_never_rendered_as_percentage(payload):
    text = render_text(build_alert(payload))
    assert "%" not in text and "score relativo 0.140" in text


def test_claim_guard_rejects_forbidden_language():
    with pytest.raises(ap.ClaimSafetyError):
        ap.assert_claim_safe("Hay 82% de probabilidad de incendio")
    with pytest.raises(ap.ClaimSafetyError):
        ap.assert_claim_safe("INCENDIO CONFIRMADO en la zona")


def test_spanish_utf8_is_preserved(payload):
    text = render_text(build_alert(payload))
    for word in (
        "Priorización",
        "evaluación",
        "anomalías térmicas",
        "día",
        "FIRMS AL DÍA",
    ):
        assert word in text
    text.encode("utf-8")


# 21-23. Telegram y seguridad -----------------------------------------------------------


def test_telegram_preview_is_plain_bounded_and_never_sent(payload):
    preview = render_telegram_preview(build_alert(payload))
    assert preview["send"] is False and preview["parse_mode"] is None
    assert preview["disable_web_page_preview"] is True
    assert preview["text"].startswith("VISTA PREVIA — NO ENVIADO")
    assert preview["length"] == len(preview["text"]) <= ap.TELEGRAM_MAX_CHARS
    full = render_telegram_preview(build_alert(payload, top_n=50))
    assert full["length"] <= ap.TELEGRAM_MAX_CHARS


def test_telegram_truncates_and_neutralizes_mentions(monkeypatch, payload):
    alert = build_alert(payload, top_n=50)
    monkeypatch.setattr(ap, "TELEGRAM_MAX_CHARS", 400)
    monkeypatch.setattr(
        ap, "render_text", lambda a: "linea @usuario\u202e\u200b\n" * 100
    )
    preview = ap.render_telegram_preview(alert)
    assert preview["length"] <= 400 and preview["text"].endswith("(texto truncado)")
    assert (
        "@" not in preview["text"]
        and "\u202e" not in preview["text"]
        and "\u200b" not in preview["text"]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_version", "<b>x</b> @everyone"),
        ("model_version", "*bold* [link](http://evil)"),
        ("model_status", "`code` \u202eRLO"),
        ("freshness", "<script>"),
        ("firms_status", "<i>FIRMS AL DÍA</i>"),
        ("firms_origin", "current\n@all"),
    ],
)
def test_malicious_metadata_cannot_inject(payload, field, value):
    p = copy.deepcopy(payload)
    p[field] = value
    alert = build_alert(p)
    assert alert["status"] == "INVALID"
    rendered = all_text(alert)
    assert (
        value not in rendered and "<b>" not in rendered and "@everyone" not in rendered
    )


def test_malicious_cell_label_cannot_inject(payload):
    p = copy.deepcopy(payload)
    p["cells"][0]["cell_id"] = "<a href='x'>VP-012</a>"
    alert = build_alert(p)
    assert alert["status"] == "INVALID" and "<a href" not in all_text(alert)


def test_unrelated_secret_like_fields_never_appear(payload):
    p = copy.deepcopy(payload)
    p.update(
        Authorization=SECRET,
        headers={"Authorization": SECRET},
        token=SECRET,
        debug={"api_key": SECRET},
        scoring_inputs={"private_path": "C:/private/secret.csv"},
    )
    p["cells"][0]["internal_token"] = SECRET
    p["cells"][0]["geometry"] = {**p["cells"][0]["geometry"], "note": SECRET}
    for alert in (build_alert(p), build_alert({"score": p})):
        text = all_text(alert)
        assert (
            "SYNTHETIC-9f8e" not in text
            and "private" not in text
            and "Authorization" not in text
        )
    assert set(build_alert(p)) <= {
        "schema_version",
        "status",
        "scoring_time",
        "inputs_fingerprint",
        "model",
        "firms",
        "summary",
        "top_cells",
        "limitations",
        "alert_fingerprint",
        "generated_at",
    }


def test_capture_score_wrapper_is_unwrapped(payload):
    wrapped = {"mode": "operational", "manifest": {"x": 1}, "score": payload}
    assert (
        build_alert(wrapped)["alert_fingerprint"]
        == build_alert(payload)["alert_fingerprint"]
    )


def test_optional_geometry_is_passed_only_when_valid(payload):
    p = copy.deepcopy(payload)
    p["cells"][0]["geometry"] = {"min_lon": "x"}
    alert = build_alert(p)
    assert (
        "geometry" not in alert["top_cells"][0] and "geometry" in alert["top_cells"][1]
    )
    assert all(math.isfinite(v) for v in alert["top_cells"][1]["geometry"].values())


# 20. Demo sintética (goldens) y CLI ----------------------------------------------------


def _cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.notifications.alert_preview", *args],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        timeout=120,
        env={
            **__import__("os").environ,
            "PYTHONIOENCODING": "cp1252",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )


@pytest.mark.parametrize(
    "fmt,golden",
    [
        ("json", "expected_alert.json"),
        ("text", "expected_text.txt"),
        ("telegram-preview", "expected_telegram.json"),
    ],
)
def test_synthetic_demo_matches_goldens(fmt, golden):
    done = _cli(
        "--input",
        str(DEMO / "synthetic_score.json"),
        "--format",
        fmt,
        "--generated-at",
        GENERATED,
    )
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    expected = (DEMO / golden).read_bytes().replace(b"\r\n", b"\n")
    assert done.stdout.replace(b"\r\n", b"\n") == expected


def test_cli_exit_codes(tmp_path, payload):
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({**payload, "cells": payload["cells"][:49]}), encoding="utf-8"
    )
    unavailable = tmp_path / "unavail.json"
    unavailable.write_text(
        json.dumps({"status": "error", "error_type": "data_unavailable"}),
        encoding="utf-8",
    )
    broken = tmp_path / "broken.json"
    broken.write_text("{ no es json", encoding="utf-8")
    assert alert_preview.main(["--input", str(DEMO / "synthetic_score.json")]) == 0
    assert alert_preview.main(["--input", str(bad)]) == 1
    assert alert_preview.main(["--input", str(unavailable)]) == 3
    assert alert_preview.main(["--input", str(broken)]) == 1
    assert alert_preview.main(["--input", str(tmp_path / "missing.json")]) == 1
    with pytest.raises(SystemExit) as exc:
        alert_preview.main(["--input", str(bad), "--top", "0"])
    assert exc.value.code == 2


def test_module_has_no_network_or_send_capability():
    source = Path(ap.__file__).read_text(encoding="utf-8") + Path(
        alert_preview.__file__
    ).read_text(encoding="utf-8")
    for forbidden in (
        "requests",
        "urllib",
        "http.client",
        "socket",
        "api.telegram.org",
        "sendMessage",
        "httpx",
    ):
        assert forbidden not in source
