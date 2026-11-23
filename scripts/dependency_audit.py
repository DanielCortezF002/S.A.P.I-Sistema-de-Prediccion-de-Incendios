"""Auditoría de dependencias Python de S.A.P.I. (SAPI-89, artefacto A6).

Ejecuta pip-audit sobre requirements.txt y requirements-dev.txt y falla si
aparece una vulnerabilidad en un paquete que no tenga una aceptación escrita
en ACCEPTED. Cada aceptación dice por qué no se corrige ahora y qué riesgo
deja; el detalle está en docs/calidad/seguridad-sprint3.md.

Uso:
    python scripts/dependency_audit.py --json-out reporte.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Paquete -> justificación. Revisar en cada actualización de dependencias.
ACCEPTED: dict[str, str] = {
    "pillow": (
        "streamlit==1.63.0 exige pillow<13 y requirements.txt está congelado; "
        "la app no abre imágenes de usuarios (sin file_uploader ni PIL propio)."
    ),
}


def evaluate(report: dict) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """Separa hallazgos aceptados de hallazgos nuevos (paquete, versión, id)."""
    accepted, new = [], []
    for dep in report.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            item = (dep["name"].lower(), dep.get("version", "?"), vuln["id"])
            (accepted if item[0] in ACCEPTED else new).append(item)
    return accepted, new


def run_pip_audit() -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip_audit",
            "-r",
            "requirements.txt",
            "-r",
            "requirements-dev.txt",
            "--format",
            "json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if not result.stdout.strip():
        raise RuntimeError(f"pip-audit no produjo reporte: {result.stderr.strip()}")
    return json.loads(result.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    report = run_pip_audit()
    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    accepted, new = evaluate(report)
    print(f"Paquetes auditados: {len(report.get('dependencies', []))}")
    print(f"Vulnerabilidades aceptadas con justificación: {len(accepted)}")
    for name in sorted({a[0] for a in accepted}):
        print(f"  - {name}: {ACCEPTED[name]}")
    if new:
        print(f"FAIL: {len(new)} vulnerabilidades sin aceptación escrita:", file=sys.stderr)
        for name, version, vid in new:
            print(f"  - {name} {version}: {vid}", file=sys.stderr)
        return 1
    print("PASS: ninguna vulnerabilidad sin aceptación escrita")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
