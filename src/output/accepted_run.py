"""Artefacto de corrida aceptada (sapi-accepted-run-v1): captura, verificación y evidencia.

Envuelve UNA salida canónica ya aceptada de `GET /score` (sapi-output-v1). No es
un modelo ni un segundo resultado: copia, por lista blanca, lo que el bridge
entregó y lo vuelve evidencia inmutable y reproducible sin servicios.

    python -m src.output.accepted_run capture --url http://127.0.0.1:8600/score [--out DIR]
    python -m src.output.accepted_run verify <accepted-run.json>
    python -m src.output.accepted_run evidence <accepted-run.json> [--out DIR]

Tres identidades distintas (ver docs/ops/ACCEPTED-RUN-ARTIFACT.md):
- `inputs_fingerprint`: QUÉ entradas se puntuaron (hash de ScoringInputs.manifest()).
- `notification_identity` (= alert_fingerprint): QUÉ alerta se derivaría (hora,
  entradas, modelo, FIRMS y Top 5).
- `artifact_fingerprint`: ESTE resultado aceptado completo (las 50 celdas, las
  identidades de entrada, la versión de contrato y el origen de datos).

Solo GET. Nunca escribe en data/raw, data/processed, models ni directorios con
CURRENT/versions. No envía nada.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from app.utils import score_contract as sc
from src.notifications.alert_payload import LIMITATIONS
from src.output.contract import OUTPUT_SCHEMA_VERSION

ARTIFACT_SCHEMA_VERSION = "sapi-accepted-run-v1"
DATA_OPERATIONAL, DATA_SYNTHETIC = "OPERATIONAL", "SYNTHETIC"
DATA_ORIGINS = (DATA_OPERATIONAL, DATA_SYNTHETIC)
SOURCE_LIVE_CAPTURE = "LIVE_CAPTURE"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE_DIR = REPO_ROOT.parent / "SAPI-71-evidence" / "accepted-runs"
FORBIDDEN_ROOTS = tuple(
    (REPO_ROOT / p).resolve() for p in ("data/raw", "data/processed", "models")
)

EXIT_OK, EXIT_USAGE, EXIT_NOT_ACCEPTED, EXIT_NETWORK = 0, 2, 3, 4

_OUTPUT_FIELDS = (
    "output_schema_version",
    "status",
    "forecast_time",
    "horizon_hours",
    "station_id",
    "station_name",
    "weather_timestamp",
    "age_hours",
    "freshness",
    "model_version",
    "model_status",
    "firms_origin",
    "firms_coverage_end",
    "firms_lag_days",
    "firms_status",
    "inputs_fingerprint",
)
_METEO_FIELDS = (
    "temperatura",
    "humedad_relativa",
    "velocidad_viento_kmh",
    "regla_30_30_30",
    "momento_observacion",
)
_CELL_FIELDS = ("cell_id", "score", "rank", "display_rank", "tie_group_size")
_GEOMETRY_KEYS = ("min_lon", "min_lat", "max_lon", "max_lat")
_CAPTURE_FIELDS = (
    "captured_at",
    "source_mode",
    "http_status",
    "content_type",
    "source_url",
)
_HEX64 = re.compile(r"[0-9a-f]{64}")
_SAFE_URL = re.compile(r"https?://[A-Za-z0-9.\-]+(:\d{1,5})?(/[A-Za-z0-9._\-/]*)?")
_CONTENT_TYPE = re.compile(
    r"[A-Za-z0-9!#$&^_.+\-/]{1,64}(; ?charset=[A-Za-z0-9_\-]{1,32})?"
)


class ArtifactError(ValueError):
    """El resultado no puede ser (o ya no es) una corrida aceptada."""

    def __init__(self, reasons: list[str]):
        super().__init__(", ".join(reasons))
        self.reasons = reasons


# --- Canonicalización e identidad ----------------------------------------------------


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def fingerprint(stable: Mapping) -> str:
    return hashlib.sha256(canonical_bytes(stable)).hexdigest()


def sanitize_url(url: str) -> str:
    """scheme://host:puerto/ruta, sin usuario, clave, query ni fragmento."""
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{parts.hostname or ''}{port}{parts.path}"


