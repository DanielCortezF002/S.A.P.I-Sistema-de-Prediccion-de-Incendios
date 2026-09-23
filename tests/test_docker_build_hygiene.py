"""Higiene del build Docker (SAPI-70): secretos y artefactos locales fuera.

Dos niveles:

- Estático (siempre): `.dockerignore` excluye `.env`, `.env.*`, `.mcp.json`,
  `.venv*` y caches de Python, con esas reglas DESPUÉS de cualquier excepción
  `!` (en .dockerignore gana la última regla que coincide). Y
  `web-presentation` no recibe `env_file` en docker-compose.yml.
- Dentro de la imagen (solo si corre en Docker con el repo en /app, sin
  volúmenes): esos archivos no existen y ningún `.pyc` viene del host.

La verificación empírica del contexto real (qué copia `COPY . .`) se hace
fuera de pytest, construyendo la imagen -- ver
docs/architecture-stack-freeze-sprint2.md §9.
"""

from __future__ import annotations

import marshal
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERIGNORE = REPO_ROOT / ".dockerignore"
COMPOSE = REPO_ROOT / "docker-compose.yml"

REQUIRED_EXCLUSIONS = (
    ".env",
    ".env.*",
    ".mcp.json",
    ".venv*",
    "**/__pycache__/",
    "**/*.py[cod]",
    "**/.pytest_cache/",
    ".coverage*",
)


def _dockerignore_rules() -> list[str]:
    lines = DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def test_dockerignore_excludes_secrets_venvs_and_caches() -> None:
    rules = _dockerignore_rules()
    missing = [pattern for pattern in REQUIRED_EXCLUSIONS if pattern not in rules]
    assert missing == []


def test_no_exception_rule_can_reinclude_secrets_or_caches() -> None:
    rules = _dockerignore_rules()
    last_exception = max(
        (i for i, rule in enumerate(rules) if rule.startswith("!")), default=-1
    )
    first_required = min(rules.index(pattern) for pattern in REQUIRED_EXCLUSIONS)
    assert (
        first_required > last_exception
    ), "Las exclusiones de secretos/caches deben ir despues de la ultima regla '!'"
    reincluded = [
        rule
        for rule in rules
        if rule.startswith("!") and (".env" in rule or ".venv" in rule)
    ]
    assert reincluded == []


def _service_block(compose_text: str, service: str) -> list[str]:
    lines = compose_text.splitlines()
    start = lines.index(f"  {service}:")
    block = []
    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("    ") and line.strip():
            break
        if line and not line.startswith(" "):
            break
        block.append(line)
    return block


def test_web_presentation_does_not_receive_env_file() -> None:
    block = _service_block(COMPOSE.read_text(encoding="utf-8"), "web-presentation")
    assert block, "servicio web-presentation no encontrado en docker-compose.yml"
    assert not any(line.strip().startswith("env_file:") for line in block)


_IN_IMAGE = Path("/.dockerenv").exists() and REPO_ROOT == Path("/app")
_in_image_only = pytest.mark.skipif(
    not _IN_IMAGE, reason="Solo aplica dentro de la imagen Docker (repo en /app)."
)


@_in_image_only
def test_image_has_no_env_mcp_or_venv() -> None:
    present = sorted(
        p.name
        for p in REPO_ROOT.iterdir()
        if p.name == ".env"
        or p.name.startswith(".env.")
        or p.name == ".mcp.json"
        or p.name.startswith(".venv")
    )
    assert present == []


def _pyc_source(path: Path) -> str | None:
    try:
        return marshal.loads(path.read_bytes()[16:]).co_filename
    except (EOFError, ValueError, TypeError):
        return None


@_in_image_only
def test_image_has_no_bytecode_compiled_on_the_host() -> None:
    """pytest y el import generan .pyc propios al correr (con este
    intérprete, bajo /app); cualquier otro .pyc vino copiado del host."""
    tag = sys.implementation.cache_tag
    foreign = []
    for pyc in REPO_ROOT.rglob("*.pyc"):
        source = _pyc_source(pyc) if f".{tag}" in pyc.name else None
        if source is None or not source.startswith(str(REPO_ROOT)):
            foreign.append(str(pyc.relative_to(REPO_ROOT)))
    assert foreign == []
