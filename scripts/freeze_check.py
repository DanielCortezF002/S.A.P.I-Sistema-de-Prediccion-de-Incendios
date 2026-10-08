"""Verificacion de congelamiento (freeze) del baseline Sprint 2 / Hito 2.

Comprueba, en solo lectura, que el trabajo posterior al checkpoint
`CHECKPOINT_SPRINT2_BASELINE` (commit cd6b58e) no altero lo que el plan de
Hito 2 declara congelado: identidad git (F1), fingerprint del ranking del
Modelo D (F2), hashes del Output Plane de readiness (F3), rutas congeladas
(F4), contratos v0 solo aditivos (F4b), servicio ML salvo `_ranking` /
`RankingResult` (F4c), artefactos Hito 1 (F5), migraciones V001-V003 (F6),
contratos v0 (F7), modificaciones accidentales (F8) y modelo (F9).

No escribe nada en el repositorio salvo el JSON opcional de `--json`. Del
codigo del repo solo carga `src/procesamiento/firms_source.py` (stdlib pura)
para leer la ruta del snapshot FIRMS, y F2, que corre en un subproceso con
`SAPI_REPRODUCIBILITY_MODE=1` y se omite (SKIP) si faltan dependencias.

Modo A: HEAD == baseline. Modo B: el baseline es ancestro de HEAD (ya hay
trabajo commiteado encima). Nunca recalcular los pins: si algo falla, se
detiene el trabajo y se investiga la causa.

Uso:
    python -B scripts/freeze_check.py [--json RUTA] [--allow-dirty]
        [--allow-tag NOMBRE ...] [--skip-remote] [--skip-fingerprint]
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

BASELINE = "cd6b58eb9bd4b9a22b8937c4cda73be46322cddb"

# Tags remotos existentes en el baseline (nombre -> objeto del tag anotado).
PINNED_TAGS = {
    "v1.0.0-data": "2b7459016c682f4e03d2951efcd5c07593c7e8cf",
    "v1.0.0-sprint1-verified": "989bd2ee86e627d83c9bb3769e4a44195cb39a09",
    "v1.1.0-corredor-verified": "612c58b8a9907d3ba5dcf4dd3c897f02191a427b",
    "v2.0.0-baseline": "1538f70b207f45fcbf620660c8b5f7bf5e94d87c",
    "v3.0.0-final-release": "affe565287b011d800a03a25361dee142f615f80",
    "v3.2.0-demo-professional": "e3923211350fd3abd3a5e4ac5a19e3cf1da8b3bd",
}

MODEL_D_RANKING_FINGERPRINT = (
    "33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff"
)
MODEL_D_FIRST_LINE = "2026-09-01 00:00:00+00:00 50 VP-001 0.131293368748"

READINESS_SOURCES_SHA256 = (
    "b3d32f5025bbdc49e2cb80718f63c0390e777af2a99fa33bcef03e76ca22fe54"
)
READINESS_IDENTITY_SHA256 = (
    "2622fcdc823157ecec1363b0f4c31323f6fe94a711450e40a0e0bea3263bc090"
)

FILE_PINS = {
    # F6: migraciones v2 congeladas (solo se admiten V004 en adelante).
    "db/migration/V001__enable_postgis.sql": (
        "5f3606cb3b51ffbcbb509213493b36f6ff2e5c298b2dedd1b39ed16aa99db0df"
    ),
    "db/migration/V002__create_sapi_v2_schema.sql": (
        "22df9f6843a21e4d00609b882e6afa9f337d6a6dbdda82626f19549241584206"
    ),
    "db/migration/V003__seed_celdas_geom.sql": (
        "02690a1684aa19bb40c7bb856a892096211ed352221d715e99d3f93cbf5bf009"
    ),
    # F9: Modelo D y su metadata.
    "models/prototype_model_d.pkl": (
        "ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f"
    ),
    "models/prototype_model_d_metadata.json": (
        "fc2c62341d821ddf2c4483050c917a2b2f0ab96607d134bb9ba05b7f82a07bd9"
    ),
    # F5: manifest de reproducibilidad Hito 1.
    "artifacts/hito1/reproducibility/manifest.json": (
        "a02500da7fb2e055766c76b154fbcf8e11b957a3f413d3e3c8c59d0ef2afa439"
    ),
}

CONTRACT_PINS = {
    "contracts/openapi/backend.v0.yaml": (
        "f3ea2916d589731852502917baa30b104d61380fccd083187b1498a2dc93531b"
    ),
    "contracts/openapi/ml-service.v0.yaml": (
        "4ca85a8719b2ea7c3516cd9ca710cb514010c10df422049da8383bbd50af49c7"
    ),
}


def _firms_reproducibility_csv() -> str:
    """Ruta del snapshot FIRMS R3, leída de su única fuente de verdad.

    tests/test_firms_source.py exige que la ruta de la línea base FIRMS viva
    solo en src/procesamiento/firms_source.py. Ese módulo usa solo la stdlib,
    así que se carga por ruta, sin ejecutar `src/procesamiento/__init__.py`.
    """
    path = REPO_ROOT / "src" / "procesamiento" / "firms_source.py"
    spec = importlib.util.spec_from_file_location("_freeze_firms_source", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resuelve el módulo por nombre
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module.FIRMS_REPRODUCIBILITY_CSV.relative_to(REPO_ROOT).as_posix()


# Snapshots R3 cuyo sha256 publicado es sobre bytes CRLF (.gitattributes -text).
CRLF_ARTIFACTS = (
    "artifacts/hito1/reproducibility/dem/grid_topography.csv",
    "artifacts/hito1/reproducibility/dmc/dmc_historico_330007_2026-08.json",
    _firms_reproducibility_csv(),
)

# Output Plane hasheado por src/output/readiness.py (OUTPUT_SOURCES, L40-56).
OUTPUT_SOURCES = (
    "app/components/ops_dashboard.py",
    "app/control_center.py",
    "app/data/demo_score_synthetic.json",
    "app/pages/dashboard.py",
    "app/utils/score_contract.py",
    "ops/n8n/build_workflow.py",
    "ops/n8n/controlled-preview.json",
    "ops/n8n/policy.js",
    "src/notifications/alert_payload.py",
    "src/output/__init__.py",
    "src/output/accepted_run.py",
    "src/output/contract.py",
    "src/output/readiness.py",
    "src/output/synthetic.py",
    "tools/n8n_bridge/app.py",
    "tools/n8n_bridge/contract.py",
    "tools/n8n_bridge/output_contract.py",
)

FROZEN_PATHS = (
    "src/inference",
    "src/procesamiento",
    "src/geo/grid.py",
    "models",
    "artifacts/hito1",
    "db/migration/V001__enable_postgis.sql",
    "db/migration/V002__create_sapi_v2_schema.sql",
    "db/migration/V003__seed_celdas_geom.sql",
    "src/ops",
    "src/convergence",
    "src/refresh",
    "tools/ops",
    "docs/ops",
    "docker/initdb",
    "src/pipeline",
    "src/modelo",
    "src/query",
    "Dockerfile.analytics",
    ".gitattributes",
    "services/backend/.gitattributes",
    "services/backend/mvnw",
    "services/backend/mvnw.cmd",
    "services/backend/.mvn/wrapper",
    "services/backend/src/main/java/cl/sapi/backend/HealthController.java",
    "app/components/prototype_view.py",
    "requirements.txt",
    "deliverables",
    ":(glob)docs/*hito1*.md",
    "docs/entrega-prototipo.md",
    "scripts/verify_reproducibility.py",
    "tests/test_reproducibility_manifest.py",
    "config/data_plane_rc1.json",
    "config/rc1_convergence_lanes.json",
) + OUTPUT_SOURCES

# Directorios de cache que un comando de solo lectura puede generar.
IGNORED_CACHE_MARKERS = (
    "__pycache__",
    ".pytest_cache",
    ".coverage",
    "htmlcov",
    "target/",
)

FINGERPRINT_SNIPPET = (
    "import hashlib\n"
    "from src.inference.prototype_service import score_current_grid as s\n"
    "r = s(); c = r.cells\n"
    "print(r.forecast_time, len(c), c[0].cell_id, round(c[0].score, 12))\n"
    "payload = '\\n'.join(f'{x.cell_id},{x.score!r},{x.rank}' for x in c)\n"
    "print(hashlib.sha256(payload.encode('utf-8')).hexdigest())\n"
)


class Report:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, check: str, status: str, expected: str, observed: str) -> None:
        self.rows.append(
            {
                "check": check,
                "status": status,
                "expected": expected,
                "observed": observed,
            }
        )

    @property
    def failed(self) -> bool:
        return any(row["status"] == "FAIL" for row in self.rows)


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=check
    )
    return result.stdout.strip()


def git_bytes(rev: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{rev}:{path}"], cwd=REPO_ROOT, capture_output=True, check=True
    ).stdout


def sha256_file(rel: str) -> str:
    return hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()


def readiness_digest(read, paths) -> str:
    """Mismo algoritmo que src/output/readiness.py::sources_sha256."""
    digest = hashlib.sha256()
    for rel in sorted(paths):
        normalized = read(rel).replace(b"\r\n", b"\n")
        digest.update(rel.encode() + b"\0" + hashlib.sha256(normalized).digest())
    return digest.hexdigest()


def output_sources_at(rev: str) -> tuple:
    module = ast.parse(git_bytes(rev, "src/output/readiness.py"))
    for node in module.body:
        if (
            isinstance(node, ast.Assign)
            and getattr(node.targets[0], "id", "") == "OUTPUT_SOURCES"
        ):
            return tuple(ast.literal_eval(node.value))
    raise RuntimeError("OUTPUT_SOURCES no encontrado en src/output/readiness.py")


def check_identity(report: Report, allowed_tags: set, skip_remote: bool) -> str:
    head = git("rev-parse", "HEAD")
    if head == BASELINE:
        mode = "A"
        report.add("F1 HEAD", "PASS", f"== {BASELINE[:7]} (modo A)", head[:7])
    else:
        ancestor = (
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", BASELINE, head], cwd=REPO_ROOT
            ).returncode
            == 0
        )
        mode = "B"
        report.add(
            "F1 HEAD",
            "PASS" if ancestor else "FAIL",
            f"{BASELINE[:7]} ancestro de HEAD (modo B)",
            f"{head[:7]} ancestro={ancestor}",
        )
    local_tags = set(filter(None, git("tag", "-l").splitlines()))
    unexpected = sorted(local_tags - set(PINNED_TAGS) - allowed_tags)
    report.add(
        "F1 tags locales",
        "FAIL" if unexpected else "PASS",
        "subconjunto de tags fijados + --allow-tag",
        ", ".join(unexpected) or f"{len(local_tags)} tag(s) esperados",
    )
    if skip_remote:
        report.add("F1 refs remotos", "SKIP", "ls-remote origin", "--skip-remote")
        return mode
    remote = {}
    for line in git("ls-remote", "--tags", "--refs", "origin").splitlines():
        obj, ref = line.split("\t")
        remote[ref.removeprefix("refs/tags/")] = obj
    moved = sorted(name for name, obj in PINNED_TAGS.items() if remote.get(name) != obj)
    extra = sorted(set(remote) - set(PINNED_TAGS) - allowed_tags)
    report.add(
        "F1 tags remotos",
        "FAIL" if moved or extra else "PASS",
        "6 tags fijados intactos, sin tags nuevos no autorizados",
        f"movidos={moved or '-'} nuevos={extra or '-'}",
    )
    remote_main = git("ls-remote", "origin", "refs/heads/main").split("\t")[0]
    main_ok = (
        remote_main == BASELINE
        or subprocess.run(
            ["git", "merge-base", "--is-ancestor", BASELINE, remote_main],
            cwd=REPO_ROOT,
            capture_output=True,
        ).returncode
        == 0
    )
    report.add(
        "F1 origin/main",
        "PASS" if main_ok else "FAIL",
        f"== {BASELINE[:7]} o descendiente",
        remote_main[:7] or "(no disponible)",
    )
    return mode


def check_fingerprint(report: Report, skip: bool) -> None:
    if skip:
        report.add(
            "F2 fingerprint Modelo D",
            "SKIP",
            MODEL_D_RANKING_FINGERPRINT[:12],
            "--skip",
        )
        return
    env = dict(os.environ, SAPI_REPRODUCIBILITY_MODE="1", PYTHONPATH=str(REPO_ROOT))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", "-c", FINGERPRINT_SNIPPET],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and "ModuleNotFoundError" in result.stderr:
        missing = result.stderr.strip().splitlines()[-1]
        report.add(
            "F2 fingerprint Modelo D", "SKIP", "dependencias de runtime", missing
        )
        return
    lines = result.stdout.strip().splitlines()[-2:]
    ok = result.returncode == 0 and lines == [
        MODEL_D_FIRST_LINE,
        MODEL_D_RANKING_FINGERPRINT,
    ]
    report.add(
        "F2 fingerprint Modelo D",
        "PASS" if ok else "FAIL",
        f"{MODEL_D_FIRST_LINE} / {MODEL_D_RANKING_FINGERPRINT[:12]}…",
        " / ".join(lines) or result.stderr.strip()[-200:],
    )


def check_readiness(report: Report) -> None:
    for label, rev in (("baseline", BASELINE), ("HEAD", "HEAD")):
        sources = output_sources_at(rev)
        read = lambda rel, rev=rev: git_bytes(rev, rel)  # noqa: E731
        full, identity = readiness_digest(read, sources), readiness_digest(
            read, sources[:5]
        )
        ok = (
            len(sources) == 17
            and full == READINESS_SOURCES_SHA256
            and identity == READINESS_IDENTITY_SHA256
        )
        report.add(
            f"F3 readiness ({label})",
            "PASS" if ok else "FAIL",
            f"17 {READINESS_SOURCES_SHA256[:12]}… {READINESS_IDENTITY_SHA256[:12]}…",
            f"{len(sources)} {full[:12]}… {identity[:12]}…",
        )
    worktree = readiness_digest(
        lambda rel: (REPO_ROOT / rel).read_bytes(), OUTPUT_SOURCES
    )
    report.add(
        "F3 readiness (worktree)",
        "PASS" if worktree == READINESS_SOURCES_SHA256 else "FAIL",
        READINESS_SOURCES_SHA256[:12] + "…",
        worktree[:12] + "…",
    )


def check_frozen_paths(report: Report) -> None:
    paths = list(FROZEN_PATHS)
    committed = git("diff", "--name-only", BASELINE, "HEAD", "--", *paths)
    report.add(
        "F4 congelados (commits)",
        "FAIL" if committed else "PASS",
        "sin cambios desde baseline",
        committed.replace("\n", ", ") or "sin cambios",
    )
    uncommitted = git("diff", "--name-only", "HEAD", "--", *paths)
    staged = git("diff", "--cached", "--name-only", "--", *paths)
    dirty = sorted(set(filter(None, (uncommitted + "\n" + staged).splitlines())))
    report.add(
        "F4 congelados (worktree)",
        "FAIL" if dirty else "PASS",
        "sin cambios locales",
        ", ".join(dirty) or "sin cambios",
    )
    untracked = git("ls-files", "--others", "--exclude-standard", "--", *paths)
    ignored = [
        line
        for line in git(
            "ls-files", "--others", "--ignored", "--exclude-standard", "--", *paths
        ).splitlines()
        if not any(marker in line for marker in IGNORED_CACHE_MARKERS)
    ]
    extra = sorted(set(filter(None, untracked.splitlines())) | set(ignored))
    report.add(
        "F4 congelados (archivos nuevos)",
        "FAIL" if extra else "PASS",
        "sin archivos nuevos bajo rutas congeladas",
        ", ".join(extra) or "ninguno",
    )


def _yaml_or_none():
    try:
        import yaml  # noqa: PLC0415
    except ModuleNotFoundError:
        return None
    return yaml


def _removed_or_changed(base, head, path, errors) -> None:
    if tuple(path[-2:]) in {("info", "version"), ("info", "description")}:
        return
    if isinstance(base, dict):
        if not isinstance(head, dict):
            errors.append(f"tipo cambiado: {'/'.join(map(str, path))}")
            return
        for key, value in base.items():
            if key not in head:
                errors.append(f"eliminado: {'/'.join(map(str, path + [key]))}")
            else:
                _removed_or_changed(value, head[key], path + [key], errors)
    elif base != head:
        errors.append(f"cambiado: {'/'.join(map(str, path))}")


def check_contracts(report: Report) -> None:
    changed = [rel for rel, pin in CONTRACT_PINS.items() if sha256_file(rel) != pin]
    if not changed:
        report.add("F7 contratos v0", "PASS", "sha256 fijados", "idénticos")
        report.add("F4b contratos aditivos", "PASS", "solo adiciones", "sin cambios")
        return
    report.add(
        "F7 contratos v0", "INFO", "sha256 fijados", "cambiados: " + ", ".join(changed)
    )
    yaml = _yaml_or_none()
    if yaml is None:
        report.add(
            "F4b contratos aditivos", "FAIL", "PyYAML disponible", "PyYAML no instalado"
        )
        return
    errors: list[str] = []
    for rel in changed:
        base = yaml.safe_load(git_bytes(BASELINE, rel))
        head = yaml.safe_load((REPO_ROOT / rel).read_bytes())
        _removed_or_changed(base, head, [rel], errors)
    report.add(
        "F4b contratos aditivos",
        "FAIL" if errors else "PASS",
        "sin claves eliminadas ni valores cambiados",
        "; ".join(errors[:10]) or "solo adiciones",
    )


def _ml_module(source: bytes):
    tree = ast.parse(source)
    ranking_model = None
    body = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_ranking":
            continue
        if isinstance(node, ast.ClassDef) and node.name == "RankingResult":
            ranking_model = node
            continue
        body.append(node)
    tree.body = body
    fields = {}
    for stmt in ranking_model.body if ranking_model else []:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            fields[stmt.target.id] = ast.dump(stmt)
    return ast.dump(tree), fields


def check_ml_service(report: Report) -> None:
    rel = "services/ml_api/main.py"
    base_rest, base_fields = _ml_module(git_bytes(BASELINE, rel))
    head_rest, head_fields = _ml_module((REPO_ROOT / rel).read_bytes())
    lost = sorted(
        name for name, dump in base_fields.items() if head_fields.get(name) != dump
    )
    ok = base_rest == head_rest and not lost
    report.add(
        "F4c servicio ML",
        "PASS" if ok else "FAIL",
        "idéntico salvo _ranking y campos nuevos de RankingResult",
        "OK" if ok else f"resto_igual={base_rest == head_rest} campos_alterados={lost}",
    )


def check_artifacts(report: Report) -> None:
    result = subprocess.run(
        [sys.executable, "-B", "scripts/verify_reproducibility.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    ok = result.returncode == 0 and "VERIFICADOS (5)" in result.stdout
    report.add(
        "F5 verify_reproducibility",
        "PASS" if ok else "FAIL",
        "exit 0, VERIFICADOS (5), sin discrepancias",
        f"exit {result.returncode}",
    )
    eol = git("ls-files", "--eol", "--", *CRLF_ARTIFACTS).splitlines()
    eol_ok = len(eol) == 3 and all(
        line.startswith("i/crlf") and "attr/-text" in line for line in eol
    )
    report.add(
        "F5 contrato CRLF (.gitattributes)",
        "PASS" if eol_ok else "FAIL",
        "3 snapshots i/crlf attr/-text",
        f"{sum('i/crlf' in line for line in eol)}/3",
    )


def check_file_pins(report: Report) -> None:
    for rel, pin in FILE_PINS.items():
        actual = sha256_file(rel)
        report.add(
            f"F6/F9 {rel}", "PASS" if actual == pin else "FAIL", pin[:12], actual[:12]
        )
    migrations = git("ls-files", "db/migration").splitlines()

    def is_new_migration(path: str) -> bool:
        name = Path(path).name
        return name[:1] == "V" and name[1:4].isdigit() and int(name[1:4]) >= 4

    unexpected = [
        path
        for path in migrations
        if path not in FILE_PINS and not is_new_migration(path)
    ]
    report.add(
        "F6 db/migration",
        "FAIL" if unexpected else "PASS",
        "V001-V003 fijados; solo V004+ nuevos",
        ", ".join(unexpected) or f"{len(migrations)} archivos",
    )
    models = sorted(git("ls-files", "models").splitlines())
    expected_models = sorted(
        [
            "models/.gitkeep",
            "models/prototype_model_d.pkl",
            "models/prototype_model_d_metadata.json",
        ]
    )
    report.add(
        "F9 models/",
        "PASS" if models == expected_models else "FAIL",
        "solo .gitkeep, pkl y metadata",
        ", ".join(models),
    )


def check_accidental(report: Report, allow_dirty: bool) -> None:
    status = git("status", "--porcelain=v1", "--untracked-files=all").splitlines()
    report.add(
        "F8 worktree limpio",
        "PASS" if not status else ("WARN" if allow_dirty else "FAIL"),
        "git status vacío",
        f"{len(status)} entrada(s)" + (": " + ", ".join(status[:5]) if status else ""),
    )
    ignored = [
        line
        for line in git(
            "status", "--porcelain", "--ignored", "--untracked-files=all"
        ).splitlines()
        if line.startswith("!!") and not any(m in line for m in IGNORED_CACHE_MARKERS)
    ]
    report.add(
        "F8 ignorados inesperados",
        "FAIL" if ignored else "PASS",
        "sin archivos ignorados fuera de caches",
        ", ".join(ignored[:5]) or "ninguno",
    )
    stash = git("stash", "list")
    worktrees = git("worktree", "list").splitlines()
    report.add(
        "F8 stash/worktrees",
        "PASS" if not stash and len(worktrees) == 1 else "FAIL",
        "stash vacío, 1 worktree",
        f"stash={len(stash.splitlines())} worktrees={len(worktrees)}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--json", type=Path, help="escribe el reporte JSON en esta ruta"
    )
    parser.add_argument(
        "--allow-dirty", action="store_true", help="F8 worktree sucio = WARN"
    )
    parser.add_argument(
        "--allow-tag", action="append", default=[], help="tag nuevo autorizado"
    )
    parser.add_argument("--skip-remote", action="store_true", help="no consulta origin")
    parser.add_argument("--skip-fingerprint", action="store_true", help="omite F2")
    args = parser.parse_args()

    report = Report()
    mode = check_identity(report, set(args.allow_tag), args.skip_remote)
    check_accidental(report, args.allow_dirty)
    check_file_pins(report)
    check_contracts(report)
    check_ml_service(report)
    check_readiness(report)
    check_frozen_paths(report)
    check_artifacts(report)
    check_fingerprint(report, args.skip_fingerprint)

    header = {
        "baseline": BASELINE,
        "head": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "mode": mode,
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": platform.node(),
        "python": platform.python_version(),
        "git": git("--version"),
        "command": "python -B scripts/freeze_check.py " + " ".join(sys.argv[1:]),
        "verdict": "FREEZE CHECK FAILED" if report.failed else "FREEZE CHECK PASS",
    }
    for key, value in header.items():
        print(f"{key}: {value}")
    width = max(len(row["check"]) for row in report.rows)
    for row in report.rows:
        print(
            f"{row['status']:<5} {row['check']:<{width}}  "
            f"esperado={row['expected']}  observado={row['observed']}"
        )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({**header, "checks": report.rows}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