def _stable_output(body: Mapping) -> dict:
    """Copia por lista blanca de una salida canónica ya aceptada."""
    out = {k: body[k] for k in _OUTPUT_FIELDS if k in body}
    meteo = body.get("meteo_actual")
    if isinstance(meteo, Mapping):
        out["meteo_actual"] = {k: meteo[k] for k in _METEO_FIELDS if k in meteo}
    cells = []
    for c in body["cells"]:
        cell = {k: c[k] for k in _CELL_FIELDS}
        if isinstance(c.get("geometry"), Mapping):
            cell["geometry"] = {k: c["geometry"][k] for k in _GEOMETRY_KEYS}
        cells.append(cell)
    out["cells"] = sorted(
        cells, key=lambda c: c["rank"]
    )  # orden del backend, no re-rank
    identity = body["input_identity"]
    out["input_identity"] = json.loads(
        json.dumps(identity)
    )  # ya validado: copia profunda
    alert = body["alert_identity"]
    out["alert_identity"] = {
        k: alert[k] for k in ("schema_version", "alert_fingerprint", "top_n")
    }
    out["limitations"] = [dict(x) for x in LIMITATIONS]
    return out


def _output_violations(body: Mapping) -> tuple[list[str], Optional[sc.DashboardView]]:
    """Mismo portón que el Control Center en vivo + chequeos propios del artefacto."""
    if not isinstance(body, Mapping):
        return ["response_not_object"], None
    view = sc.from_payload(
        body
    )  # contrato, identidad de alerta, geometría, input_identity
    if view.state != sc.LIVE_READY:
        reasons = list(view.reasons) or [view.state.lower()]
        if view.state in (sc.DATA_UNAVAILABLE, sc.PROTOTYPE_UNAVAILABLE):
            reasons = [view.state.lower()]
        return reasons, None
    reasons = []
    if body.get("output_schema_version") != OUTPUT_SCHEMA_VERSION:
        reasons.append("output_schema_version_mismatch")
    if body.get("limitations") != [dict(x) for x in LIMITATIONS]:
        reasons.append("limitations_mismatch")
    meteo = body.get("meteo_actual")
    if isinstance(meteo, Mapping):
        if "regla_30_30_30" in meteo and not isinstance(meteo["regla_30_30_30"], bool):
            reasons.append("invalid_meteo_rule")
        if "momento_observacion" in meteo and not sc._is_iso(
            meteo["momento_observacion"]
        ):
            reasons.append("invalid_meteo_observation")
    return reasons, view


def build_artifact(
    body: Mapping,
    *,
    data_origin: str,
    captured_at: str,
    http_status: int = 200,
    content_type: Optional[str] = None,
    source_url: str,
) -> dict:
    """Salida canónica aceptada → artefacto. Lanza ArtifactError si no es aceptable."""
    if data_origin not in DATA_ORIGINS:
        raise ArtifactError(["invalid_data_origin"])
    if http_status != 200:
        raise ArtifactError([f"http_{http_status}"])
    reasons, view = _output_violations(body)
    if reasons:
        raise ArtifactError(reasons)
    assert view is not None and view.alert is not None
    stable = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "canonical_output_schema_version": OUTPUT_SCHEMA_VERSION,
        "data_origin": data_origin,
        "output": _stable_output(body),
    }
    fp = fingerprint(stable)
    ctype = (
        content_type if content_type and _CONTENT_TYPE.fullmatch(content_type) else None
    )
    return {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_fingerprint": fp,
        "identities": {
            "inputs_fingerprint": view.inputs_fingerprint,
            "notification_identity": view.alert.fingerprint,
            "artifact_fingerprint": fp,
        },
        "stable": stable,
        # Fuera del fingerprint: dos capturas del mismo resultado difieren solo aquí.
        "capture": {
            "captured_at": captured_at,
            "source_mode": SOURCE_LIVE_CAPTURE,
            "http_status": http_status,
            "content_type": ctype,
            "source_url": sanitize_url(source_url),
        },
    }


