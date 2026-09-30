"""Materializador del workspace operacional canónico (resuelve CRR-OPS-02).

Construye un directorio operacional NUEVO con:
  1. el código exacto de un SHA commiteado (fetch depth 1 + checkout
     detached desde el objeto Git; nunca se copia un worktree mutable);
  2. copias físicas e independientes de los stores `raw`, `processed` y
     `models` (sin symlinks, junctions ni hardlinks hacia la fuente);
  3. un manifiesto determinista (ruta relativa, tamaño, sha256);
  4. verificación de la copia, de la inmutabilidad de la fuente y de la
     guarda `workspace_safety` en modo OPERATIONAL_REAL_DATA.

Todo se construye en `<destino>.staging-<run_id>` y solo se promueve
(renombre atómico) si cada verificación pasa. Los stores de origen nunca se
modifican. Ante un fallo, el staging queda marcado como FAILED y no se borra.

La copia real exige un gate humano: `--confirm-real-copy <PLAN_ID>`, donde
PLAN_ID es el que imprime `plan` para exactamente estas entradas y este
estado de los stores. `--dry-run` no escribe nada.

Comandos:
    python -m src.ops.operational_workspace plan|materialize|verify|status ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional

from src.ops import workspace_safety as ws

SCHEMA_VERSION = 1
MANIFEST_NAME = "OPERATIONAL-WORKSPACE-MANIFEST.json"
IDENTITY_NAME = "CODE-IDENTITY.json"
FAILED_MARKER = "MATERIALIZATION-FAILED.json"
REQUIRED_STORES = ("raw", "processed", "models")
METADATA_EXCLUDES = (f"/{MANIFEST_NAME}", f"/{IDENTITY_NAME}", f"/{FAILED_MARKER}")

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_INCOMPLETE = (
    ws.EXIT_PASS,
    ws.EXIT_FAIL,
    ws.EXIT_USAGE,
    ws.EXIT_INCOMPLETE,
)
EXIT_BLOCKED = 4  # falta el gate humano o el plan cambió

MIN_MARGIN_BYTES = 256 * 1024 * 1024
MARGIN_RATIO = 0.10
_FULL_SHA = re.compile(r"[0-9a-f]{40}")
_CRITICAL = re.compile(
    r"(^CURRENT.*\.json$|^history.*\.jsonl$|manifest.*\.json$|\.sha256$)", re.I
)
_SECRET_NAME = re.compile(
    r"(^|/)(\.env(\.(?!example$)[^/]+)?|[^/]*\.pem|id_rsa[^/]*"
    r"|credentials[^/]*|secrets?\.(json|ya?ml|txt))$",
    re.I,
)
_SECRET_CONTENT = re.compile(
    rb"/csv/[0-9a-fA-F]{32}|(?i:(map_?key|api_?key|token|usuario)="
    rb"(?!your[_-]|<|\$\{|changeme|example|xxx|redacted)[^&\s\"'<>]{6,})"
)
SECRET_SCAN_MAX_BYTES = 50 * 1024 * 1024
_READ_CHUNK = 1024 * 1024

FINDINGS = {
    "MW-001": "INVALID_OR_UNKNOWN_SHA",
    "MW-002": "SOURCE_STORE_MISSING",
    "MW-003": "SOURCE_STORE_ROOT_REPARSE",
    "MW-004": "SOURCE_STORE_INTERNAL_REPARSE",
    "MW-005": "DESTINATION_EXISTS",
    "MW-006": "DESTINATION_REPARSE",
    "MW-007": "DESTINATION_OVERLAP",
    "MW-008": "INSUFFICIENT_SPACE",
    "MW-009": "TRACKED_FILE_CONFLICT",
    "MW-010": "SOURCE_UNREADABLE",
    "MW-011": "SECRET_DETECTED",
    "MW-012": "COPY_VERIFICATION_MISMATCH",
    "MW-013": "SOURCE_CHANGED_DURING_COPY",
    "MW-014": "DESTINATION_NOT_PHYSICAL",
    "MW-015": "WORKSPACE_SAFETY_NOT_PASS",
    "MW-016": "STAGING_CONFLICT",
    "MW-017": "DESTINATION_PARENT_MISSING",
    "MW-018": "REQUIRED_STORE_NOT_DECLARED",
    "MW-019": "GIT_EXTRACTION_FAILED",
    "MW-020": "UNKNOWN_STORE_NAME",
}
# Solo MW-003 es advertencia (la fuente se lee desde su ruta física resuelta).
_WARN_ONLY = {"MW-003"}


class MaterializationError(RuntimeError):
    def __init__(self, finding_id: str, message: str, subject: Optional[str] = None):
        super().__init__(message)
        self.finding = _finding(finding_id, message, subject)


def _finding(finding_id: str, message: str, subject: Optional[str] = None) -> dict:
    return {
        "id": finding_id,
        "code": FINDINGS[finding_id],
        "severity": "WARN" if finding_id in _WARN_ONLY else "FAIL",
        "message": message,
        "subject": subject,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _long(path) -> str:
    """Ruta apta para rutas largas en Windows (prefijo \\\\?\\ en absolutas)."""
    text = os.path.abspath(str(path))
    if os.name == "nt" and not text.startswith("\\\\?\\") and len(text) > 240:
        return (
            "\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text
        )
    return text


def _sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(_long(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(_READ_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _disk_free(path: str) -> int:
    return shutil.disk_usage(path).free


def _git(repo: str, *args: str, check: bool = False) -> Optional[str]:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
    try:
        done = subprocess.run(
            ["git", "--no-optional-locks", "-C", repo, *args],
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if check:
            raise MaterializationError(
                "MW-019", f"git {args[0]} no se pudo ejecutar: {type(exc).__name__}"
            ) from None
        return None
    if done.returncode != 0:
        if check:
            raise MaterializationError(
                "MW-019", f"git {args[0]} falló (exit {done.returncode})"
            )
        return None
    return done.stdout.strip()


# --- Inventario de stores (solo lectura) ---------------------------------------


def walk_store(root: str) -> dict:
    """Inventario sin seguir enlaces.

    Devuelve {files: {rel: (size, mtime_ns)}, dirs, reparse, unreadable}."""
    files: dict[str, tuple[int, int]] = {}
    dirs: list[str] = []
    reparse: list[dict] = []
    unreadable: list[str] = []
    stack = [""]
    while stack:
        rel_dir = stack.pop()
        current = os.path.join(root, rel_dir) if rel_dir else root
        try:
            entries = sorted(os.scandir(_long(current)), key=lambda e: e.name)
        except OSError:
            unreadable.append(rel_dir or ".")
            continue
        for entry in entries:
            rel = f"{rel_dir}/{entry.name}" if rel_dir else entry.name
            info = ws.classify_entry(entry.path)
            if info["kind"] == "directory":
                dirs.append(rel)
                stack.append(rel)
            elif info["kind"] == "file":
                try:
                    st = entry.stat(follow_symlinks=False)
                    files[rel] = (st.st_size, st.st_mtime_ns)
                except OSError:
                    unreadable.append(rel)
            elif info["kind"] == "unknown":
                unreadable.append(rel)
            else:
                reparse.append({"path": rel, **info})
    return {
        "files": dict(sorted(files.items())),
        "dirs": sorted(dirs),
        "reparse": reparse,
        "unreadable": unreadable,
    }


def _listing_digest(files: Mapping[str, tuple[int, int]]) -> str:
    return _canonical_sha(
        sorted([rel, size, mtime] for rel, (size, mtime) in files.items())
    )


# --- Solicitud y plan -----------------------------------------------------------


@dataclass(frozen=True)
class WorkspaceRequest:
    repo_root: Path
    code_sha: str
    source_stores: Mapping[str, Path]
    destination: Path
    margin_bytes: Optional[int] = None
    environ: Optional[Mapping[str, str]] = field(default=None, compare=False)

    @classmethod
    def from_dict(cls, data: Mapping) -> "WorkspaceRequest":
        return cls(
            repo_root=Path(data["repo_root"]),
            code_sha=data["code_sha"],
            source_stores={k: Path(v) for k, v in data["source_stores"].items()},
            destination=Path(data["destination"]),
            margin_bytes=data.get("margin_bytes"),
        )


def plan(request: WorkspaceRequest) -> dict:
    """Solo lectura: identidad del código, inventario de fuentes, destino,
    espacio, escaneo de secretos del objeto Git y hallazgos."""
    findings: list[dict] = []
    repo = os.path.abspath(str(request.repo_root))
    sha = (request.code_sha or "").strip().lower()
    code: dict = {
        "repo_root": repo,
        "sha": sha,
        "tree": None,
        "commit_exists": False,
        "blob_bytes": None,
    }
    if not _FULL_SHA.fullmatch(sha):
        findings.append(
            _finding(
                "MW-001", "code_sha debe ser un SHA completo de 40 hex", sha or None
            )
        )
    elif _git(repo, "cat-file", "-e", f"{sha}^{{commit}}") is None:
        findings.append(
            _finding("MW-001", "El SHA no existe como commit en el repositorio", sha)
        )
    else:
        code["commit_exists"] = True
        code["tree"] = _git(repo, "rev-parse", f"{sha}^{{tree}}")
        listing = _git(repo, "ls-tree", "-r", "-l", "--full-tree", sha) or ""
        rows = [line.split(None, 4) for line in listing.splitlines()]
        code["tracked_files"] = len(rows)
        code["blob_bytes"] = sum(
            int(r[3]) for r in rows if len(r) == 5 and r[3].isdigit()
        )
        names = [r[4] for r in rows if len(r) == 5]
        bad_names = [n for n in names if _SECRET_NAME.search(n)]
        grep = _git(repo, "grep", "-I", "-l", "-E", r"/csv/[0-9a-fA-F]{32}", sha)
        content_hits = [line.split(":", 1)[-1] for line in (grep or "").splitlines()]
        code["secret_scan"] = {
            "secret_named_files": bad_names,
            "firms_key_url_files": content_hits,
            "status": "FAIL" if bad_names or content_hits else "PASS",
        }
        for n in bad_names + content_hits:
            findings.append(
                _finding(
                    "MW-011",
                    "El commit contiene un archivo con nombre o contenido de secreto",
                    n,
                )
            )

    names = set(request.source_stores)
    for missing in sorted(set(REQUIRED_STORES) - names):
        findings.append(_finding("MW-018", "Store obligatorio no declarado", missing))
    for unknown in sorted(names - set(REQUIRED_STORES)):
        findings.append(_finding("MW-020", "Nombre de store no soportado", unknown))

    stores, total_bytes = [], 0
    for name in [n for n in REQUIRED_STORES if n in names]:
        requested = os.path.abspath(str(request.source_stores[name]))
        chain, unknown = ws.reparse_chain(requested)
        resolved = os.path.realpath(requested)
        entry = {
            "logical_name": name,
            "destination_subpath": ws.CODE_STORE_SUBPATHS[name],
            "requested_path": requested,
            "resolved_path": resolved,
            "reparse_points": chain,
            "file_count": 0,
            "total_bytes": 0,
            "dir_count": 0,
            "critical_files": {},
        }
        if not os.path.isdir(resolved):
            findings.append(
                _finding(
                    "MW-002", "El store de origen no existe o no es un directorio", name
                )
            )
            stores.append(entry)
            continue
        if chain or unknown:
            findings.append(
                _finding(
                    "MW-003",
                    "La ruta del store atraviesa enlaces/reparse points; "
                    "se leerá desde la ruta física resuelta",
                    name,
                )
            )
        inv = walk_store(resolved)
        for r in inv["reparse"]:
            findings.append(
                _finding(
                    "MW-004",
                    f"Enlace/reparse point dentro del store ({r['kind']})",
                    f"{name}/{r['path']}",
                )
            )
        for u in inv["unreadable"]:
            findings.append(
                _finding("MW-010", "Entrada ilegible dentro del store", f"{name}/{u}")
            )
        entry.update(
            file_count=len(inv["files"]),
            dir_count=len(inv["dirs"]),
            total_bytes=sum(s for s, _ in inv["files"].values()),
            listing_digest=_listing_digest(inv["files"]),
        )
        for rel in inv["files"]:
            if _CRITICAL.search(rel.rsplit("/", 1)[-1]):
                try:
                    entry["critical_files"][rel] = _sha256_file(
                        os.path.join(resolved, rel)
                    )
                except OSError:
                    findings.append(
                        _finding("MW-010", "Archivo crítico ilegible", f"{name}/{rel}")
                    )
        total_bytes += entry["total_bytes"]
        stores.append(entry)

    dest = os.path.abspath(str(request.destination))
    parent = os.path.dirname(dest)
    dest_chain, dest_unknown = ws.reparse_chain(dest)
    destination = {
        "path": dest,
        "exists": os.path.lexists(dest),
        "parent_exists": os.path.isdir(parent),
        "reparse_points": dest_chain,
        "staging_pattern": f"{dest}.staging-<run_id>",
    }
    if destination["exists"]:
        findings.append(
            _finding(
                "MW-005",
                "El destino ya existe; nunca se sobrescribe un workspace",
                dest,
            )
        )
    if not destination["parent_exists"]:
        findings.append(
            _finding("MW-017", "El directorio padre del destino no existe", parent)
        )
    if dest_chain or dest_unknown:
        findings.append(
            _finding(
                "MW-006", "La ruta del destino atraviesa enlaces/reparse points", dest
            )
        )
    dest_norm = ws._norm(os.path.realpath(dest))
    for other, label in [(repo, "repositorio de origen")] + [
        (s["resolved_path"], f"store {s['logical_name']}") for s in stores
    ]:
        o = ws._norm(os.path.realpath(other))
        if ws._is_within(dest_norm, o) or ws._is_within(o, dest_norm):
            findings.append(
                _finding("MW-007", f"El destino se solapa con el {label}", dest)
            )

    code_bytes = 2 * (
        code.get("blob_bytes") or 0
    )  # checkout + pack depth 1 (cota superior)
    required = total_bytes + code_bytes
    margin = (
        request.margin_bytes
        if request.margin_bytes is not None
        else max(MIN_MARGIN_BYTES, int(required * MARGIN_RATIO))
    )
    try:
        free = _disk_free(parent) if destination["parent_exists"] else None
    except OSError:
        free = None
    space = {
        "store_bytes": total_bytes,
        "code_bytes_estimate": code_bytes,
        "margin_bytes": margin,
        "required_bytes": required + margin,
        "free_bytes": free,
        "sufficient": None if free is None else free >= required + margin,
    }
    if space["sufficient"] is False:
        findings.append(
            _finding(
                "MW-008",
                f"Espacio libre {free} < requerido {required + margin} (incluye margen)",
                parent,
            )
        )
    elif space["sufficient"] is None and destination["parent_exists"]:
        findings.append(
            _finding("MW-010", "No se pudo medir el espacio libre del destino", parent)
        )

    plan_basis = {
        "repo": ws._norm(repo),
        "sha": sha,
        "tree": code.get("tree"),
        "destination": ws._norm(dest),
        "stores": [
            [
                s["logical_name"],
                ws._norm(s["resolved_path"]),
                s["file_count"],
                s["total_bytes"],
                s.get("listing_digest"),
                s["critical_files"],
            ]
            for s in stores
        ],
    }
    status = "FAIL" if any(f["severity"] == "FAIL" for f in findings) else "PASS"
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "plan",
        "observed_at": _now(),
        "plan_id": _canonical_sha(plan_basis)[:16],
        "code": code,
        "source_stores": stores,
        "destination": destination,
        "space": space,
        "findings": findings,
        "overall_status": status,
    }


# --- Materialización ------------------------------------------------------------


def _copy_file(src: str, dst: str) -> str:
    """Copia byte a byte a un archivo NUEVO (exclusivo) y devuelve el sha256 leído de la fuente."""
    h = hashlib.sha256()
    with open(_long(src), "rb") as fin, open(_long(dst), "xb") as fout:
        for chunk in iter(lambda: fin.read(_READ_CHUNK), b""):
            h.update(chunk)
            fout.write(chunk)
    shutil.copystat(_long(src), _long(dst), follow_symlinks=False)
    return h.hexdigest()


def _extract_code(repo: str, sha: str, tree: str, staging: str) -> dict:
    _git(staging, "init", "-q", check=True)
    _git(staging, "config", "core.autocrlf", "false", check=True)
    _git(staging, "config", "core.symlinks", "false", check=True)
    _git(staging, "fetch", "-q", "--depth", "1", "--no-tags", repo, sha, check=True)
    _git(staging, "checkout", "-q", "--detach", sha, check=True)
    head, got_tree = _git(staging, "rev-parse", "HEAD"), _git(
        staging, "rev-parse", "HEAD^{tree}"
    )
    if head != sha or got_tree != tree:
        raise MaterializationError(
            "MW-019", f"Código extraído {head}/{got_tree} != {sha}/{tree}"
        )
    if _git(staging, "remote") not in ("", None):
        raise MaterializationError(
            "MW-019", "El checkout extraído no debe tener remotos"
        )
    return {
        "sha": head,
        "tree": got_tree,
        "method": "git fetch --depth 1 + checkout --detach (core.autocrlf=false)",
    }


def _write_excludes(staging: str, store_subpaths: list[str]) -> list[str]:
    lines = list(METADATA_EXCLUDES) + [f"/{p}/" for p in store_subpaths]
    info = Path(staging, ".git", "info")
    info.mkdir(parents=True, exist_ok=True)
    with open(info / "exclude", "a", encoding="utf-8") as fh:
        fh.write(
            "\n# operational_workspace: metadatos y stores "
            "(verificados por manifiesto, no por Git)\n"
        )
        fh.write("\n".join(lines) + "\n")
    return lines


def _copy_store(
    src_root: str, dst_root: str, inv: dict, name: str, tracked: set[str], subpath: str
) -> list[dict]:
    os.makedirs(_long(dst_root), exist_ok=True)
    for rel in inv["dirs"]:
        os.makedirs(_long(os.path.join(dst_root, rel)), exist_ok=True)
    entries = []
    for rel in inv["files"]:
        src, dst = os.path.join(src_root, rel), os.path.join(dst_root, rel)
        workspace_rel = f"{subpath}/{rel}"
        try:
            if workspace_rel in tracked and os.path.exists(_long(dst)):
                digest = _sha256_file(src)
                if _sha256_file(dst) != digest:
                    raise MaterializationError(
                        "MW-009",
                        "El store sobrescribiría un archivo commiteado con otro contenido",
                        workspace_rel,
                    )
                origin = "identical_to_committed"
            else:
                digest = _copy_file(src, dst)
                origin = "copied"
        except FileNotFoundError:
            raise MaterializationError(
                "MW-013",
                "Un archivo de origen desapareció durante la copia",
                f"{name}/{rel}",
            ) from None
        except FileExistsError:
            raise MaterializationError(
                "MW-016", "El archivo destino ya existía en staging", workspace_rel
            ) from None
        entries.append(
            {
                "path": workspace_rel,
                "size": inv["files"][rel][0],
                "sha256": digest,
                "origin": origin,
            }
        )
    return entries


def _verify_copy(
    staging: str, src_root: str, entries: list[dict], subpath: str
) -> None:
    for e in entries:
        dst = os.path.join(staging, e["path"])
        src = os.path.join(src_root, e["path"][len(subpath) + 1 :])
        try:
            st = os.stat(_long(dst))
        except OSError:
            raise MaterializationError(
                "MW-012", "Falta un archivo en el staging", e["path"]
            ) from None
        if st.st_size != e["size"] or _sha256_file(dst) != e["sha256"]:
            raise MaterializationError(
                "MW-012", "Tamaño o sha256 distinto entre fuente y destino", e["path"]
            )
        if e["origin"] == "copied":
            sst = os.stat(_long(src))
            if st.st_nlink != 1 or (st.st_dev, st.st_ino) == (sst.st_dev, sst.st_ino):
                raise MaterializationError(
                    "MW-014",
                    "El archivo destino no es una copia física independiente",
                    e["path"],
                )


def _recheck_source(store: dict, entries: list[dict]) -> None:
    after = walk_store(store["resolved_path"])
    if (
        _listing_digest(after["files"]) != store["listing_digest"]
        or after["reparse"]
        or after["unreadable"]
    ):
        raise MaterializationError(
            "MW-013",
            "El store de origen cambió durante la copia (listado distinto)",
            store["logical_name"],
        )
    prefix = store["destination_subpath"] + "/"
    for e in entries:
        rel = e["path"][len(prefix) :]
        if _sha256_file(os.path.join(store["resolved_path"], rel)) != e["sha256"]:
            raise MaterializationError(
                "MW-013",
                "Contenido de origen cambió durante la copia",
                f"{store['logical_name']}/{rel}",
            )


def _secret_scan_tree(root: str, store_subpaths: list[str]) -> dict:
    named, content = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/")
            if _SECRET_NAME.search(rel):
                named.append(rel)
            if any(rel == p or rel.startswith(p + "/") for p in store_subpaths):
                path = os.path.join(dirpath, fn)
                if os.path.getsize(path) <= SECRET_SCAN_MAX_BYTES:
                    with open(_long(path), "rb") as fh:
                        if _SECRET_CONTENT.search(fh.read()):
                            content.append(rel)
    return {
        "secret_named_files": sorted(named),
        "secret_content_files": sorted(content),
        "status": "FAIL" if named or content else "PASS",
        "values_recorded": False,
    }


def _guard(workspace: str, sha: str, tree: str, environ) -> dict:
    stores = {
        n: os.path.join(workspace, ws.CODE_STORE_SUBPATHS[n]) for n in REQUIRED_STORES
    }
    return ws.check_workspace(
        ws.GuardRequest(
            mode=ws.Mode.OPERATIONAL_REAL_DATA,
            code_root=Path(workspace),
            expected_code_sha=sha,
            expected_tree_sha=tree,
            stores={k: Path(v) for k, v in stores.items()},
            environ=environ,
        )
    )


def _write_json(path: str, data: dict) -> None:
    with open(_long(path), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


def materialize(
    request: WorkspaceRequest,
    *,
    confirm_plan_id: Optional[str] = None,
    dry_run: bool = False,
    stage_only: bool = False,
) -> dict:
    """Plan → gate humano → staging → código → stores → verificación → guarda → promoción.
    Con `dry_run=True` no escribe nada. Sin `confirm_plan_id` igual al plan actual: BLOCKED.
    """
    environ = os.environ if request.environ is None else request.environ
    p = plan(request)
    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": "materialize",
        "observed_at": _now(),
        "dry_run": dry_run,
        "plan": p,
        "findings": list(p["findings"]),
        "promotion_status": "NOT_STARTED",
    }
    if p["overall_status"] != "PASS":
        return {**result, "overall_status": "FAIL", "exit_code": EXIT_FAIL}
    if dry_run:
        return {
            **result,
            "overall_status": "PASS",
            "exit_code": EXIT_PASS,
            "promotion_status": "DRY_RUN",
            "note": "Dry run: sin extracción de código, sin copia, sin crear destino ni staging.",
        }
    if confirm_plan_id != p["plan_id"]:
        return {
            **result,
            "overall_status": "BLOCKED",
            "exit_code": EXIT_BLOCKED,
            "note": "Gate humano: la copia real exige --confirm-real-copy igual al plan_id actual "
            f"({p['plan_id']}). Revise el plan antes de confirmar.",
        }

    sha, tree, dest = p["code"]["sha"], p["code"]["tree"], p["destination"]["path"]
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + p["plan_id"][:8]
    )
    staging = f"{dest}.staging-{run_id}"
    subpaths = [ws.CODE_STORE_SUBPATHS[n] for n in REQUIRED_STORES]
    manifest: dict = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "plan_id": p["plan_id"],
        "code_sha": sha,
        "tree_sha": tree,
        "source_repository": p["code"]["repo_root"],
        "destination": dest,
        "staging": staging,
        "created_at": _now(),
        "promotion_status": "STAGING",
        "source_store_paths": {
            s["logical_name"]: {
                "requested": s["requested_path"],
                "resolved": s["resolved_path"],
            }
            for s in p["source_stores"]
        },
    }
    try:
        os.mkdir(_long(staging))
    except OSError as exc:
        return {
            **result,
            "overall_status": "FAIL",
            "exit_code": EXIT_FAIL,
            "findings": result["findings"]
            + [
                _finding(
                    "MW-016",
                    f"No se pudo crear el staging ({type(exc).__name__})",
                    staging,
                )
            ],
        }
    try:
        code = _extract_code(p["code"]["repo_root"], sha, tree, staging)
        manifest["excludes"] = _write_excludes(staging, subpaths)
        tracked = set((_git(staging, "ls-files") or "").splitlines())
        identity = {
            "schema_version": SCHEMA_VERSION,
            "sha": sha,
            "tree": tree,
            "materialized_at": _now(),
            "source_repository": p["code"]["repo_root"],
            "run_id": run_id,
            "extraction": code["method"],
        }
        _write_json(os.path.join(staging, IDENTITY_NAME), identity)
        store_manifests = {}
        for store in p["source_stores"]:
            name, sub = store["logical_name"], store["destination_subpath"]
            inv = walk_store(store["resolved_path"])
            if _listing_digest(inv["files"]) != store["listing_digest"]:
                raise MaterializationError(
                    "MW-013", "El store de origen cambió entre el plan y la copia", name
                )
            entries = _copy_store(
                store["resolved_path"],
                os.path.join(staging, sub),
                inv,
                name,
                tracked,
                sub,
            )
            _recheck_source(store, entries)
            _verify_copy(staging, store["resolved_path"], entries, sub)
            for rel, digest in store["critical_files"].items():
                if _sha256_file(os.path.join(staging, sub, rel)) != digest:
                    raise MaterializationError(
                        "MW-012",
                        "Archivo crítico distinto en el destino",
                        f"{sub}/{rel}",
                    )
            store_manifests[name] = {
                "file_count": len(entries),
                "total_bytes": sum(e["size"] for e in entries),
                "files": entries,
                "manifest_sha256": _canonical_sha(
                    [[e["path"], e["size"], e["sha256"]] for e in entries]
                ),
            }
        manifest["stores"] = store_manifests
        manifest["file_count"] = sum(m["file_count"] for m in store_manifests.values())
        manifest["total_bytes"] = sum(
            m["total_bytes"] for m in store_manifests.values()
        )
        manifest["copy_verification"] = "PASS"
        reparse, limited = ws._scan_context_reparse(
            staging, skip={ws._norm(os.path.join(staging, ".git"))}
        )
        if reparse or limited:
            raise MaterializationError(
                "MW-014",
                "El staging contiene enlaces/reparse points o no se pudo escanear",
                staging,
            )
        manifest["physical_check"] = "PASS"
        manifest["secret_scan"] = _secret_scan_tree(staging, subpaths)
        if manifest["secret_scan"]["status"] != "PASS":
            raise MaterializationError(
                "MW-011",
                "Secretos detectados en el staging (solo rutas registradas)",
                staging,
            )
        guard = _guard(staging, sha, tree, environ)
        manifest["workspace_safety"] = {"staging": guard}
        if guard["overall_status"] != "PASS":
            raise MaterializationError(
                "MW-015",
                f"workspace_safety OPERATIONAL_REAL_DATA = {guard['overall_status']}: "
                + ", ".join(
                    sorted({f["id"] for f in guard["failures"] + guard["incomplete"]})
                ),
                staging,
            )
        manifest["promotion_status"] = "VALIDATED"
        _write_json(os.path.join(staging, MANIFEST_NAME), manifest)
        if stage_only:
            return {
                **result,
                "overall_status": "PASS",
                "exit_code": EXIT_PASS,
                "promotion_status": "VALIDATED",
                "staging": staging,
                "manifest": manifest,
            }
        if os.path.lexists(dest):
            raise MaterializationError(
                "MW-005",
                "El destino apareció antes de la promoción; no se sobrescribe",
                dest,
            )
        os.rename(_long(staging), _long(dest))
    except MaterializationError as exc:
        return _fail(result, manifest, staging, exc.finding)
    except OSError as exc:
        return _fail(
            result,
            manifest,
            staging,
            _finding(
                "MW-012",
                f"Error de E/S durante la materialización ({type(exc).__name__})",
                staging,
            ),
        )

    final_guard = _guard(dest, sha, tree, environ)
    manifest["workspace_safety"]["promoted"] = final_guard
    manifest["promotion_status"] = (
        "PROMOTED"
        if final_guard["overall_status"] == "PASS"
        else "PROMOTED_POSTCHECK_FAILED"
    )
    manifest["promoted_at"] = _now()
    _write_json(os.path.join(dest, MANIFEST_NAME), manifest)
    ok = manifest["promotion_status"] == "PROMOTED"
    return {
        **result,
        "overall_status": "PASS" if ok else "FAIL",
        "exit_code": EXIT_PASS if ok else EXIT_FAIL,
        "promotion_status": manifest["promotion_status"],
        "destination": dest,
        "manifest": manifest,
    }


def _fail(result: dict, manifest: dict, staging: str, finding: dict) -> dict:
    manifest["promotion_status"] = "FAILED"
    marker = {
        "status": "FAILED",
        "failed_at": _now(),
        "finding": finding,
        "staging": staging,
        "cleanup": (
            "No se borra nada automáticamente. Revise este directorio como evidencia; contiene "
            "solo COPIAS (los stores de origen no se tocan). Para limpiarlo, verifique "
            "primero que la ruta termina en '.staging-<run_id>' y luego bórrela "
            "manualmente con una decisión humana."
        ),
    }
    try:
        _write_json(os.path.join(staging, FAILED_MARKER), marker)
        _write_json(os.path.join(staging, MANIFEST_NAME), manifest)
    except OSError:
        pass
    return {
        **result,
        "overall_status": "FAIL",
        "exit_code": EXIT_FAIL,
        "promotion_status": "FAILED",
        "staging": staging,
        "findings": result["findings"] + [finding],
        "manifest": manifest,
    }


# --- Verificación y estado (solo lectura) ----------------------------------------


def verify(workspace: Path, environ: Optional[Mapping[str, str]] = None) -> dict:
    """Reverifica un workspace materializado contra su manifiesto: hashes de
    stores, ausencia de enlaces y workspace_safety. No escribe nada."""
    root = os.path.abspath(str(workspace))
    findings: list[dict] = []
    try:
        with open(_long(os.path.join(root, MANIFEST_NAME)), encoding="utf-8") as fh:
            manifest = json.load(fh)
        with open(_long(os.path.join(root, IDENTITY_NAME)), encoding="utf-8") as fh:
            identity = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {
            "kind": "verify",
            "workspace": root,
            "observed_at": _now(),
            "overall_status": "INCOMPLETE",
            "exit_code": EXIT_INCOMPLETE,
            "findings": [_finding("MW-010", "Manifiesto o identidad ilegibles", root)],
        }
    drift = []
    for name, sm in manifest.get("stores", {}).items():
        for e in sm["files"]:
            path = os.path.join(root, e["path"])
            try:
                if _sha256_file(path) != e["sha256"]:
                    drift.append(e["path"])
            except OSError:
                drift.append(e["path"])
    if drift:
        findings.append(
            _finding(
                "MW-012",
                f"{len(drift)} archivos difieren del manifiesto (esperable después de refreshes)",
                drift[0],
            )
        )
    reparse, limited = ws._scan_context_reparse(
        root, skip={ws._norm(os.path.join(root, ".git"))}
    )
    if reparse or limited:
        findings.append(
            _finding("MW-014", "El workspace contiene enlaces/reparse points", root)
        )
    guard = _guard(
        root,
        identity["sha"],
        identity["tree"],
        os.environ if environ is None else environ,
    )
    if guard["overall_status"] != "PASS":
        findings.append(
            _finding("MW-015", f"workspace_safety = {guard['overall_status']}", root)
        )
    status = "FAIL" if findings else "PASS"
    return {
        "kind": "verify",
        "workspace": root,
        "observed_at": _now(),
        "run_id": manifest.get("run_id"),
        "code_sha": identity["sha"],
        "drifted_files": drift,
        "workspace_safety": guard,
        "findings": findings,
        "overall_status": status,
        "exit_code": EXIT_PASS if status == "PASS" else EXIT_FAIL,
    }


def status(destination: Path) -> dict:
    dest = os.path.abspath(str(destination))
    parent, base = os.path.dirname(dest), os.path.basename(dest)

    def read(root: str) -> dict:
        out = {"path": root}
        for name in (MANIFEST_NAME, FAILED_MARKER):
            try:
                with open(_long(os.path.join(root, name)), encoding="utf-8") as fh:
                    data = json.load(fh)
                out["promotion_status" if name == MANIFEST_NAME else "failed"] = (
                    data.get("promotion_status")
                    if name == MANIFEST_NAME
                    else data.get("finding")
                )
                if name == MANIFEST_NAME:
                    out.update(
                        run_id=data.get("run_id"),
                        code_sha=data.get("code_sha"),
                        file_count=data.get("file_count"),
                    )
            except (OSError, json.JSONDecodeError):
                pass
        return out

    stagings = (
        sorted(
            e.path for e in os.scandir(parent) if e.name.startswith(base + ".staging-")
        )
        if os.path.isdir(parent)
        else []
    )
    return {
        "kind": "status",
        "observed_at": _now(),
        "destination": read(dest) if os.path.isdir(dest) else None,
        "stagings": [read(s) for s in stagings],
    }


def run(command: str, request: Mapping) -> dict:
    """Entrada JSON-compatible para el operador del Attempt 2."""
    if command == "plan":
        return plan(WorkspaceRequest.from_dict(request))
    if command == "materialize":
        return materialize(
            WorkspaceRequest.from_dict(request),
            confirm_plan_id=request.get("confirm_plan_id"),
            dry_run=bool(request.get("dry_run")),
            stage_only=bool(request.get("stage_only")),
        )
    if command == "verify":
        return verify(Path(request["workspace"]))
    if command == "status":
        return status(Path(request["destination"]))
    raise ValueError(f"comando desconocido: {command}")


# --- CLI ---------------------------------------------------------------------------


def _summary(result: dict) -> str:
    lines = [
        f"[{result.get('overall_status', '-')}] {result.get('kind')} — {result.get('observed_at')}"
    ]
    p = result if result.get("kind") == "plan" else result.get("plan")
    if p:
        lines.append(
            f"plan_id {p['plan_id']} | código {p['code']['sha']} (tree {p['code']['tree']})"
        )
        for s in p["source_stores"]:
            lines.append(
                f"  {s['logical_name']:<9} {s['file_count']} archivos, "
                f"{s['total_bytes']} bytes <- {s['resolved_path']}"
            )
        sp = p["space"]
        lines.append(
            f"  destino {p['destination']['path']} | requerido {sp['required_bytes']} "
            f"| libre {sp['free_bytes']}"
        )
    for key in ("promotion_status", "staging", "destination", "note"):
        if isinstance(result.get(key), str):
            lines.append(f"{key}: {result[key]}")
    for f in result.get("findings", []):
        lines.append(
            f"  {f['severity']:<5} {f['id']} {f['code']}: {f['message']}"
            + (f" [{f['subject']}]" if f.get("subject") else "")
        )
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.ops.operational_workspace",
        description=(__doc__ or "").split("\n\n")[0],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--repo-root", required=True)
        sp.add_argument("--code-sha", required=True)
        sp.add_argument(
            "--source-store", action="append", default=[], metavar="NOMBRE=RUTA"
        )
        sp.add_argument("--destination", required=True)
        sp.add_argument("--margin-bytes", type=int)

    common(
        sub.add_parser(
            "plan", help="Solo lectura: inventario, espacio, hallazgos y plan_id"
        )
    )
    mat = sub.add_parser(
        "materialize", help="Staging + verificación + promoción (requiere gate humano)"
    )
    common(mat)
    mat.add_argument("--dry-run", action="store_true")
    mat.add_argument(
        "--confirm-real-copy",
        metavar="PLAN_ID",
        help="plan_id revisado; sin él la copia real queda BLOCKED",
    )
    mat.add_argument(
        "--stage-only", action="store_true", help="Validar en staging sin promover"
    )
    ver = sub.add_parser(
        "verify", help="Solo lectura: reverificar un workspace materializado"
    )
    ver.add_argument("--workspace", required=True)
    st = sub.add_parser(
        "status", help="Solo lectura: estado del destino y de sus stagings"
    )
    st.add_argument("--destination", required=True)
    for sp in (sub.choices["plan"], mat, ver, st):
        sp.add_argument("--json", action="store_true")
        sp.add_argument("--json-out")
    args = parser.parse_args(argv)
    # Consolas Windows en cp1252: nunca abortar por un carácter de ruta o mensaje.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="replace")
    request: Optional[WorkspaceRequest] = None
    if args.command in ("plan", "materialize"):
        stores = {}
        for value in args.source_store:
            name, sep, path = value.partition("=")
            if not sep:
                parser.error(f"--source-store espera nombre=RUTA: {value!r}")
            stores[name.strip()] = Path(path)
        request = WorkspaceRequest(
            Path(args.repo_root),
            args.code_sha,
            stores,
            Path(args.destination),
            args.margin_bytes,
        )
        result = (
            plan(request)
            if args.command == "plan"
            else materialize(
                request,
                confirm_plan_id=args.confirm_real_copy,
                dry_run=args.dry_run,
                stage_only=args.stage_only,
            )
        )
    elif args.command == "verify":
        result = verify(Path(args.workspace))
    else:
        result = status(Path(args.destination))
    if args.json_out:
        out = ws._norm(os.path.realpath(args.json_out))
        guarded = (
            [str(v) for v in request.source_stores.values()]
            if request is not None
            else []
        )
        if any(ws._is_within(out, ws._norm(os.path.realpath(g))) for g in guarded):
            print(
                "--json-out no puede apuntar dentro de un store de origen",
                file=sys.stderr,
            )
            return EXIT_USAGE
        Path(args.json_out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(result, ensure_ascii=False, indent=2)
        if args.json
        else _summary(result)
    )
    code = result.get("exit_code")
    if code is None:
        statuses = {"PASS": EXIT_PASS, "FAIL": EXIT_FAIL, "INCOMPLETE": EXIT_INCOMPLETE}
        code = statuses.get(str(result.get("overall_status")), EXIT_PASS)
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
