"""Phase validators used by the operator (synthetic-safe; optional external tools).

Technical PASS/FAIL/INCOMPLETE stay separate from evidence ACCEPTED/REJECTED.
Phase acceptance for the state machine is decided by the operator after explicit
human gates — validators never set human_authorization true.
"""

from __future__ import annotations

from typing import Any

from src.ops.attempt2_operator.canonical import normalize_current
from src.ops.attempt2_operator.events import content_hash
from src.ops.attempt2_operator.states import FIRMS_HARD_EXIT_CODES


def validate_preflight_snapshot(
    snapshot: dict[str, Any],
    *,
    expected_code_sha: str | None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    hard: list[str] = []

    def add(rule: str, status: str, detail: str = "") -> None:
        checks.append({"rule": rule, "status": status, "detail": detail})
        if status == "FAIL":
            hard.append(rule)

    code = snapshot.get("code") or {}
    head = code.get("head_sha")
    if expected_code_sha:
        if head and head.lower() == expected_code_sha.lower():
            add("PF-SHA", "PASS", f"HEAD matches {expected_code_sha}")
        else:
            add("PF-SHA", "FAIL", f"HEAD={head} expected={expected_code_sha}")
    else:
        add("PF-SHA", "INCOMPLETE", "expected_code_sha not provided")

    clean = code.get("worktree_clean")
    if clean is True:
        add("PF-CLEAN", "PASS", "worktree clean")
    elif clean is False:
        add("PF-CLEAN", "FAIL", f"dirty: {code.get('status_entries')}")
    else:
        add("PF-CLEAN", "INCOMPLETE", "worktree_clean unknown")

    # Runtime freshness
    if code.get("observed_at"):
        add("PF-FRESH", "PASS", f"observed_at={code.get('observed_at')}")
    else:
        add("PF-FRESH", "FAIL", "runtime facts missing observed_at")

    firms = normalize_current((snapshot.get("firms") or {}).get("current"))
    dmc = normalize_current((snapshot.get("dmc") or {}).get("current"))
    if firms["state"] == "UNKNOWN":
        add("PF-FIRMS-CURRENT", "INCOMPLETE", "FIRMS CURRENT UNKNOWN (≠ ABSENT)")
    else:
        add("PF-FIRMS-CURRENT", "PASS", f"state={firms['state']}")
    if dmc["state"] == "UNKNOWN":
        add("PF-DMC-CURRENT", "INCOMPLETE", "DMC CURRENT UNKNOWN (≠ ABSENT)")
    else:
        add("PF-DMC-CURRENT", "PASS", f"state={dmc['state']}")

    a1 = snapshot.get("attempt1") or {}
    if a1.get("preserve") is False:
        add("PF-ATTEMPT1", "FAIL", "Attempt1 preservation disabled")
    else:
        add("PF-ATTEMPT1", "PASS", "Attempt1 preservation required")

    # Stale test SHA: if provided tests claim a sha, must match expected
    tests = snapshot.get("tests") or {}
    test_sha = tests.get("code_sha")
    if test_sha and expected_code_sha and test_sha.lower() != expected_code_sha.lower():
        add("PF-TEST-SHA", "FAIL", f"stale test SHA {test_sha}")
    elif test_sha and expected_code_sha:
        add("PF-TEST-SHA", "PASS", "test SHA matches expected")
    else:
        add("PF-TEST-SHA", "PASS", "no test SHA claim")

    docker = (snapshot.get("docker") or {}).get("status", "UNKNOWN")
    if docker not in ("AVAILABLE", "UNAVAILABLE", "UNKNOWN"):
        add("PF-DOCKER", "FAIL", f"invalid docker status {docker}")
    else:
        add("PF-DOCKER", "PASS", docker)

    # Never infer human auth from env/files
    if (snapshot.get("policy") or {}).get("human_authorization") is True:
        add("PF-AUTH-INFER", "FAIL", "snapshot must not claim human_authorization=true")
    else:
        add("PF-AUTH-INFER", "PASS", "human_authorization remains false in snapshot")

    if hard:
        technical = "FAIL"
    elif any(c["status"] == "INCOMPLETE" for c in checks):
        # SHA mismatch is hard; missing expected sha alone can block readiness
        if expected_code_sha is None:
            technical = "INCOMPLETE"
        elif any(c["rule"] == "PF-SHA" and c["status"] == "INCOMPLETE" for c in checks):
            technical = "INCOMPLETE"
        else:
            # UNKNOWN currents are INCOMPLETE but do not alone fail if expected was to observe
            technical = "INCOMPLETE" if any(
                c["rule"] in ("PF-FIRMS-CURRENT", "PF-DMC-CURRENT") and c["status"] == "INCOMPLETE"
                for c in checks
            ) else "PASS"
    else:
        technical = "PASS"

    # For operator readiness: require PF-SHA PASS and PF-CLEAN PASS and no hard fails
    ready = (
        technical == "PASS"
        or (
            not hard
            and any(c["rule"] == "PF-SHA" and c["status"] == "PASS" for c in checks)
            and any(c["rule"] == "PF-CLEAN" and c["status"] == "PASS" for c in checks)
            and not any(
                c["rule"] in ("PF-FIRMS-CURRENT", "PF-DMC-CURRENT") and c["status"] == "INCOMPLETE"
                for c in checks
            )
        )
    )
    # Stricter: UNKNOWN current blocks PREFLIGHT_READY (must be known ABSENT or PRESENT)
    unknown_current = any(
        c["rule"] in ("PF-FIRMS-CURRENT", "PF-DMC-CURRENT") and c["status"] == "INCOMPLETE"
        for c in checks
    )
    sha_ok = any(c["rule"] == "PF-SHA" and c["status"] == "PASS" for c in checks)
    clean_ok = any(c["rule"] == "PF-CLEAN" and c["status"] == "PASS" for c in checks)
    ready = bool(sha_ok and clean_ok and not hard and not unknown_current)

    out = {
        "schema_version": 1,
        "technical_result": "FAIL" if hard else ("INCOMPLETE" if not ready else "PASS"),
        "ready_for_authorization": ready,
        "checks": checks,
        "hard_failures": hard,
        "firms_current": firms,
        "dmc_current": dmc,
        "human_authorization": False,
        "note": "UNKNOWN CURRENT is not ABSENT. PASS≠ACCEPTED_EVIDENCE.",
    }
    out["content_hash"] = content_hash(out)
    return out


def validate_firms_import(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate imported FIRMS writer evidence (does not run refresh)."""
    checks: list[dict[str, Any]] = []
    hard: list[str] = []

    def add(rule: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        checks.append({"rule": rule, "status": status, "detail": detail})
        if not ok:
            hard.append(rule)

    exit_code = payload.get("exit_code")
    add("exit_known", exit_code is not None, f"exit={exit_code}")
    add("stdout_present", payload.get("stdout_sha256") is not None, "")
    add("stderr_present", payload.get("stderr_sha256") is not None, "")
    add("sanitization", payload.get("sanitization_status") == "PASS", str(payload.get("sanitization_status")))

    schema_ok = payload.get("schema_ok", True)
    hash_ok = payload.get("hash_ok", True)
    pointer_ok = payload.get("pointer_ok", True)
    add("schema_ok", bool(schema_ok), "")
    add("hash_ok", bool(hash_ok), "")
    add("pointer_ok", bool(pointer_ok), "")

    after_cur = normalize_current(payload.get("firms_current_after"))
    if after_cur["state"] == "UNKNOWN":
        checks.append(
            {
                "rule": "current_known",
                "status": "FAIL",
                "detail": "after CURRENT UNKNOWN",
            }
        )
        hard.append("current_known")

    # Attempt1 preservation
    if payload.get("attempt1_modified") is True:
        add("attempt1_preserved", False, "Attempt1 evidence modified")
    else:
        add("attempt1_preserved", True, "")

    operation_failed = exit_code in FIRMS_HARD_EXIT_CODES or (
        exit_code not in (None, 0)
    )
    if operation_failed:
        hard.append("operation_exit")
        checks.append(
            {
                "rule": "operation_exit",
                "status": "FAIL",
                "detail": f"exit_code={exit_code}",
            }
        )

    success = (
        exit_code == 0
        and schema_ok
        and hash_ok
        and pointer_ok
        and after_cur["state"] == "PRESENT"
        and payload.get("sanitization_status") == "PASS"
        and not payload.get("attempt1_modified")
    )

    # Evidence quality vs operation
    if operation_failed and not any(
        h in hard for h in ("schema_ok", "hash_ok", "pointer_ok", "attempt1_preserved", "sanitization")
    ):
        evidence = "ACCEPTED_EVIDENCE"  # accepted evidence of failure
    elif hard and not success:
        evidence = "REJECTED_EVIDENCE" if any(
            h in ("schema_ok", "hash_ok", "pointer_ok", "sanitization", "attempt1_preserved")
            for h in hard
        ) else "ACCEPTED_EVIDENCE"
    elif success:
        evidence = "ACCEPTED_EVIDENCE"
    else:
        evidence = "INCOMPLETE_EVIDENCE"

    out = {
        "schema_version": 1,
        "phase": "FIRMS",
        "validation_result": evidence,
        "operation_success": success,
        "checks": checks,
        "hard_failures": sorted(set(hard)),
        "human_authorization": False,
        "phase_accepted": False,
    }
    out["content_hash"] = content_hash(out)
    return out


def validate_dmc_import(payload: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    hard: list[str] = []

    def add(rule: str, ok: bool, detail: str = "") -> None:
        checks.append({"rule": rule, "status": "PASS" if ok else "FAIL", "detail": detail})
        if not ok:
            hard.append(rule)

    exit_code = payload.get("exit_code")
    add("exit_known", exit_code is not None, f"exit={exit_code}")
    add("exit_zero", exit_code == 0, f"exit={exit_code}")
    add("quality_ok", bool(payload.get("quality_ok", False)), "")
    add("pointer_ok", bool(payload.get("pointer_ok", False)), "")
    add("sanitization", payload.get("sanitization_status") == "PASS", "")
    after = normalize_current(payload.get("dmc_current_after"))
    add("current_present", after["state"] == "PRESENT", after["state"])
    add("attempt1_preserved", payload.get("attempt1_modified") is not True, "")

    success = not hard
    if success:
        evidence = "ACCEPTED_EVIDENCE"
    elif exit_code not in (None, 0):
        evidence = "ACCEPTED_EVIDENCE"  # evidence of failed op
    else:
        evidence = "REJECTED_EVIDENCE"
    out = {
        "schema_version": 1,
        "phase": "DMC",
        "validation_result": evidence,
        "operation_success": success,
        "checks": checks,
        "hard_failures": hard,
        "human_authorization": False,
        "phase_accepted": False,
    }
    out["content_hash"] = content_hash(out)
    return out


def validate_scoring_result(payload: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    hard: list[str] = []

    def add(rule: str, ok: bool, detail: str = "") -> None:
        checks.append({"rule": rule, "status": "PASS" if ok else "FAIL", "detail": detail})
        if not ok:
            hard.append(rule)

    cells = payload.get("cells") or []
    add("cells_50", len(cells) == 50, f"n={len(cells)}")
    fp = payload.get("inputs_fingerprint")
    add("fingerprint_live", isinstance(fp, str) and len(fp) == 64, "operational live-input fingerprint")
    frozen = payload.get("frozen_fingerprint")
    # frozen is separate — optional presence but must not be confused
    add(
        "fingerprint_namespaces",
        not (fp and frozen and fp == frozen and payload.get("confuse_fingerprints")),
        "live ≠ frozen unless explicitly same object",
    )
    add("model_sha_known", bool(payload.get("model_sha")), "")
    ranks = [c.get("rank") for c in cells if isinstance(c, dict)]
    add("ranks_1_n", sorted(ranks) == list(range(1, len(cells) + 1)) if cells else False, "")
    scores = [c.get("score") for c in cells if isinstance(c, dict)]
    finite = all(isinstance(s, (int, float)) and s == s and abs(s) != float("inf") for s in scores)
    add("scores_finite", finite and len(scores) == len(cells), "")

    success = not hard
    out = {
        "schema_version": 1,
        "phase": "SCORING",
        "operation_success": success,
        "validation_result": "ACCEPTED_EVIDENCE" if success else "REJECTED_EVIDENCE",
        "checks": checks,
        "hard_failures": hard,
        "human_authorization": False,
        "note": "Does not claim scientific accuracy. Distinguishes live inputs_fingerprint from frozen reproducibility fingerprint.",
    }
    out["content_hash"] = content_hash(out)
    return out


def validate_bridge_result(payload: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    hard: list[str] = []

    def add(rule: str, ok: bool, detail: str = "") -> None:
        checks.append({"rule": rule, "status": "PASS" if ok else "FAIL", "detail": detail})
        if not ok:
            hard.append(rule)

    status = payload.get("http_status")
    add("http_200", status == 200, f"status={status}")
    body = payload.get("body") or {}
    add("status_ok", body.get("status") == "ok", "")
    cells = body.get("cells") or []
    add("cells_50", len(cells) == 50, f"n={len(cells)}")
    add("fingerprint", isinstance(body.get("inputs_fingerprint"), str), "")
    # fail-closed cases for error paths
    if status in (500, 503):
        add("http_200", False, f"error status={status}")
    success = not hard
    out = {
        "schema_version": 1,
        "phase": "BRIDGE",
        "operation_success": success,
        "validation_result": "ACCEPTED_EVIDENCE" if success else "REJECTED_EVIDENCE",
        "checks": checks,
        "hard_failures": hard,
        "human_authorization": False,
        "note": "Validates against active main SHA contract; Claude bridge hardening may be unmerged.",
    }
    out["content_hash"] = content_hash(out)
    return out


def validate_n8n_result(payload: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    hard: list[str] = []

    def add(rule: str, ok: bool, detail: str = "") -> None:
        checks.append({"rule": rule, "status": "PASS" if ok else "FAIL", "detail": detail})
        if not ok:
            hard.append(rule)

    add("manual_only", payload.get("schedule_enabled") is not True, "schedule must be OFF")
    add("telegram_not_sent", payload.get("telegram_sent") is not True, "Telegram must NOT SENT")
    add("score_path_ok", bool(payload.get("score_path_ok")), "")
    # expected fail-closed cases recorded
    cases = payload.get("fail_closed_cases") or {}
    add("case_503_proto", cases.get("prototype_unavailable") is True, "")
    add("case_503_data", cases.get("data_unavailable") is True, "")
    add("case_500", cases.get("internal_error") is True, "")
    if payload.get("telegram_authorized") is True and payload.get("telegram_sent") is True:
        add("telegram_gate", False, "Telegram without separate campaign gate")
    success = not hard
    out = {
        "schema_version": 1,
        "phase": "N8N",
        "operation_success": success,
        "validation_result": "ACCEPTED_EVIDENCE" if success else "REJECTED_EVIDENCE",
        "checks": checks,
        "hard_failures": hard,
        "human_authorization": False,
    }
    out["content_hash"] = content_hash(out)
    return out