def verify_artifact(
    doc: Any, *, expected_fingerprint: Optional[str] = None
) -> tuple[list[str], Optional[sc.DashboardView]]:
    """(motivos de rechazo, vista REPLAY). Sin motivos ⇒ el artefacto es íntegro.

    El fingerprint es auto-referente: detecta cualquier edición que no lo recalcule.
    Quien edite el contenido Y recalcule el fingerprint obtiene OTRO artefacto
    (otra identidad); para descartarlo hay que anclar el fingerprint registrado en
    la captura con `expected_fingerprint` (CLI `--expect-fingerprint`).
    """
    if not isinstance(doc, Mapping):
        return ["artifact_not_object"], None
    reasons: list[str] = []
    if set(doc) - {
        "artifact_schema_version",
        "artifact_fingerprint",
        "identities",
        "stable",
        "capture",
    }:
        reasons.append("artifact_unknown_field")
    stable = doc.get("stable")
    if (
        doc.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION
        or not isinstance(stable, Mapping)
        or stable.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION
    ):
        return reasons + ["artifact_schema_version_mismatch"], None
    if set(stable) != {
        "artifact_schema_version",
        "canonical_output_schema_version",
        "data_origin",
        "output",
    }:
        reasons.append("artifact_stable_fields_mismatch")
    declared = doc.get("artifact_fingerprint")
    if not (isinstance(declared, str) and _HEX64.fullmatch(declared)):
        return reasons + ["artifact_fingerprint_missing"], None
    try:
        recomputed = fingerprint(stable)
    except (TypeError, ValueError):
        return reasons + ["artifact_not_canonical"], None
    if recomputed != declared:
        reasons.append("artifact_fingerprint_mismatch")
    if expected_fingerprint is not None and declared != expected_fingerprint:
        reasons.append("artifact_fingerprint_not_expected")
    if stable.get("data_origin") not in DATA_ORIGINS:
        reasons.append("invalid_data_origin")
    if stable.get("canonical_output_schema_version") != OUTPUT_SCHEMA_VERSION:
        reasons.append("output_schema_version_mismatch")
    output = stable.get("output")
    if not isinstance(output, Mapping) or "_synthetic" in output:
        return sorted(set(reasons + ["artifact_output_invalid"])), None
    extra = (
        set(output)
        - set(_OUTPUT_FIELDS)
        - {"meteo_actual", "cells", "input_identity", "alert_identity", "limitations"}
    )
    if extra:
        reasons.append("artifact_output_unknown_field")
    out_reasons, view = _output_violations(output)
    reasons += out_reasons
    capture = doc.get("capture")
    if not isinstance(capture, Mapping) or set(capture) != set(_CAPTURE_FIELDS):
        reasons.append("capture_metadata_invalid")
    else:
        if not sc._is_iso(capture.get("captured_at")):
            reasons.append("capture_time_invalid")
        if (
            capture.get("source_mode") != SOURCE_LIVE_CAPTURE
            or capture.get("http_status") != 200
        ):
            reasons.append("capture_metadata_invalid")
        url = capture.get("source_url")
        if not (isinstance(url, str) and _SAFE_URL.fullmatch(url)):
            reasons.append("capture_url_unsafe")
        ctype = capture.get("content_type")
        if ctype is not None and not (
            isinstance(ctype, str) and _CONTENT_TYPE.fullmatch(ctype)
        ):
            reasons.append("capture_metadata_invalid")
    if view is not None and view.alert is not None:
        expected = {
            "inputs_fingerprint": view.inputs_fingerprint,
            "notification_identity": view.alert.fingerprint,
            "artifact_fingerprint": declared,
        }
        if doc.get("identities") != expected:
            reasons.append("identities_mismatch")
    if reasons or view is None:
        return sorted(set(reasons)) or ["artifact_output_invalid"], None
    replay = dataclasses.replace(
        view,
        state=sc.REPLAY_READY,
        mode=sc.MODE_REPLAY,
        fetched_at=None,
        endpoint=capture["source_url"],
        artifact_fingerprint=declared,
        captured_at=capture["captured_at"],
        data_origin=stable["data_origin"],
    )
    return [], replay


