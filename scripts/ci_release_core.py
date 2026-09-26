"""Release evidence primitives built on the recovered local CI harness."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
from urllib.parse import quote, quote_plus

try:
    from .ci_local import clean_env, sanitize
except ImportError:
    from ci_local import clean_env, sanitize

STATUSES = {"PASS", "FAIL", "INCOMPLETE"}


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def redact(text):
    text = str(text)
    for name, value in os.environ.items():
        if value and re.search(
            r"(?i)(token|password|secret|api_?key|dmc_usuario|authorization|cookie)",
            name,
        ):
            for variant in sorted(
                {value, quote(value, safe=""), quote_plus(value)}, key=len, reverse=True
            ):
                text = text.replace(variant, "[REDACTED]")
    text = re.sub(
        r"(?i)([?&](?:usuario|token|key|api_key)=)[^&\s\"']+", r"\1[REDACTED]", text
    )
    text = re.sub(
        r"(?im)^\s*(?:authorization|cookie|set-cookie)\s*:.*$",
        "[REDACTED header]",
        text,
    )
    return sanitize(text)


def safe(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(value), sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def git(root, *args):
    return (
        subprocess.check_output(
            ["git", "-C", str(root), *args], timeout=30, stderr=subprocess.DEVNULL
        )
        .decode("utf-8")
        .strip()
    )


def resolve(root, requested):
    if not re.fullmatch(r"[0-9a-fA-F]{40}", requested):
        raise ValueError("RC-CODE-SHA: full immutable commit SHA required")
    actual = git(root, "rev-parse", "--verify", requested + "^{commit}")
    if actual.lower() != requested.lower():
        raise ValueError("RC-CODE-SHA: object is not the requested commit")
    return {"sha": actual, "tree": git(root, "rev-parse", actual + "^{tree}")}


def export(root, commit, target):
    """Archive only committed blobs; reject links/submodules and verify each blob."""
    target = Path(target)
    target.mkdir(parents=True, exist_ok=False)
    archive = target.parent / (target.name + ".tar")
    subprocess.run(
        [
            "git",
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.eol=lf",
            "-C",
            str(root),
            "archive",
            "--format=tar",
            "--output",
            str(archive),
            commit,
        ],
        check=True,
        timeout=120,
        capture_output=True,
    )
    with tarfile.open(archive) as stream:
        for item in stream.getmembers():
            if not (item.isfile() or item.isdir()) or not (
                target / item.name
            ).resolve().is_relative_to(target.resolve()):
                raise ValueError("RC-CODE-ARCHIVE: unsafe archive member")
        stream.extractall(target, filter="data")
    entries = git(root, "ls-tree", "-r", "-z", commit).split("\0")
    verified = {}
    for entry in entries:
        if not entry:
            continue
        metadata, name = entry.split("\t", 1)
        mode, kind, expected = metadata.split()
        if kind != "blob" or mode not in ("100644", "100755"):
            raise ValueError("RC-CODE-ARCHIVE: unsupported tracked object")
        data = (target / name).read_bytes()
        actual = hashlib.sha1(
            b"blob " + str(len(data)).encode() + b"\0" + data
        ).hexdigest()
        if actual != expected:
            raise ValueError(
                "RC-CODE-ARCHIVE: exported bytes differ from committed blob"
            )
        verified[name] = hashlib.sha256(data).hexdigest()
    return {
        "method": "git archive + per-blob verification",
        "files": len(verified),
        "content_fingerprint": fingerprint(verified),
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }


class ReleaseRunner:
    def __init__(self, root, output):
        self.root, self.output = Path(root), Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.env = clean_env()
        home = self.output / "isolated-home"
        home.mkdir(exist_ok=True)
        self.env.update(
            HOME=str(home),
            USERPROFILE=str(home),
            BLACK_CACHE_DIR=str(home / "black"),
            PIP_CONFIG_FILE=os.devnull,
        )
        self.steps = []

    def run(self, name, command, required=True, timeout=1200, env=None):
        start = utc()
        import time

        elapsed = time.monotonic()
        try:
            process = subprocess.run(
                command,
                cwd=self.root,
                env=env or self.env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            code, reason = process.returncode, "EXIT"
            status = "PASS" if code == 0 else "FAIL"
            text = process.stdout + process.stderr
        except subprocess.TimeoutExpired:
            code, status, reason, text = (
                None,
                "INCOMPLETE",
                "TIMEOUT",
                "Command exceeded bounded timeout",
            )
        except OSError:
            code, status, reason, text = (
                None,
                "INCOMPLETE",
                "UNAVAILABLE",
                "Command unavailable",
            )
        log = self.output / "logs" / (name + ".log")
        log.parent.mkdir(exist_ok=True)
        log.write_text(redact(text), encoding="utf-8")
        result = {
            "name": name,
            "status": status,
            "required": required,
            "reason": reason,
            "exit_code": code,
            "command": safe(command),
            "start": start,
            "end": utc(),
            "duration": time.monotonic() - elapsed,
            "evidence": {
                "log": str(log.relative_to(self.output)),
                "sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            },
        }
        self.steps.append(result)
        write_json(self.output / "steps" / (name + ".json"), result)
        return result


def aggregate(checks):
    if any(c.get("status") == "FAIL" for c in checks):
        return "FAIL"
    if not checks or any(
        c.get("status") not in STATUSES
        or (c.get("required", True) and c["status"] != "PASS")
        for c in checks
    ):
        return "INCOMPLETE"
    return "PASS"


def quality_delta(baseline, candidate, changed):
    """Multiset debt accounting: line shifts do not hide or invent findings."""
    output = {}
    for tool in ("black", "flake8"):
        before, after = Counter(baseline[tool]), Counter(candidate[tool])
        new, resolved = after - before, before - after
        output[tool] = {
            "baseline": sum(before.values()),
            "absolute": sum(after.values()),
            "new": list(new.elements()),
            "resolved": list(resolved.elements()),
            "changed_file_findings": [
                x for x in after.elements() if x.split("|", 1)[0] in changed
            ],
        }
    output["changed_files"] = sorted(changed)
    output["status"] = (
        "FAIL" if any(output[t]["new"] for t in ("black", "flake8")) else "PASS"
    )
    return output


def stable_result(result):
    """Only explicitly selected content identities; no log hash, clock or temp path."""
    names = (
        "schema_version",
        "candidate",
        "baseline",
        "gate_identity",
        "environment_identity",
        "static_analysis",
        "tests",
        "coverage",
        "sentinels",
        "component_manifests",
        "findings",
        "status",
        "ancestry",
        "handshake",
        "docker",
        "postgis",
        "cache_identity",
    )
    stable = {key: result.get(key) for key in names}
    stable["checks"] = [
        {k: c.get(k) for k in ("id", "status", "required")} for c in result["checks"]
    ]
    return stable


def validate_result(result):
    if result.get("schema_version") != 1 or result.get("kind") != "RC_GATE_RESULT":
        raise ValueError("RC-ENV-RESULT: unsupported schema")
    if result.get("status") not in STATUSES or not isinstance(
        result.get("checks"), list
    ):
        raise ValueError("RC-ENV-RESULT: missing status/checks")
    if aggregate(result["checks"]) != result["status"]:
        raise ValueError("RC-ENV-RESULT: inconsistent aggregation")
    if result.get("stable_result_fingerprint") != fingerprint(stable_result(result)):
        raise ValueError("RC-ENV-RESULT: fingerprint mismatch")
    return result


def reusable(result, identity):
    try:
        validate_result(result)
        return result.get("cache_identity") == identity and result["status"] == "PASS"
    except (KeyError, TypeError, ValueError):
        return False


def compare(left, right):
    validate_result(left)
    validate_result(right)
    keys = (
        "candidate",
        "tests",
        "coverage",
        "static_analysis",
        "sentinels",
        "component_manifests",
        "findings",
        "status",
    )
    return {
        key: {"before": left.get(key), "after": right.get(key)}
        for key in keys
        if left.get(key) != right.get(key)
    }
