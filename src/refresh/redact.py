"""Quita credenciales de cualquier texto antes de loguearlo o persistirlo.

La MAP_KEY de FIRMS va en la ruta de la URL y el token DMC en el
querystring: `str(exc)` de un error HTTP de `requests` los incluye.
"""

from __future__ import annotations

from typing import Iterable

REDACTED = "[REDACTADO]"


def redact(text: object, secrets: Iterable[str]) -> str:
    out = str(text)
    for secret in secrets:
        if secret:
            out = out.replace(secret, REDACTED)
    return out
