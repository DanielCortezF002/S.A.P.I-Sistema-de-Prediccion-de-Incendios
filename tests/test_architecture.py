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
        # SAPI-61.CA1: la UI no ejecuta inferencia; el ranking llega por REST.
        "src.inference",
    }
)

# Única excepción a `src.inference` en app/: la vista Hito 1 congelada por
# freeze_check (F4), conservada detrás de SAPI_UI_LEGACY_MODES=1 (H7). No se
# modifica ni se importa desde el flujo por defecto (app.py la carga de forma
# perezosa solo en el modo legacy).
_LEGACY_LOCAL_SCORING_VIEW = Path("app/components/prototype_view.py")
_LOCAL_SCORING_SYMBOL = "score_current_grid"

# Flujo SAPI-61 activo: estos módulos no pueden cargar `src.inference` ni
# siquiera transitivamente (ver `test_sapi61_flow_has_no_transitive_local_scoring`).
_SAPI61_FLOW_ENTRYPOINTS = (
    "app.app",
    "app.components.ranking_backend_view",
    "app.utils.backend_client",
)
_FORBIDDEN_IN_SAPI61_FLOW = (
    "src.inference",
    "src.procesamiento",
    "src.modelo",
    "sklearn",
    "joblib",
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
        rel = file_path.relative_to(project_root)
        prohibited = set(_PROHIBITED_MODULES)
        if rel == _LEGACY_LOCAL_SCORING_VIEW:
            prohibited.discard("src.inference")
        source = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as exc:
            pytest.fail(f"Error de sintaxis en {rel}: {exc}")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for module in prohibited:
                        if alias.name.startswith(module):
                            pytest.fail(
                                f"Ruptura de Arquitectura en {rel}: "
                                f"infracción del Data Contract al importar '{alias.name}'."
                            )
            elif isinstance(node, ast.ImportFrom) and node.module:
                for module in prohibited:
                    if node.module.startswith(module):
                        pytest.fail(
                            f"Ruptura de Arquitectura en {rel}: "
                            f"infracción del Data Contract al importar desde '{node.module}'."
                        )


def _names_in(tree: ast.AST) -> set[str]:
    """Identificadores usados como nombre, atributo o alias importado."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.name.split(".")[-1])
                if alias.asname:
                    names.add(alias.asname)
    return names


def test_sapi61_app_never_references_score_current_grid() -> None:
    """SAPI-61.CA1: ningún módulo de app/ importa, nombra ni llama a
    `score_current_grid`, salvo la vista legacy congelada (H7).

    Es una regla por identificador (no solo por módulo importado): también
    atrapa un `getattr(importlib.import_module(...), "score_current_grid")`
    o un alias local del símbolo.

    Raises:
        AssertionError: Si el símbolo reaparece fuera de la excepción explícita.
    """
    project_root = Path(__file__).parent.parent
    offenders = []
    for file_path in sorted((project_root / "app").glob("**/*.py")):
        rel = file_path.relative_to(project_root)
        if rel == _LEGACY_LOCAL_SCORING_VIEW:
            continue
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        if _LOCAL_SCORING_SYMBOL in _names_in(tree):
            offenders.append(str(rel))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == _LOCAL_SCORING_SYMBOL:
                offenders.append(f"{rel} (string literal)")
    assert not offenders, (
        f"SAPI-61.CA1 roto: `{_LOCAL_SCORING_SYMBOL}` aparece en {offenders}; "
        "el flujo principal de Streamlit debe consumir GET /api/v1/ranking."
    )


def test_sapi61_default_flow_does_not_import_the_legacy_view_eagerly() -> None:
    """`app/app.py` solo puede cargar `prototype_view` de forma perezosa (dentro
    de una función), para que el flujo por defecto nunca arrastre `src.inference`."""
    project_root = Path(__file__).parent.parent
    tree = ast.parse((project_root / "app" / "app.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "prototype_view" not in node.module, (
                "app/app.py importa prototype_view a nivel de módulo: el flujo por "
                "defecto cargaría src.inference (SAPI-61.CA1)"
            )
        if isinstance(node, ast.Import):
            assert all("prototype_view" not in a.name for a in node.names)


@pytest.mark.parametrize("entrypoint", _SAPI61_FLOW_ENTRYPOINTS)
def test_sapi61_flow_has_no_transitive_local_scoring(entrypoint: str) -> None:
    """SAPI-61.CA1 (árbol transitivo real): importar el flujo activo de la UI
    en un subproceso limpio no carga `src.inference` ni el stack del Modelo D.

    Raises:
        AssertionError: Si aparece algún módulo de `_FORBIDDEN_IN_SAPI61_FLOW`.
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
        timeout=120,
    )
    assert result.returncode == 0, f"No se pudo importar '{entrypoint}': {result.stderr[-2000:]}"
    imported = set(result.stdout.strip().splitlines())
    violations = {
        forbidden
        for forbidden in _FORBIDDEN_IN_SAPI61_FLOW
        if any(m == forbidden or m.startswith(forbidden + ".") for m in imported)
    }
    assert (
        not violations
    ), f"'{entrypoint}' arrastra scoring local al flujo SAPI-61: {sorted(violations)}"
