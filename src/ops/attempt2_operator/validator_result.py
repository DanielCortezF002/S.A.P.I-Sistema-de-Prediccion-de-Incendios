"""Canonical ValidatorResult structure."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ValidatorResult:
    name: str
    status: str  # PASS | FAIL | INCOMPLETE — technical only
    code_sha: str | None
    started_at: str
    finished_at: str
    exit_code: int | None
    evidence: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    evidence_acceptance: str | None = None  # ACCEPTED_EVIDENCE | REJECTED_EVIDENCE | ...
    note: str = (
        "status is technical PASS/FAIL/INCOMPLETE; "
        "evidence_acceptance is separate and never auto-authorizes"
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def incomplete(
        cls,
        name: str,
        *,
        code_sha: str | None,
        reason: str,
        started_at: str | None = None,
    ) -> ValidatorResult:
        start = started_at or _utc_now()
        return cls(
            name=name,
            status="INCOMPLETE",
            code_sha=code_sha,
            started_at=start,
            finished_at=_utc_now(),
            exit_code=None,
            warnings=[reason],
            failures=[],
        )
