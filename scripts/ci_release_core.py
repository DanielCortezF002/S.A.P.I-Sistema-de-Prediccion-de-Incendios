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
import signal
import xml.etree.ElementTree as ET
from urllib.parse import quote, quote_plus

try:
    from .ci_local import clean_env, sanitize, findings
except ImportError:
    from ci_local import clean_env, sanitize, findings

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
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(safe(value), sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


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
        temporary = self.output / "temporary"
        temporary.mkdir(exist_ok=True)
        self.env.update(
            HOME=str(home),
            USERPROFILE=str(home),
            BLACK_CACHE_DIR=str(home / "black"),
            PIP_CONFIG_FILE=os.devnull,
            PIP_CACHE_DIR=str(self.output.parent / "dependency-cache"),
            TEMP=str(temporary),
            TMP=str(temporary),
            TMPDIR=str(temporary),
            APPDATA=str(home / "appdata"),
            LOCALAPPDATA=str(home / "localappdata"),
            XDG_CACHE_HOME=str(home / "cache"),
            XDG_CONFIG_HOME=str(home / "config"),
        )
        self.steps = []

    def run(self, name, command, required=True, timeout=1200, env=None):
        start = utc()
        import time

        elapsed = time.monotonic()
        write_json(
            self.output / "steps" / (name + ".json"),
            {
                "name": name,
                "status": "INCOMPLETE",
                "reason": "RUNNING",
                "start": start,
                "command": safe(command),
                "required": required,
            },
        )
        print(f"[{name}] START", flush=True)
        try:
            process = subprocess.Popen(
                command,
                cwd=self.root,
                env=env or self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                ),
                start_new_session=os.name != "nt",
            )
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                # Kill only the process tree started by this exact Popen handle.
                if process.poll() is None:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            capture_output=True,
                            timeout=15,
                        )
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=15)
                raise
            code, reason = process.returncode, "EXIT"
            status = "PASS" if code == 0 else "FAIL"
            text = stdout + stderr
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


def match_status(actual, expected):
    if actual is None:
        return "INCOMPLETE"
    return "PASS" if actual == expected else "FAIL"


def test_identity(junit):
    cases = []
    for case in ET.parse(junit).getroot().iter("testcase"):
        status = "PASS"
        for tag, state in (
            ("skipped", "SKIP"),
            ("failure", "FAIL"),
            ("error", "ERROR"),
        ):
            if case.find(tag) is not None:
                status = state
        cases.append((case.get("classname", ""), case.get("name", ""), status))
    if not cases:
        raise ValueError("No test identities in report")
    return fingerprint(sorted(cases))


def environment_reusable(receipt, cache_identity, probe):
    return (
        receipt.get("cache_identity") == cache_identity
        and probe.get("status") == "PASS"
        and probe.get("evidence", {}).get("sha256") is not None
        and probe["evidence"]["sha256"] == receipt.get("packages_sha256")
    )


def seal_reports(output):
    """Redact generated reports only, never candidate sources or environments."""
    paths = [
        p
        for p in output.iterdir()
        if p.is_file() and p.suffix in (".json", ".xml", ".txt")
    ]
    for directory, pattern in (("logs", "*.log"), ("steps", "*.json")):
        paths.extend((output / directory).glob(pattern))
    unresolved = []
    for path in paths:
        original = path.read_text(encoding="utf-8")
        cleaned = redact(original)
        if original != cleaned:
            path.write_text(cleaned, encoding="utf-8")
        unresolved.extend(findings(path.relative_to(output), cleaned))
    return {
        "status": "FAIL" if unresolved else "PASS",
        "reports": len(paths),
        "finding_rules": sorted({f["rule"] for f in unresolved}),
    }


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
    required = (
        "candidate",
        "baseline",
        "gate_identity",
        "environment_identity",
        "findings",
        "tests",
        "coverage",
        "sentinels",
        "component_manifests",
        "authorization",
        "remote_github_ci",
    )
    if any(key not in result for key in required):
        raise ValueError("RC-ENV-RESULT: missing required result fields")
    if (
        result["authorization"] is not False
        or result["remote_github_ci"] != "NOT VERIFIED"
    ):
        raise ValueError("RC-ENV-RESULT: unsupported authorization or remote claim")
    for key in ("candidate", "baseline"):
        value = result[key]
        if not isinstance(value, dict) or (
            value
            and (
                set(value) != {"sha", "tree"}
                or any(
                    not re.fullmatch(r"[0-9a-f]{40}", str(value[k]))
                    for k in ("sha", "tree")
                )
            )
        ):
            raise ValueError("RC-ENV-RESULT: malformed code identity")
    if result.get("schema_version") != 1 or result.get("kind") != "RC_GATE_RESULT":
        raise ValueError("RC-ENV-RESULT: unsupported schema")
    if result.get("status") not in STATUSES or not isinstance(
        result.get("checks"), list
    ):
        raise ValueError("RC-ENV-RESULT: missing status/checks")
    if aggregate(result["checks"]) != result["status"]:
        raise ValueError("RC-ENV-RESULT: inconsistent aggregation")
    if any(
        not isinstance(c.get("id"), str)
        or c.get("status") not in STATUSES
        or not isinstance(c.get("required"), bool)
        for c in result["checks"]
    ):
        raise ValueError("RC-ENV-RESULT: invalid check schema")
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