def load_replay(
    path: Path | str, expected_fingerprint: Optional[str] = None
) -> sc.DashboardView:
    """Artefacto en disco → vista REPLAY, o INVALID_RESULT en modo REPLAY."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return sc.DashboardView(
            sc.INVALID_RESULT, mode=sc.MODE_REPLAY, reasons=("artifact_unreadable",)
        )
    reasons, view = verify_artifact(doc, expected_fingerprint=expected_fingerprint)
    if reasons or view is None:
        return sc.DashboardView(
            sc.INVALID_RESULT, mode=sc.MODE_REPLAY, reasons=tuple(reasons)
        )
    return view


def verify_artifact_file(
    path: Path | str, expected_fingerprint: Optional[str] = None
) -> list[str]:
    """Motivos de rechazo de un artefacto en disco (vacío = íntegro)."""
    view = load_replay(path, expected_fingerprint)
    return [] if view.state == sc.REPLAY_READY else list(view.reasons)


# --- Escritura segura ----------------------------------------------------------------


def unsafe_output_dir(out_dir: Path) -> Optional[str]:
    """Motivo por el que un directorio de evidencia NO es aceptable (None = seguro)."""
    target = out_dir.resolve()
    for root in FORBIDDEN_ROOTS:
        if target == root or root in target.parents:
            return f"directorio operacional protegido: {root.relative_to(REPO_ROOT)}"
    for folder in (target, *target.parents):
        if folder.name.lower() == "versions":
            return "directorio de versiones operacionales"
        if (folder / "CURRENT.json").exists():
            return "directorio con puntero CURRENT"
    return None


def _write_once(path: Path, data: bytes) -> str:
    """Escribe atómicamente; si ya existe con los mismos bytes no hace nada."""
    if path.exists():
        if path.read_bytes() == data:
            return "unchanged"
        raise FileExistsError(str(path))
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return "written"


def artifact_filename(doc: Mapping) -> str:
    scoring = str(doc["stable"]["output"]["forecast_time"])
    stamp = re.sub(r"[^0-9T]", "", scoring)[:15]
    return f"accepted-run_{stamp}_{doc['artifact_fingerprint'][:12]}.json"


def write_artifact(doc: Mapping, out_dir: Path) -> tuple[Path, str]:
    reason = unsafe_output_dir(out_dir)
    if reason:
        raise PermissionError(reason)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / artifact_filename(doc)
    if path.exists():
        # Mismo resultado aceptado capturado otra vez: se conserva la primera captura.
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            existing = None
        reasons, _ = verify_artifact(existing)
        if (
            not reasons
            and existing["artifact_fingerprint"] == doc["artifact_fingerprint"]
        ):
            return path, "already_captured"
        raise FileExistsError(str(path))
    data = (
        json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )
    return path, _write_once(path, data)


# --- Evidencia compacta --------------------------------------------------------------


def evidence_summary(doc: Mapping, view: sc.DashboardView) -> dict:
    stable, capture = doc["stable"], doc["capture"]
    synthetic = stable["data_origin"] == DATA_SYNTHETIC
    return {
        "evidence_schema_version": "sapi-accepted-run-evidence-v1",
        "evidence_kind": "ACCEPTED RUN (LIVE CAPTURE)",
        "data_origin": stable["data_origin"],
        "synthetic_banner": (
            "SYNTHETIC — datos sintéticos, no operacionales" if synthetic else None
        ),
        "modes": {
            "captured_as": "LIVE CAPTURE",
            "replay": "python -m app.control_center --replay <este artefacto>",
            "demo": "DEMO es la fixture local del Control Center; nunca es un artefacto",
        },
        "identities": dict(doc["identities"]),
        "scoring_time": view.scoring_time,
        "captured_at": capture["captured_at"],
        "source_url": capture["source_url"],
        "firms": dict(view.firms),
        "model": {"version": view.model_version, "status": view.model_status},
        "cell_count": len(view.cells),
        "top5": [
            {
                "rank": c.rank,
                "cell_id": c.cell_id,
                "score": c.score,
                "display_rank": c.display_rank,
                "tie_group_size": c.tie_group_size,
            }
            for c in view.top
        ],
        "limitations": [x["text"] for x in LIMITATIONS],
        "scientific_note": (
            "El score representa prioridad relativa dentro de las celdas evaluadas. "
            "No corresponde a una probabilidad calibrada ni confirma la existencia de un incendio."
        ),
    }


def evidence_markdown(summary: Mapping) -> str:
    lines = []
    if summary["synthetic_banner"]:
        lines += [f"> **{summary['synthetic_banner']}**", ""]
    ids = summary["identities"]
    lines += [
        f"# SAPI — {summary['evidence_kind']}",
        "",
        f"- Origen de datos: **{summary['data_origin']}**",
        f"- Hora de evaluación: {summary['scoring_time']}",
        f"- Capturado: {summary['captured_at']} desde {summary['source_url']}",
        f"- FIRMS: {summary['firms']['status']}, cobertura hasta "
        f"{summary['firms']['coverage_end']} (desfase {summary['firms']['lag_days']} d, "
        f"origen {summary['firms']['origin']})",
        f"- Modelo: {summary['model']['version']} ({summary['model']['status']})",
        f"- Celdas evaluadas: {summary['cell_count']}",
        f"- inputs_fingerprint: `{ids['inputs_fingerprint']}`",
        f"- notification_identity: `{ids['notification_identity']}`",
        f"- artifact_fingerprint: `{ids['artifact_fingerprint']}`",
        "",
        "## Top 5 (rank del backend, score relativo)",
        "",
    ]
    lines += [
        f"{c['rank']}. {c['cell_id']} · score relativo {c['score']:.4f}"
        + (
            f" (empate ×{c['tie_group_size']}, posición {c['display_rank']})"
            if c["tie_group_size"] > 1
            else ""
        )
        for c in summary["top5"]
    ]
    lines += ["", f"_{summary['scientific_note']}_", "", "## Limitaciones", ""]
    lines += [f"- {x}" for x in summary["limitations"]]
    lines += ["", f"Replay: `{summary['modes']['replay']}`", ""]
    return "\n".join(lines)


def export_evidence(doc: Mapping, out_dir: Path) -> Path:
    reasons, view = verify_artifact(doc)
    if reasons or view is None:
        raise ArtifactError(reasons)
    reason = unsafe_output_dir(out_dir)
    if reason:
        raise PermissionError(reason)
    folder = out_dir / f"evidence_{doc['artifact_fingerprint'][:12]}"
    folder.mkdir(parents=True, exist_ok=True)
    summary = evidence_summary(doc, view)
    _write_once(
        folder / "summary.json",
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n",
    )
    _write_once(folder / "summary.md", evidence_markdown(summary).encode("utf-8"))
    _write_once(
        folder / "artifact_fingerprint.txt",
        (doc["artifact_fingerprint"] + "\n").encode(),
    )
    return folder


# --- Captura en vivo (solo GET) ------------------------------------------------------


def capture(
    url: str,
    *,
    data_origin: str = DATA_OPERATIONAL,
    session=None,
    timeout: tuple[float, float] = (3.0, 90.0),
) -> dict:
    """GET de solo lectura → artefacto validado (no escribe). Lanza ArtifactError o
    ConnectionError; nunca devuelve un artefacto para una respuesta no aceptada."""
    import requests

    http = session or requests
    try:
        response = http.get(
            url,
            timeout=timeout,
            headers={"Accept": "application/json"},
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise ConnectionError(type(exc).__name__) from None
    try:
        body = response.json()
    except ValueError:
        raise ArtifactError(["response_not_json"]) from None
    if response.status_code != 200:
        kind = body.get("error_type") if isinstance(body, Mapping) else None
        allowed = {"data_unavailable", "prototype_unavailable", "internal_error"}
        raise ArtifactError(
            [kind if kind in allowed else f"http_{response.status_code}"]
        )
    headers = getattr(response, "headers", {}) or {}
    return build_artifact(
        body,
        data_origin=data_origin,
        captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        http_status=200,
        content_type=headers.get("content-type"),
        source_url=url,
    )


def _print(obj: Mapping) -> None:
    print(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.output.accepted_run",
        description="Artefacto de corrida aceptada (solo lectura).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture", help="GET /score → artefacto validado")
    cap.add_argument("--url", required=True)
    cap.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE_DIR)
    cap.add_argument(
        "--synthetic",
        action="store_true",
        help="rotula el artefacto como SYNTHETIC (fixtures, pruebas)",
    )
    ver = sub.add_parser("verify", help="verifica un artefacto sin red")
    ver.add_argument("artifact", type=Path)
    ver.add_argument(
        "--expect-fingerprint", help="fingerprint registrado en la captura"
    )
    evi = sub.add_parser(
        "evidence", help="paquete de evidencia compacto de un artefacto"
    )
    evi.add_argument("artifact", type=Path)
    evi.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args(argv)

    if args.command == "capture":
        reason = unsafe_output_dir(args.out)
        if reason:  # antes de cualquier red
            _print({"result": "REFUSED", "reason": reason})
            return EXIT_USAGE
        origin = DATA_SYNTHETIC if args.synthetic else DATA_OPERATIONAL
        try:
            doc = capture(args.url, data_origin=origin)
        except ConnectionError as exc:
            _print(
                {
                    "result": "NOT_CAPTURED",
                    "reason": f"network:{exc}",
                    "source_url": sanitize_url(args.url),
                }
            )
            return EXIT_NETWORK
        except ArtifactError as exc:
            _print(
                {
                    "result": "NOT_ACCEPTED",
                    "reasons": exc.reasons,
                    "source_url": sanitize_url(args.url),
                }
            )
            return EXIT_NOT_ACCEPTED
        try:
            path, status = write_artifact(doc, args.out)
        except FileExistsError as exc:
            _print(
                {"result": "REFUSED", "reason": f"ya existe con otro contenido: {exc}"}
            )
            return EXIT_USAGE
        _print(
            {
                "result": "CAPTURED",
                "write": status,
                "path": str(path),
                "data_origin": origin,
                **doc["identities"],
            }
        )
        return EXIT_OK

    try:
        doc = json.loads(args.artifact.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _print({"result": "INVALID", "reasons": ["artifact_unreadable"]})
        return EXIT_NOT_ACCEPTED
    expected = getattr(args, "expect_fingerprint", None)
    reasons, view = verify_artifact(doc, expected_fingerprint=expected)
    if reasons or view is None:
        _print({"result": "INVALID", "reasons": reasons})
        return EXIT_NOT_ACCEPTED
    if args.command == "verify":
        _print(
            {"result": "VALID", "data_origin": view.data_origin, **doc["identities"]}
        )
        return EXIT_OK
    try:
        folder = export_evidence(doc, args.out)
    except (PermissionError, FileExistsError) as exc:
        _print({"result": "REFUSED", "reason": str(exc)})
        return EXIT_USAGE
    _print({"result": "EXPORTED", "path": str(folder), **doc["identities"]})
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
