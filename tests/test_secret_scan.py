"""Pruebas del escaneo de secretos (SAPI-89).

Incluye el caso negativo exigido por la HU: un secreto nuevo agregado a un
árbol git hace fallar el escaneo.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


from scripts import secret_scan


REPO_ROOT = Path(__file__).resolve().parents[1]
# Clave con formato AWS, construida por partes para que este archivo no la contenga.
_FAKE_AWS_KEY = "AKIA" + "Z7Q2" + "M4XK" + "P9RT" + "W3LB"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _repo_with_baseline(tmp_path: Path, content: str) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "app.py").write_text(content, encoding="utf-8")
    shutil.copy(REPO_ROOT / secret_scan.BASELINE_NAME, root / secret_scan.BASELINE_NAME)
    baseline = json.loads((root / secret_scan.BASELINE_NAME).read_text(encoding="utf-8"))
    baseline["results"] = {}
    (root / secret_scan.BASELINE_NAME).write_text(json.dumps(baseline), encoding="utf-8")
    _git(root, "add", "-A")
    return root


def test_arbol_limpio_pasa(tmp_path: Path) -> None:
    root = _repo_with_baseline(tmp_path, "VALOR = 42\n")
    assert secret_scan.scan(root) == 0


def test_caso_negativo_secreto_nuevo_hace_fallar(tmp_path: Path) -> None:
    root = _repo_with_baseline(tmp_path, f'AWS_ACCESS_KEY_ID = "{_FAKE_AWS_KEY}"\n')
    assert secret_scan.scan(root) != 0


def test_sin_linea_base_falla(tmp_path: Path) -> None:
    root = _repo_with_baseline(tmp_path, "VALOR = 42\n")
    (root / secret_scan.BASELINE_NAME).unlink()
    assert secret_scan.scan(root) == 2


def test_repositorio_actual_sin_secretos_nuevos() -> None:
    assert secret_scan.scan(REPO_ROOT) == 0


def test_linea_base_excluye_binarios() -> None:
    files = secret_scan.tracked_files(REPO_ROOT)
    assert secret_scan.BASELINE_NAME not in files
    assert not any(f.endswith(".pkl") for f in files)


# --- Auditoría de dependencias (misma HU) -----------------------------------
from scripts import dependency_audit  # noqa: E402


def _report(*deps: tuple[str, str, list[str]]) -> dict:
    return {
        "dependencies": [
            {"name": n, "version": v, "vulns": [{"id": i} for i in ids]} for n, v, ids in deps
        ]
    }


def test_auditoria_acepta_solo_paquetes_justificados() -> None:
    accepted, new = dependency_audit.evaluate(_report(("Pillow", "12.3.0", ["CVE-X"])))
    assert accepted == [("pillow", "12.3.0", "CVE-X")] and new == []


def test_caso_negativo_vulnerabilidad_sin_aceptacion_falla() -> None:
    _, new = dependency_audit.evaluate(_report(("requests", "1.0", ["CVE-Y"])))
    assert new == [("requests", "1.0", "CVE-Y")]


def test_cada_aceptacion_tiene_justificacion() -> None:
    assert all(len(text) > 30 for text in dependency_audit.ACCEPTED.values())
