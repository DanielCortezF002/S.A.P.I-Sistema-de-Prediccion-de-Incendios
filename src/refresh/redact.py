"""Quita credenciales de cualquier texto antes de loguearlo o persistirlo.

La MAP_KEY de FIRMS va en la ruta de la URL y el token DMC en el
querystring: `str(exc)` de un error HTTP de `requests` los incluye, y
`requests` los codifica al construir la URL (`sapi@dmc.cl` pasa a
`sapi%40dmc.cl`). Por eso se reemplaza el valor crudo y también sus
variantes URL-encoded (querystring con `+` o `%20`, ruta, y los escapes en
minúscula). Es una red de seguridad: quien construye el mensaje no debería
incluir la URL en primer lugar.
"""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import quote, quote_plus

REDACTED = "[REDACTADO]"

_PERCENT_ESCAPE = re.compile(r"%[0-9A-F]{2}")


def _variants(secret: str) -> set[str]:
    encoded = {quote_plus(secret), quote(secret, safe=""), quote(secret)}
    lowered = {_PERCENT_ESCAPE.sub(lambda m: m.group().lower(), v) for v in encoded}
    return {secret} | encoded | lowered


def redact(text: object, secrets: Iterable[str]) -> str:
    out = str(text)
    variants: set[str] = set()
    for secret in secrets:
        if secret:
            variants |= _variants(secret)
    # La más larga primero: una variante nunca queda a medio reemplazar
    # porque otra más corta sea subcadena suya.
    for variant in sorted(variants, key=len, reverse=True):
        out = out.replace(variant, REDACTED)
    return out
