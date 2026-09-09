"""Auditoría estática del Data Contract en la capa de presentación."""

from __future__ import annotations

import ast
import subprocess
import sys
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

# Auditoría de arquitectura 4+1 (09-09-2026, ver
# docs/architecture-4plus1-hito1.md): a diferencia de
# `test_no_legacy_imports_in_prototype_modules` (tests/test_prototype_service.py),
# que solo busca texto prohibido en 2 archivos puntuales, este test verifica
# el ARBOL TRANSITIVO REAL de imports (via sys.modules, en un subproceso
# limpio) de los dos puntos de entrada del pipeline temporal/inferencia.
# Nace de un hallazgo real: `regional_meteo.py` importaba constantes desde
# `features.py` (consumido principalmente por el pipeline legacy
# `src.modelo.*`, que a su vez importa `imblearn`/SMOTE) -- ningún test
# existente lo detectaba porque ninguno recorría el árbol transitivo de
# imports, solo grepeaba texto en un puñado de archivos. Corregido moviendo
# las constantes a `src/procesamiento/shared_thresholds.py` (módulo hoja,
# sin dependencias). Este test hace esa propiedad permanente y automática.
_TEMPORAL_PIPELINE_ENTRYPOINTS = (
    "src.inference.prototype_service",
    "scripts.build_temporal_dataset",
)

_FORBIDDEN_TRANSITIVE_MODULES = (
    "src.modelo",
    "src.procesamiento.features",
    "src.procesamiento.data_processor",
    "imblearn",
)


@pytest.mark.parametrize("entrypoint", _TEMPORAL_PIPELINE_ENTRYPOINTS)
def test_temporal_pipeline_has_no_transitive_legacy_dependency(entrypoint: str) -> None:
    """Verifica el árbol transitivo real de imports, no solo el directo.

    Ejecuta la importación en un subproceso limpio (no comparte
    `sys.modules` con el resto de la suite, que puede haber cacheado los
    módulos legacy por otras pruebas) y falla si aparece cualquier módulo
    de `_FORBIDDEN_TRANSITIVE_MODULES` en el árbol resultante.

    Raises:
        AssertionError: Si `entrypoint` arrastra transitivamente una
            dependencia legacy prohibida.
    """
    project_root = Path(__file__).parent.parent
    probe = (
        "import sys; before = set(sys.modules);"
        f"import {entrypoint}; "
        "after = set(sys.modules); "
        "print('\\n'.join(sorted(after - before)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"No se pudo importar '{entrypoint}' en subproceso limpio: {result.stderr}"
    )
    imported = set(result.stdout.strip().splitlines())
    violations = {
        forbidden
        for forbidden in _FORBIDDEN_TRANSITIVE_MODULES
        if any(m == forbidden or m.startswith(forbidden + ".") for m in imported)
    }
    assert not violations, (
        f"'{entrypoint}' arrastra transitivamente dependencias legacy prohibidas: "
        f"{sorted(violations)} — ver docs/architecture-4plus1-hito1.md"
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
