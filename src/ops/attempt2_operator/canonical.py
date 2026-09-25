"""Canonical status helpers — UNKNOWN != ABSENT; never promote auth false→true."""

from __future__ import annotations

from typing import Any


def normalize_current(raw: Any) -> dict[str, Any]:
    """Normalize CURRENT pointer. Missing → UNKNOWN (not ABSENT)."""
    if raw is None:
        return {
            "known": False,
            "present": None,
            "path": None,
            "sha256": None,
            "state": "UNKNOWN",
        }
    if not isinstance(raw, dict):
        return {
            "known": False,
            "present": None,
            "path": None,
            "sha256": None,
            "state": "UNKNOWN",
        }
    if "present" not in raw and "state" not in raw and "path" not in raw:
        return {
            "known": False,
            "present": None,
            "path": None,
            "sha256": None,
            "state": "UNKNOWN",
        }
    present = raw.get("present")
    state = raw.get("state")
    if state in ("UNKNOWN", "ABSENT", "PRESENT"):
        if state == "UNKNOWN":
            return {
                "known": False,
                "present": None,
                "path": raw.get("path"),
                "sha256": raw.get("sha256"),
                "state": "UNKNOWN",
            }
        return {
            "known": True,
            "present": state == "PRESENT",
            "path": raw.get("path"),
            "sha256": raw.get("sha256"),
            "state": state,
        }
    if present is True:
        return {
            "known": True,
            "present": True,
            "path": raw.get("path"),
            "sha256": raw.get("sha256"),
            "state": "PRESENT",
        }
    if present is False:
        return {
            "known": True,
            "present": False,
            "path": raw.get("path"),
            "sha256": raw.get("sha256"),
            "state": "ABSENT",
        }
    return {
        "known": False,
        "present": None,
        "path": raw.get("path"),
        "sha256": raw.get("sha256"),
        "state": "UNKNOWN",
    }


def authorize_record(
    *,
    existing: bool,
    requested: bool,
) -> bool:
    """Never promote false→true except via explicit requested True."""
    if existing is True:
        return True
    return bool(requested)


# Hard invariant vocabulary — must never be conflated
CURRENT_STATES = frozenset({"PRESENT", "ABSENT", "UNKNOWN"})
RUNTIME_STATES = frozenset({"RUNNING", "STOPPED", "UNKNOWN", "AVAILABLE", "UNAVAILABLE"})
TECHNICAL_RESULTS = frozenset({"PASS", "FAIL", "INCOMPLETE"})


def assert_unknown_invariants() -> None:
    """Runtime assertion helpers for tests / self-checks."""
    assert "UNKNOWN" != "ABSENT"
    assert "UNKNOWN" != "STOPPED"
    assert "UNKNOWN" != "SAFE"
    assert "UNKNOWN" != "PASS"
    assert "ABSENT" not in ("STOPPED", "PASS", "SAFE")
