"""Credential presence only — never values."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

CREDENTIAL_NAMES = (
    "NASA_FIRMS_API_KEY",
    "DMC_USUARIO",
    "DMC_TOKEN",
)


def collect_credential_presence(
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    source = env if env is not None else os.environ
    items = [
        {"name": n, "present": bool(source.get(n))}
        for n in CREDENTIAL_NAMES
    ]
    # Fail closed: ensure no accidental value keys
    for item in items:
        assert set(item.keys()) == {"name", "present"}
        assert "value" not in item
    return {
        "credentials": items,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
