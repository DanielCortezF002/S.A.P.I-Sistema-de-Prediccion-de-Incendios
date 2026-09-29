"""Release Candidate Execution Context (Phase G & G1).

Machine-readable evidence object binding:
- expected final code SHA (parameterized; never hardcoded)
- workspace manifest fingerprint
- data plane manifest fingerprint
- output plane manifest fingerprint where available
- operator version/code SHA
- Attempt 2 run ID

This represents IDENTITY / EVIDENCE, never authorization.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class RC1ExecutionContext:
    expected_code_sha: str
    run_id: str
    operator_code_sha: str
    workspace_manifest_fingerprint: str | None = None
    data_plane_manifest_fingerprint: str | None = None
    output_plane_manifest_fingerprint: str | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(
                self, "created_at", datetime.now(timezone.utc).isoformat()
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def compute_fingerprint(self) -> str:
        """Deterministic canonical fingerprint binding all identity components."""
        data = {
            "expected_code_sha": self.expected_code_sha,
            "run_id": self.run_id,
            "operator_code_sha": self.operator_code_sha,
            "workspace_manifest_fingerprint": self.workspace_manifest_fingerprint,
            "data_plane_manifest_fingerprint": self.data_plane_manifest_fingerprint,
            "output_plane_manifest_fingerprint": self.output_plane_manifest_fingerprint,
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RC1ExecutionContext:
        return cls(
            expected_code_sha=str(data["expected_code_sha"]),
            run_id=str(data["run_id"]),
            operator_code_sha=str(data["operator_code_sha"]),
            workspace_manifest_fingerprint=data.get("workspace_manifest_fingerprint"),
            data_plane_manifest_fingerprint=data.get("data_plane_manifest_fingerprint"),
            output_plane_manifest_fingerprint=data.get(
                "output_plane_manifest_fingerprint"
            ),
            created_at=data.get("created_at", ""),
        )
