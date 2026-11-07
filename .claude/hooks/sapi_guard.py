#!/usr/bin/env python3
"""Best-effort PreToolUse guard; not a sandbox/security boundary."""
import json
import re
import sys

PROTECTED = re.compile(
    r"(?:^|[/\\])(?:artifacts[/\\]hito1|src[/\\](?:refresh|inference|modelo|output)|"
    r"tools[/\\]n8n_bridge|config[/\\]data_plane_rc1\.json|scripts[/\\](?:freeze_check|merge_gate)\.py)"
    r"(?:[/\\]|$)", re.IGNORECASE,
)
# Commands whose approval is intentionally outside this project's autonomous delegation.
DANGEROUS = [
    r"\bgit\s+(?:-C\s+\S+\s+)?(?:push|merge|rebase|reset|clean)\b",
    r"\bgh\s+pr\s+(?:create|merge|close|reopen)\b",
    r"\bdocker\s+(?:volume\s+(?:rm|prune)|system\s+prune)\b",
    r"\bdocker\s+compose\b[^\n;&|]*\bdown\b[^\n;&|]*\s(?:-v|--volumes)\b",
    r"\bterraform\s+(?:apply|destroy)\b",
    r"\bkubectl\s+(?:apply|delete|replace)\b",
    r"\b(?:rm\s+-[A-Za-z]*r[A-Za-z]*f|rm\s+-[A-Za-z]*f[A-Za-z]*r|Remove-Item\b[^\n]*-Recurse)\b",
    r"\b(?:chmod\s+-R|icacls\b[^\n]*\b/grant\b)\b",
    r"\b(?:gh\s+api\s+-X\s+(?:POST|PATCH|PUT|DELETE))\b",
]
PATTERNS = [re.compile(x, re.I) for x in DANGEROUS]
WRITE_SHELL = re.compile(r"(?:\b(?:Set-Content|Add-Content|Out-File|New-Item|Copy-Item|Move-Item|Remove-Item)\b|\b(?:sed\s+-i|tee|cp|mv|rm)\b|(?:^|\s)>{1,2}\s*)", re.I)
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def decide(payload):
    tool = payload.get("tool_name", "")
    args = payload.get("tool_input") or {}
    if not isinstance(args, dict):
        return "Invalid tool input to SAPI guard"
    if tool in WRITE_TOOLS:
        path = str(args.get("file_path", args.get("notebook_path", ""))).replace("/", "\\")
        if PROTECTED.search(path):
            return "SAPI freeze: protected file; needs explicit change control"
        if "\\.claude\\hooks\\" in path.lower() or path.lower().endswith("\\.claude\\settings.json"):
            return "SAPI protection: hook/settings changes require manual review"
    if tool in ("Bash", "PowerShell"):
        cmd = str(args.get("command", ""))
        for pattern in PATTERNS:
            if pattern.search(cmd):
                return "SAPI scope: irreversible/remote/volume command requires manual authorization"
        if PROTECTED.search(cmd) and WRITE_SHELL.search(cmd):
            return "SAPI freeze: potential shell mutation of protected file"
        if re.search(r"\b(?:refresh[_ -]?(?:dmc|firms)|run[_ -]?daily[_ -]?pipeline)\b", cmd, re.I) and re.search(r"\b(?:--live|--real|--publish|--apply|--operational)\b", cmd, re.I):
            return "SAPI operational refresh is not authorized"
    return None


def main():
    try:
        p = json.load(sys.stdin)
        reason = decide(p)
    except Exception:
        reason = "SAPI guard cannot inspect malformed hook request"
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
