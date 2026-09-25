"""Guard observacional del workspace operacional (CRR-OPS-02).

Responde una sola pregunta: ¿la topología de este checkout y de estos stores
cumple la política declarada para el modo de operación pedido, en este
instante? Nunca modifica nada: no crea ni borra enlaces, no toca Git (solo
comandos de lectura con `--no-optional-locks`), no monta, no arranca Docker,
no ejecuta refresh ni cambia CURRENT.

Motivación: el código integrado es la autoridad, pero los stores reales viven
históricamente en el checkout WIP. Un worktree post-merge con `data/` y
`models/` enlazados a esos stores produjo un casi-incidente real (un refresh
desde ahí habría escrito en los stores). Además, parte del código fija rutas
relativas a la raíz del repo (`firms_source.FIRMS_CURRENT_DIR`,
`prototype_service.MODEL_PATH`) mientras `src.config` acepta overrides por
variable de entorno: el código lee y escribe en `code_root/data/*` y
`code_root/models`, y un override parcial dividiría las lecturas.

Un PASS significa solo que la topología observada cumplió la política
declarada en `observed_at`. No es una autorización ni una garantía futura.
UNKNOWN nunca se convierte en PASS.

Uso:
    python -m src.ops.workspace_safety check --mode operational-real-data \\
        --code-root PATH --expected-code-sha SHA \\
        --store raw=PATH --store processed=PATH --store models=PATH
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Mapping, Optional

SCHEMA_VERSION = 1
GUARD_NAME = "sapi-workspace-safety"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2  # argparse
EXIT_INCOMPLETE = 3

# Dónde lee y escribe el código de SAPI, relativo a la raíz del checkout
# (espejo de los defaults de src/config.py y de las rutas fijas de
# firms_source / prototype_service).
CODE_STORE_SUBPATHS: dict[str, str] = {
    "raw": "data/raw",
    "processed": "data/processed",
    "predictions": "data/predictions",
    "models": "models",
}
# Variables que redirigen solo una parte del código (ver docstring).
STORE_ENV_OVERRIDES = (
    "DATA_RAW_DIR",
    "DATA_PROCESSED_DIR",
    "DATA_PREDICTIONS_DIR",
    "MODELS_DIR",
)
DOCKER_SCAN_LIMIT = 300_000

_FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003  # junction
_IO_REPARSE_TAG_SYMLINK = 0xA000000C
_FULL_SHA = re.compile(r"[0-9a-f]{40}")

PASS_DISCLAIMER = (
    "PASS significa solo que la topología observada cumplió la política declarada "
    "en observed_at. No autoriza operaciones ni garantiza el estado futuro."
)


class Mode(str, Enum):
    READ_ONLY = "READ_ONLY"
    TEST_ISOLATED = "TEST_ISOLATED"
    OPERATIONAL_REAL_DATA = "OPERATIONAL_REAL_DATA"
    DOCKER_BUILD = "DOCKER_BUILD"

    @classmethod
    def parse(cls, value: str) -> "Mode":
        return cls(value.strip().upper().replace("-", "_"))


# id -> (código, severidad por modo). Severidades: FAIL | INCOMPLETE | WARN | INFO.
R, T, O, D = (
    Mode.READ_ONLY,
    Mode.TEST_ISOLATED,
    Mode.OPERATIONAL_REAL_DATA,
    Mode.DOCKER_BUILD,
)
FINDINGS: dict[str, tuple[str, dict[Mode, str]]] = {
    "WS-001": ("WRONG_CODE_SHA", {R: "WARN", T: "FAIL", O: "FAIL", D: "FAIL"}),
    "WS-002": ("DIRTY_CODE", {R: "WARN", T: "WARN", O: "FAIL", D: "FAIL"}),
    "WS-003": ("CODE_ROOT_REPARSE", {R: "WARN", T: "WARN", O: "FAIL", D: "FAIL"}),
    "WS-004": ("STORE_PATH_MISMATCH", {R: "WARN", T: "WARN", O: "FAIL", D: "WARN"}),
    "WS-005": ("STORE_REPARSE", {R: "WARN", T: "WARN", O: "FAIL", D: "WARN"}),
    "WS-006": ("CODE_STORE_OVERLAP", {R: "WARN", T: "FAIL", O: "FAIL", D: "FAIL"}),
    "WS-007": (
        "DOCKER_REAL_STORE_EXPOSURE",
        {R: "WARN", T: "WARN", O: "WARN", D: "FAIL"},
    ),
    "WS-008": (
        "UNKNOWN_FILESYSTEM_IDENTITY",
        {R: "INCOMPLETE", T: "INCOMPLETE", O: "FAIL", D: "FAIL"},
    ),
    "WS-009": ("STORE_MISSING", {R: "INCOMPLETE", T: "WARN", O: "FAIL", D: "INFO"}),
    "WS-010": ("STORE_ALIAS", {R: "WARN", T: "WARN", O: "FAIL", D: "WARN"}),
    "WS-011": (
        "CODE_STORE_PATH_INDIRECTION",
        {R: "WARN", T: "FAIL", O: "FAIL", D: "FAIL"},
    ),
    "WS-012": (
        "CODE_STORE_BINDING_MISMATCH",
        {R: "WARN", T: "INFO", O: "FAIL", D: "INFO"},
    ),
    "WS-013": (
        "CODE_IDENTITY_UNAVAILABLE",
        {R: "INCOMPLETE", T: "INCOMPLETE", O: "FAIL", D: "INCOMPLETE"},
    ),
    "WS-014": ("WRONG_TREE_SHA", {R: "WARN", T: "FAIL", O: "FAIL", D: "FAIL"}),
    "WS-015": ("EXPECTED_SHA_REQUIRED", {R: "INFO", T: "INFO", O: "FAIL", D: "WARN"}),
    "WS-016": ("STORE_ENV_OVERRIDE", {R: "WARN", T: "WARN", O: "FAIL", D: "WARN"}),
    "WS-017": ("CODE_ROOT_NOT_TOPLEVEL", {R: "WARN", T: "WARN", O: "FAIL", D: "FAIL"}),
    "WS-018": ("STORES_NOT_DECLARED", {R: "INFO", T: "INFO", O: "FAIL", D: "INFO"}),
}
del R, T, O, D


@dataclass(frozen=True)
class GuardRequest:
    """Entrada del guard. `stores`: nombre lógico -> ruta declarada del store
    real. `expected_stores`: nombre lógico -> ubicación física esperada (si se
    omite, la ruta declarada debe resolverse a sí misma, sin indirección)."""

    mode: Mode
    code_root: Path
    expected_code_sha: Optional[str] = None
    expected_tree_sha: Optional[str] = None
    stores: Mapping[str, Path] = field(default_factory=dict)
    expected_stores: Mapping[str, Path] = field(default_factory=dict)
    require_clean: Optional[bool] = None  # None -> política del modo
    environ: Optional[Mapping[str, str]] = None

    @classmethod
    def from_dict(cls, data: Mapping) -> "GuardRequest":
        return cls(
            mode=Mode.parse(data["mode"]),
            code_root=Path(data["code_root"]),
            expected_code_sha=data.get("expected_code_sha"),
            expected_tree_sha=data.get("expected_tree_sha"),
            stores={k: Path(v) for k, v in (data.get("stores") or {}).items()},
            expected_stores={
                k: Path(v) for k, v in (data.get("expected_stores") or {}).items()
            },
            require_clean=data.get("require_clean"),
        )


# --- Filesystem (solo lectura) -------------------------------------------------


def _norm(path) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))


def _display(path) -> str:
    text = str(path)
    for prefix in ("\\\\?\\UNC\\", "\\\\?\\"):
        if text.startswith(prefix):
            return ("\\\\" if "UNC" in prefix else "") + text[len(prefix) :]
    return text


def _is_within(child: str, parent: str) -> bool:
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:  # distintas unidades
        return False


def _lstat(path: str):
    return os.lstat(path)


def classify_entry(path) -> dict:
    """Tipo de entrada sin seguir enlaces: missing | file | directory |
    symlink | junction | reparse_other | unknown."""
    p = str(path)
    try:
        st = _lstat(p)
    except FileNotFoundError:
        return {
            "kind": "missing",
            "is_symlink": False,
            "is_junction": False,
            "is_reparse_point": False,
        }
    except OSError as exc:
        return {
            "kind": "unknown",
            "error": type(exc).__name__,
            "is_symlink": None,
            "is_junction": None,
            "is_reparse_point": None,
        }
    attrs = getattr(st, "st_file_attributes", None)
    tag = getattr(st, "st_reparse_tag", 0) or 0
    is_symlink = stat.S_ISLNK(st.st_mode) or tag == _IO_REPARSE_TAG_SYMLINK
    is_junction = tag == _IO_REPARSE_TAG_MOUNT_POINT
    is_reparse = (
        bool(attrs & _FILE_ATTRIBUTE_REPARSE_POINT) if attrs is not None else is_symlink
    )
    if is_junction:
        kind = "junction"
    elif is_symlink:
        kind = "symlink"
    elif is_reparse:
        kind = "reparse_other"
    elif stat.S_ISDIR(st.st_mode):
        kind = "directory"
    else:
        kind = "file"
    out = {
        "kind": kind,
        "is_symlink": is_symlink,
        "is_junction": is_junction,
        "is_reparse_point": is_reparse,
    }
    if is_symlink or is_junction:
        try:
            out["target"] = _display(os.readlink(p))
        except OSError:
            out["target"] = None
    if is_reparse and not (is_symlink or is_junction):
        out["reparse_tag"] = hex(tag)
    return out


def reparse_chain(path) -> tuple[list[dict], bool]:
    """Enlaces y reparse points en cada componente de `path` (desde la raíz).
    Devuelve (lista, algún_componente_desconocido)."""
    absolute = Path(os.path.abspath(str(path)))
    found, unknown = [], False
    parts = absolute.parts
    for i in range(1, len(parts)):
        prefix = Path(*parts[: i + 1])
        info = classify_entry(prefix)
        if info["kind"] == "missing":
            break
        if info["kind"] == "unknown":
            unknown = True
            found.append({"path": str(prefix), **info})
        elif info["is_reparse_point"] or info["is_symlink"]:
            found.append({"path": str(prefix), **info})
    return found, unknown


def _identity(path: str) -> Optional[dict]:
    try:
        st = os.stat(path)
    except OSError:
        return None
    if not st.st_ino:
        return None
    return {"dev": st.st_dev, "ino": st.st_ino}


def _git_toplevel_of(path: str) -> Optional[str]:
    """Checkout Git que contiene `path` físicamente (busca `.git`, sin Git)."""
    current = Path(path)
    for candidate in (current, *current.parents):
        if os.path.lexists(candidate / ".git"):
            return _norm(candidate)
    return None


def describe_path(logical_name: str, requested, expected=None) -> dict:
    requested_abs = os.path.abspath(str(requested))
    info = classify_entry(requested_abs)
    chain, unknown = reparse_chain(requested_abs)
    resolved = os.path.realpath(requested_abs)
    exists = info["kind"] not in ("missing", "unknown") and os.path.exists(
        requested_abs
    )
    identity = _identity(resolved) if exists else None
    expected_norm = _norm(expected) if expected is not None else _norm(requested_abs)
    return {
        "logical_name": logical_name,
        "requested_path": requested_abs,
        "resolved_path": _display(resolved),
        "exists": exists,
        "kind": info["kind"],
        "is_symlink": info["is_symlink"],
        "is_junction": info["is_junction"],
        "is_reparse_point": info["is_reparse_point"],
        "reparse_points": chain,
        "filesystem_identity": identity,
        "identity_known": identity is not None and not unknown,
        "writable": os.access(resolved, os.W_OK) if exists else None,
        "expected_path": _display(expected) if expected is not None else None,
        "expected_path_match": _norm(resolved) == expected_norm,
        "git_checkout": _git_toplevel_of(resolved),
        "_resolved_norm": _norm(resolved),
    }


# --- Git (solo lectura) --------------------------------------------------------


def _git(code_root: str, *args: str) -> Optional[str]:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
    try:
        done = subprocess.run(
            ["git", "--no-optional-locks", "-C", code_root, *args],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def describe_code(code_root: str) -> dict:
    head = _git(code_root, "rev-parse", "HEAD")
    if head is None:
        return {
            "is_git": False,
            "head_sha": None,
            "tree_sha": None,
            "branch": None,
            "toplevel": None,
            "dirty": None,
            "dirty_count": None,
            "dirty_sample": [],
            "is_linked_worktree": None,
        }
    status = _git(code_root, "status", "--porcelain=v1", "--untracked-files=normal")
    dirty_lines = [line for line in (status or "").splitlines() if line.strip()]
    git_dir = _git(code_root, "rev-parse", "--absolute-git-dir")
    common = _git(code_root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    toplevel = _git(code_root, "rev-parse", "--show-toplevel")
    return {
        "is_git": True,
        "head_sha": head,
        "tree_sha": _git(code_root, "rev-parse", "HEAD^{tree}"),
        "branch": _git(code_root, "symbolic-ref", "-q", "--short", "HEAD")
        or "DETACHED",
        "toplevel": _norm(toplevel) if toplevel else None,
        "dirty": None if status is None else bool(dirty_lines),
        "dirty_count": None if status is None else len(dirty_lines),
        "dirty_sample": dirty_lines[:20],
        "is_linked_worktree": (
            None if not (git_dir and common) else _norm(git_dir) != _norm(common)
        ),
    }


def _docker_ignored_or_untracked(
    code_root: str, subpaths: list[str]
) -> Optional[list[str]]:
    out = _git(
        code_root,
        "status",
        "--porcelain=v1",
        "--ignored=matching",
        "--untracked-files=normal",
        "--",
        *subpaths,
    )
    if out is None:
        return None
    return [line[3:] for line in out.splitlines() if line[:2] in ("!!", "??")]


def _scan_context_reparse(root: str, skip: set[str]) -> tuple[list[dict], bool]:
    """Reparse points dentro del build context, sin seguirlos. (lista, límite_alcanzado)."""
    found, seen, stack = [], 0, [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            found.append({"path": current, "kind": "unknown"})
            continue
        for entry in entries:
            seen += 1
            if seen > DOCKER_SCAN_LIMIT:
                return found, True
            if entry.name == ".git" or _norm(entry.path) in skip:
                continue
            info = classify_entry(entry.path)
            if info["kind"] in ("symlink", "junction", "reparse_other", "unknown"):
                found.append({"path": entry.path, **info})
            elif info["kind"] == "directory":
                stack.append(entry.path)
    return found, False


# --- Evaluación ------------------------------------------------------------------


class _Collector:
    def __init__(self, mode: Mode):
        self.mode, self.findings = mode, []

    def add(
        self,
        finding_id: str,
        message: str,
        subject: Optional[str] = None,
        severity: Optional[str] = None,
    ):
        code, severities = FINDINGS[finding_id]
        self.findings.append(
            {
                "id": finding_id,
                "code": code,
                "severity": severity or severities[self.mode],
                "message": message,
                "subject": subject,
            }
        )


def check_workspace(request: GuardRequest) -> dict:
    """Evalúa la topología para `request.mode`. Solo observa; devuelve un
    dict serializable a JSON (ver docs/ops/WORKSPACE-SAFETY-GUARD.md)."""
    mode = request.mode
    environ = os.environ if request.environ is None else request.environ
    require_clean = (
        request.require_clean
        if request.require_clean is not None
        else mode in (Mode.OPERATIONAL_REAL_DATA, Mode.DOCKER_BUILD)
    )
    col = _Collector(mode)
    code_root = os.path.abspath(str(request.code_root))

    # 1-3. Identidad e indirección del código.
    code_fs = describe_path("code_root", code_root)
    code = {
        **{
            k: v
            for k, v in code_fs.items()
            if not k.startswith("_") and k != "logical_name"
        },
        **describe_code(code_root),
    }
    if not code_fs["exists"]:
        col.add(
            "WS-013",
            "code_root no existe o no es accesible",
            code_root,
            "FAIL" if mode is not Mode.READ_ONLY else "INCOMPLETE",
        )
    elif not code["is_git"]:
        col.add(
            "WS-013",
            "code_root no es un checkout Git legible: identidad del código desconocida",
            code_root,
        )
    if code_fs["reparse_points"]:
        col.add(
            "WS-003",
            "La ruta del código atraviesa enlaces o reparse points: "
            + ", ".join(
                f"{r['path']} ({r['kind']})" for r in code_fs["reparse_points"]
            ),
            code_root,
        )
    if code_fs["exists"] and not code_fs["identity_known"]:
        col.add(
            "WS-008",
            "No se pudo establecer la identidad de filesystem del código",
            code_root,
        )
    if code.get("toplevel") and code["toplevel"] != _norm(os.path.realpath(code_root)):
        col.add("WS-017", "code_root no es la raíz del checkout Git", code_root)

    expected_sha = (request.expected_code_sha or "").strip().lower() or None
    if expected_sha is None or not _FULL_SHA.fullmatch(expected_sha):
        if mode in (Mode.OPERATIONAL_REAL_DATA, Mode.DOCKER_BUILD):
            col.add(
                "WS-015",
                "Se requiere expected_code_sha completo (40 hex); "
                "no se aceptan prefijos ni SHA ausente",
                code_root,
            )
        expected_sha = (
            expected_sha if expected_sha and _FULL_SHA.fullmatch(expected_sha) else None
        )
    code["expected_code_sha"] = expected_sha
    code["sha_match"] = (
        None
        if expected_sha is None or not code["head_sha"]
        else code["head_sha"] == expected_sha
    )
    if code["sha_match"] is False:
        col.add(
            "WS-001", f"HEAD {code['head_sha']} != esperado {expected_sha}", code_root
        )
    expected_tree = (request.expected_tree_sha or "").strip().lower() or None
    code["expected_tree_sha"] = expected_tree
    code["tree_match"] = (
        None
        if expected_tree is None or not code["tree_sha"]
        else code["tree_sha"] == expected_tree
    )
    if code["tree_match"] is False:
        col.add(
            "WS-014", f"tree {code['tree_sha']} != esperado {expected_tree}", code_root
        )
    if code["dirty"]:
        col.add(
            "WS-002",
            f"{code['dirty_count']} cambios sin commit en el checkout",
            code_root,
            None if require_clean else "WARN",
        )
    elif code["is_git"] and code["dirty"] is None:
        col.add(
            "WS-013", "No se pudo leer el estado de cambios del checkout", code_root
        )

    # 4. Stores declarados.
    stores = [
        describe_path(name, path, request.expected_stores.get(name))
        for name, path in sorted(request.stores.items())
    ]
    if not stores:
        col.add("WS-018", "No se declararon stores reales", None)
    code_norm = _norm(os.path.realpath(code_root))
    for s in stores:
        name = s["logical_name"]
        if s["kind"] == "unknown" or (s["exists"] and not s["identity_known"]):
            col.add("WS-008", "Identidad de filesystem desconocida para el store", name)
        if not s["exists"] and s["kind"] != "unknown":
            col.add("WS-009", f"El store no existe: {s['requested_path']}", name)
        if s["reparse_points"]:
            col.add(
                "WS-005",
                "La ruta del store atraviesa enlaces o reparse points: "
                + ", ".join(f"{r['path']} ({r['kind']})" for r in s["reparse_points"]),
                name,
            )
        if s["exists"] and not s["expected_path_match"]:
            col.add(
                "WS-004",
                f"El store se resuelve a {s['resolved_path']}, no a la ubicación esperada",
                name,
            )
        # 5. Solapamientos código/store.
        if _is_within(code_norm, s["_resolved_norm"]):
            col.add("WS-006", "El checkout de código está dentro de un store", name)
        elif _is_within(s["_resolved_norm"], code_norm):
            effective = CODE_STORE_SUBPATHS.get(name)
            at_binding = effective and s["_resolved_norm"] == _norm(
                os.path.join(code_norm, effective)
            )
            if mode is Mode.DOCKER_BUILD:
                col.add("WS-007", "Un store real está dentro del build context", name)
            elif not (mode is Mode.OPERATIONAL_REAL_DATA and at_binding):
                col.add(
                    "WS-006",
                    "Un store real está dentro del checkout de código"
                    + ("" if at_binding else " fuera de su ruta de binding"),
                    name,
                )
        elif (
            s["git_checkout"]
            and code.get("toplevel")
            and s["git_checkout"] != code["toplevel"]
        ):
            col.add(
                "WS-006",
                f"El store vive dentro de otro checkout Git ({s['git_checkout']})",
                name,
                None if mode is Mode.OPERATIONAL_REAL_DATA else "WARN",
            )
    # Alias: dos nombres lógicos -> mismo lugar físico (o anidados).
    for i, a in enumerate(stores):
        for b in stores[i + 1 :]:
            same_id = (
                a["filesystem_identity"]
                and a["filesystem_identity"] == b["filesystem_identity"]
            )
            nested = _is_within(a["_resolved_norm"], b["_resolved_norm"]) or _is_within(
                b["_resolved_norm"], a["_resolved_norm"]
            )
            if same_id or nested:
                col.add(
                    "WS-010",
                    f"'{a['logical_name']}' y '{b['logical_name']}' apuntan al mismo "
                    "lugar físico o están anidados",
                    f"{a['logical_name']},{b['logical_name']}",
                )

    # Binding: dónde leerá/escribirá realmente el código.
    declared = {s["logical_name"]: s for s in stores}
    effective_paths = []
    for name, sub in CODE_STORE_SUBPATHS.items():
        e = describe_path(name, os.path.join(code_root, sub))
        del e["expected_path"], e["expected_path_match"]
        own_chain = [
            r
            for r in e["reparse_points"]
            if _is_within(_norm(r["path"]), _norm(code_root))
            and _norm(r["path"]) != _norm(code_root)
        ]
        e["reparse_inside_code_root"] = own_chain
        target = declared.get(name)
        e["declared_store"] = target["requested_path"] if target else None
        e["binds_to_declared_store"] = (
            None if target is None else e["_resolved_norm"] == target["_resolved_norm"]
        )
        effective_paths.append(e)
        if own_chain:
            reaches_store = any(
                _is_within(e["_resolved_norm"], s["_resolved_norm"]) for s in stores
            )
            other = (
                e["git_checkout"]
                and code.get("toplevel")
                and e["git_checkout"] != code["toplevel"]
            )
            detail = (" hacia un store real declarado" if reaches_store else "") + (
                " en otro checkout Git" if other else ""
            )
            finding = "WS-007" if mode is Mode.DOCKER_BUILD else "WS-011"
            col.add(
                finding,
                f"{sub} dentro del checkout es un enlace/reparse point{detail}",
                name,
            )
        if (
            mode is Mode.OPERATIONAL_REAL_DATA
            and target is not None
            and not e["binds_to_declared_store"]
        ):
            col.add(
                "WS-012",
                f"El código leerá/escribirá en {e['resolved_path']}, "
                f"no en el store declarado {target['resolved_path']}",
                name,
            )
        if (
            mode is Mode.TEST_ISOLATED
            and not own_chain
            and any(
                _is_within(e["_resolved_norm"], s["_resolved_norm"])
                or _is_within(s["_resolved_norm"], e["_resolved_norm"])
                for s in stores
                if e["exists"]
            )
        ):
            col.add(
                "WS-006",
                f"{sub} del checkout de tests es un store real declarado",
                name,
            )

    overrides = sorted(k for k in STORE_ENV_OVERRIDES if environ.get(k))
    if overrides:
        col.add(
            "WS-016",
            "Overrides de rutas activos (solo parte del código los respeta): "
            + ", ".join(overrides),
            None,
        )

    # 7. Build context de Docker.
    docker: Optional[dict] = None
    if mode is Mode.DOCKER_BUILD:
        docker = {
            "context": code_root,
            "recommendation": "Construir desde un directorio aislado creado con "
            "`git archive <sha>`; este guard no copia ni borra nada.",
        }
        subs = list(dict.fromkeys(CODE_STORE_SUBPATHS.values()))
        exposed = (
            _docker_ignored_or_untracked(code_root, subs) if code["is_git"] else None
        )
        if exposed is None and code["is_git"]:
            col.add(
                "WS-008",
                "No se pudo listar contenido no versionado del build context",
                code_root,
            )
        elif exposed:
            col.add(
                "WS-007",
                f"{len(exposed)} rutas no versionadas (datos locales) dentro del "
                f"build context, p. ej. {exposed[:3]}",
                code_root,
            )
        elif not code["is_git"]:
            for sub in ("data/raw", "data/processed", "data/predictions"):
                p = os.path.join(code_root, sub)
                if os.path.isdir(p) and any(n != ".gitkeep" for n in os.listdir(p)):
                    col.add(
                        "WS-007",
                        f"{sub} contiene archivos en un build context sin Git",
                        sub,
                    )
        docker["untracked_or_ignored_in_store_paths"] = exposed
        reparse, limited = _scan_context_reparse(code_root, skip=set())
        docker["reparse_points_in_context"] = reparse
        for r in reparse:
            if r["kind"] == "unknown":
                col.add(
                    "WS-008", "Entrada ilegible dentro del build context", r["path"]
                )
            else:
                col.add(
                    "WS-007",
                    f"Enlace/reparse point dentro del build context ({r['kind']})",
                    r["path"],
                )
        if limited:
            col.add(
                "WS-008",
                f"Escaneo del build context truncado en {DOCKER_SCAN_LIMIT} entradas",
                code_root,
            )

    failures = [f for f in col.findings if f["severity"] == "FAIL"]
    incomplete = [f for f in col.findings if f["severity"] == "INCOMPLETE"]
    warnings = [f for f in col.findings if f["severity"] == "WARN"]
    overall = "FAIL" if failures else "INCOMPLETE" if incomplete else "PASS"

    def strip(d: dict) -> dict:
        return {k: v for k, v in d.items() if not k.startswith("_")}

    return {
        "schema_version": SCHEMA_VERSION,
        "guard": GUARD_NAME,
        "mode": mode.value,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "require_clean": require_clean,
            "code_store_subpaths": CODE_STORE_SUBPATHS,
        },
        "code": code,
        "stores": [strip(s) for s in stores],
        "topology": {
            "code_effective_store_paths": [strip(e) for e in effective_paths],
            "store_env_overrides": overrides,
            "docker_context": docker,
        },
        "findings": col.findings,
        "warnings": warnings,
        "failures": failures,
        "incomplete": incomplete,
        "overall_status": overall,
        "exit_code": {
            "PASS": EXIT_PASS,
            "FAIL": EXIT_FAIL,
            "INCOMPLETE": EXIT_INCOMPLETE,
        }[overall],
        "disclaimer": PASS_DISCLAIMER,
    }


def run(request: Mapping) -> dict:
    """Entrada JSON-compatible para integraciones (p. ej. el operador del Attempt 2)."""
    return check_workspace(GuardRequest.from_dict(request))


# --- CLI ---------------------------------------------------------------------------


def _pairs(values: list[str], flag: str) -> dict[str, Path]:
    out = {}
    for value in values or []:
        name, sep, path = value.partition("=")
        if not sep or not name or not path:
            raise SystemExit(f"{flag} espera nombre=RUTA, recibido {value!r}")
        out[name.strip()] = Path(path)
    return out


def _summary(result: dict) -> str:
    code = result["code"]
    lines = [
        f"[{result['overall_status']}] modo {result['mode']} — observado {result['observed_at']}",
        f"código: {code['requested_path']} -> {code['resolved_path']}",
        f"  HEAD {code['head_sha']} ({code['branch']}), tree {code['tree_sha']}, "
        f"dirty={code['dirty']}, sha_match={code['sha_match']}",
    ]
    for s in result["stores"]:
        lines.append(
            f"store {s['logical_name']}: {s['requested_path']} -> {s['resolved_path']} "
            f"[{s['kind']}, existe={s['exists']}, reparse={len(s['reparse_points'])}, "
            f"esperado={s['expected_path_match']}]"
        )
    for f in result["findings"]:
        lines.append(
            f"  {f['severity']:<10} {f['id']} {f['code']}: {f['message']}"
            + (f" [{f['subject']}]" if f["subject"] else "")
        )
    lines.append(result["disclaimer"])
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.ops.workspace_safety",
        description=(__doc__ or "").split("\n\n")[0],
    )
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser(
        "check", help="Observar la topología y evaluar la política del modo"
    )
    check.add_argument(
        "--mode",
        required=True,
        choices=[m.value.lower().replace("_", "-") for m in Mode],
    )
    check.add_argument("--code-root", required=True)
    check.add_argument("--expected-code-sha")
    check.add_argument("--expected-tree-sha")
    check.add_argument("--store", action="append", default=[], metavar="NOMBRE=RUTA")
    check.add_argument(
        "--expected-store", action="append", default=[], metavar="NOMBRE=RUTA"
    )
    clean = check.add_mutually_exclusive_group()
    clean.add_argument(
        "--require-clean", dest="require_clean", action="store_true", default=None
    )
    clean.add_argument("--allow-dirty", dest="require_clean", action="store_false")
    check.add_argument(
        "--json", action="store_true", help="Imprimir el resultado JSON en stdout"
    )
    check.add_argument(
        "--json-out",
        help="Escribir el resultado JSON en este archivo (nunca dentro de un store)",
    )
    args = parser.parse_args(argv)

    request = GuardRequest(
        mode=Mode.parse(args.mode),
        code_root=Path(args.code_root),
        expected_code_sha=args.expected_code_sha,
        expected_tree_sha=args.expected_tree_sha,
        stores=_pairs(args.store, "--store"),
        expected_stores=_pairs(args.expected_store, "--expected-store"),
        require_clean=args.require_clean,
    )
    if args.json_out:
        out = _norm(os.path.realpath(args.json_out))
        if any(
            _is_within(out, _norm(os.path.realpath(p))) for p in request.stores.values()
        ):
            print(
                "--json-out no puede apuntar dentro de un store declarado",
                file=sys.stderr,
            )
            return EXIT_USAGE
    result = check_workspace(request)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(payload + "\n", encoding="utf-8")
    print(payload if args.json else _summary(result))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
