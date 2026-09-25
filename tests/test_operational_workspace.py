"""Tests del materializador del workspace operacional (src/ops/operational_workspace.py).

Solo fixtures sintéticas en tmp_path: un repo Git falso con la forma de SAPI
(stores dentro del checkout, igual que el WIP), CURRENT de ejemplo, archivos
tipo Attempt 1 y un `.env` no versionado. Nunca datos reales.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import src.ops.operational_workspace as ow
from src.ops.operational_workspace import WorkspaceRequest, materialize, plan

GIT = [
    "git",
    "-c",
    "user.name=t",
    "-c",
    "user.email=t@example.invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "core.autocrlf=false",
]
GITIGNORE = (
    ".env\n*.pkl\ndata/raw/*\ndata/processed/*\ndata/predictions/*\n!data/raw/.gitkeep\n"
    "!data/processed/.gitkeep\n!data/predictions/.gitkeep\nmodels/*.pkl\n!models/.gitkeep\n"
    "!models/prototype_model_d.pkl\n"
)
MODEL_BYTES = b"modelo-d-" * 100
FAKE_KEY = "0123456789abcdef0123456789abcdef"  # sintético; forma de MAP_KEY


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [*GIT, "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return path


@pytest.fixture(autouse=True)
def _no_store_overrides(monkeypatch):
    for name in (
        "DATA_RAW_DIR",
        "DATA_PROCESSED_DIR",
        "DATA_PREDICTIONS_DIR",
        "MODELS_DIR",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def wip(tmp_path) -> dict:
    """Checkout 'WIP' con historia, cambios sin commit, .env y stores reales sintéticos."""
    repo = tmp_path / "wip repo"
    repo.mkdir()
    subprocess.run([*GIT, "init", "-q", str(repo)], check=True)
    _write(repo / ".gitignore", GITIGNORE)
    _write(repo / ".env.example", "NASA_FIRMS_API_KEY=your_key_here\nDMC_TOKEN=\n")
    _write(repo / "src/app.py", "print('v1')\n")
    for sub in ("data/raw", "data/processed", "data/predictions", "models"):
        _write(repo / sub / ".gitkeep", "")
    _write(repo / "models/prototype_model_d.pkl", MODEL_BYTES)
    _write(repo / "models/prototype_model_d_metadata.json", '{"model_version": "v1"}\n')
    _git(repo, "add", "-A")
    _git(repo, "add", "-f", "models/prototype_model_d.pkl")
    _git(repo, "commit", "-q", "-m", "c1")
    sha = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    _write(repo / "src/app.py", "print('v2')\n")
    _git(repo, "commit", "-qam", "c2")
    # Estado mutable del WIP que NUNCA debe llegar al workspace.
    _write(repo / "src/app.py", "print('sin commit')\n")
    _write(repo / ".env", f"NASA_FIRMS_API_KEY={FAKE_KEY}\n")
    # Stores sintéticos.
    raw, processed, models = repo / "data/raw", repo / "data/processed", repo / "models"
    _write(raw / "dmc_meteo_2026-09-01.json", '{"330007": []}')
    for i, rows in enumerate((17, 29, 12, 16, 11)):
        _write(
            raw / "firms_refresh/20260924T180743Z/VIIRS_SNPP_NRT" / f"w{i}.csv",
            "latitude,longitude\n" + "-33.1,-71.4\n" * rows,
        )
    _write(processed / "firms/CURRENT.json", '{"schema_version": 3, "sha256": "ab"}\n')
    _write(processed / "firms/versions/firms_x.csv", "a,b\n1,2\n")
    _write(processed / "dmc/330007/CURRENT.json", '{"schema_version": 1}\n')
    _write(processed / "carpeta con espacios/año ñandú.txt", "unicode ok")
    (processed / "empty_dir").mkdir()
    _write(models / "xgboost_optimized.pkl", b"legacy")
    return {
        "repo": repo,
        "sha": sha,
        "tree": tree,
        "head": _git(repo, "rev-parse", "HEAD"),
        "stores": {"raw": raw, "processed": processed, "models": models},
        "dest": tmp_path / "SAPI operational canonical",
    }


def request(w: dict, **kw) -> WorkspaceRequest:
    return WorkspaceRequest(
        repo_root=kw.pop("repo", w["repo"]),
        code_sha=kw.pop("sha", w["sha"]),
        source_stores=kw.pop("stores", w["stores"]),
        destination=kw.pop("dest", w["dest"]),
        margin_bytes=kw.pop("margin_bytes", 0),
        environ=kw.pop("environ", {}),
    )


def ids(result: dict) -> set[str]:
    return {f["id"] for f in result["findings"]}


def run_ok(w: dict, **kw) -> dict:
    req = request(w, **kw)
    return materialize(req, confirm_plan_id=plan(req)["plan_id"])


def fingerprint(root: Path) -> str:
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            p = Path(dirpath, fn)
            st = p.lstat()
            h.update(f"{p.relative_to(root)}|{st.st_size}|{st.st_mtime_ns}|".encode())
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def make_junction(link: Path, target: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("junctions solo en Windows")
    import _winapi

    _winapi.CreateJunction(str(target), str(link))


# --- Plan y SHA -----------------------------------------------------------------------


def test_plan_is_read_only_and_describes_everything(wip, tmp_path):
    before = fingerprint(tmp_path)
    p = plan(request(wip))
    assert fingerprint(tmp_path) == before
    assert p["overall_status"] == "PASS", p["findings"]
    assert p["code"]["tree"] == wip["tree"] and len(p["plan_id"]) == 16
    raw = next(s for s in p["source_stores"] if s["logical_name"] == "raw")
    assert (
        raw["file_count"] == 7 and raw["total_bytes"] > 0
    )  # .gitkeep + dmc json + 5 CSV tipo Attempt 1
    processed = next(s for s in p["source_stores"] if s["logical_name"] == "processed")
    assert set(processed["critical_files"]) == {
        "firms/CURRENT.json",
        "dmc/330007/CURRENT.json",
    }
    assert p["space"]["required_bytes"] >= p["space"]["store_bytes"]
    assert not wip["dest"].exists()


@pytest.mark.parametrize("sha", ["f" * 40, "abc1234", ""])
def test_wrong_or_abbreviated_sha_rejected(wip, sha):
    p = plan(request(wip, sha=sha))
    assert p["overall_status"] == "FAIL" and "MW-001" in ids(p)


def test_exact_sha_extracted_and_dirty_worktree_irrelevant(wip):
    r = run_ok(wip)
    assert r["overall_status"] == "PASS", r["findings"]
    dest = wip["dest"]
    assert (
        dest / "src/app.py"
    ).read_text() == "print('v1')\n"  # c1, no c2 ni el cambio sin commit
    assert _git(dest, "rev-parse", "HEAD") == wip["sha"] != wip["head"]
    assert (
        _git(dest, "rev-list", "--count", "HEAD") == "1" and _git(dest, "remote") == ""
    )
    identity = json.loads((dest / ow.IDENTITY_NAME).read_text(encoding="utf-8"))
    assert identity["sha"] == wip["sha"] and identity["tree"] == wip["tree"]


# --- Topología de fuente y destino -------------------------------------------------------


def test_source_store_junction_is_surfaced_and_internal_reparse_fails(wip, tmp_path):
    alias = tmp_path / "raw_alias"
    make_junction(alias, wip["stores"]["raw"])
    p = plan(request(wip, stores={**wip["stores"], "raw": alias}))
    assert "MW-003" in ids(p) and p["overall_status"] == "PASS"
    assert next(s for s in p["source_stores"] if s["logical_name"] == "raw")[
        "resolved_path"
    ] == os.path.realpath(wip["stores"]["raw"])
    make_junction(wip["stores"]["processed"] / "link_out", tmp_path)
    assert "MW-004" in ids(plan(request(wip)))


def test_destination_reparse_point_rejected(wip, tmp_path):
    real_parent = tmp_path / "real_parent"
    real_parent.mkdir()
    link_parent = tmp_path / "link_parent"
    make_junction(link_parent, real_parent)
    p = plan(request(wip, dest=link_parent / "canonical"))
    assert p["overall_status"] == "FAIL" and "MW-006" in ids(p)


def test_destination_overlapping_repo_or_store_rejected(wip):
    assert "MW-007" in ids(plan(request(wip, dest=wip["repo"] / "canonical")))


def test_insufficient_free_space_rejected_before_any_write(wip, monkeypatch, tmp_path):
    monkeypatch.setattr(ow, "_disk_free", lambda path: 10)
    before = fingerprint(tmp_path)
    r = materialize(request(wip), confirm_plan_id="x")
    assert r["overall_status"] == "FAIL" and "MW-008" in ids(r)
    assert fingerprint(tmp_path) == before and not list(tmp_path.glob("*.staging-*"))


def test_default_margin_is_applied(wip):
    p = plan(request(wip, margin_bytes=None))
    assert p["space"]["margin_bytes"] >= ow.MIN_MARGIN_BYTES


def test_destination_already_exists_rejected(wip):
    wip["dest"].mkdir()
    r = materialize(request(wip), confirm_plan_id="x")
    assert "MW-005" in ids(r) and r["promotion_status"] == "NOT_STARTED"


def test_missing_required_and_unknown_stores(wip):
    p = plan(
        request(
            wip, stores={"raw": wip["stores"]["raw"], "extra": wip["stores"]["raw"]}
        )
    )
    assert {"MW-018", "MW-020"} <= ids(p)


# --- Gate humano y dry run -------------------------------------------------------------------


def test_dry_run_produces_zero_mutations(wip, tmp_path):
    before = fingerprint(tmp_path)
    r = materialize(request(wip), dry_run=True)
    assert r["overall_status"] == "PASS" and r["promotion_status"] == "DRY_RUN"
    assert fingerprint(tmp_path) == before
    assert not wip["dest"].exists() and not list(tmp_path.glob("*.staging-*"))


@pytest.mark.parametrize("confirm", [None, "", "0" * 16])
def test_real_copy_requires_matching_plan_id(wip, tmp_path, confirm):
    before = fingerprint(tmp_path)
    r = materialize(request(wip), confirm_plan_id=confirm)
    assert r["overall_status"] == "BLOCKED" and r["exit_code"] == ow.EXIT_BLOCKED
    assert fingerprint(tmp_path) == before


def test_plan_id_changes_when_source_changes(wip):
    first = plan(request(wip))["plan_id"]
    _write(wip["stores"]["raw"] / "nuevo.json", "{}")
    assert plan(request(wip))["plan_id"] != first
    assert (
        materialize(request(wip), confirm_plan_id=first)["overall_status"] == "BLOCKED"
    )


# --- Materialización completa ----------------------------------------------------------------


def test_successful_synthetic_promotion(wip, tmp_path):
    src_before = fingerprint(wip["repo"])
    r = run_ok(wip)
    dest = wip["dest"]
    assert r["overall_status"] == "PASS" and r["promotion_status"] == "PROMOTED", r[
        "findings"
    ]
    assert not list(
        tmp_path.glob("*.staging-*")
    )  # renombrado atómico: no queda staging
    m = json.loads((dest / ow.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert m["promotion_status"] == "PROMOTED" and m["copy_verification"] == "PASS"
    assert m["workspace_safety"]["staging"]["overall_status"] == "PASS"
    assert m["workspace_safety"]["promoted"]["overall_status"] == "PASS"
    assert (
        m["secret_scan"]["status"] == "PASS"
        and m["secret_scan"]["values_recorded"] is False
    )
    assert fingerprint(wip["repo"]) == src_before  # la fuente no cambió
    assert ow.verify(dest, environ={})["overall_status"] == "PASS"
    assert ow.status(dest)["destination"]["promotion_status"] == "PROMOTED"


def test_full_physical_copy_without_links_or_hardlinks(wip):
    run_ok(wip)
    dest = wip["dest"]
    for dirpath, dirnames, filenames in os.walk(dest):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in dirnames + filenames:
            info = ow.ws.classify_entry(Path(dirpath, name))
            assert info["kind"] in ("file", "directory"), (name, info)
    copied = dest / "data/processed/carpeta con espacios/año ñandú.txt"
    src = wip["stores"]["processed"] / "carpeta con espacios/año ñandú.txt"
    assert copied.read_text(encoding="utf-8") == "unicode ok"
    assert copied.stat().st_nlink == 1 and not os.path.samefile(copied, src)
    assert (dest / "data/processed/empty_dir").is_dir()


def test_store_files_are_not_excluded_accidentally(wip):
    m = run_ok(wip)["manifest"]
    for name, root in wip["stores"].items():
        src_files = {
            p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
        }
        sub = ow.ws.CODE_STORE_SUBPATHS[name]
        got = {e["path"][len(sub) + 1 :] for e in m["stores"][name]["files"]}
        assert (
            got == src_files
        ), name  # incluye .gitkeep, .pkl legacy, anidados y unicode


def test_attempt1_raw_files_preserved(wip):
    m = run_ok(wip)["manifest"]
    raw = [
        e
        for e in m["stores"]["raw"]["files"]
        if "firms_refresh/20260924T180743Z" in e["path"]
    ]
    assert len(raw) == 5
    rows = sum((wip["dest"] / e["path"]).read_text().count("\n") - 1 for e in raw)
    assert rows == 85


def test_current_pointers_copied_exactly_and_none_created(wip):
    run_ok(wip)
    for rel in ("firms/CURRENT.json", "dmc/330007/CURRENT.json"):
        assert (wip["dest"] / "data/processed" / rel).read_bytes() == (
            wip["stores"]["processed"] / rel
        ).read_bytes()
    currents = {
        p.relative_to(wip["dest"]).as_posix() for p in wip["dest"].rglob("CURRENT.json")
    }
    assert currents == {
        "data/processed/firms/CURRENT.json",
        "data/processed/dmc/330007/CURRENT.json",
    }


def test_tracked_model_identical_is_verified_not_duplicated(wip):
    m = run_ok(wip)["manifest"]
    entry = next(
        e
        for e in m["stores"]["models"]["files"]
        if e["path"] == "models/prototype_model_d.pkl"
    )
    assert entry["origin"] == "identical_to_committed"
    assert entry["sha256"] == hashlib.sha256(MODEL_BYTES).hexdigest()


def test_tracked_file_conflict_blocks_promotion(wip):
    _write(wip["stores"]["models"] / "prototype_model_d.pkl", b"otro modelo")
    r = run_ok(wip)
    assert (
        r["promotion_status"] == "FAILED"
        and "MW-009" in ids(r)
        and not wip["dest"].exists()
    )


def test_manifest_is_deterministic(wip, tmp_path):
    a = run_ok(wip)["manifest"]
    b = run_ok(wip, dest=tmp_path / "second")["manifest"]
    for name in ow.REQUIRED_STORES:
        assert (
            a["stores"][name]["manifest_sha256"] == b["stores"][name]["manifest_sha256"]
        )
        assert [e["path"] for e in a["stores"][name]["files"]] == sorted(
            e["path"] for e in a["stores"][name]["files"]
        )


# --- Fallos: nunca promover -------------------------------------------------------------------


def _assert_failed_not_promoted(r: dict, wip: dict, finding: str) -> Path:
    assert r["overall_status"] == "FAIL" and r["promotion_status"] == "FAILED", r[
        "findings"
    ]
    assert finding in ids(r)
    assert not wip["dest"].exists()
    staging = Path(r["staging"])
    marker = json.loads((staging / ow.FAILED_MARKER).read_text(encoding="utf-8"))
    assert marker["status"] == "FAILED" and "No se borra" in marker["cleanup"]
    return staging


def test_hash_mismatch_detected(wip, monkeypatch):
    real = ow._copy_file

    def corrupting(src, dst):
        digest = real(src, dst)
        if dst.endswith("w0.csv"):
            with open(dst, "ab") as fh:
                fh.write(b"x")
        return digest

    monkeypatch.setattr(ow, "_copy_file", corrupting)
    _assert_failed_not_promoted(run_ok(wip), wip, "MW-012")


def test_missing_source_file_during_copy_detected(wip, monkeypatch):
    real, victim = (
        ow._copy_file,
        wip["stores"]["raw"] / "firms_refresh/20260924T180743Z/VIIRS_SNPP_NRT/w4.csv",
    )

    def deleting(src, dst):
        if victim.exists():
            victim.unlink()
        return real(src, dst)

    monkeypatch.setattr(ow, "_copy_file", deleting)
    _assert_failed_not_promoted(run_ok(wip), wip, "MW-013")


def test_source_mutation_during_copy_detected(wip, monkeypatch):
    real = ow._copy_file
    target = wip["stores"]["processed"] / "firms/versions/firms_x.csv"

    def mutating(src, dst):
        digest = real(src, dst)
        if Path(src) == target:
            target.write_text("a,b\n9,9\n")  # mismo tamaño, contenido distinto
        return digest

    monkeypatch.setattr(ow, "_copy_file", mutating)
    _assert_failed_not_promoted(run_ok(wip), wip, "MW-013")


def test_workspace_safety_fail_prevents_promotion(wip):
    staging = _assert_failed_not_promoted(
        run_ok(wip, environ={"DATA_RAW_DIR": "x"}), wip, "MW-015"
    )
    manifest = json.loads((staging / ow.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["workspace_safety"]["staging"]["overall_status"] == "FAIL"


def test_staging_verification_failure_leaves_evidence(wip, monkeypatch):
    monkeypatch.setattr(
        ow,
        "_verify_copy",
        lambda *a: (_ for _ in ()).throw(
            ow.MaterializationError("MW-012", "verificación simulada")
        ),
    )
    staging = _assert_failed_not_promoted(run_ok(wip), wip, "MW-012")
    assert (staging / "src/app.py").exists()  # la evidencia no se borra
    assert ow.status(wip["dest"])["stagings"][0]["promotion_status"] == "FAILED"


def test_stage_only_validates_without_promotion(wip):
    req = request(wip)
    r = materialize(req, confirm_plan_id=plan(req)["plan_id"], stage_only=True)
    assert r["promotion_status"] == "VALIDATED" and not wip["dest"].exists()
    assert Path(r["staging"]).is_dir()


# --- Secretos -------------------------------------------------------------------------------------


def test_untracked_secrets_never_materialized(wip):
    r = run_ok(wip)
    assert r["promotion_status"] == "PROMOTED"
    assert (
        not (wip["dest"] / ".env").exists() and (wip["dest"] / ".env.example").exists()
    )
    assert FAKE_KEY not in json.dumps(r)


def test_committed_secret_file_blocks_plan(wip):
    _write(wip["repo"] / "config/.env.local", "TOKEN=abc\n")
    _git(wip["repo"], "add", "-f", "config/.env.local")
    _git(wip["repo"], "commit", "-qm", "oops")
    p = plan(request(wip, sha=_git(wip["repo"], "rev-parse", "HEAD")))
    assert p["overall_status"] == "FAIL" and "MW-011" in ids(p)


def test_secret_inside_store_blocks_promotion(wip):
    _write(
        wip["stores"]["raw"] / "log.txt",
        f"GET /api/area/csv/{FAKE_KEY}/VIIRS_SNPP_NRT\n",
    )
    r = run_ok(wip)
    staging = _assert_failed_not_promoted(r, wip, "MW-011")
    manifest = json.loads((staging / ow.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["secret_scan"]["secret_content_files"] == ["data/raw/log.txt"]
    assert FAKE_KEY not in json.dumps(r)


# --- CLI y API ------------------------------------------------------------


def test_cli_plan_dry_run_and_gate(wip, capsys):
    base = [
        "--repo-root",
        str(wip["repo"]),
        "--code-sha",
        wip["sha"],
        "--destination",
        str(wip["dest"]),
        "--margin-bytes",
        "0",
    ] + [a for n, p in wip["stores"].items() for a in ("--source-store", f"{n}={p}")]
    assert ow.main(["plan", *base, "--json"]) == ow.EXIT_PASS
    plan_id = json.loads(capsys.readouterr().out)["plan_id"]
    assert ow.main(["materialize", *base, "--dry-run"]) == ow.EXIT_PASS
    assert ow.main(["materialize", *base]) == ow.EXIT_BLOCKED
    assert not wip["dest"].exists()
    assert (
        ow.main(["materialize", *base, "--confirm-real-copy", plan_id]) == ow.EXIT_PASS
    )
    assert ow.main(["verify", "--workspace", str(wip["dest"])]) == ow.EXIT_PASS
    assert ow.main(["status", "--destination", str(wip["dest"])]) == ow.EXIT_PASS


def test_cli_survives_cp1252_console(wip):
    """Regresión: la consola Windows en cp1252 no debe abortar la CLI."""
    repo_root = Path(__file__).resolve().parent.parent
    args = [
        "plan",
        "--repo-root",
        str(wip["repo"]),
        "--code-sha",
        wip["sha"],
        "--destination",
        str(wip["dest"]),
        "--margin-bytes",
        "0",
    ]
    args += [
        a for n, p in wip["stores"].items() for a in ("--source-store", f"{n}={p}")
    ]
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run(
        [sys.executable, "-m", "src.ops.operational_workspace", *args],
        cwd=repo_root,
        env=env,
        capture_output=True,
        timeout=300,
    )
    assert done.returncode == ow.EXIT_PASS, done.stderr.decode("cp1252", "replace")
    assert b"plan_id" in done.stdout


def test_run_api_for_operator(wip):
    req = {
        "repo_root": str(wip["repo"]),
        "code_sha": wip["sha"],
        "destination": str(wip["dest"]),
        "margin_bytes": 0,
        "source_stores": {k: str(v) for k, v in wip["stores"].items()},
    }
    p = ow.run("plan", req)
    assert (
        ow.run("materialize", {**req, "dry_run": True})["promotion_status"] == "DRY_RUN"
    )
    assert (
        ow.run("materialize", {**req, "confirm_plan_id": p["plan_id"]})[
            "promotion_status"
        ]
        == "PROMOTED"
    )
    assert (
        ow.run("status", {"destination": str(wip["dest"])})["destination"][
            "promotion_status"
        ]
        == "PROMOTED"
    )
