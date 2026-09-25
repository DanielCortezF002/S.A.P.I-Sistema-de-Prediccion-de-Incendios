"""Tests del guard observacional de workspace (src/ops/workspace_safety.py).

Solo directorios temporales. En Windows se crean junctions reales con
`_winapi.CreateJunction` (sin privilegios); los symlinks se omiten si el SO
no concede el privilegio. Los mocks se usan solo para comportamiento de API
(stat con reparse tag, errores de lectura).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.ops.workspace_safety as ws
from src.ops.workspace_safety import GuardRequest, Mode, check_workspace

GIT = [
    "git",
    "-c",
    "user.name=t",
    "-c",
    "user.email=t@example.invalid",
    "-c",
    "commit.gpgsign=false",
]
OTHER_SHA = "0" * 40


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [*GIT, "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def make_repo(root: Path, with_stores: bool = True) -> tuple[Path, str, str]:
    """Checkout mínimo con la forma de SAPI: data/ y models/ ignorados."""
    root.mkdir(parents=True)
    subprocess.run([*GIT, "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text(
        "data/*/*\n!data/*/.gitkeep\nmodels/*.bin\n", encoding="utf-8"
    )
    (root / "app.py").write_text("print('sapi')\n", encoding="utf-8")
    for sub in ("data/raw", "data/processed", "data/predictions", "models"):
        (root / sub).mkdir(parents=True)
        (root / sub / ".gitkeep").write_text("", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    if with_stores:
        (root / "data/raw/dmc.json").write_text("{}", encoding="utf-8")
        (root / "data/processed/firms.csv").write_text("a\n", encoding="utf-8")
        (root / "models/real.bin").write_bytes(b"x")
    return root, _git(root, "rev-parse", "HEAD"), _git(root, "rev-parse", "HEAD^{tree}")


def bound_stores(root: Path) -> dict:
    return {
        "raw": root / "data/raw",
        "processed": root / "data/processed",
        "models": root / "models",
    }


def check(mode: Mode, root: Path, sha=None, stores=None, **kw) -> dict:
    kw.setdefault("environ", {})
    return check_workspace(
        GuardRequest(
            mode=mode,
            code_root=root,
            expected_code_sha=sha,
            stores=stores if stores is not None else {},
            **kw,
        )
    )


def ids(result: dict, severity: str | None = None) -> set[str]:
    return {
        f["id"]
        for f in result["findings"]
        if severity is None or f["severity"] == severity
    }


def make_junction(link: Path, target: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("junctions solo en Windows")
    import _winapi

    _winapi.CreateJunction(str(target), str(link))


def make_symlink(link: Path, target: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink no disponible: {exc}")


def tree_fingerprint(root: Path) -> str:
    """Hash de rutas+contenido+mtime de todo el árbol (incluye .git), sin seguir enlaces."""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in sorted(filenames):
            p = Path(dirpath, name)
            st = p.lstat()
            h.update(f"{p.relative_to(root)}|{st.st_size}|{st.st_mtime_ns}".encode())
    return h.hexdigest()


# --- 1. Árbol limpio -----------------------------------------------------------


def test_clean_bound_checkout_passes_operational(tmp_path):
    root, sha, tree = make_repo(tmp_path / "op")
    r = check(
        Mode.OPERATIONAL_REAL_DATA,
        root,
        sha,
        bound_stores(root),
        expected_tree_sha=tree,
    )
    assert r["overall_status"] == "PASS", r["findings"]
    assert r["exit_code"] == ws.EXIT_PASS
    assert r["code"]["sha_match"] is True and r["code"]["tree_match"] is True
    assert all(
        e["binds_to_declared_store"]
        for e in r["topology"]["code_effective_store_paths"]
        if e["declared_store"]
    )
    assert "no autoriza" in r["disclaimer"].lower()


def test_result_is_json_serializable_and_has_contract_keys(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    r = json.loads(json.dumps(check(Mode.READ_ONLY, root, sha, bound_stores(root))))
    for key in (
        "schema_version",
        "mode",
        "observed_at",
        "code",
        "stores",
        "topology",
        "findings",
        "warnings",
        "failures",
        "overall_status",
    ):
        assert key in r


# --- 2. SHA ------------------------------------------------------------------------


def test_wrong_sha_fails_operational(tmp_path):
    root, _, _ = make_repo(tmp_path / "op")
    r = check(Mode.OPERATIONAL_REAL_DATA, root, OTHER_SHA, bound_stores(root))
    assert r["overall_status"] == "FAIL" and "WS-001" in ids(r, "FAIL")


@pytest.mark.parametrize("sha", [None, "7ef8d3c", "ABC"])
def test_missing_or_abbreviated_sha_is_never_close_enough(tmp_path, sha):
    root, real, _ = make_repo(tmp_path / "op")
    prefix = real[:12] if sha == "7ef8d3c" else sha
    r = check(Mode.OPERATIONAL_REAL_DATA, root, prefix, bound_stores(root))
    assert r["overall_status"] == "FAIL" and "WS-015" in ids(r, "FAIL")


def test_wrong_tree_fails(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    r = check(
        Mode.OPERATIONAL_REAL_DATA,
        root,
        sha,
        bound_stores(root),
        expected_tree_sha=OTHER_SHA,
    )
    assert "WS-014" in ids(r, "FAIL")


def test_uppercase_full_sha_is_normalized(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    r = check(Mode.OPERATIONAL_REAL_DATA, root, sha.upper(), bound_stores(root))
    assert r["code"]["sha_match"] is True


# --- 3. Dirty ------------------------------------------------------------------------


def test_dirty_tree_fails_operational_and_is_surfaced_read_only(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    (root / "app.py").write_text("print('modificado')\n", encoding="utf-8")
    op = check(Mode.OPERATIONAL_REAL_DATA, root, sha, bound_stores(root))
    ro = check(Mode.READ_ONLY, root, sha, bound_stores(root))
    assert "WS-002" in ids(op, "FAIL") and op["code"]["dirty_count"] == 1
    assert "WS-002" in ids(ro, "WARN") and ro["overall_status"] == "PASS"


def test_allow_dirty_downgrades_to_warning(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    (root / "nuevo.txt").write_text("x", encoding="utf-8")
    r = check(
        Mode.OPERATIONAL_REAL_DATA, root, sha, bound_stores(root), require_clean=False
    )
    assert "WS-002" in ids(r, "WARN") and r["overall_status"] == "PASS"


# --- 4. Indirección de la raíz del código -------------------------------------------


def test_symlinked_code_root_is_detected(tmp_path):
    root, sha, _ = make_repo(tmp_path / "real")
    link = tmp_path / "alias"
    make_symlink(link, root)
    r = check(Mode.OPERATIONAL_REAL_DATA, link, sha, bound_stores(root))
    assert "WS-003" in ids(r, "FAIL")


def test_junction_code_root_is_detected(tmp_path):
    root, sha, _ = make_repo(tmp_path / "real")
    link = tmp_path / "alias"
    make_junction(link, root)
    r = check(Mode.OPERATIONAL_REAL_DATA, link, sha, bound_stores(root))
    assert "WS-003" in ids(r, "FAIL")
    assert r["code"]["reparse_points"][0]["kind"] == "junction"


# --- 5. Junction real en un store ------------------------------------------------------


def test_real_windows_junction_is_classified(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    make_junction(link, target)
    info = ws.classify_entry(link)
    assert (
        info["kind"] == "junction" and info["is_junction"] and info["is_reparse_point"]
    )
    assert Path(info["target"]).resolve() == target.resolve()
    assert ws.classify_entry(target)["kind"] == "directory"


def test_data_raw_junctioned_into_other_checkout_fails(tmp_path):
    """El casi-incidente real: un worktree cuyo data/raw apunta a los stores del WIP."""
    wip, _, _ = make_repo(tmp_path / "wip")
    op, sha, _ = make_repo(tmp_path / "op", with_stores=False)
    (op / "data/raw/.gitkeep").unlink()
    (op / "data/raw").rmdir()
    make_junction(op / "data/raw", wip / "data/raw")
    stores = {"raw": wip / "data/raw"}
    for mode in (Mode.OPERATIONAL_REAL_DATA, Mode.TEST_ISOLATED):
        r = check(mode, op, sha, stores, require_clean=False)
        assert "WS-011" in ids(r, "FAIL"), (mode, r["findings"])
        assert r["overall_status"] == "FAIL"
    effective = next(
        e
        for e in r["topology"]["code_effective_store_paths"]
        if e["logical_name"] == "raw"
    )
    assert effective["reparse_inside_code_root"][0]["kind"] == "junction"


def test_store_path_through_junction_fails_operational(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    alias = tmp_path / "raw_alias"
    make_junction(alias, root / "data/raw")
    r = check(Mode.OPERATIONAL_REAL_DATA, root, sha, {"raw": alias})
    assert "WS-005" in ids(r, "FAIL") and "WS-004" in ids(r, "FAIL")


def test_reparse_tag_detection_without_platform_support(monkeypatch):
    """Nivel API: un stat con FILE_ATTRIBUTE_REPARSE_POINT y tag de junction se
    clasifica como junction aunque S_ISLNK sea falso (lo que Path.is_symlink no ve)."""
    fake = SimpleNamespace(
        st_mode=0o040755, st_file_attributes=0x400, st_reparse_tag=0xA0000003
    )
    monkeypatch.setattr(ws, "_lstat", lambda p: fake)
    monkeypatch.setattr(ws.os, "readlink", lambda p: "\\\\?\\D:\\otro")
    info = ws.classify_entry("X:/cualquiera")
    assert info["kind"] == "junction" and info["target"] == "D:\\otro"
    fake.st_reparse_tag = 0x9000601A  # otro reparse (p. ej. placeholder de nube)
    assert ws.classify_entry("X:/cualquiera")["kind"] == "reparse_other"


# --- 6. Store fuera de la ruta esperada -------------------------------------------------


def test_store_resolving_outside_expected_path_fails(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    r = check(
        Mode.OPERATIONAL_REAL_DATA,
        root,
        sha,
        bound_stores(root),
        expected_stores={"raw": tmp_path / "otro" / "raw"},
    )
    assert "WS-004" in ids(r, "FAIL")


def test_declared_store_not_where_code_reads_fails(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    external = tmp_path / "stores" / "raw"
    external.mkdir(parents=True)
    r = check(Mode.OPERATIONAL_REAL_DATA, root, sha, {"raw": external})
    assert "WS-012" in ids(r, "FAIL")


def test_env_override_splits_store_paths(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    r = check(
        Mode.OPERATIONAL_REAL_DATA,
        root,
        sha,
        bound_stores(root),
        environ={"DATA_RAW_DIR": "x"},
    )
    assert "WS-016" in ids(r, "FAIL")
    assert r["topology"]["store_env_overrides"] == [
        "DATA_RAW_DIR"
    ]  # nombres, nunca valores


# --- 7. Solapamiento código/store ------------------------------------------------------


def test_code_root_inside_store_fails(tmp_path):
    store = tmp_path / "store"
    root, sha, _ = make_repo(store / "code")
    r = check(Mode.OPERATIONAL_REAL_DATA, root, sha, {"raw": store})
    assert "WS-006" in ids(r, "FAIL")


def test_store_inside_code_root_outside_binding_fails(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    r = check(Mode.OPERATIONAL_REAL_DATA, root, sha, {"raw": root / "data/processed"})
    assert "WS-006" in ids(r, "FAIL")


def test_store_in_other_git_checkout_fails_operational_but_warns_read_only(tmp_path):
    wip, _, _ = make_repo(tmp_path / "wip")
    op, sha, _ = make_repo(tmp_path / "op", with_stores=False)
    stores = {"raw": wip / "data/raw"}
    op_r = check(Mode.OPERATIONAL_REAL_DATA, op, sha, stores)
    assert "WS-006" in ids(op_r, "FAIL")
    assert check(Mode.READ_ONLY, op, sha, stores)["overall_status"] == "PASS"


def test_test_isolated_fails_when_checkout_holds_real_stores(tmp_path):
    root, sha, _ = make_repo(tmp_path / "wip")
    r = check(Mode.TEST_ISOLATED, root, sha, bound_stores(root))
    assert "WS-006" in ids(r, "FAIL") and r["overall_status"] == "FAIL"


def test_test_isolated_passes_for_clean_copy_away_from_stores(tmp_path):
    wip, _, _ = make_repo(tmp_path / "wip")
    copy, sha, _ = make_repo(tmp_path / "copy", with_stores=False)
    r = check(Mode.TEST_ISOLATED, copy, sha, bound_stores(wip))
    assert r["overall_status"] == "PASS", r["findings"]


# --- 8. Alias ------------------------------------------------------------------------------


def test_two_logical_names_same_physical_store_are_surfaced(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    stores = {**bound_stores(root), "raw_again": root / "data" / "raw"}
    r = check(Mode.READ_ONLY, root, sha, stores)
    assert "WS-010" in ids(r, "WARN")
    assert "WS-010" in ids(check(Mode.OPERATIONAL_REAL_DATA, root, sha, stores), "FAIL")


def test_alias_through_junction_is_surfaced(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    alias = tmp_path / "alias"
    make_junction(alias, root / "data/raw")
    r = check(Mode.READ_ONLY, root, sha, {"raw": root / "data/raw", "other": alias})
    assert "WS-010" in ids(r)


# --- 9. Docker ------------------------------------------------------------------------------


def test_docker_context_with_real_data_fails(tmp_path):
    root, sha, _ = make_repo(tmp_path / "wip")
    r = check(Mode.DOCKER_BUILD, root, sha)
    assert "WS-007" in ids(r, "FAIL") and r["overall_status"] == "FAIL"
    assert "git archive" in r["topology"]["docker_context"]["recommendation"]


def test_docker_context_with_store_junction_fails(tmp_path):
    wip, _, _ = make_repo(tmp_path / "wip")
    ctx, sha, _ = make_repo(tmp_path / "ctx", with_stores=False)
    make_junction(ctx / "stores_link", wip / "data")
    r = check(Mode.DOCKER_BUILD, ctx, sha, require_clean=False)
    assert "WS-007" in ids(r, "FAIL")
    assert any(
        p["kind"] == "junction"
        for p in r["topology"]["docker_context"]["reparse_points_in_context"]
    )


def test_clean_docker_context_passes(tmp_path):
    ctx, sha, _ = make_repo(tmp_path / "ctx", with_stores=False)
    r = check(Mode.DOCKER_BUILD, ctx, sha)
    assert r["overall_status"] == "PASS", r["findings"]


def test_non_git_docker_context_is_never_pass(tmp_path):
    ctx = tmp_path / "archive"
    (ctx / "data/raw").mkdir(parents=True)
    r = check(Mode.DOCKER_BUILD, ctx, OTHER_SHA)
    assert r["overall_status"] == "INCOMPLETE" and "WS-013" in ids(r)
    (ctx / "data/raw/real.json").write_text("{}", encoding="utf-8")
    assert check(Mode.DOCKER_BUILD, ctx, OTHER_SHA)["overall_status"] == "FAIL"


# --- 10. Store ausente ------------------------------------------------------------------------


def test_missing_store_fails_operational_and_is_incomplete_read_only(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    stores = {"raw": tmp_path / "no-existe"}
    assert "WS-009" in ids(check(Mode.OPERATIONAL_REAL_DATA, root, sha, stores), "FAIL")
    ro = check(Mode.READ_ONLY, root, sha, stores)
    assert (
        ro["overall_status"] == "INCOMPLETE" and ro["exit_code"] == ws.EXIT_INCOMPLETE
    )


def test_operational_without_declared_stores_fails(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    assert "WS-018" in ids(check(Mode.OPERATIONAL_REAL_DATA, root, sha, {}), "FAIL")


# --- 11. UNKNOWN nunca es SAFE ---------------------------------------------------------------


@pytest.mark.parametrize(
    "mode,expected",
    [
        (Mode.READ_ONLY, "INCOMPLETE"),
        (Mode.TEST_ISOLATED, "INCOMPLETE"),
        (Mode.OPERATIONAL_REAL_DATA, "FAIL"),
        (Mode.DOCKER_BUILD, "FAIL"),
    ],
)
def test_unreadable_store_is_never_pass(tmp_path, monkeypatch, mode, expected):
    root, sha, _ = make_repo(tmp_path / "op", with_stores=False)
    store = tmp_path / "blocked"
    store.mkdir()
    real = ws._lstat

    def denying(path):
        if Path(path) == store:
            raise PermissionError(13, "denied")
        return real(path)

    monkeypatch.setattr(ws, "_lstat", denying)
    r = check(mode, root, sha, {"raw": store})
    assert "WS-008" in ids(r)
    assert r["overall_status"] == expected


def test_unknown_filesystem_identity_is_never_pass(tmp_path, monkeypatch):
    root, sha, _ = make_repo(tmp_path / "op")
    monkeypatch.setattr(ws, "_identity", lambda path: None)
    r = check(Mode.READ_ONLY, root, sha, bound_stores(root))
    assert "WS-008" in ids(r) and r["overall_status"] != "PASS"


@pytest.mark.parametrize(
    "mode,expected",
    [(Mode.READ_ONLY, "INCOMPLETE"), (Mode.OPERATIONAL_REAL_DATA, "FAIL")],
)
def test_non_git_code_root_identity_is_unknown(tmp_path, mode, expected):
    plain = tmp_path / "plain"
    (plain / "data/raw").mkdir(parents=True)
    r = check(mode, plain, OTHER_SHA, {"raw": plain / "data/raw"})
    assert "WS-013" in ids(r) and r["overall_status"] == expected


# --- 12. READ_ONLY no autoriza operación real ---------------------------------------------------


def test_read_only_pass_does_not_imply_operational_pass(tmp_path):
    wip, _, _ = make_repo(tmp_path / "wip")
    (wip / "app.py").write_text("print('wip')\n", encoding="utf-8")
    stores = bound_stores(wip)
    ro = check(Mode.READ_ONLY, wip, OTHER_SHA, stores)
    op = check(Mode.OPERATIONAL_REAL_DATA, wip, OTHER_SHA, stores)
    assert ro["overall_status"] == "PASS" and ro["mode"] == "READ_ONLY"
    assert op["overall_status"] == "FAIL" and {"WS-001", "WS-002"} <= ids(op, "FAIL")


# --- No mutación y CLI -------------------------------------------------------------------------


def test_guard_does_not_mutate_workspace_or_git_index(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    (root / "app.py").write_text(
        "sucio\n", encoding="utf-8"
    )  # fuerza a git status a mirar el índice
    before = tree_fingerprint(tmp_path)
    for mode in Mode:
        check(mode, root, sha, bound_stores(root))
    assert tree_fingerprint(tmp_path) == before


def test_cli_exit_codes_and_json_out(tmp_path, capsys):
    root, sha, _ = make_repo(tmp_path / "op")
    out = tmp_path / "result.json"
    args = [
        "check",
        "--mode",
        "operational-real-data",
        "--code-root",
        str(root),
        "--expected-code-sha",
        sha,
        "--store",
        f"raw={root / 'data/raw'}",
        "--store",
        f"processed={root / 'data/processed'}",
        "--store",
        f"models={root / 'models'}",
        "--json-out",
        str(out),
    ]
    os.environ.pop("DATA_RAW_DIR", None)
    assert ws.main(args) == ws.EXIT_PASS
    assert json.loads(out.read_text(encoding="utf-8"))["overall_status"] == "PASS"
    assert "[PASS]" in capsys.readouterr().out
    bad = [a if a != sha else OTHER_SHA for a in args]
    assert ws.main(bad) == ws.EXIT_FAIL
    ro = [
        "check",
        "--mode",
        "read-only",
        "--code-root",
        str(root),
        "--store",
        f"raw={tmp_path / 'nope'}",
    ]
    assert ws.main(ro) == ws.EXIT_INCOMPLETE


def test_cli_refuses_json_out_inside_a_store(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    rc = ws.main(
        [
            "check",
            "--mode",
            "read-only",
            "--code-root",
            str(root),
            "--store",
            f"raw={root / 'data/raw'}",
            "--json-out",
            str(root / "data/raw/out.json"),
        ]
    )
    assert rc == ws.EXIT_USAGE and not (root / "data/raw/out.json").exists()


def test_run_accepts_json_request(tmp_path):
    root, sha, _ = make_repo(tmp_path / "op")
    r = ws.run(
        {
            "mode": "operational-real-data",
            "code_root": str(root),
            "expected_code_sha": sha,
            "stores": {k: str(v) for k, v in bound_stores(root).items()},
        }
    )
    assert r["mode"] == "OPERATIONAL_REAL_DATA" and r["overall_status"] in {
        "PASS",
        "FAIL",
    }


def test_every_finding_has_severity_for_every_mode():
    for code, severities in ws.FINDINGS.values():
        assert set(severities) == set(Mode) and set(severities.values()) <= {
            "FAIL",
            "INCOMPLETE",
            "WARN",
            "INFO",
        }
