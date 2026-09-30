"""Assemble QuiescenceResult and evaluate QUIESCENT / NOT_QUIESCENT / INCOMPLETE."""

from __future__ import annotations

from typing import Any

from src.ops.attempt2_operator.quiescence.findings import (
    FINDING_PRIORITY,
    FINDING_REMEDIATION,
    QG_ACTIVE_DMC_LOCK,
    QG_ACTIVE_FIRMS_LOCK,
    QG_ACTIVE_N8N_EXECUTION,
    QG_ACTIVE_WRITER,
    QG_BRIDGE_MUST_BE_STOPPED,
    QG_CONFLICTING_SERVICE,
    QG_ENABLED_SCHEDULE,
    QG_N8N_MUST_BE_STOPPED,
    QG_SCHEDULE_UNKNOWN,
    QG_STALE_LOCK,
    QG_TELEGRAM_ARMED,
    QG_TELEGRAM_UNKNOWN,
    QG_UNKNOWN_LOCK_STATE,
    QG_UNKNOWN_N8N_STATE,
    QG_UNKNOWN_WRITER_STATE,
    QG_WEB_MUST_BE_STOPPED,
)
from src.ops.attempt2_operator.quiescence.locks import (
    ACTIVE_LOCK,
    NO_LOCK,
    STALE_LOCK,
    UNKNOWN as LOCK_UNKNOWN,
)
from src.ops.attempt2_operator.quiescence.policy import QuiescencePolicy
from src.ops.attempt2_operator.quiescence.writers import (
    WRITER_ACTIVE,
    WRITER_NOT_DETECTED,
    WRITER_UNKNOWN,
)

QUIESCENT = "QUIESCENT"
NOT_QUIESCENT = "NOT_QUIESCENT"
INCOMPLETE = "INCOMPLETE"


def _finding(fid: str, severity: str, detail: str) -> dict[str, str]:
    return {
        "id": fid,
        "severity": severity,
        "detail": detail,
        "remediation": FINDING_REMEDIATION.get(
            fid, "Resolve finding, then rerun preflight."
        ),
    }


