"""Workspace safety integration point — do NOT duplicate Claude implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

ALLOWED_STATUSES = frozenset({"PASS", "FAIL", "INCOMPLETE", "NOT_AVAILABLE"})


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
            "evidence": {},
            "note": "Integration point only — never silently PASS",
        }


_PROVIDER: WorkspaceSafetyProvider = NotAvailableWorkspaceSafety()


def set_workspace_safety_provider(provider: WorkspaceSafetyProvider) -> None:
    global _PROVIDER
    _PROVIDER = provider


def check_workspace_safety(repo: Path) -> dict[str, Any]:
    result = dict(_PROVIDER.check(Path(repo)))
    status = result.get("status")
    if status not in ALLOWED_STATUSES:
        result["status"] = "INCOMPLETE"
        result["note"] = f"invalid_status_coerced_from:{status}"
    # Hard rule: default stub must not look like PASS
    if (
        result.get("status") == "PASS"
        and type(_PROVIDER) is NotAvailableWorkspaceSafety
    ):
        result["status"] = "NOT_AVAILABLE"
        result["note"] = "stub_cannot_pass"
    result.setdefault("evidence", {})
    result.setdefault("observed_at", datetime.now(timezone.utc).isoformat())
    return result
