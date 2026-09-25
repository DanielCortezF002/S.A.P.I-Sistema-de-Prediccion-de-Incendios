"""Workspace safety integration point — do NOT duplicate Claude implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


class WorkspaceSafetyProvider(Protocol):
    def check(self, repo: Path) -> dict[str, Any]:
        ...


class NotAvailableWorkspaceSafety:
    """Default until Claude workspace_safety is wired."""

    def check(self, repo: Path) -> dict[str, Any]:
        return {
            "status": "NOT_AVAILABLE",
            "provider": "NotAvailableWorkspaceSafety",
            "repo": str(repo),
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "note": "Integration point only — never silently PASS",
        }


_PROVIDER: WorkspaceSafetyProvider = NotAvailableWorkspaceSafety()


def set_workspace_safety_provider(provider: WorkspaceSafetyProvider) -> None:
    global _PROVIDER
    _PROVIDER = provider


def check_workspace_safety(repo: Path) -> dict[str, Any]:
    result = _PROVIDER.check(Path(repo))
    # Hard rule: missing provider must not look like PASS
    if result.get("status") == "PASS" and type(_PROVIDER) is NotAvailableWorkspaceSafety:
        result = {**result, "status": "NOT_AVAILABLE"}
    return result