def evaluate_quiescence(
    *,
    processes: dict[str, Any],
    writers: dict[str, Any],
    locks: dict[str, Any],
    n8n: dict[str, Any],
    bridge: dict[str, Any],
    web: dict[str, Any],
    policy: QuiescencePolicy | None = None,
    observed_at_start: str,
    observed_at_end: str,
) -> dict[str, Any]:
    """Return canonical QuiescenceResult. UNKNOWN never becomes QUIESCENT."""
    policy = policy or QuiescencePolicy.from_env()
    findings: list[dict[str, str]] = []
    warnings: list[str] = []
    failures: list[str] = []

    # --- Writers ---
    wstatus = writers.get("status")
    if wstatus == WRITER_ACTIVE:
        failures.append("active_writer")
        findings.append(
            _finding(QG_ACTIVE_WRITER, "NOT_QUIESCENT", "protected_writer_running")
        )
    elif wstatus == WRITER_UNKNOWN:
        warnings.append("unknown_writer_state")
        findings.append(
            _finding(QG_UNKNOWN_WRITER_STATE, "INCOMPLETE", "writer_visibility_unknown")
        )

    # --- Locks ---
    firms = locks.get("firms") or {}
    dmc = locks.get("dmc") or {}
    for side, block, qg_active in (
        ("firms", firms, QG_ACTIVE_FIRMS_LOCK),
        ("dmc", dmc, QG_ACTIVE_DMC_LOCK),
    ):
        cls = block.get("classification")
        if cls == ACTIVE_LOCK:
            failures.append(f"active_{side}_lock")
            findings.append(_finding(qg_active, "NOT_QUIESCENT", f"{side}_lock_active"))
        elif cls == STALE_LOCK:
            failures.append(f"stale_{side}_lock")
            findings.append(
                _finding(QG_STALE_LOCK, "NOT_QUIESCENT", f"{side}_lock_stale")
            )
        elif cls == LOCK_UNKNOWN:
            warnings.append(f"unknown_{side}_lock")
            findings.append(
                _finding(QG_UNKNOWN_LOCK_STATE, "INCOMPLETE", f"{side}_lock_unknown")
            )

    # --- n8n activation / executions / schedule / telegram ---
    activation = n8n.get("activation") or {}
    schedule = n8n.get("schedule") or {}
    telegram = n8n.get("telegram") or {}
    execution = n8n.get("execution") or {}
    container_status = n8n.get("container_status")

    if (
        activation.get("status") == "UNKNOWN"
        or activation.get("any_relevant_active") is None
    ):
        # Only required when container is RUNNING or policy allows running-if-inactive
        if container_status == "RUNNING" or policy.allow_n8n_running_if_inactive:
            warnings.append("unknown_n8n_state")
            findings.append(
                _finding(QG_UNKNOWN_N8N_STATE, "INCOMPLETE", "n8n_activation_unknown")
            )
    elif activation.get("any_relevant_active") is True:
        # Active workflow while we expect quiescence
        if policy.n8n_container == "MUST_BE_STOPPED" and container_status == "RUNNING":
            pass  # covered by MUST_BE_STOPPED finding below
        else:
            failures.append("active_n8n_workflow")
            findings.append(
                _finding(
                    QG_CONFLICTING_SERVICE, "NOT_QUIESCENT", "relevant_workflow_active"
                )
            )

    if execution.get("state") == "RUNNING":
        failures.append("active_n8n_execution")
        findings.append(
            _finding(QG_ACTIVE_N8N_EXECUTION, "NOT_QUIESCENT", "n8n_execution_running")
        )
    elif execution.get("state") == "UNKNOWN" or execution.get("status") == "UNKNOWN":
        if container_status == "RUNNING":
            warnings.append("unknown_n8n_execution")
            findings.append(
                _finding(QG_UNKNOWN_N8N_STATE, "INCOMPLETE", "n8n_execution_unknown")
            )

    sched_state = schedule.get("state")
    if sched_state == "SCHEDULE_ENABLED":
        failures.append("enabled_schedule")
        findings.append(
            _finding(QG_ENABLED_SCHEDULE, "NOT_QUIESCENT", "schedule_enabled")
        )
    elif sched_state == "UNKNOWN" or schedule.get("status") == "UNKNOWN":
        if container_status in ("RUNNING", "STOPPED"):
            # When stopped without DB we already marked UNKNOWN — incomplete
            warnings.append("schedule_unknown")
            findings.append(
                _finding(
                    QG_SCHEDULE_UNKNOWN, "INCOMPLETE", "schedule_visibility_unknown"
                )
            )

    tg_state = telegram.get("state")
    if tg_state == "ARMED":
        failures.append("telegram_armed")
        findings.append(
            _finding(QG_TELEGRAM_ARMED, "NOT_QUIESCENT", "telegram_path_armed")
        )
    elif tg_state == "UNKNOWN" or telegram.get("status") == "UNKNOWN":
        warnings.append("telegram_unknown")
        findings.append(
            _finding(QG_TELEGRAM_UNKNOWN, "INCOMPLETE", "telegram_visibility_unknown")
        )

    # --- Container policy ---
    if policy.n8n_container == "MUST_BE_STOPPED":
        if container_status == "RUNNING":
            failures.append("n8n_must_be_stopped")
            findings.append(
                _finding(
                    QG_N8N_MUST_BE_STOPPED,
                    "NOT_QUIESCENT",
                    "policy_requires_n8n_stopped",
                )
            )
        elif container_status == "UNKNOWN":
            warnings.append("n8n_container_unknown")
            findings.append(
                _finding(QG_UNKNOWN_N8N_STATE, "INCOMPLETE", "n8n_container_unknown")
            )
    elif policy.allow_n8n_running_if_inactive and container_status == "RUNNING":
        # Require proven inactive + schedule off + telegram disarmed + no exec
        needed_ok = (
            activation.get("any_relevant_active") is False
            and sched_state in ("SCHEDULE_DISABLED", "SCHEDULE_NOT_PRESENT")
            and tg_state == "DISARMED"
            and execution.get("state") == "NOT_RUNNING"
        )
        if activation.get("status") != "READY" or not needed_ok:
            if activation.get("any_relevant_active") is True:
                failures.append("n8n_active_while_running_policy")
                findings.append(
                    _finding(
                        QG_CONFLICTING_SERVICE,
                        "NOT_QUIESCENT",
                        "n8n_running_with_active_workflow",
                    )
                )
            elif not needed_ok:
                warnings.append("n8n_running_unproven_safe")
                findings.append(
                    _finding(
                        QG_UNKNOWN_N8N_STATE,
                        "INCOMPLETE",
                        "n8n_running_safety_not_proven",
                    )
                )

    if policy.bridge == "MUST_BE_STOPPED":
        bstat = bridge.get("status")
        if bstat == "RUNNING":
            failures.append("bridge_must_be_stopped")
            findings.append(
                _finding(QG_BRIDGE_MUST_BE_STOPPED, "NOT_QUIESCENT", "bridge_running")
            )
        elif bstat == "UNKNOWN":
            warnings.append("bridge_unknown")
            findings.append(
                _finding(QG_CONFLICTING_SERVICE, "INCOMPLETE", "bridge_state_unknown")
            )

    if policy.web == "MUST_BE_STOPPED":
        wstat = web.get("status")
        if wstat == "RUNNING":
            failures.append("web_must_be_stopped")
            findings.append(
                _finding(QG_WEB_MUST_BE_STOPPED, "NOT_QUIESCENT", "web_running")
            )
        elif wstat == "UNKNOWN":
            warnings.append("web_unknown")
            findings.append(
                _finding(QG_CONFLICTING_SERVICE, "INCOMPLETE", "web_state_unknown")
            )

    # Deduplicate findings by id (keep first)
    seen: set[str] = set()
    uniq: list[dict[str, str]] = []
    for f in findings:
        if f["id"] in seen:
            continue
        seen.add(f["id"])
        uniq.append(f)
    order = {fid: i for i, fid in enumerate(FINDING_PRIORITY)}
    uniq.sort(key=lambda f: order.get(f["id"], 999))

    if failures:
        status = NOT_QUIESCENT
    elif warnings or any(f["severity"] == "INCOMPLETE" for f in uniq):
        status = INCOMPLETE
    elif wstatus == WRITER_NOT_DETECTED and locks.get("overall") == NO_LOCK:
        # Require known-safe n8n/telegram/schedule when MUST_BE_STOPPED and stopped
        if policy.n8n_container == "MUST_BE_STOPPED" and container_status == "STOPPED":
            # When stopped, schedule/telegram UNKNOWN without DB stays INCOMPLETE
            if any(
                x.get("state") == "UNKNOWN" or x.get("status") == "UNKNOWN"
                for x in (schedule, telegram, activation)
            ):
                status = INCOMPLETE
            else:
                status = QUIESCENT
        elif (
            policy.allow_n8n_running_if_inactive
            and container_status == "RUNNING"
            and activation.get("any_relevant_active") is False
            and sched_state in ("SCHEDULE_DISABLED", "SCHEDULE_NOT_PRESENT")
            and tg_state == "DISARMED"
            and execution.get("state") == "NOT_RUNNING"
        ):
            status = QUIESCENT
        elif container_status == "STOPPED" and tg_state == "DISARMED":
            status = QUIESCENT
        else:
            status = INCOMPLETE
    else:
        status = INCOMPLETE

    # Hard rule: UNKNOWN never QUIESCENT
    if status == QUIESCENT and any(f["severity"] == "INCOMPLETE" for f in uniq):
        status = INCOMPLETE
    if status == QUIESCENT and (
        wstatus == WRITER_UNKNOWN
        or locks.get("overall") == LOCK_UNKNOWN
        or tg_state == "UNKNOWN"
        or sched_state == "UNKNOWN"
        or execution.get("state") == "UNKNOWN"
        or activation.get("status") == "UNKNOWN"
    ):
        status = INCOMPLETE

    highest = uniq[0] if uniq else None
    return {
        "schema_version": 1,
        "observed_at_start": observed_at_start,
        "observed_at_end": observed_at_end,
        "processes": processes,
        "writers": writers,
        "locks": locks,
        "n8n": n8n,
        "schedule": schedule,
        "telegram": telegram,
        "bridge": {
            **bridge,
            "policy": policy.bridge,
        },
        "web": {
            **web,
            "policy": policy.web,
        },
        "policy": {
            "n8n_container": policy.n8n_container,
            "bridge": policy.bridge,
            "web": policy.web,
            "allow_n8n_running_if_inactive": policy.allow_n8n_running_if_inactive,
            "source": "docs/ops/FIRST-CONTROLLED-REFRESH.md",
        },
        "findings": uniq,
        "warnings": warnings,
        "failures": failures,
        "highest_priority_finding": highest,
        "status": status,
        "mutations": False,
        "note": "Read-only gate. UNKNOWN!=QUIESCENT. No auto-remediation.",
    }


def remediation_for(result: dict[str, Any]) -> dict[str, str]:
    top = result.get("highest_priority_finding") or {}
    fid = top.get("id") or "QUIESCENCE_BLOCKED"
    return {
        "reason_code": fid,
        "next": top.get("remediation")
        or FINDING_REMEDIATION.get(
            fid, "Resolve quiescence finding, then rerun preflight."
        ),
    }
