"""Independent producer-recipe verification of supplied immutable plane evidence."""

import hashlib
import json
import re
import subprocess

try:
    from .ci_release_core import fingerprint, git, resolve
except ImportError:
    from ci_release_core import fingerprint, git, resolve


def blob(repo, revision, path):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid component SHA")
    if path.startswith(("/", "\\")) or ".." in path.split("/") or ":" in path:
        raise ValueError("Invalid source path")
    return subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{revision}:{path}"],
        timeout=30,
        stderr=subprocess.DEVNULL,
    )


def ancestry(repo, candidate, required):
    result = {}
    for name, sha in required.items():
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            result[name] = {"sha": sha, "status": "FAIL"}
            continue
        try:
            git(repo, "merge-base", "--is-ancestor", sha, candidate)
            state = "PASS"
        except subprocess.SubprocessError:
            state = "FAIL"
        result[name] = {"sha": sha, "status": state}
    return result


def verify_data(document, repo, candidate, expected=None):
    body = document["identity"]
    claimed = document["fingerprint"]
    if (
        document["schema_version"] != 1
        or body["schema_version"] != 1
        or body["kind"] != "DATA_PLANE_MANIFEST"
        or fingerprint(body) != claimed
        or (expected is not None and claimed != expected)
    ):
        raise ValueError("Data manifest schema/fingerprint")
    origin = body["code_identity"]["sha"]
    if (
        body["code_identity"]["clean"] is not True
        or body["code_identity"]["tree"] != resolve(repo, origin)["tree"]
    ):
        raise ValueError("Data producer commit/tree identity mismatch")
    policy = json.loads(blob(repo, origin, "config/data_plane_rc1.json"))
    if (
        fingerprint(policy) != body["policy_sha256"]
        or body["components"] != policy["components"]
    ):
        raise ValueError("Data component policy mismatch")
    if (
        body["data_readiness_status"] != "PREPARED"
        or body["findings"]
        or body["current_state"] != policy["expected_current"]
        or body["authorizations"]
        != {k: False for k in ("attempt2", "writers", "telegram", "schedule")}
        or body["data_ready_for_scoring"] != "NOT_EVALUATED"
    ):
        raise ValueError("Data readiness is not preparation evidence")
    for name in ("model", "baseline"):
        if (
            body[name]["status"] != "PASS"
            or body[name]["sha256"] != policy[name]["sha256"]
        ):
            raise ValueError("Data artifact identity mismatch")
    topography = body["topography"]
    if (
        topography["status"] != "PASS"
        or topography["table_sha256"] != policy["topography"]["table_sha256"]
        or topography["grid_sha256"] != policy["topography"]["grid_sha256"]
    ):
        raise ValueError("Topography identity mismatch")
    if {p: v["sha256"] for p, v in topography["files"].items()} != policy["topography"][
        "files"
    ]:
        raise ValueError("Topography files mismatch")
    required = {
        "data": origin,
        **{name: value["sha"] for name, value in body["components"].items()},
    }
    reachable = ancestry(repo, candidate, required)
    if any(v["status"] != "PASS" for v in reachable.values()):
        raise ValueError("Candidate lacks Data history")
    return {
        "status": "PASS",
        "fingerprint": claimed,
        "producer_sha": origin,
        "readiness": "PREPARED",
        "authorization": False,
        "ancestry": reachable,
    }


def verify_output(document, repo, candidate, expected=None):
    body = {k: v for k, v in document.items() if k != "manifest_fingerprint"}
    actual = hashlib.sha256(
        json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    if (
        document["manifest_schema_version"] != "sapi-output-plane-manifest-v1"
        or actual != document["manifest_fingerprint"]
        or (expected and actual != expected)
    ):
        raise ValueError("Output manifest schema/fingerprint")
    code = document["output_code"]
    if (
        code["output_sources_clean"] is not True
        or document["readiness"]["status"] != "READY"
    ):
        raise ValueError("Output readiness not verified")
    if not document["readiness"]["checks"] or any(
        c["status"] != "PASS" for c in document["readiness"]["checks"]
    ):
        raise ValueError("Output checks incomplete")
    if not document["authorization"].startswith("NONE:"):
        raise ValueError("Output evidence cannot authorize")

    def source_hash(revision):
        h = hashlib.sha256()
        for path in sorted(code["sources"]):
            raw = blob(repo, revision, path).replace(b"\r\n", b"\n")
            h.update(path.encode() + b"\0" + hashlib.sha256(raw).digest())
        return h.hexdigest()

    origin = code["git_head"]
    if source_hash(origin) != code["sources_sha256"]:
        raise ValueError("Output producer source identity mismatch")
    reachable = ancestry(repo, candidate, {"output": origin})
    if reachable["output"]["status"] != "PASS":
        raise ValueError("Candidate lacks Output history")
    return {
        "status": "PASS",
        "fingerprint": actual,
        "producer_sha": origin,
        "producer_source_hash": code["sources_sha256"],
        "candidate_source_hash": source_hash(candidate),
        "authorization": False,
        "ancestry": reachable,
        "scope": "producer evidence verified; later candidate source changes separately tested",
    }


def verify(kind, path, repo, candidate, expected=None):
    if path is None:
        return {"status": "NOT_AVAILABLE", "required": False}
    try:
        document = json.loads(path.read_bytes())
        if kind == "operations":
            return {
                "status": "INCOMPLETE",
                "reason": "No producer schema registered; use explicit lane SHA ancestry",
            }
        return {"data": verify_data, "output": verify_output}[kind](
            document, repo, candidate, expected
        )
    except (OSError, subprocess.SubprocessError, KeyError, TypeError, ValueError):
        return {
            "status": "FAIL",
            "reason": (
                "Supplied manifest failed producer schema, identity, "
                "readiness or ancestry verification"
            ),
        }
