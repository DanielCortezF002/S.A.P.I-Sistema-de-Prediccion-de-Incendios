"""Attempt 2 operator workflow — human-gated; no auto writers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.ops.attempt2_operator.canonical import authorize_record
from src.ops.attempt2_operator.data_plane_manifest import verify_data_plane_manifest
from src.ops.attempt2_operator.events import content_hash, sha256_file, utc_now_iso
from src.ops.attempt2_operator.collectors.preflight_collect import collect_real_preflight
from src.ops.attempt2_operator.output_plane_manifest import verify_output_plane_manifest
from src.ops.attempt2_operator.rc_context import RC1ExecutionContext
from src.ops.attempt2_operator.redaction import credential_presence, redact_text, sha256_text
from src.ops.attempt2_operator.workspace_manifest import verify_workspace_manifest
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
from src.ops.attempt2_operator.validator_hooks import (
    run_dmc_validator_hook,
    run_firms_validator_hook,
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
        workspace_manifest: Path | str | None = None,
        data_plane_manifest: Path | str | None = None,
        output_manifest: Path | str | None = None,
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

        ws_fp: str | None = None
        if workspace_manifest:
            ws_path = Path(workspace_manifest)
            ws_ver = verify_workspace_manifest(
                ws_path,
                expected_code_sha=expected_code_sha,
                expected_workspace_root=repo,
            )
            if ws_ver.get("status") != "PASS" and not dry_run:
                findings_msg = "; ".join(f.get("message", "") for f in ws_ver.get("findings", []))
                raise ValueError(f"Workspace manifest verification failed: {findings_msg}")
            ws_fp = ws_ver.get("manifest_fingerprint")

        dm_fp: str | None = None
        if data_plane_manifest:
            dm_ver = verify_data_plane_manifest(data_plane_manifest, expected_code_sha=expected_code_sha)
            # PREPARED is the highest valid producer state (producer never emits READY).
            # Accept PREPARED for fingerprint recording; execution gates remain at
            # preflight + explicit human authorization (not here).
            # Producer-invalid manifests (FAIL / INCOMPLETE / NOT_AVAILABLE) are blocked.
            if dm_ver.get("prepared") is not True and not dry_run:
                findings_msg = "; ".join(f.get("message", "") for f in dm_ver.get("findings", []))
                raise ValueError(f"Data plane manifest verification failed: {findings_msg}")
            dm_fp = dm_ver.get("manifest_fingerprint")


        op_fp: str | None = None
        if output_manifest:
            op_ver = verify_output_plane_manifest(output_manifest)
            if op_ver.get("status") != "PASS" and not dry_run:
                findings_msg = "; ".join(f.get("message", "") for f in op_ver.get("findings", []))
                raise ValueError(f"Output plane manifest verification failed: {findings_msg}")
            # Never bind an unverified fingerprint into the RC1 execution context.
            op_fp = op_ver.get("manifest_fingerprint") if op_ver.get("status") == "PASS" else None

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

        state = run.read_state()
        state["workspace_manifest_path"] = str(workspace_manifest) if workspace_manifest else None
        state["workspace_manifest_fingerprint"] = ws_fp
        state["data_plane_manifest_path"] = str(data_plane_manifest) if data_plane_manifest else None
        state["data_plane_manifest_fingerprint"] = dm_fp
        state["output_manifest_path"] = str(output_manifest) if output_manifest else None
        state["output_manifest_fingerprint"] = op_fp
        run.write_state(state)

        rc_ctx = RC1ExecutionContext(
            expected_code_sha=expected_code_sha or ident.get("code_sha") or "UNKNOWN",
            run_id=run.run_id,
            operator_code_sha=ident.get("code_sha") or "UNKNOWN",
            workspace_manifest_fingerprint=ws_fp,
            data_plane_manifest_fingerprint=dm_fp,
            output_plane_manifest_fingerprint=op_fp,
        )
        run.write_json("identity/rc1_execution_context.json", rc_ctx.to_dict())

        return cls(run, repo=repo)

    @classmethod
    def open_run(cls, run_dir: Path, *, repo: Path | None = None) -> Attempt2Operator:
        return cls(Attempt2Run.open(run_dir), repo=repo)

    def status(self) -> dict[str, Any]:
        state = self.run.read_state()
        auth = self.run.read_authorizations()
        rc_ctx_file = self.run.root / "identity" / "rc1_execution_context.json"
        rc_ctx = json.loads(rc_ctx_file.read_text(encoding="utf-8")) if rc_ctx_file.is_file() else None
        return {
            "run_id": state["run_id"],
            "state": state["state"],
            "code_sha": state.get("code_sha"),
            "expected_code_sha": state.get("expected_code_sha"),
            "dry_run": state.get("dry_run"),
            "workspace_manifest_fingerprint": state.get("workspace_manifest_fingerprint"),
            "data_plane_manifest_fingerprint": state.get("data_plane_manifest_fingerprint"),
            "rc_execution_context": rc_ctx,
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
            # ONE next action from highest-priority blocking reason
            pf_path = self.run.root / "preflight" / "preflight.json"
            reason_code = "PREFLIGHT_FAILED"
            detail = "Fix preflight failures, then re-run preflight"
            if pf_path.is_file():
                try:
                    pf = json.loads(pf_path.read_text(encoding="utf-8"))
                    top = pf.get("highest_priority_reason") or {}
                    if top.get("remediation"):
                        reason_code = top.get("code") or reason_code
                        detail = top["remediation"]
                    elif top.get("code"):
                        reason_code = top["code"]
                        detail = (
                            f"Address {reason_code} ({top.get('detail')}), "
                            "then re-run preflight"
                        )
                    # Quiescence finding may be nested
                    q = pf.get("quiescence") or {}
                    qtop = q.get("highest_priority_finding") or {}
                    if q.get("status") in ("NOT_QUIESCENT", "INCOMPLETE") and qtop.get(
                        "remediation"
                    ):
                        # Prefer quiescence remediation when that blocks
                        if (top.get("code") or "").startswith("QG-") or top.get(
                            "code"
                        ) in (
                            "OPERATIONAL_NOT_QUIESCENT",
                            "OPERATIONAL_QUIESCENCE_INCOMPLETE",
                        ):
                            reason_code = qtop.get("id") or reason_code
                            detail = qtop["remediation"]
                except (OSError, json.JSONDecodeError):
                    pass
            return {
                "state": st.value,
                "next": detail,
                "reason_code": reason_code,
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
        workspace_manifest: Path | str | None = None,
        data_plane_manifest: Path | str | None = None,
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

        ws_man = workspace_manifest or state.get("workspace_manifest_path")
        dm_man = data_plane_manifest or state.get("data_plane_manifest_path")
        if workspace_manifest or data_plane_manifest:
            state = self.run.read_state()
            if workspace_manifest:
                state["workspace_manifest_path"] = str(workspace_manifest)
            if data_plane_manifest:
                state["data_plane_manifest_path"] = str(data_plane_manifest)
            self.run.write_state(state)
        else:
            state = self.run.read_state()

        if snapshot is None:
            snapshot = self._collect_preflight(
                refresh_runtime=refresh_runtime,
                workspace_manifest=ws_man,
                data_plane_manifest=dm_man,
            )
        else:
            # still stamp observed_at if missing on code block
            code = dict(snapshot.get("code") or {})
            if refresh_runtime or not code.get("observed_at"):
                code["observed_at"] = utc_now_iso()
            snapshot = dict(snapshot)
            snapshot["code"] = code

        # Update RC1 execution context with any discovered fingerprints
        ws_info = snapshot.get("workspace_manifest") or {}
        ws_fp = ws_info.get("fingerprint") or ws_info.get("manifest_fingerprint") or state.get("workspace_manifest_fingerprint")
        dm_info = snapshot.get("data_plane") or {}
        dm_fp = dm_info.get("manifest_fingerprint") or state.get("data_plane_manifest_fingerprint")
        if ws_fp or dm_fp:
            state = self.run.read_state()
            if ws_fp:
                state["workspace_manifest_fingerprint"] = ws_fp
            if dm_fp:
                state["data_plane_manifest_fingerprint"] = dm_fp
            self.run.write_state(state)
            rc_ctx_file = self.run.root / "identity" / "rc1_execution_context.json"
            if rc_ctx_file.is_file():
                try:
                    ctx_data = json.loads(rc_ctx_file.read_text(encoding="utf-8"))
                    if ws_fp:
                        ctx_data["workspace_manifest_fingerprint"] = ws_fp
                    if dm_fp:
                        ctx_data["data_plane_manifest_fingerprint"] = dm_fp
                    self.run.write_json("identity/rc1_execution_context.json", ctx_data)
                except Exception:
                    pass

        self.run.write_json("preflight/attempt2-preflight.snapshot.json", snapshot)
        # Canonical Phase-2 preflight object (same content, explicit name)
        self.run.write_json("preflight/preflight.json", snapshot)
        result = validate_preflight_snapshot(
            snapshot, expected_code_sha=state.get("expected_code_sha")
        )
        # Fold overall_status from real collector if present.
        # INCOMPLETE (e.g. workspace_safety NOT_AVAILABLE) must never become PASS.
        if snapshot.get("overall_status") in ("FAIL", "INCOMPLETE") and result.get(
            "ready_for_authorization"
        ):
            overall = snapshot["overall_status"]
            result = {
                **result,
                "ready_for_authorization": False,
                "technical_result": overall,
            }
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
                    "preflight/preflight.json",
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
                    "preflight/preflight.json",
                    "preflight/attempt2-preflight.validation.json",
                ],
            )
        return result

    def _collect_preflight(
        self,
        *,
        refresh_runtime: bool,
        workspace_manifest: Path | str | None = None,
        data_plane_manifest: Path | str | None = None,
    ) -> dict[str, Any]:
        """Fresh read-only collectors — never reuse old evidence as live facts."""
        state = self.run.read_state()
        repo = self.repo
        if repo is None and not state.get("dry_run"):
            repo = Path.cwd()
        ws_manifest = workspace_manifest or state.get("workspace_manifest_path")
        dm_manifest = data_plane_manifest or state.get("data_plane_manifest_path")
        if repo is not None:
            return collect_real_preflight(
                repo=Path(repo),
                run_id=state["run_id"],
                expected_code_sha=state.get("expected_code_sha"),
                workspace_manifest_path=ws_manifest,
                data_plane_manifest_path=dm_manifest,
            )
        # dry-run without repo: synthetic ABSENT currents (explicit, not UNKNOWN)
        return {
            "schema_version": 1,
            "run_id": state["run_id"],
            "expected_code_sha": state.get("expected_code_sha"),
            "observed_code_sha": state.get("code_sha"),
            "tree_sha": state.get("tree_sha"),
            "dirty": False,
            "code": {
                "head_sha": state.get("code_sha"),
                "tree_sha": state.get("tree_sha"),
                "worktree_clean": True,
                "status_entries": [],
                "expected_main_sha": state.get("expected_code_sha"),
                "observed_at": utc_now_iso(),
            },
            "firms": {"current": {"state": "ABSENT", "known": True, "present": False}},
            "dmc": {"current": {"state": "ABSENT", "known": True, "present": False}},
            "firms_current_state": "ABSENT",
            "dmc_current_state": "ABSENT",
            "stores": {},
            "artifacts": {"overall_status": "INCOMPLETE"},
            "credentials": {"credentials": []},
            "runtime": {
                "docker": {"status": "UNKNOWN", "observed_at": utc_now_iso()},
                "n8n": {"status": "UNKNOWN", "observed_at": utc_now_iso()},
                "bridge": {"status": "UNKNOWN", "observed_at": utc_now_iso()},
            },
            "workspace_safety": {"status": "NOT_AVAILABLE"},
            "tool_results": [],
            "warnings": ["dry_run_without_repo"],
            "failures": [],
            "overall_status": "INCOMPLETE",
            "observed_at": utc_now_iso(),
            "attempt1": {"preserve": True},
            "docker": {"status": "UNKNOWN", "observed_at": utc_now_iso()},
            "policy": {"human_authorization": False},
            "tests": {},
            "note": "Dry-run synthetic fallback; real collectors require --repo",
        }

    def _enforce_import_binding(self, phase: str, payload: dict[str, Any]) -> None:
        state = self.run.read_state()
        run_id = state["run_id"]
        expected_sha = state.get("expected_code_sha")
        observed_sha = state.get("code_sha")

        if payload.get("run_id") and payload["run_id"] != run_id:
            raise RuntimeError(f"wrong_run: payload.run_id={payload.get('run_id')} != {run_id}")
        step = payload.get("step") or payload.get("phase")
        allowed_steps = {
            phase,
            f"{phase}_writer",
            f"02-{phase}",
            f"03-{phase}",
            f"02-{phase.upper()}",
            f"03-{phase.upper()}",
        }
        if step and str(step).lower() not in {s.lower() for s in allowed_steps}:
            raise RuntimeError(f"wrong_step: payload.step={step} expected={phase}")
        code_sha = payload.get("code_sha")
        if code_sha and expected_sha and code_sha.lower() != str(expected_sha).lower():
            raise RuntimeError(
                f"stale_or_wrong_sha: payload.code_sha={code_sha} expected={expected_sha}"
            )
        for req in ("started_at", "finished_at", "exit_code"):
            if phase in ("firms", "dmc") and req not in payload:
                raise RuntimeError(f"missing_binding_field:{req}")

    def accept_output_manifest(
        self,
        manifest_path: Path | str,
        *,
        score_artifact_path: Path | str | None = None,
    ) -> dict[str, Any]:
        """Record and verify Output Plane manifest for post-score acceptance."""
        ver = verify_output_plane_manifest(
            manifest_path,
            score_artifact_path=score_artifact_path,
        )
        if ver.get("status") == "FAIL":
            finding_msg = "; ".join(f.get("message", "") for f in ver.get("findings", []))
            raise ValueError(f"Output plane manifest verification failed: {finding_msg}")

        fp = ver.get("manifest_fingerprint")
        state = self.run.read_state()
        state["output_manifest_path"] = str(manifest_path)
        state["output_manifest_fingerprint"] = fp
        state["output_contract_version"] = ver.get("output_contract_version")
        self.run.write_state(state)

        rc_ctx_file = self.run.root / "identity" / "rc1_execution_context.json"
        if rc_ctx_file.is_file():
            try:
                ctx_data = json.loads(rc_ctx_file.read_text(encoding="utf-8"))
                ctx_data["output_plane_manifest_fingerprint"] = fp
                self.run.write_json("identity/rc1_execution_context.json", ctx_data)
            except Exception:
                pass

        self.run.write_json("validation/output_plane_manifest.verification.json", ver)
        return ver

    def import_result(
        self,
        phase: str,
        payload: dict[str, Any],
        *,
        output_manifest: Path | str | None = None,
    ) -> dict[str, Any]:
        if output_manifest is not None:
            self.accept_output_manifest(output_manifest)
        phase = phase.lower()
        state = self.run.read_state()
        payload = dict(payload)
        # Bind identity fields (do not invent secrets)
        payload.setdefault("run_id", state["run_id"])
        payload.setdefault("step", phase)
        payload.setdefault("code_sha", state.get("expected_code_sha") or state.get("code_sha"))
        if "expected_command_identity" not in payload:
            if phase == "firms":
                payload["expected_command_identity"] = "python -m src.refresh.firms_refresh refresh"
            elif phase == "dmc":
                payload["expected_command_identity"] = "python -m src.refresh.dmc_refresh refresh"

        self._enforce_import_binding(phase, payload)

        fp = content_hash(payload)
        imports = dict(state.get("import_fingerprints") or {})
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

        tool_hook = None
        if phase == "firms":
            tool_hook = run_firms_validator_hook(
                work_dir=self.run.root / "validation" / "toolpack",
                before=payload.get("before")
                or {"firms_current": {"present": False}},
                after=payload.get("after")
                or {"firms_current": payload.get("firms_current_after")},
                delta=payload.get("delta")
                or {
                    "firms_current_transition": {
                        "after_present": bool(
                            (payload.get("firms_current_after") or {}).get("present")
                        ),
                        "changed": payload.get("exit_code") == 0,
                    },
                    "baseline_sha_changed": False,
                    "model_sha_changed": False,
                    "hito1_changed": False,
                    "files_added": payload.get("files_added") or [],
                    "files_changed": [],
                    "files_removed": [],
                    "lock_changes": [],
                    "worst_classification": "EXPECTED",
                },
                command_evidence={
                    "exit_code": payload.get("exit_code"),
                    "stdout_sha256": payload.get("stdout_sha256"),
                    "stderr_sha256": payload.get("stderr_sha256"),
                    "sanitization_status": payload.get("sanitization_status"),
                    "metadata": payload.get("metadata") or {},
                },
                code_sha=state.get("code_sha"),
            )
            self.run.write_json(
                "validation/firms_toolpack.json", tool_hook.to_dict()
            )
        elif phase == "dmc":
            tool_hook = run_dmc_validator_hook(
                work_dir=self.run.root / "validation" / "toolpack",
                before=payload.get("before") or {"dmc_current": {"present": False}},
                after=payload.get("after")
                or {"dmc_current": payload.get("dmc_current_after")},
                delta=payload.get("delta")
                or {
                    "dmc_current_transition": {
                        "changed": payload.get("exit_code") == 0,
                        "after_present": bool(
                            (payload.get("dmc_current_after") or {}).get("present")
                        ),
                    },
                    "model_sha_changed": False,
                    "hito1_changed": False,
                    "files_added": [],
                    "files_changed": [],
                    "files_removed": [],
                    "worst_classification": "EXPECTED",
                },
                command_evidence={
                    "exit_code": payload.get("exit_code"),
                    "stdout_sha256": payload.get("stdout_sha256"),
                    "stderr_sha256": payload.get("stderr_sha256"),
                    "sanitization_status": payload.get("sanitization_status"),
                },
                external=payload.get("external"),
                code_sha=state.get("code_sha"),
            )
            self.run.write_json("validation/dmc_toolpack.json", tool_hook.to_dict())

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
        return {
            "result": "PASS" if ok else "FAIL",
            "validation": validation,
            "fingerprint": fp,
            "tool_hook": tool_hook.to_dict() if tool_hook else None,
        }

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
