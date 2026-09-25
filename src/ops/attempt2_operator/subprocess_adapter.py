"""Bounded subprocess execution for external toolpacks."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from src.ops.attempt2_operator.redaction import redact_text, sha256_text
from src.ops.attempt2_operator.validator_result import ValidatorResult


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


DEFAULT_TIMEOUT_S = 60


def run_tool(
    *,
    tool_name: str,
    command: Sequence[str],
    cwd: Path | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    code_sha: str | None = None,
    output_dir: Path | None = None,
    env: dict[str, str] | None = None,
) -> ValidatorResult:
    """Run a tool with timeout; redact and optionally persist stdout/stderr."""
    started_at = _utc_now()
    cmd_list = [str(c) for c in command]
    try:
        proc = subprocess.run(
            cmd_list,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            env=env,
        )
        finished_at = _utc_now()
        stdout_raw = proc.stdout or ""
        stderr_raw = proc.stderr or ""
        exit_code = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        finished_at = _utc_now()
        stdout_raw = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr_raw = (exc.stderr or "") if isinstance(exc.stderr, str) else "TIMEOUT"
        exit_code = 124
        timed_out = True
    except FileNotFoundError:
        finished_at = _utc_now()
        stdout_raw = ""
        stderr_raw = "executable_not_found"
        exit_code = 127
        timed_out = False
    except OSError as exc:
        finished_at = _utc_now()
        stdout_raw = ""
        stderr_raw = type(exc).__name__
        exit_code = 1
        timed_out = False

    stdout, stdout_secret = redact_text(stdout_raw)
    stderr, stderr_secret = redact_text(stderr_raw)
    evidence: dict[str, Any] = {
        "command": cmd_list,
        "command_identity": " ".join(cmd_list),
        "stdout_sha256": sha256_text(stdout),
        "stderr_sha256": sha256_text(stderr),
        "stdout_redacted": True,
        "stderr_redacted": True,
        "secret_hit": bool(stdout_secret or stderr_secret),
        "timed_out": timed_out,
    }

    stdout_path = stderr_path = None
    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = output_dir / f"{tool_name}.stdout.txt"
        stderr_path = output_dir / f"{tool_name}.stderr.txt"
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        evidence["stdout_path"] = str(stdout_path)
        evidence["stderr_path"] = str(stderr_path)

    parsed: dict[str, Any] | None = None
    warnings: list[str] = []
    failures: list[str] = []
    if timed_out:
        failures.append("timeout")
        status = "FAIL"
    elif exit_code == 127:
        failures.append("executable_not_found")
        status = "FAIL"
    else:
        # Try parse JSON from stdout last non-empty line / whole stdout
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            # not all tools emit JSON; leave INCOMPLETE for parse if expected
            parsed = None
            warnings.append("stdout_not_json")
        if exit_code == 0:
            status = "PASS"
        else:
            status = "FAIL"
            failures.append(f"exit_code_{exit_code}")

    evidence_acceptance = None
    if parsed and isinstance(parsed, dict):
        evidence["parsed"] = {
            k: parsed.get(k)
            for k in (
                "validation_result",
                "operation_result",
                "evidence_capture",
                "hard_failures",
                "status",
            )
            if k in parsed
        }
        evidence_acceptance = parsed.get("validation_result")
        # Keep technical status separate from evidence acceptance
        if evidence_acceptance and status == "PASS" and evidence_acceptance == "REJECTED_EVIDENCE":
            warnings.append("evidence_rejected_but_process_exited_0")

    return ValidatorResult(
        name=tool_name,
        status=status,
        code_sha=code_sha,
        started_at=started_at,
        finished_at=finished_at,
        exit_code=exit_code,
        evidence=evidence,
        warnings=warnings,
        failures=failures,
        evidence_acceptance=evidence_acceptance,
    )


def parse_validator_stdout(stdout: str) -> dict[str, Any] | None:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None
