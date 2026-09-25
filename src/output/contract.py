"""Piezas puras del contrato canónico de salida (sapi-output-v1).

Fuente única de la versión del contrato y de la lista blanca de identidades de
entrada. La usan el bridge (tools/n8n_bridge/output_contract.py, al emitir), el
Control Center (al leer) y el artefacto de corrida aceptada (al capturar y al
reproducir). Sin I/O.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

OUTPUT_SCHEMA_VERSION = "sapi-output-v1"
IDENTITY_BLOCKS = ("model", "firms", "dmc", "topography")

# Patrones estrictos por tipo: nada de espacios ni ":" fuera de fechas ISO, para
# que un valor inesperado (p. ej. "Authorization: Bearer …") nunca pase como etiqueta.
PATTERNS = {
    "sha": re.compile(r"[0-9a-f]{64}"),
    "token": re.compile(r"[A-Za-z0-9._-]{1,128}"),
    "iso": re.compile(
        r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2}))?"
    ),
}

# bloque → {clave de salida: (clave en ScoringInputs.manifest(), tipo)}
WHITELIST: dict[str, dict[str, tuple[str, str]]] = {
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


def safe_value(value: Any, kind: str) -> Optional[str]:
    if not isinstance(value, str):
        return None
    return value if PATTERNS[kind].fullmatch(value) else None


def input_identity(manifest: Optional[Mapping]) -> dict:
    """Identidades seguras del manifest de ScoringInputs (o nulls si no hay).

    `code` es null: hoy no existe una identidad de código/corrida upstream.
    """
    out: dict[str, Any] = {"code": None}
    for block, fields in WHITELIST.items():
        source = manifest.get(block) if isinstance(manifest, Mapping) else None
        if not isinstance(source, Mapping):
            out[block] = None
            continue
        out[block] = {
            name: safe_value(source.get(key), kind)
            for name, (key, kind) in fields.items()
        }
    mode = (
        manifest.get("reproducibility_mode") if isinstance(manifest, Mapping) else None
    )
    out["reproducibility_mode"] = mode if isinstance(mode, bool) else None
    return out


def input_identity_violations(identity: Any) -> list[str]:
    """Motivos por los que un `input_identity` RECIBIDO no es seguro (vacío = apto).

    Más estricto que `input_identity`: al capturar o reproducir no se limpia en
    silencio; cualquier clave desconocida o valor fuera de patrón es rechazo.
    """
    if not isinstance(identity, Mapping):
        return ["input_identity_missing"]
    reasons: list[str] = []
    allowed = set(IDENTITY_BLOCKS) | {"code", "reproducibility_mode"}
    if set(identity) - allowed:
        reasons.append("input_identity_unknown_field")
    if identity.get("code") is not None:
        reasons.append("input_identity_code_unexpected")
    if identity.get("reproducibility_mode") not in (None, True, False):
        reasons.append("input_identity_invalid_mode")
    for block in IDENTITY_BLOCKS:
        value = identity.get(block)
        if value is None:
            continue
        if not isinstance(value, Mapping) or set(value) - set(WHITELIST[block]):
            reasons.append(f"input_identity_{block}_unknown_field")
            continue
        for name, (_, kind) in WHITELIST[block].items():
            item = value.get(name)
            if item is not None and safe_value(item, kind) is None:
                reasons.append(f"input_identity_{block}_unsafe_value")
    return sorted(set(reasons))
