"""Optional path hooks to Cursor evidence tools (read-only integration)."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PLANNING = Path(r"D:\portafolio y seminario\SAPI-71-evidence\planning")


def evidence_tools_root() -> Path | None:
    env = os.environ.get("SAPI_ATTEMPT2_EVIDENCE_TOOLS")
    p = Path(env) if env else DEFAULT_PLANNING / "attempt2-evidence-tools"
    return p if p.is_dir() else None


def preflight_tools_root() -> Path | None:
    env = os.environ.get("SAPI_ATTEMPT2_PREFLIGHT_TOOLS")
    p = Path(env) if env else DEFAULT_PLANNING / "attempt2-preflight-tools"
    return p if p.is_dir() else None


def adapter_root() -> Path | None:
    env = os.environ.get("SAPI_ATTEMPT2_ADAPTER")
    p = (
        Path(env)
        if env
        else DEFAULT_PLANNING / "tooling-integration-rehearsal" / "adapter"
    )
    return p if p.is_dir() else None


def tools_inventory() -> dict[str, bool]:
    return {
        "attempt2_evidence_tools": evidence_tools_root() is not None,
        "attempt2_preflight_tools": preflight_tools_root() is not None,
        "canonical_adapter": adapter_root() is not None,
    }
