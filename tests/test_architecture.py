"""Auditoría estática del Data Contract en la capa de presentación."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_PROHIBITED_MODULES = frozenset(
    {
        "src.ingesta",
        "src.procesamiento",
        "src.modelo",
        "src.pipeline",
    }
)


def test_frontend_data_contract_compliance() -> None:
    """Valida que app/ no importe módulos analíticos prohibidos.

    Raises:
        AssertionError: Si se detecta un acoplamiento prohibido en el frontend.
    """
    project_root = Path(__file__).parent.parent
    app_dir = project_root / "app"
    python_files = list(app_dir.glob("**/*.py"))

    assert python_files, "No se encontraron archivos Python en app/"

    for file_path in python_files:
        source = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as exc:
            pytest.fail(f"Error de sintaxis en {file_path.relative_to(project_root)}: {exc}")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for module in _PROHIBITED_MODULES:
                        if alias.name.startswith(module):
                            pytest.fail(
                                f"Ruptura de Arquitectura en {file_path.relative_to(project_root)}: "
                                f"infracción del Data Contract al importar '{alias.name}'."
                            )
            elif isinstance(node, ast.ImportFrom) and node.module:
                for module in _PROHIBITED_MODULES:
                    if node.module.startswith(module):
                        pytest.fail(
                            f"Ruptura de Arquitectura en {file_path.relative_to(project_root)}: "
                            f"infracción del Data Contract al importar desde '{node.module}'."
                        )
