"""Hooks to invoke existing FIRMS/DMC validators via subprocess adapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from src.ops.attempt2_operator.subprocess_adapter import run_tool
from src.ops.attempt2_operator.tooling_paths import evidence_tools_root
from src.ops.attempt2_operator.validator_result import ValidatorResult


def _write_json(path: Path, obj: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def run_firms_validator_hook(
    *,
    work_dir: Path,
    before: dict[str, Any],
    after: dict[str, Any],
    delta: dict[str, Any],
    command_evidence: dict[str, Any] | None,
    code_sha: str | None,
    timeout_s: float = 60,
) -> ValidatorResult:
    """Validate imported FIRMS evidence — no writer/refresh."""
    tools = evidence_tools_root()
    if tools is None:
        return ValidatorResult.incomplete(
            "firms_validator",
            code_sha=code_sha,
            reason="attempt2_evidence_tools_not_found",
        )

    script = tools / "validate_firms_phase.py"
    if not script.is_file():
        return ValidatorResult.incomplete(
            "firms_validator",
            code_sha=code_sha,
            reason="validate_firms_phase.py_missing",
        )

    inp = work_dir / "firms_validator_inputs"
    out = work_dir / "firms_validator_out.json"
    before_p = _write_json(inp / "before.json", before)
    after_p = _write_json(inp / "after.json", after)
    delta_p = _write_json(inp / "delta.json", delta)
    cmd = [
        sys.executable,
        str(script),
        "--before",
        str(before_p),
        "--after",
        str(after_p),
        "--delta",
        str(delta_p),
        "--output",
        str(out),
    ]
    if command_evidence is not None:
        cmd_p = _write_json(inp / "command.json", command_evidence)
        cmd.extend(["--command-evidence", str(cmd_p)])

    result = run_tool(
        tool_name="firms_validator",
        command=cmd,
        cwd=tools,
        timeout_s=timeout_s,
        code_sha=code_sha,
        output_dir=work_dir / "tool_logs",
    )
    if out.is_file():
        try:
            parsed = json.loads(out.read_text(encoding="utf-8"))
            result.evidence["output_file"] = str(out)
            result.evidence_acceptance = parsed.get("validation_result")
            result.evidence["parsed"] = {
                "validation_result": parsed.get("validation_result"),
                "operation_result": parsed.get("operation_result"),
                "hard_failures": parsed.get("hard_failures"),
            }
            # Tool exited 0 even on REJECTED_EVIDENCE typically
            if result.exit_code == 0 and not result.failures:
                result.status = "PASS"
        except json.JSONDecodeError:
            result.warnings.append("malformed_validator_output")
            if result.status == "PASS":
                result.status = "INCOMPLETE"
    return result


def run_dmc_validator_hook(
    *,
    work_dir: Path,
    before: dict[str, Any],
    after: dict[str, Any],
    delta: dict[str, Any],
    command_evidence: dict[str, Any] | None,
    external: dict[str, Any] | None,
    code_sha: str | None,
    timeout_s: float = 60,
) -> ValidatorResult:
    tools = evidence_tools_root()
    if tools is None:
        return ValidatorResult.incomplete(
            "dmc_validator",
            code_sha=code_sha,
            reason="attempt2_evidence_tools_not_found",
        )
    script = tools / "validate_dmc_phase.py"
    if not script.is_file():
        return ValidatorResult.incomplete(
            "dmc_validator",
            code_sha=code_sha,
            reason="validate_dmc_phase.py_missing",
        )

    inp = work_dir / "dmc_validator_inputs"
    out = work_dir / "dmc_validator_out.json"
    before_p = _write_json(inp / "before.json", before)
    after_p = _write_json(inp / "after.json", after)
    delta_p = _write_json(inp / "delta.json", delta)
    cmd = [
        sys.executable,
        str(script),
        "--before",
        str(before_p),
        "--after",
        str(after_p),
        "--delta",
        str(delta_p),
        "--output",
        str(out),
    ]
    if command_evidence is not None:
        cmd.extend(
            [
                "--command-evidence",
                str(_write_json(inp / "command.json", command_evidence)),
            ]
        )
    if external is not None:
        cmd.extend(
            [
                "--external-dmc-result",
                str(_write_json(inp / "external.json", external)),
            ]
        )

    result = run_tool(
        tool_name="dmc_validator",
        command=cmd,
        cwd=tools,
        timeout_s=timeout_s,
        code_sha=code_sha,
        output_dir=work_dir / "tool_logs",
    )
    if out.is_file():
        try:
            parsed = json.loads(out.read_text(encoding="utf-8"))
            result.evidence["output_file"] = str(out)
            result.evidence_acceptance = parsed.get("validation_result")
            result.evidence["parsed"] = {
                "validation_result": parsed.get("validation_result"),
                "operation_result": parsed.get("operation_result"),
                "hard_failures": parsed.get("hard_failures"),
            }
            if result.exit_code == 0 and not result.failures:
                result.status = "PASS"
        except json.JSONDecodeError:
            result.warnings.append("malformed_validator_output")
            if result.status == "PASS":
                result.status = "INCOMPLETE"
    return result
