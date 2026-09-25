"""Contrato canónico de salida de `/score` (sapi-output-v1).

Es una representación de TRANSPORTE del mismo `GridScoreResult` ya validado por
`contract.validate_grid_result`: no hay un segundo resultado de scoring. A los
campos que el bridge ya emitía se agregan, sin cambiarlos:

- `output_schema_version`: "sapi-output-v1";
- `input_identity`: identidades seguras de `ScoringInputs.manifest()` (lista
  blanca; lo que no existe upstream queda en null, nunca se inventa);
- `alert_identity`: identidad canónica de la notificación, calculada con la
  ÚNICA receta de `src.notifications.alert_payload.build_alert` sobre este mismo
  payload (Control Center y ops/n8n/policy.js la verifican con esa receta);
- `limitations`: las limitaciones científicas del payload de alerta.

Mapa de nombres: `forecast_time` es la hora de evaluación (scoring_time del
payload de alerta); `cells`, `firms_*` e `inputs_fingerprint` quedan como estaban.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from src.inference.scoring_inputs import _canonical_sha as manifest_fingerprint
from src.notifications.alert_payload import LIMITATIONS, STATUS_READY, build_alert
from tools.n8n_bridge.contract import InvalidScoreResultError

OUTPUT_SCHEMA_VERSION = "sapi-output-v1"
# Patrones estrictos por tipo: nada de espacios ni ":" fuera de fechas ISO, para
# que un valor inesperado (p. ej. "Authorization: Bearer …") nunca pase como etiqueta.
_PATTERNS = {
    "sha": re.compile(r"[0-9a-f]{64}"),
    "token": re.compile(r"[A-Za-z0-9._-]{1,128}"),
    "iso": re.compile(
        r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2}))?"
    ),
}

# bloque → {clave de salida: (clave en el manifest, tipo)}
_WHITELIST: dict[str, dict[str, tuple[str, str]]] = {
    "model": {
        "sha256": ("sha256", "sha"),
        "name": ("name", "token"),
        "version": ("model_version", "token"),
    },
    "firms": {
        "sha256": ("sha256", "sha"),
        "origin": ("origin", "token"),
        "pointer_version": ("pointer_version", "token"),
        "coverage_start": ("coverage_start", "iso"),
        "coverage_end": ("coverage_end", "iso"),
    },
    "dmc": {
        "manifest_sha256": ("manifest_sha256", "sha"),
        "pointer_version": ("pointer_version", "token"),
        "coverage_start": ("coverage_start", "iso"),
        "coverage_end": ("coverage_end", "iso"),
    },
    "topography": {
        "sha256": ("sha256", "sha"),
        "origin": ("origin", "token"),
    },
}


def _safe(value: Any, kind: str) -> Optional[str]:
    if not isinstance(value, str):
        return None
    return value if _PATTERNS[kind].fullmatch(value) else None


def input_identity(manifest: Optional[Mapping]) -> dict:
    """Identidades seguras del manifest de ScoringInputs (o nulls si no hay).

    `code` es null: hoy no existe una identidad de código/corrida upstream.
    """
    out: dict[str, Any] = {"code": None}
    for block, fields in _WHITELIST.items():
        source = manifest.get(block) if isinstance(manifest, Mapping) else None
        if not isinstance(source, Mapping):
            out[block] = None
            continue
        out[block] = {
            name: _safe(source.get(key), kind) for name, (key, kind) in fields.items()
        }
    mode = (
        manifest.get("reproducibility_mode") if isinstance(manifest, Mapping) else None
    )
    out["reproducibility_mode"] = mode if isinstance(mode, bool) else None
    return out


def attach_output_contract(payload: dict, manifest: Optional[Mapping]) -> dict:
    """Agrega el contrato canónico a un payload de `/score` ya serializado.

    Lanza `InvalidScoreResultError` (→ 500 `internal_error`) si el manifest no
    corresponde al `inputs_fingerprint` o si la receta de alerta no acepta el
    resultado: nunca sale un 200 con identidades inconsistentes.
    """
    if isinstance(manifest, Mapping) and manifest_fingerprint(manifest) != payload.get(
        "inputs_fingerprint"
    ):
        raise InvalidScoreResultError(
            ["inputs_fingerprint no corresponde a scoring_inputs"]
        )
    alert = build_alert(payload)
    if alert["status"] != STATUS_READY:
        raise InvalidScoreResultError(
            [
                f"alert_payload rechaza el resultado: {', '.join(alert.get('reasons', []))}"
            ]
        )
    return {
        **payload,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "input_identity": input_identity(manifest),
        "alert_identity": {
            "schema_version": alert["schema_version"],
            "alert_fingerprint": alert["alert_fingerprint"],
            "top_n": alert["summary"]["top_n"],
        },
        "limitations": [dict(x) for x in LIMITATIONS],
    }
