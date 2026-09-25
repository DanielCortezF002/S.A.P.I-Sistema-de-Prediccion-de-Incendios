"""Attempt 2 operator workflow — human-gated; no auto writers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.ops.attempt2_operator.canonical import authorize_record
from src.ops.attempt2_operator.events import content_hash, sha256_file, utc_now_iso
from src.ops.attempt2_operator.redaction import credential_presence, redact_text, sha256_text
from src.ops.attempt2_operator.run_store import (
    Attempt2Run,
    InvalidTransitionError,
    git_identity,
    resolve_evidence_root,
)
from src.ops.attempt2_operator.states import (
    GATE_FOR_STATE,
    HUMAN_GATES,
    Attempt2State,
)
from src.ops.attempt2_operator.validators import (
    validate_bridge_result,
    validate_dmc_import,
    validate_firms_import,
    validate_n8n_result,
    validate_preflight_snapshot,
    validate_scoring_result,
)

FIRMS_MANUAL_CMD = (
    "python -m src.refresh.firms_refresh refresh\n"
    "# HUMAN ONLY — blocked from auto-execution by Attempt2 operator.\n"
    "# Capture: exit code, stdout, stderr, started_at, finished_at,\n"
    "# and if available HTTP status + Content-Type (no secrets).\n"
)

DMC_MANUAL_CMD = (
    "python -m src.refresh.dmc_refresh refresh\n"
    "# HUMAN ONLY — never auto-run by Attempt2 operator.\n"
)


class Attempt2Operator:
    def __init__(self, run: Attempt2Run, *, repo: Path | None = None):
        self.run = run
        self.repo = repo

    # --- lifecycle ---

    @classmethod
    def init_run(
        cls,
        *,
        evidence_root: Path | None = None,
        repo: Path | None = None,
        expected_code_sha: str | None = None,
        dry_run: bool = False,
        run_id: str | None = None,
        synthetic_identity: dict[str, Any] | None = None,
    ) -> Attempt2Operator:
        root = resolve_evidence_root(evidence_root)
        root.mkdir(parents=True, exist_ok=True)
        if dry_run and synthetic_identity:
            ident = {
                "code_sha": synthetic_identity.get("code_sha"),
                "tree_sha": synthetic_identity.get("tree_sha"),
                "worktree_clean": synthetic_identity.get("worktree_clean", True),
                "status_entries": [],
                "observed_at": utc_now_iso(),
            }
        else:
            ident = git_identity(repo) if repo else {
                "code_sha": None,
                "tree_sha": None,
                "worktree_clean": None,
                "status_entries": [],
                "observed_at": utc_now_iso(),
            }
        run = Attempt2Run.create(
            root,
            code_sha=ident.get("code_sha"),
            tree_sha=ident.get("tree_sha"),
            expected_code_sha=expected_code_sha,
            dry_run=dry_run,
            mode="SYNTHETIC" if dry_run else "CONTROLLED",
            run_id=run_id,
        )
        run.write_json("snapshots/git_identity.json", ident)
        return cls(run, repo=repo)

    @classmethod
    def open_run(cls, run_dir: Path, *, repo: Path | None = None) -> Attempt2Operator:
        return cls(Attempt2Run.open(run_dir), repo=repo)

    def status(self) -> dict[str, Any]:
        state = self.run.read_state()
        auth = self.run.read_authorizations()
        return {
            "run_id": state["run_id"],
            "state": state["state"],
            "code_sha": state.get("code_sha"),
            "expected_code_sha": state.get("expected_code_sha"),
            "dry_run": state.get("dry_run"),
            "gates": auth.get("gates"),
            "acceptance": state.get("acceptance"),
            "last_error": state.get("last_error"),
        }

    def next_action(self) -> dict[str, Any]:
        st = self.run.current_state()
        auth = self.run.read_authorizations()["gates"]
        if st == Attempt2State.NEW:
            return {
                "state": st.value,
                "next": "Run preflight",
                "command": "python -m src.ops.attempt2_operator preflight --run <run_dir>",
            }
        if st == Attempt2State.PREFLIGHT_PENDING:
            return {"state": st.value, "next": "Wait for / re-run preflight", "command": None}
        if st == Attempt2State.PREFLIGHT_FAILED:
            return {
                "state": st.value,
                "next": "Fix preflight failures, then re-run preflight",
                "command": "python -m src.ops.attempt2_operator preflight --run <run_dir>",
            }
        if st == Attempt2State.PREFLIGHT_READY:
            return {
                "state": st.value,
                "next": "Advance to authorization gate",
                "command": "python -m src.ops.attempt2_operator next --run <run_dir> --advance",
            }
        if st == Attempt2State.ATTEMPT2_AUTHORIZATION_REQUIRED:
            return {
                "state": st.value,
                "HUMAN ACTION REQUIRED": True,
                "next": "Human authorization required.",
                "gate": "ATTEMPT2_AUTHORIZATION",
                "command": (
                    "python -m src.ops.attempt2_operator authorize "
                    "--run <run_dir> --gate ATTEMPT2_AUTHORIZATION"
                ),
            }
        if st == Attempt2State.ATTEMPT2_AUTHORIZED:
            return {
                "state": st.value,
                "next": "Advance to FIRMS writer gate",
                "command": "python -m src.ops.attempt2_operator next --run <run_dir> --advance",
            }
        if st == Attempt2State.FIRMS_WRITER_REQUIRED:
            if not auth.get("FIRMS_WRITER_AUTHORIZATION"):
                return {
                    "state": st.value,
                    "HUMAN ACTION REQUIRED": True,
                    "next": "Human authorization required.",
                    "gate": "FIRMS_WRITER_AUTHORIZATION",
                    "command": (
                        "python -m src.ops.attempt2_operator authorize "
                        "--run <run_dir> --gate FIRMS_WRITER_AUTHORIZATION"
                    ),
                }
            return {
                "state": st.value,
                "HUMAN ACTION REQUIRED": True,
                "next": "Execute the following command manually:",
                "manual_command_file": "commands/firms.txt",
                "manual_command": FIRMS_MANUAL_CMD.strip(),
                "then_import": (
                    "python -m src.ops.attempt2_operator import-result "
                    "--run <run_dir> --phase firms --from <payload.json>"
                ),
            }
        if st == Attempt2State.FIRMS_RESULT_PENDING:
            return {
                "state": st.value,
                "next": "Import FIRMS result then validate",
                "command": (
                    "python -m src.ops.attempt2_operator import-result "
                    "--run <run_dir> --phase firms --from <payload.json>"
                ),
            }
        if st == Attempt2State.FIRMS_VALIDATED:
            return {
                "state": st.value,
                "next": "Advance to DMC writer gate",
                "command": "python -m src.ops.attempt2_operator next --run <run_dir> --advance",
            }
        if st == Attempt2State.DMC_WRITER_REQUIRED:
            if not auth.get("DMC_WRITER_AUTHORIZATION"):
                return {
                    "state": st.value,
                    "HUMAN ACTION REQUIRED": True,
                    "next": "Human authorization required.",
                    "gate": "DMC_WRITER_AUTHORIZATION",
                    "command": (
                        "python -m src.ops.attempt2_operator authorize "
                        "--run <run_dir> --gate DMC_WRITER_AUTHORIZATION"
                    ),
                }
            return {
                "state": st.value,
                "HUMAN ACTION REQUIRED": True,
                "next": "Execute the following command manually:",
                "manual_command_file": "commands/dmc.txt",
                "manual_command": DMC_MANUAL_CMD.strip(),
                "then_import": (
                    "python -m src.ops.attempt2_operator import-result "
                    "--run <run_dir> --phase dmc --from <payload.json>"
                ),
            }
        if st == Attempt2State.DMC_RESULT_PENDING:
            return {
                "state": st.value,
                "next": "Import DMC result then validate",
                "command": (
                    "python -m src.ops.attempt2_operator import-result "
                    "--run <run_dir> --phase dmc --from <payload.json>"
                ),
            }
        if st == Attempt2State.DMC_VALIDATED:
            return {
                "state": st.value,
                "next": "Advance to scoring",
                "command": "python -m src.ops.attempt2_operator next --run <run_dir> --advance",
            }
        if st == Attempt2State.SCORING_READY:
            return {
                "state": st.value,
                "next": "Import scoring payload (pinned ScoringInputs) then validate",
                "command": (
                    "python -m src.ops.attempt2_operator import-result "
                    "--run <run_dir> --phase scoring --from <payload.json>"
                ),
            }
        if st == Attempt2State.SCORING_VALIDATED:
            return {
                "state": st.value,
                "next": "Advance to bridge",
                "command": "python -m src.ops.attempt2_operator next --run <run_dir> --advance",
            }
        if st == Attempt2State.BRIDGE_READY:
            return {
                "state": st.value,
                "next": "Import bridge HTTP result then validate",
                "command": (
                    "python -m src.ops.attempt2_operator import-result "
                    "--run <run_dir> --phase bridge --from <payload.json>"
                ),
            }
        if st == Attempt2State.BRIDGE_VALIDATED:
            return {
                "state": st.value,
                "next": "Advance to manual n8n",
                "command": "python -m src.ops.attempt2_operator next --run <run_dir> --advance",
            }
        if st == Attempt2State.N8N_MANUAL_READY:
            return {
                "state": st.value,
                "HUMAN ACTION REQUIRED": True,
                "next": "Run n8n manually (no schedule, no Telegram). Then import.",
                "command": (
                    "python -m src.ops.attempt2_operator import-result "
                    "--run <run_dir> --phase n8n --from <payload.json>"
                ),
            }
        if st == Attempt2State.N8N_VALIDATED:
            return {
                "state": st.value,
                "next": "Advance to acceptance",
                "command": "python -m src.ops.attempt2_operator next --run <run_dir> --advance",
            }
        if st == Attempt2State.ACCEPTANCE_READY:
            return {
                "state": st.value,
                "next": "Mark operational acceptance (not scientific validation)",
                "command": "python -m src.ops.attempt2_operator next --run <run_dir> --advance",
            }
        if st == Attempt2State.ACCEPTED:
            return {
                "state": st.value,
                "next": "Done. Telegram/schedule remain separate human gates (not auto).",
                "command": None,
            }
        if st in (
            Attempt2State.FIRMS_VALIDATION_FAILED,
            Attempt2State.DMC_VALIDATION_FAILED,
            Attempt2State.SCORING_FAILED,
            Attempt2State.BRIDGE_FAILED,
            Attempt2State.N8N_FAILED,
            Attempt2State.STOPPED,
        ):
            return {
                "state": st.value,
                "next": "Stopped / failed — no automatic advance",
                "command": None,
            }
        return {"state": st.value, "next": "See status", "command": None}

    def advance(self) -> dict[str, Any]:
        """Advance through non-import states that only need acknowledgement."""
        st = self.run.current_state()
        mapping = {
            Attempt2State.PREFLIGHT_READY: Attempt2State.ATTEMPT2_AUTHORIZATION_REQUIRED,
            Attempt2State.ATTEMPT2_AUTHORIZED: Attempt2State.FIRMS_WRITER_REQUIRED,
            Attempt2State.FIRMS_VALIDATED: Attempt2State.DMC_WRITER_REQUIRED,
            Attempt2State.DMC_VALIDATED: Attempt2State.SCORING_READY,
            Attempt2State.SCORING_VALIDATED: Attempt2State.BRIDGE_READY,
            Attempt2State.BRIDGE_VALIDATED: Attempt2State.N8N_MANUAL_READY,
            Attempt2State.N8N_VALIDATED: Attempt2State.ACCEPTANCE_READY,
            Attempt2State.ACCEPTANCE_READY: Attempt2State.ACCEPTED,
        }
        if st == Attempt2State.FIRMS_WRITER_REQUIRED:
            auth = self.run.read_authorizations()["gates"]
            if not auth.get("FIRMS_WRITER_AUTHORIZATION"):
                raise PermissionError("FIRMS_WRITER_AUTHORIZATION required")
            self.run.write_text("commands/firms.txt", FIRMS_MANUAL_CMD)
            self.run.set_state(
                Attempt2State.FIRMS_RESULT_PENDING,
                event_type="FIRMS_COMMAND_ISSUED",
                result="HUMAN_ACTION_REQUIRED",
                evidence_refs=["commands/firms.txt"],
            )
            return self.next_action()
        if st == Attempt2State.DMC_WRITER_REQUIRED:
            auth = self.run.read_authorizations()["gates"]
            if not auth.get("DMC_WRITER_AUTHORIZATION"):
                raise PermissionError("DMC_WRITER_AUTHORIZATION required")
            self.run.write_text("commands/dmc.txt", DMC_MANUAL_CMD)
            self.run.set_state(
                Attempt2State.DMC_RESULT_PENDING,
                event_type="DMC_COMMAND_ISSUED",
                result="HUMAN_ACTION_REQUIRED",
                evidence_refs=["commands/dmc.txt"],
            )
            return self.next_action()
        if st == Attempt2State.ACCEPTANCE_READY:
            state = self.run.read_state()
            state["acceptance"] = {
                "software_operational": True,
                "scientific_model_validation": False,
                "note": "SOFTWARE/OPERATIONAL ACCEPTANCE only — not scientific model validation",
                "accepted_at": utc_now_iso(),
            }
            self.run.write_state(state)
            self.run.set_state(
                Attempt2State.ACCEPTED,
                event_type="ACCEPTED",
                result="OPERATIONAL_ACCEPTANCE",
            )
            return self.next_action()
        nxt = mapping.get(st)
        if not nxt:
            raise InvalidTransitionError(st, st)
        if st == Attempt2State.ATTEMPT2_AUTHORIZATION_REQUIRED:
            raise PermissionError("Use authorize for ATTEMPT2_AUTHORIZATION")
        self.run.set_state(nxt, event_type="ADVANCE", result="OK")
        if nxt == Attempt2State.FIRMS_WRITER_REQUIRED:
            self.run.write_text("commands/firms.txt", FIRMS_MANUAL_CMD)
        if nxt == Attempt2State.DMC_WRITER_REQUIRED:
            self.run.write_text("commands/dmc.txt", DMC_MANUAL_CMD)
        return self.next_action()

    def authorize(self, gate: str, *, actor: str = "local-operator") -> dict[str, Any]:
        if gate not in HUMAN_GATES:
            raise ValueError(f"Unknown gate: {gate}")
        if gate in ("TELEGRAM_AUTHORIZATION", "SCHEDULE_AUTHORIZATION"):
            # Recordable but Attempt2 path must not consume them for auto-send/enable
            pass
        auth = self.run.read_authorizations()
        before = bool(auth["gates"].get(gate, False))
        # Explicit action only — never infer
        auth["gates"][gate] = authorize_record(existing=before, requested=True)
        state = self.run.read_state()
        state_before = state["state"]
        record = {
            "gate": gate,
            "timestamp": utc_now_iso(),
            "actor": actor,
            "state_before": state_before,
            "explicit": True,
            "inferred_from_env": False,
            "inferred_from_files": False,
        }
        auth["records"].append(record)
        self.run.write_authorizations(auth)
        # Explicit gate transitions (never inferred)
        if gate == "ATTEMPT2_AUTHORIZATION" and state_before == (
            Attempt2State.ATTEMPT2_AUTHORIZATION_REQUIRED.value
        ):
            self.run.set_state(
                Attempt2State.ATTEMPT2_AUTHORIZED,
                event_type="AUTHORIZE",
                result=gate,
                evidence_refs=["authorizations.json"],
            )
            record["state_after"] = Attempt2State.ATTEMPT2_AUTHORIZED.value
        elif gate == "FIRMS_WRITER_AUTHORIZATION" and state_before == (
            Attempt2State.FIRMS_WRITER_REQUIRED.value
        ):
            self.run.write_text("commands/firms.txt", FIRMS_MANUAL_CMD)
            self.run.set_state(
                Attempt2State.FIRMS_RESULT_PENDING,
                event_type="AUTHORIZE",
                result=gate,
                evidence_refs=["authorizations.json", "commands/firms.txt"],
            )
            record["state_after"] = Attempt2State.FIRMS_RESULT_PENDING.value
        elif gate == "DMC_WRITER_AUTHORIZATION" and state_before == (
            Attempt2State.DMC_WRITER_REQUIRED.value
        ):
            self.run.write_text("commands/dmc.txt", DMC_MANUAL_CMD)
            self.run.set_state(
                Attempt2State.DMC_RESULT_PENDING,
                event_type="AUTHORIZE",
                result=gate,
                evidence_refs=["authorizations.json", "commands/dmc.txt"],
            )
            record["state_after"] = Attempt2State.DMC_RESULT_PENDING.value
        else:
            record["state_after"] = state_before
            self.run.events.append(
                {
                    "event_type": "AUTHORIZE",
                    "state_before": state_before,
                    "state_after": state_before,
                    "code_sha": state.get("code_sha"),
                    "result": gate,
                    "evidence_refs": ["authorizations.json"],
                }
            )
            self.run.rebuild_manifest()

        auth = self.run.read_authorizations()
        if auth["records"] and auth["records"][-1].get("gate") == gate:
            auth["records"][-1] = {**auth["records"][-1], **record}
        else:
            auth["records"].append(record)
        self.run.write_authorizations(auth)
        return {"gate": gate, "authorized": True, "record": record}

    def preflight(
        self,
        *,
        snapshot: dict[str, Any] | None = None,
        refresh_runtime: bool = True,
    ) -> dict[str, Any]:
        state = self.run.read_state()
        st = Attempt2State(state["state"])
        if st == Attempt2State.NEW:
            self.run.set_state(
                Attempt2State.PREFLIGHT_PENDING,
                event_type="PREFLIGHT_START",
                result="PENDING",
            )
        elif st not in (
            Attempt2State.PREFLIGHT_PENDING,
            Attempt2State.PREFLIGHT_FAILED,
            Attempt2State.PREFLIGHT_READY,
        ):
            # allow re-entry only from failed
            if st != Attempt2State.PREFLIGHT_FAILED:
                raise InvalidTransitionError(st, Attempt2State.PREFLIGHT_PENDING)

        if snapshot is None:
            snapshot = self._collect_preflight(refresh_runtime=refresh_runtime)
        else:
            # still stamp observed_at if missing on code block
            code = dict(snapshot.get("code") or {})
            if refresh_runtime or not code.get("observed_at"):
                code["observed_at"] = utc_now_iso()
            snapshot = dict(snapshot)
            snapshot["code"] = code

        self.run.write_json("preflight/attempt2-preflight.snapshot.json", snapshot)
        result = validate_preflight_snapshot(
            snapshot, expected_code_sha=state.get("expected_code_sha")
        )
        self.run.write_json("preflight/attempt2-preflight.validation.json", result)

        if result["ready_for_authorization"]:
            target = Attempt2State.PREFLIGHT_READY
            outcome = "PASS"
        else:
            target = Attempt2State.PREFLIGHT_FAILED
            outcome = result["technical_result"]
        # from PREFLIGHT_READY re-run: go via pending if needed
        cur = self.run.current_state()
        if cur == Attempt2State.PREFLIGHT_READY and target == Attempt2State.PREFLIGHT_FAILED:
            # not in allowed map directly — stop
            self.run.set_state(
                Attempt2State.STOPPED,
                event_type="PREFLIGHT",
                result="REGRESSED",
                extra={"last_error": "preflight regressed from READY"},
            )
        elif cur == Attempt2State.PREFLIGHT_FAILED and target == Attempt2State.PREFLIGHT_READY:
            self.run.set_state(
                Attempt2State.PREFLIGHT_PENDING,
                event_type="PREFLIGHT_RETRY",
                result="PENDING",
            )
            self.run.set_state(
                target,
                event_type="PREFLIGHT",
                result=outcome,
                evidence_refs=[
                    "preflight/attempt2-preflight.snapshot.json",
                    "preflight/attempt2-preflight.validation.json",
                ],
            )
        else:
            self.run.set_state(
                target,
                event_type="PREFLIGHT",
                result=outcome,
                evidence_refs=[
                    "preflight/attempt2-preflight.snapshot.json",
                    "preflight/attempt2-preflight.validation.json",
                ],
            )
        return result

    def _collect_preflight(self, *, refresh_runtime: bool) -> dict[str, Any]:
        """Fresh runtime observations — never reuse old evidence as live facts."""
        state = self.run.read_state()
        if self.repo and not state.get("dry_run"):
            ident = git_identity(self.repo)
        else:
            # dry-run / synthetic: use run identity
            ident = {
                "head_sha": state.get("code_sha"),
                "tree_sha": state.get("tree_sha"),
                "worktree_clean": True,
                "status_entries": [],
                "observed_at": utc_now_iso(),
            }
        # normalize key names for validator
        code = {
            "head_sha": ident.get("head_sha") or ident.get("code_sha") or state.get("code_sha"),
            "tree_sha": ident.get("tree_sha") or state.get("tree_sha"),
            "worktree_clean": ident.get("worktree_clean"),
            "status_entries": ident.get("status_entries") or [],
            "expected_main_sha": state.get("expected_code_sha"),
            "observed_at": ident.get("observed_at") or utc_now_iso(),
        }
        creds = credential_presence(
            ["NASA_FIRMS_MAP_KEY", "DMC_API_KEY", "TELEGRAM_BOT_TOKEN"]
        )
        return {
            "schema_version": 1,
            "code": code,
            "firms": {"current": {"present": False, "state": "ABSENT"}},
            "dmc": {"current": {"present": False, "state": "ABSENT"}},
            "attempt1": {"preserve": True},
            "docker": {"status": "UNKNOWN", "observed_at": utc_now_iso()},
            "n8n": {"status": "UNKNOWN", "schedule_enabled": False},
            "bridge": {"status": "UNKNOWN"},
            "credentials": creds,
            "policy": {
                "human_authorization": False,
                "telegram_authorization": False,
                "schedule_authorization": False,
            },
            "tests": {},
            "note": "Fresh collection; post-reboot must re-observe.",
        }

    def import_result(self, phase: str, payload: dict[str, Any]) -> dict[str, Any]:
        phase = phase.lower()
        fp = content_hash(payload)
        state = self.run.read_state()
        imports = dict(state.get("import_fingerprints") or {})
        key = f"{phase}:{fp}"
        if imports.get(phase) == fp:
            return {
                "result": "DUPLICATE",
                "phase": phase,
                "fingerprint": fp,
                "note": "Identical evidence already imported — idempotent no-op",
            }
        if phase in imports and imports[phase] != fp:
            raise RuntimeError(
                f"Refusing to overwrite {phase} evidence with different payload "
                f"(existing={imports[phase][:12]}… new={fp[:12]}…)"
            )

        # redact any embedded logs
        payload = dict(payload)
        if "stdout" in payload:
            red, hit = redact_text(payload.get("stdout"))
            payload["stdout"] = red
            payload["stdout_sha256"] = sha256_text(red)
            if hit:
                payload["sanitization_status"] = "PASS"
        if "stderr" in payload:
            red, hit = redact_text(payload.get("stderr"))
            payload["stderr"] = red
            payload["stderr_sha256"] = sha256_text(red)
            if hit and payload.get("sanitization_status") != "QUARANTINE_REFERENCE":
                payload["sanitization_status"] = payload.get("sanitization_status") or "PASS"
        if "sanitization_status" not in payload:
            payload["sanitization_status"] = "PASS"

        out_path = f"imports/{phase}.json"
        self.run.write_json(out_path, payload)

        validators = {
            "firms": (validate_firms_import, Attempt2State.FIRMS_RESULT_PENDING),
            "dmc": (validate_dmc_import, Attempt2State.DMC_RESULT_PENDING),
            "scoring": (validate_scoring_result, Attempt2State.SCORING_READY),
            "bridge": (validate_bridge_result, Attempt2State.BRIDGE_READY),
            "n8n": (validate_n8n_result, Attempt2State.N8N_MANUAL_READY),
        }
        if phase not in validators:
            raise ValueError(f"Unknown phase: {phase}")
        validate_fn, required_state = validators[phase]
        cur = self.run.current_state()
        if cur != required_state:
            raise InvalidTransitionError(cur, required_state)

        # Gate checks for writers
        if phase == "firms":
            if not self.run.read_authorizations()["gates"].get("FIRMS_WRITER_AUTHORIZATION"):
                raise PermissionError("Unauthorized FIRMS writer import")
        if phase == "dmc":
            if not self.run.read_authorizations()["gates"].get("DMC_WRITER_AUTHORIZATION"):
                raise PermissionError("Unauthorized DMC writer import")
        if phase == "n8n":
            if payload.get("telegram_sent") and not self.run.read_authorizations()["gates"].get(
                "TELEGRAM_AUTHORIZATION"
            ):
                raise PermissionError("Telegram without TELEGRAM_AUTHORIZATION")
            if payload.get("schedule_enabled") and not self.run.read_authorizations()["gates"].get(
                "SCHEDULE_AUTHORIZATION"
            ):
                raise PermissionError("Schedule without SCHEDULE_AUTHORIZATION")

        validation = validate_fn(payload)
        self.run.write_json(f"validation/{phase}.json", validation)

        success_map = {
            "firms": (Attempt2State.FIRMS_VALIDATED, Attempt2State.FIRMS_VALIDATION_FAILED),
            "dmc": (Attempt2State.DMC_VALIDATED, Attempt2State.DMC_VALIDATION_FAILED),
            "scoring": (Attempt2State.SCORING_VALIDATED, Attempt2State.SCORING_FAILED),
            "bridge": (Attempt2State.BRIDGE_VALIDATED, Attempt2State.BRIDGE_FAILED),
            "n8n": (Attempt2State.N8N_VALIDATED, Attempt2State.N8N_FAILED),
        }
        ok_state, fail_state = success_map[phase]
        ok = bool(validation.get("operation_success"))
        self.run.set_state(
            ok_state if ok else fail_state,
            event_type="IMPORT_VALIDATE",
            result="PASS" if ok else "FAIL",
            evidence_refs=[out_path, f"validation/{phase}.json"],
            extra={
                "import_fingerprints": {**imports, phase: fp},
                "last_error": None if ok else validation.get("hard_failures"),
            },
        )
        return {"result": "PASS" if ok else "FAIL", "validation": validation, "fingerprint": fp}

    def report(self) -> dict[str, Any]:
        state = self.run.read_state()
        auth = self.run.read_authorizations()
        events = self.run.events.read_all()
        report = {
            "schema_version": 1,
            "run_id": state["run_id"],
            "state": state["state"],
            "code_sha": state.get("code_sha"),
            "expected_code_sha": state.get("expected_code_sha"),
            "dry_run": state.get("dry_run"),
            "gates": auth.get("gates"),
            "acceptance": state.get("acceptance"),
            "event_count": len(events),
            "distinction": {
                "software_operational_acceptance": bool(
                    (state.get("acceptance") or {}).get("software_operational")
                ),
                "scientific_model_validation": False,
            },
            "never_automated": [
                "firms_refresh",
                "dmc_refresh",
                "telegram_send",
                "schedule_enable",
                "jira_write",
                "git_merge",
            ],
            "generated_at": utc_now_iso(),
        }
        path = self.run.write_json("reports/attempt2-report.json", report)
        md = self._render_md(report)
        self.run.write_text("reports/ATTEMPT2-REPORT.md", md)
        return {"report": report, "paths": [str(path), "reports/ATTEMPT2-REPORT.md"]}

    def _render_md(self, report: dict[str, Any]) -> str:
        return (
            f"# Attempt 2 Report — {report['run_id']}\n\n"
            f"- State: `{report['state']}`\n"
            f"- Code SHA: `{report.get('code_sha')}`\n"
            f"- Expected SHA: `{report.get('expected_code_sha')}`\n"
            f"- Dry-run: {report.get('dry_run')}\n"
            f"- Software/operational acceptance: "
            f"{report['distinction']['software_operational_acceptance']}\n"
            f"- Scientific model validation: **false** (never claimed by this operator)\n"
            f"- Events: {report['event_count']}\n"
        )

    def verify_manifest_integrity(self) -> bool:
        """Detect tampering of tracked files vs manifest (except manifest itself)."""
        man = json.loads(self.run.manifest_path.read_text(encoding="utf-8"))
        for rel, expected in (man.get("files") or {}).items():
            path = self.run.root / rel
            if not path.exists():
                return False
            if sha256_file(path) != expected:
                return False
        return True
