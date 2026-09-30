"""Payload de alerta canónico y vistas previas (texto y Telegram) de SAPI.

Transformación pura: un resultado de scoring válido (el JSON que expone el
bridge en `/score`, o un `GridScoreResult`) → `AlertPayload` versionado,
texto en español y vista previa lista para Telegram. **Nunca envía nada**:
no hay red, base de datos, n8n ni Telegram en este módulo.

Reglas de contenido:
- el score es una prioridad **relativa** (Model D), no una probabilidad
  calibrada; FIRMS reporta anomalías térmicas, no incendios confirmados;
- no se inventan umbrales de riesgo: solo se usa el ranking validado;
- el orden es el del ranking (`rank`); los empates se muestran con
  `display_rank` compartido, igual que la UI;
- la frescura FIRMS se **presenta** con los valores de SAPI; no se redefine;
- cualquier entrada inválida o no disponible produce INVALID / UNAVAILABLE,
  nunca una alerta tranquilizadora.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import date, datetime
from typing import Any, Mapping, Optional, get_args

import pandas as pd

from src.geo.grid import all_cells
from src.inference.prototype_service import (
    FIRMS_STATUS_CURRENT,
    FIRMS_STATUS_STALE,
    FRESHNESS_DELAYED,
    FRESHNESS_HISTORICAL,
    FRESHNESS_RECENT,
    PrototypeUnavailableError,
    classify_firms_lag,
)
from src.procesamiento.firms_source import FirmsOrigin

SCHEMA_VERSION = "sapi-alert-v1"
STATUS_READY, STATUS_UNAVAILABLE, STATUS_INVALID = "READY", "UNAVAILABLE", "INVALID"
# Solo presentación: el mismo corte "Top-5" documentado en
# src/inference/prototype_service.py (mapa / panel). No es un umbral de riesgo.
DEFAULT_TOP_N = 5
EXPECTED_CELL_IDS = tuple(c["cell_id"] for c in all_cells())
MAX_TOP_N = len(EXPECTED_CELL_IDS)
FIRMS_ORIGINS = frozenset(get_args(FirmsOrigin))
FIRMS_STATUSES = frozenset({FIRMS_STATUS_CURRENT, FIRMS_STATUS_STALE})
FRESHNESS_VALUES = frozenset(
    {FRESHNESS_RECENT, FRESHNESS_DELAYED, FRESHNESS_HISTORICAL}
)
UNAVAILABLE_ERROR_TYPES = frozenset({"prototype_unavailable", "data_unavailable"})
TELEGRAM_MAX_CHARS = 4096

_HEX64 = re.compile(r"[0-9a-f]{64}")
_ISO_TZ = re.compile(r"\d{4}-\d{2}-\d{2}T[0-9:.]+(Z|[+-]\d{2}:\d{2})")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_LABEL = re.compile(r"[A-Za-z0-9 ._/()-]{1,64}")
_GEOMETRY_KEYS = ("min_lon", "min_lat", "max_lon", "max_lat")

LIMITATIONS = (
    {
        "code": "RANKING_RELATIVO",
        "text": "Ranking exploratorio de prioridad relativa (Model D). El score relativo "
        "no es una probabilidad calibrada.",
    },
    {
        "code": "FIRMS_ANOMALIAS_TERMICAS",
        "text": "FIRMS reporta anomalías térmicas satelitales; "
        "no confirma la existencia de un incendio.",
    },
    {
        "code": "VALIDACION_HISTORICA",
        "text": "La validación disponible es histórica; no existe validación operacional "
        "point-in-time con datos FIRMS NRT.",
    },
)
NO_RESULT_NOTE = (
    "La falta de ranking no significa que la situación sea segura. "
    "Revisar el estado del servicio antes de actuar."
)

# Frases que la salida nunca debe contener (comparación sin tildes ni mayúsculas).
FORBIDDEN_PHRASES = (
    "probabilidad de incendio",
    "% de probabilidad",
    "incendio confirmado",
    "incendios confirmados",
    "incendio detectado",
    "incendios detectados",
    "prediccion confirmada",
    "certeza",
    "riesgo bajo",
    "sin incendios",
    "todo normal",
)

_REASON_TEXT = {
    "prototype_unavailable": "el modelo o sus insumos no están disponibles",
    "data_unavailable": "un insumo de datos no está disponible o es ilegible",
}


class ClaimSafetyError(AssertionError):
    """Una plantilla produjo lenguaje prohibido. Es un bug: no se degrada a otra salida."""


def _fold(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    ).lower()


def assert_claim_safe(text: str) -> str:
    folded = _fold(text)
    for phrase in FORBIDDEN_PHRASES:
        if _fold(phrase) in folded:
            raise ClaimSafetyError(f"lenguaje prohibido en la salida: {phrase!r}")
    return text


def _canonical(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _sha256(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj)).hexdigest()


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# --- Normalización de entrada (lista blanca) ---------------------------------------


def _from_grid_result(result) -> dict:
    """GridScoreResult → dict con los mismos campos que serializa el bridge."""

    def iso(v):
        return v.isoformat() if hasattr(v, "isoformat") else v

    return {
        "status": "ok",
        "model_version": getattr(result, "model_version", None),
        "model_status": getattr(result, "model_status", None),
        "forecast_time": iso(getattr(result, "forecast_time", None)),
        "freshness": getattr(result, "freshness", None),
        "firms_origin": getattr(result, "firms_origin", None),
        "firms_coverage_end": iso(getattr(result, "firms_coverage_end", None)),
        "firms_lag_days": getattr(result, "firms_lag_days", None),
        "firms_status": getattr(result, "firms_status", None),
        "inputs_fingerprint": getattr(result, "inputs_fingerprint", None),
        "cells": [
            {
                k: getattr(c, k, None)
                for k in (
                    "cell_id",
                    "score",
                    "rank",
                    "display_rank",
                    "tie_group_size",
                    "geometry",
                )
            }
            for c in (getattr(result, "cells", None) or [])
        ],
    }


def _as_mapping(source) -> Optional[dict]:
    if isinstance(source, Mapping):
        data = dict(source)
        # Envoltorio de evidencia (tools/ops/capture_score.py): {"score": {...}}
        if (
            "cells" not in data
            and "status" not in data
            and isinstance(data.get("score"), Mapping)
        ):
            data = dict(data["score"])
        return data
    if hasattr(source, "cells"):
        return _from_grid_result(source)
    return None


# --- Validación --------------------------------------------------------------------


def _validate(data: dict) -> tuple[list[str], dict]:
    """(motivos de rechazo, campos validados). Sin motivos ⇒ apto para READY."""
    reasons: list[str] = []
    ok: dict = {}

    t = data.get("forecast_time")
    if t is None:
        reasons.append("missing_scoring_time")
    elif not (isinstance(t, str) and _ISO_TZ.fullmatch(t)):
        reasons.append("invalid_scoring_time")
    else:
        try:
            datetime.fromisoformat(t.replace("Z", "+00:00"))
            ok["scoring_time"] = t
        except ValueError:
            reasons.append("invalid_scoring_time")

    fp = data.get("inputs_fingerprint")
    if fp in (None, ""):
        reasons.append("missing_inputs_fingerprint")
    elif not (isinstance(fp, str) and _HEX64.fullmatch(fp)):
        reasons.append("invalid_inputs_fingerprint")
    else:
        ok["inputs_fingerprint"] = fp

    model = {}
    for key, out in (("model_version", "version"), ("model_status", "status")):
        v = data.get(key)
        if v is None:
            continue
        if isinstance(v, str) and _LABEL.fullmatch(v):
            model[out] = v
        else:
            reasons.append("invalid_model_identity")
    ok["model"] = model or None

    fresh = data.get("freshness")
    if fresh is not None:
        if fresh in FRESHNESS_VALUES:
            ok["meteo_freshness"] = fresh
        else:
            reasons.append("invalid_meteo_freshness")

    origin, cov, lag, fstatus = (
        data.get(k)
        for k in (
            "firms_origin",
            "firms_coverage_end",
            "firms_lag_days",
            "firms_status",
        )
    )
    if origin not in FIRMS_ORIGINS:
        reasons.append("invalid_firms_origin")
    if not (isinstance(cov, str) and _ISO_DATE.fullmatch(cov)):
        reasons.append("invalid_firms_coverage_end")
        cov = None
    else:
        try:
            date.fromisoformat(cov)
        except ValueError:
            reasons.append("invalid_firms_coverage_end")
            cov = None
    if not _is_int(lag):
        reasons.append("invalid_firms_lag_days")
    if fstatus not in FIRMS_STATUSES:
        reasons.append("invalid_firms_status")
    if cov and "scoring_time" in ok and _is_int(lag) and fstatus in FIRMS_STATUSES:
        # Semántica existente de SAPI (classify_firms_lag); aquí no se redefine.
        scoring_ts = pd.Timestamp(ok["scoring_time"])
        assert isinstance(scoring_ts, pd.Timestamp)  # validado arriba: nunca NaT
        try:
            expected_lag, expected_status = classify_firms_lag(
                scoring_ts, date.fromisoformat(cov)
            )
        except PrototypeUnavailableError:
            reasons.append("firms_lag_exceeds_policy")
        else:
            if expected_lag != lag:
                reasons.append("firms_lag_inconsistent")
            if expected_status != fstatus:
                reasons.append("firms_status_inconsistent")
    ok["firms"] = {
        "origin": origin,
        "coverage_end": cov,
        "lag_days": lag,
        "status": fstatus,
    }

    cells = data.get("cells")
    if not isinstance(cells, list):
        reasons.append("missing_cells")
        return reasons, ok
    if len(cells) != len(EXPECTED_CELL_IDS):
        reasons.append("wrong_cell_count")
    parsed = []
    for c in cells:
        if not isinstance(c, Mapping):
            reasons.append("invalid_cell")
            continue
        score = c.get("score")
        if score is None:
            reasons.append("missing_score")
        elif not _is_number(score) or not math.isfinite(score):
            reasons.append("non_finite_score")
        elif not 0.0 <= score <= 1.0:
            reasons.append("score_out_of_range")
        for key in ("rank", "display_rank", "tie_group_size"):
            value = c.get(key)
            if not (
                isinstance(value, int) and not isinstance(value, bool) and value >= 1
            ):
                reasons.append(f"invalid_{key}")
        if c.get("cell_id") not in EXPECTED_CELL_IDS:
            reasons.append("cell_id_not_in_grid")
        parsed.append(c)
    if reasons:
        return sorted(set(reasons)), ok

    ids = [c["cell_id"] for c in parsed]
    ranks = [c["rank"] for c in parsed]
    if len(set(ids)) != len(ids):
        reasons.append("duplicate_cell_id")
    if len(set(ranks)) != len(ranks):
        reasons.append("duplicate_rank")
    if 1 not in ranks:
        reasons.append("missing_rank_1")
    if sorted(set(ranks)) != list(range(1, len(set(ranks)) + 1)) or max(ranks) != len(
        ranks
    ):
        reasons.append("rank_gap")
    if reasons:
        return sorted(set(reasons)), ok

    by_rank = sorted(parsed, key=lambda c: c["rank"])
    if any(a["score"] < b["score"] for a, b in zip(by_rank, by_rank[1:])):
        reasons.append("rank_order_violation")
    scores = [c["score"] for c in parsed]
    for c in parsed:
        if c["display_rank"] != 1 + sum(s > c["score"] for s in scores):
            reasons.append("display_rank_inconsistent")
        if c["tie_group_size"] != scores.count(c["score"]):
            reasons.append("tie_group_inconsistent")
    ok["cells"] = by_rank
    return sorted(set(reasons)), ok


# --- Construcción del payload ---------------------------------------------------------


def _geometry(c: Mapping) -> Optional[dict]:
    g = c.get("geometry")
    if isinstance(g, Mapping) and all(
        _is_number(g.get(k)) and math.isfinite(g[k]) for k in _GEOMETRY_KEYS
    ):
        return {k: g[k] for k in _GEOMETRY_KEYS}
    return None


def _non_ready(
    status: str,
    reasons: list[str],
    generated_at: Optional[str],
    upstream: Optional[str] = None,
) -> dict:
    identity = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "reasons": sorted(reasons),
    }
    alert = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "reasons": sorted(reasons),
        "upstream_error_type": upstream,
        "limitations": [dict(x) for x in LIMITATIONS],
        "note": NO_RESULT_NOTE,
        "alert_fingerprint": _sha256(identity),
    }
    if generated_at is not None:
        alert["generated_at"] = generated_at
    return alert


def build_alert(
    source, *, top_n: int = DEFAULT_TOP_N, generated_at: Optional[str] = None
) -> dict:
    """Resultado de scoring → AlertPayload (dict JSON-compatible).

    `top_n` es solo presentación (1..50) y respeta el orden del ranking.
    `generated_at` se informa aparte y NO entra en `alert_fingerprint`."""
    if not _is_int(top_n) or not 1 <= top_n <= MAX_TOP_N:
        raise ValueError(f"top_n debe estar entre 1 y {MAX_TOP_N}")
    data = _as_mapping(source)
    if data is None:
        return _non_ready(STATUS_INVALID, ["input_not_object"], generated_at)
    if data.get("status") == "error":
        error_type = data.get("error_type")
        if error_type in UNAVAILABLE_ERROR_TYPES:
            return _non_ready(
                STATUS_UNAVAILABLE, [error_type], generated_at, upstream=error_type
            )
        return _non_ready(
            STATUS_INVALID,
            ["invalid_result"],
            generated_at,
            upstream="internal_error" if error_type == "internal_error" else None,
        )
    if data.get("status") != "ok":
        return _non_ready(STATUS_INVALID, ["unexpected_status"], generated_at)

    reasons, ok = _validate(data)
    if reasons:
        return _non_ready(STATUS_INVALID, reasons, generated_at)

    ranked = ok["cells"]
    shown = ranked[:top_n]
    last = shown[-1]
    ties_beyond = sum(1 for c in ranked[top_n:] if c["score"] == last["score"])
    top_cells = []
    for c in shown:
        cell = {
            "rank": c["rank"],
            "display_rank": c["display_rank"],
            "tie_group_size": c["tie_group_size"],
            "cell_id": c["cell_id"],
            "score": c["score"],
        }
        geometry = _geometry(c)
        if geometry is not None:
            cell["geometry"] = geometry
        top_cells.append(cell)

    identity = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS_READY,
        "scoring_time": ok["scoring_time"],
        "inputs_fingerprint": ok["inputs_fingerprint"],
        "model": ok["model"],
        "firms": ok["firms"],
        "top_n": top_n,
        # score siempre como float: JSON no distingue 1 de 1.0 y ops/n8n/policy.js
        # reproduce esta misma receta (formato de float de Python) para verificarla.
        "cells": [
            [
                c["rank"],
                c["display_rank"],
                c["tie_group_size"],
                c["cell_id"],
                float(c["score"]),
            ]
            for c in shown
        ],
    }
    alert = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS_READY,
        "scoring_time": ok["scoring_time"],
        "inputs_fingerprint": ok["inputs_fingerprint"],
        "model": ok["model"],
        "firms": ok["firms"],
        "summary": {
            "ranking_basis": "rank",
            "cell_count": len(ranked),
            "top_n": top_n,
            "top_group_size": sum(1 for c in ranked if c["display_rank"] == 1),
            "ties_beyond_top_n": ties_beyond,
            "meteo_freshness": ok.get("meteo_freshness"),
        },
        "top_cells": top_cells,
        "limitations": [dict(x) for x in LIMITATIONS],
        "alert_fingerprint": _sha256(identity),
    }
    if generated_at is not None:
        alert["generated_at"] = generated_at
    assert_claim_safe(json.dumps(alert, ensure_ascii=False))
    return alert


def stable_json(alert: Mapping) -> str:
    """JSON canónico sin `generated_at`: idéntico para la misma entrada."""
    return _canonical({k: v for k, v in alert.items() if k != "generated_at"}).decode(
        "utf-8"
    )


# --- Vistas previas -----------------------------------------------------------------------


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def render_text(alert: Mapping) -> str:
    """Vista previa en español. Solo usa campos ya validados del payload."""
    if alert["status"] != STATUS_READY:
        if alert["status"] == STATUS_UNAVAILABLE:
            motive = _REASON_TEXT.get(
                alert.get("upstream_error_type") or "", "insumos no disponibles"
            )
            lines = ["SAPI — Ranking no disponible", f"Motivo: {motive}."]
        else:
            lines = [
                "SAPI — Resultado inválido: no se genera alerta",
                "Motivos: " + ", ".join(alert.get("reasons", [])) + ".",
            ]
        lines += ["", alert.get("note", NO_RESULT_NOTE)]
        return assert_claim_safe("\n".join(lines))

    firms, summary = alert["firms"], alert["summary"]
    lag = firms["lag_days"]
    lines = [
        "SAPI — Priorización territorial (evaluación exploratoria)",
        f"Evaluación: {alert['scoring_time']}",
    ]
    if alert.get("model"):
        model = alert["model"]
        lines.append(
            "Modelo: "
            + model.get("version", "-")
            + (f" ({model['status']})" if model.get("status") else "")
        )
    lines.append(
        f"Cobertura FIRMS (anomalías térmicas): hasta {firms['coverage_end']}, "
        f"desfase {lag} {_plural(abs(lag), 'día', 'días')}, {firms['status']}, "
        f"origen {firms['origin']}"
    )
    if summary.get("meteo_freshness"):
        lines.append(f"Datos meteorológicos: {summary['meteo_freshness']}")
    lines.append(f"Entradas: {alert['inputs_fingerprint'][:12]}")
    lines += [
        "",
        f"Celdas priorizadas ({summary['top_n']} de {summary['cell_count']}, "
        "en orden del ranking):",
    ]
    for c in alert["top_cells"]:
        line = f"{c['display_rank']}. Celda {c['cell_id']} | score relativo {c['score']:.3f}"
        if c["tie_group_size"] > 1:
            line += f" (empate: {c['tie_group_size']} celdas comparten este score)"
        lines.append(line)
    if summary["ties_beyond_top_n"]:
        n = summary["ties_beyond_top_n"]
        lines.append(
            f"+ {n} {_plural(n, 'celda más comparte', 'celdas más comparten')} "
            "el score de la última posición mostrada."
        )
    lines += ["", "Nota: " + " ".join(x["text"] for x in alert["limitations"])]
    return assert_claim_safe("\n".join(lines))


_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f​-‏‪-‮⁦-⁩]")


def render_telegram_preview(alert: Mapping) -> dict:
    """Vista previa para Telegram. **No envía.** Texto plano (sin parse_mode):
    ningún campo puede inyectar Markdown/HTML. '@' se neutraliza para no
    crear menciones y se eliminan caracteres de control/bidi. Largo acotado."""
    text = "VISTA PREVIA — NO ENVIADO\n" + render_text(alert)
    text = _CONTROL.sub("", text).replace("@", "(at)")
    if len(text) > TELEGRAM_MAX_CHARS:
        text = text[: TELEGRAM_MAX_CHARS - 20].rsplit("\n", 1)[0] + "\n(texto truncado)"
    return {
        "send": False,
        "parse_mode": None,
        "disable_web_page_preview": True,
        "status": alert["status"],
        "alert_fingerprint": alert["alert_fingerprint"],
        "length": len(text),
        "text": assert_claim_safe(text),
    }
