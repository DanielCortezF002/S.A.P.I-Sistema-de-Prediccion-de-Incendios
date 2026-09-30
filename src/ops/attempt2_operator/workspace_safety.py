"""Workspace safety integration point — wires real Claude workspace_safety guard."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol

from src.ops import workspace_safety as ws
from src.ops.workspace_safety import Mode

ALLOWED_STATUSES = frozenset({"PASS", "FAIL", "INCOMPLETE", "NOT_AVAILABLE"})


class WorkspaceSafetyProvider(Protocol):
    def check(self, repo: Path, **kwargs: Any) -> dict[str, Any]: ...


class NotAvailableWorkspaceSafety:
    """Historical stub provider — never silently PASS."""

    def check(self, repo: Path, **kwargs: Any) -> dict[str, Any]:
        return {
            "status": "NOT_AVAILABLE",
            "overall_status": "NOT_AVAILABLE",
            "provider": "NotAvailableWorkspaceSafety",
            "repo": str(repo),
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence": {},
            "note": "Integration point stub — never silently PASS",
        }


class ClaudeWorkspaceSafetyProvider:
    """Real Workspace Safety Guard powered by src.ops.workspace_safety."""

    def __init__(self, default_mode: Mode | str = Mode.OPERATIONAL_REAL_DATA):
        if isinstance(default_mode, str):
            self.default_mode = Mode.parse(default_mode)
        else:
            self.default_mode = default_mode

    def check(
        self,
        repo: Path,
        *,
        mode: Mode | str | None = None,
        expected_code_sha: str | None = None,
        expected_tree_sha: str | None = None,
        stores: Mapping[str, Path] | None = None,
        expected_stores: Mapping[str, Path] | None = None,
        environ: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        target_mode = (
            Mode.parse(mode)
            if isinstance(mode, str)
            else mode if mode is not None else self.default_mode
        )
        resolved_stores = dict(stores) if stores is not None else {}
        if not resolved_stores and target_mode == Mode.OPERATIONAL_REAL_DATA:
            resolved_stores = {
                n: Path(repo) / ws.CODE_STORE_SUBPATHS[n]
                for n in ("raw", "processed", "models")
            }
        try:
            req = ws.GuardRequest(
                mode=target_mode,
                code_root=Path(repo),
                expected_code_sha=expected_code_sha,
                expected_tree_sha=expected_tree_sha,
                stores=resolved_stores,
                expected_stores=dict(expected_stores) if expected_stores else {},
                environ=environ,
            )
            raw = ws.check_workspace(req)
            overall = raw.get("overall_status", "INCOMPLETE")
            status = overall if overall in ALLOWED_STATUSES else "INCOMPLETE"
            return {
                "status": status,
                "overall_status": status,
                "provider": "ClaudeWorkspaceSafetyProvider",
                "repo": str(repo),
                "mode": target_mode.value,
                "observed_at": raw.get(
                    "observed_at", datetime.now(timezone.utc).isoformat()
                ),
                "evidence": raw,
                "findings": raw.get("findings", []),
                "failures": raw.get("failures", []),
                "warnings": raw.get("warnings", []),
                "incomplete": raw.get("incomplete", []),
                "exit_code": raw.get("exit_code"),
                "note": raw.get("disclaimer"),
            }
        except Exception as exc:
            return {
                "status": "NOT_AVAILABLE",
                "overall_status": "NOT_AVAILABLE",
                "provider": "ClaudeWorkspaceSafetyProvider",
                "repo": str(repo),
                "mode": (
                    target_mode.value
                    if isinstance(target_mode, Mode)
                    else str(target_mode)
                ),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "evidence": {},
                "findings": [
                    {"id": "WS-ERROR", "message": str(exc), "severity": "INCOMPLETE"}
                ],
                "note": f"Provider error: {type(exc).__name__}: {exc}",
            }


_PROVIDER: WorkspaceSafetyProvider = ClaudeWorkspaceSafetyProvider()


def set_workspace_safety_provider(provider: WorkspaceSafetyProvider) -> None:
    global _PROVIDER
    _PROVIDER = provider


def check_workspace_safety(repo: Path, **kwargs: Any) -> dict[str, Any]:
    result = dict(_PROVIDER.check(Path(repo), **kwargs))
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
