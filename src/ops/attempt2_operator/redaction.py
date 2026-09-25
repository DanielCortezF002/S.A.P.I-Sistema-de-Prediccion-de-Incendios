"""Secret redaction for imported logs — never persist credential values."""

from __future__ import annotations

import hashlib
import re
from typing import Any

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|authorization|secret|bearer)\s*[=:]\s*\S+"),
    re.compile(r"(?i)MAP_KEY[=:]\S+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
]


def redact_text(text: str | None) -> tuple[str, bool]:
    """Return (redacted_text, had_secret)."""
    if text is None:
        return "", False
    out = text
    hit = False
    for pat in _SECRET_PATTERNS:
        if pat.search(out):
            hit = True
            out = pat.sub(r"\1=REDACTED", out)
    return out, hit


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def credential_presence(names: list[str], env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Record presence only — never values."""
    import os

    source = env if env is not None else os.environ
    return [{"credential_name": n, "present": bool(source.get(n))} for n in names]
