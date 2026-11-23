"""Escaneo de secretos de S.A.P.I. (SAPI-89, artefacto A6).

Compara los archivos versionados contra `.secrets.baseline`, la línea base
auditada el 22-11-2026. Cualquier secreto que no esté en la línea base hace
fallar el escaneo (código de salida distinto de 0), y el PR queda bloqueado
cuando el job es obligatorio en la protección de `main`.

Uso:
    python scripts/secret_scan.py            # escanea el repositorio
    python scripts/secret_scan.py --root DIR # escanea otro árbol git (pruebas)

La línea base solo admite falsos positivos revisados uno por uno: hashes
SHA-256 de evidencias, credenciales sintéticas de pruebas y placeholders de
documentación. Ver docs/calidad/seguridad-sprint3.md.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_NAME = ".secrets.baseline"
# Binarios y artefactos que no contienen texto escaneable.
EXCLUDED_SUFFIXES = (".png", ".jpg", ".pdf", ".pkl", ".parquet", ".docx", ".svg")


def tracked_files(root: Path) -> list[str]:
    """Archivos versionados en git, sin binarios ni la propia línea base."""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True
    ).stdout.decode("utf-8")
    files = [f for f in out.split("\0") if f]
    return [
        f
        for f in files
        if f != BASELINE_NAME and not f.lower().endswith(EXCLUDED_SUFFIXES)
    ]


def scan(root: Path) -> int:
    """Ejecuta detect-secrets-hook contra la línea base. Devuelve su código."""
    baseline = root / BASELINE_NAME
    if not baseline.exists():
        print(f"FAIL: falta {BASELINE_NAME} en {root}", file=sys.stderr)
        return 2
    files = tracked_files(root)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "detect_secrets.pre_commit_hook",
            "--baseline",
            BASELINE_NAME,
            *files,
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"PASS: 0 secretos nuevos en {len(files)} archivos versionados")
    else:
        print("FAIL: secretos nuevos fuera de la línea base", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    return scan(args.root.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
