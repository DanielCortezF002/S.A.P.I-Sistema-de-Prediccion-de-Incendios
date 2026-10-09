"""Regresión del checker de Flyway de `scripts/w0_host_checks.ps1` (W0.4).

La primera corrida en el Omen (43c17fd) dio un HARNESS_FALSE_NEGATIVE: Flyway
guarda en `flyway_schema_history.version` la versión tal como aparece en el
nombre del archivo (`V001__` -> `001`), y el checker esperaba `1:true,2:true,
3:true`, escrito a mano. Estos tests fijan la corrección:

- los tests estáticos corren en cualquier entorno (también en el gate de la
  nube sin PowerShell): nada escrito a mano, la expectativa sale de
  `db/migration`;
- los tests de comportamiento ejecutan las funciones reales del script con
  PowerShell (`pwsh` en el PATH, como en ubuntu-latest, o `SAPI_PWSH`); sin
  PowerShell se omiten de forma explícita.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "w0_host_checks.ps1"
MIGRATIONS = ROOT / "db" / "migration"
PWSH = os.environ.get("SAPI_PWSH") or shutil.which("pwsh")
HELPERS = (
    "ConvertTo-FlywayVersionKey",
    "Get-ExpectedFlywayVersions",
    "Compare-FlywayHistory",
)

needs_pwsh = pytest.mark.skipif(
    PWSH is None, reason="PowerShell no disponible (pwsh en PATH o SAPI_PWSH)"
)


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _pwsh(body: str) -> str:
    """Carga las funciones del checker vía AST (sin correr el script) y ejecuta `body`."""
    loader = (
        "$ast = [System.Management.Automation.Language.Parser]::ParseFile("
        f"'{SCRIPT}', [ref]$null, [ref]$null)\n"
        "$names = @(" + ", ".join(f"'{name}'" for name in HELPERS) + ")\n"
        "$defs = $ast.FindAll({ param($n) "
        "$n -is [System.Management.Automation.Language.FunctionDefinitionAst] "
        "-and $names -contains $n.Name }, $true)\n"
        "foreach ($d in $defs) { Invoke-Expression $d.Extent.Text }\n"
    )
    result = subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-Command", loader + body],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _compare(expected: list[str], observed: str) -> dict:
    versions = ", ".join(f"'{v}'" for v in expected)
    out = _pwsh(
        f"Compare-FlywayHistory @({versions}) '{observed}' | ConvertTo-Json -Compress"
    )
    return json.loads(out)


# --- Estáticos: sin PowerShell ---------------------------------------------------


def test_checker_has_no_hand_written_flyway_history():
    text = _script_text()
    assert '"1:true,2:true,3:true"' not in text
    assert 'Expect $r "migrate_1_executed" 3 ' not in text


def test_checker_derives_expectation_from_migration_files():
    text = _script_text()
    for name in HELPERS:
        assert f"function {name}" in text, name
    assert "$expectedVersions = Get-ExpectedFlywayVersions $migrations" in text
    assert "Compare-FlywayHistory $expectedVersions $history" in text
    for key in (
        "flyway_history_expected_literal",
        "flyway_history_observed_raw",
        "flyway_history_expected_normalized",
        "flyway_history_observed_normalized",
    ):
        assert key in text, key


def test_checker_does_not_log_the_postgis_password():
    text = _script_text()
    assert "POSTGRES_PASSWORD=***" in text


def test_harness_never_removes_outdir_and_writes_never_throw():
    text = _script_text()
    assert "Remove-Item -Recurse" not in text
    assert "Remove-Item -Force $OutDir" not in text
    assert "function Save-Evidence" in text
    write_text = text.split("function Write-Text", 1)[1].split("}", 1)[0]
    add_log = text.split("function Add-Log", 1)[1].split("}", 1)[0]
    assert "Save-Evidence" in write_text and "Save-Evidence" in add_log
    assert "exit 3" in text


# --- Comportamiento: funciones reales con PowerShell -----------------------------


@needs_pwsh
def test_expected_versions_come_from_db_migration_with_padding():
    out = _pwsh(f"Get-ExpectedFlywayVersions '{MIGRATIONS}' | ConvertTo-Json -Compress")
    expected = sorted(p.name[1:].split("__")[0] for p in MIGRATIONS.glob("V*__*.sql"))
    assert json.loads(out) == expected
    assert expected[:3] == ["001", "002", "003"]


@needs_pwsh
@pytest.mark.parametrize(
    "version,key",
    [
        ("001", "1"),
        ("1", "1"),
        ("010", "10"),
        ("0", "0"),
        ("1.0", "1.0"),
        ("1_1", "1.1"),
    ],
)
def test_version_key_normalization(version, key):
    assert _pwsh(f"ConvertTo-FlywayVersionKey '{version}'") == key


@needs_pwsh
@pytest.mark.parametrize(
    "observed",
    ["001:true,002:true,003:true", "1:true,2:true,3:true"],
    ids=["literal-padded", "semantic-001-vs-1"],
)
def test_history_matches(observed):
    result = _compare(["001", "002", "003"], observed)
    assert result["match"] is True
    assert result["expected_literal"] == "001:true,002:true,003:true"
    assert result["observed_raw"] == observed
    assert result["expected_normalized"] == "1:true,2:true,3:true"
    assert result["observed_normalized"] == "1:true,2:true,3:true"


@needs_pwsh
@pytest.mark.parametrize(
    "observed",
    [
        "001:true,002:false,003:true",
        "001:true,002:true",
        "001:true,002:true,003:true,004:true",
        "001:true,003:true,002:true",
        "001:true,002:true,004:true",
        "",
    ],
    ids=["success-false", "missing", "extra", "wrong-order", "wrong-version", "empty"],
)
def test_history_mismatches_fail(observed):
    assert _compare(["001", "002", "003"], observed)["match"] is False


@needs_pwsh
def test_first_omen_run_would_now_pass():
    """La evidencia histórica de 43c17fd, reevaluada con el checker corregido."""
    evidence = (
        ROOT / "artifacts/hito2/w0/host/43c17fd/extracted/flyway-integration.json"
    )
    observed = json.loads(evidence.read_text(encoding="utf-8-sig"))["observed"]
    assert observed["flyway_schema_history"] == "001:true,002:true,003:true"
    assert _compare(["001", "002", "003"], observed["flyway_schema_history"])["match"]
