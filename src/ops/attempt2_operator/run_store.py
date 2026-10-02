"""Immutable Attempt 2 run directory layout and persistence."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from src.ops.attempt2_operator.events import (
    EventLog,
    content_hash,
    sha256_file,
    utc_now_iso,
)
from src.ops.attempt2_operator.states import Attempt2State, HUMAN_GATES

REPO_ROOT = Path(__file__).resolve().parents[3]
# Sibling of the checkout, as in src/output/accepted_run.py; env/CLI take precedence.
DEFAULT_EVIDENCE_ROOT = REPO_ROOT.parent / "SAPI-71-evidence" / "attempt2"

RUN_DIRS = (
    "commands",
    "imports",
    "validation",
    "reports",
    "preflight",
    "snapshots",
)


def make_run_id(when: datetime | None = None) -> str:
    ts = when or datetime.now().astimezone()
    return f"SAPI-ATTEMPT2-{ts.strftime('%Y%m%d-%H%M%S')}"


def git_identity(repo: Path) -> dict[str, Any]:
    def _run(args: list[str]) -> str | None:
        try:
            return subprocess.check_output(
                args, cwd=str(repo), text=True, stderr=subprocess.DEVNULL
            ).strip()
        except Exception:
            return None

    head = _run(["git", "rev-parse", "HEAD"])
    tree = _run(["git", "rev-parse", "HEAD^{tree}"])
    dirty_out = _run(["git", "status", "--porcelain"])
    dirty = None if dirty_out is None else bool(dirty_out.strip())
    return {
        "code_sha": head,
        "tree_sha": tree,
        "worktree_clean": (not dirty) if dirty is not None else None,
        "status_entries": (dirty_out.splitlines() if dirty_out else []),
        "repo_path": str(repo),
        "observed_at": utc_now_iso(),
    }


class Attempt2Run:
    """Persisted run — reconstructible from disk (crash recovery)."""

    def __init__(self, root: Path):
        self.root = root
        self.state_path = root / "state.json"
        self.auth_path = root / "authorizations.json"
        self.manifest_path = root / "manifest.json"
        self.events = EventLog(root / "events.jsonl")

    @property
    def run_id(self) -> str:
        return self.root.name

    @classmethod
    def create(
        cls,
        evidence_root: Path,
        *,
        code_sha: str | None,
        tree_sha: str | None,
        expected_code_sha: str | None,
        dry_run: bool,
        mode: str = "CONTROLLED",
        run_id: str | None = None,
    ) -> Attempt2Run:
        rid = run_id or make_run_id()
        root = evidence_root / rid
        if root.exists():
            raise FileExistsError(f"Run directory already exists: {root}")
        root.mkdir(parents=True, exist_ok=False)
        for d in RUN_DIRS:
            (root / d).mkdir(parents=True, exist_ok=True)
        run = cls(root)
        state = {
            "schema_version": 1,
            "run_id": rid,
            "state": Attempt2State.NEW.value,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "code_sha": code_sha,
            "tree_sha": tree_sha,
            "expected_code_sha": expected_code_sha,
            "dry_run": bool(dry_run),
            "mode": mode,
            "attempt1_preservation": {
                "policy": "NEVER_DELETE_OR_MODIFY",
                "note": "Attempt 1 five raw files / 85-record evidence must remain untouched",
            },
            "acceptance": {
                "software_operational": False,
                "scientific_model_validation": False,
                "note": "ACCEPTED means operational gates only — never model accuracy",
            },
            "gates_deferred": ["TELEGRAM_AUTHORIZATION", "SCHEDULE_AUTHORIZATION"],
            "last_error": None,
            "import_fingerprints": {},
        }
        run.write_state(state)
        run.write_authorizations(
            {
                "schema_version": 1,
                "gates": {g: False for g in HUMAN_GATES},
                "records": [],
            }
        )
        run.events.append(
            {
                "event_type": "RUN_INIT",
                "state_before": None,
                "state_after": Attempt2State.NEW.value,
                "code_sha": code_sha,
                "result": "CREATED",
                "evidence_refs": [str(root)],
                "dry_run": bool(dry_run),
            }
        )
        run.rebuild_manifest()
        return run

    @classmethod
    def open(cls, root: Path) -> Attempt2Run:
        if not (root / "state.json").exists():
            raise FileNotFoundError(f"Not an Attempt2 run: {root}")
        return cls(root)

    def read_state(self) -> dict[str, Any]:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def write_state(self, state: dict[str, Any]) -> None:
        state = dict(state)
        state["updated_at"] = utc_now_iso()
        self.state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def read_authorizations(self) -> dict[str, Any]:
        return json.loads(self.auth_path.read_text(encoding="utf-8"))

    def write_authorizations(self, data: dict[str, Any]) -> None:
        self.auth_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def current_state(self) -> Attempt2State:
        return Attempt2State(self.read_state()["state"])

    def set_state(
        self,
        new_state: Attempt2State,
        *,
        event_type: str,
        result: str,
        evidence_refs: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        from src.ops.attempt2_operator.states import ALLOWED_TRANSITIONS

        state = self.read_state()
        before = Attempt2State(state["state"])
        allowed = ALLOWED_TRANSITIONS.get(before, frozenset())
        if new_state not in allowed and new_state != before:
            raise InvalidTransitionError(before, new_state)
        state["state"] = new_state.value
        if extra:
            state.update(extra)
        self.write_state(state)
        self.events.append(
            {
                "event_type": event_type,
                "state_before": before.value,
                "state_after": new_state.value,
                "code_sha": state.get("code_sha"),
                "result": result,
                "evidence_refs": evidence_refs or [],
            }
        )
        self.rebuild_manifest()

    def rebuild_manifest(self) -> dict[str, Any]:
        files: dict[str, str] = {}
        for p in sorted(self.root.rglob("*")):
            if not p.is_file():
                continue
            if p.name == "manifest.json":
                continue
            rel = str(p.relative_to(self.root)).replace("\\", "/")
            files[rel] = sha256_file(p)
        state = self.read_state()
        man = {
            "schema_version": 1,
            "run_id": state["run_id"],
            "code_sha": state.get("code_sha"),
            "tree_sha": state.get("tree_sha"),
            "expected_code_sha": state.get("expected_code_sha"),
            "state": state["state"],
            "events_sha256": self.events.file_hash(),
            "files": files,
            "built_at": utc_now_iso(),
        }
        man["manifest_hash"] = content_hash(
            {k: v for k, v in man.items() if k != "manifest_hash"}
        )
        self.manifest_path.write_text(
            json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return man

    def write_json(self, relative: str, obj: Any) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
        self.rebuild_manifest()
        return path

    def write_text(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.rebuild_manifest()
        return path


class InvalidTransitionError(RuntimeError):
    def __init__(self, before: Attempt2State, after: Attempt2State):
        super().__init__(f"Invalid transition {before.value} → {after.value}")
        self.before = before
        self.after = after


def resolve_evidence_root(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get("SAPI_ATTEMPT2_EVIDENCE_ROOT")
    if env:
        return Path(env)
    return DEFAULT_EVIDENCE_ROOT
