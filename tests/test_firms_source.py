"""Resolución centralizada de la fuente FIRMS (src/procesamiento/firms_source.py)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.procesamiento.firms_source import (
    FIRMS_BASELINE_COVERAGE,
    FIRMS_BASELINE_CSV,
    FIRMS_BASELINE_SHA256,
    FIRMS_REPRODUCIBILITY_CSV,
    POINTER_SCHEMA_VERSION,
    FirmsSourceError,
    resolve_firms_source,
)
from src.procesamiento.pipeline_validators import (
    FORBIDDEN_LEGACY_REFERENCES,
    validate_pipeline_isolation,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_FILENAME = "nasa_firms_2021-08-30_2026-08-30.csv"


def _write_version(
    versions_dir: Path, name: str = "v1.csv", content: str = "latitude,longitude\n1,2\n"
) -> str:
    versions_dir.mkdir(parents=True, exist_ok=True)
    path = versions_dir / name
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_pointer(pointer: Path, **overrides) -> None:
    payload = {
        "schema_version": POINTER_SCHEMA_VERSION,
        "relative_path": "v1.csv",
        "sha256": "",
        "coverage_start": "2021-08-30",
        "coverage_end": "2026-09-22",
        "created_at": "2026-09-23T00:00:00+00:00",
    }
    payload.update(overrides)
    pointer.write_text(json.dumps(payload), encoding="utf-8")


def _resolve(tmp_path: Path, **kwargs):
    return resolve_firms_source(
        reproducibility=kwargs.pop("reproducibility", False),
        pointer_path=tmp_path / "CURRENT.json",
        versions_dir=tmp_path / "versions",
        **kwargs,
    )


def test_baseline_path_is_the_frozen_training_file() -> None:
    assert FIRMS_BASELINE_CSV == REPO_ROOT / "data" / "processed" / BASELINE_FILENAME
    assert (
        FIRMS_REPRODUCIBILITY_CSV
        == REPO_ROOT
        / "artifacts"
        / "hito1"
        / "reproducibility"
        / "firms"
        / BASELINE_FILENAME
    )


def test_without_pointer_resolves_to_baseline(tmp_path) -> None:
    source = _resolve(tmp_path)
    assert source.origin == "baseline"
    assert source.path == FIRMS_BASELINE_CSV
    assert (source.coverage_start, source.coverage_end) == FIRMS_BASELINE_COVERAGE
    assert source.sha256 is None


def test_reproducibility_wins_even_if_pointer_exists(tmp_path) -> None:
    sha = _write_version(tmp_path / "versions")
    _write_pointer(tmp_path / "CURRENT.json", sha256=sha)
    source = _resolve(tmp_path, reproducibility=True)
    assert source.origin == "reproducibility"
    assert source.path == FIRMS_REPRODUCIBILITY_CSV


def test_reproducibility_defaults_to_env_var(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "1")
    assert (
        resolve_firms_source(pointer_path=tmp_path / "CURRENT.json").origin
        == "reproducibility"
    )
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "0")
    assert (
        resolve_firms_source(pointer_path=tmp_path / "CURRENT.json").origin
        == "baseline"
    )


def test_valid_pointer_resolves_to_current_version(tmp_path) -> None:
    sha = _write_version(tmp_path / "versions")
    _write_pointer(tmp_path / "CURRENT.json", sha256=sha)
    source = _resolve(tmp_path)
    assert source.origin == "current"
    assert source.path == (tmp_path / "versions" / "v1.csv").resolve()
    assert source.sha256 == sha
    assert source.coverage_end == date(2026, 9, 22)


@pytest.mark.parametrize(
    "pointer_text",
    [
        "{no es json",
        json.dumps(["lista"]),
        json.dumps({"schema_version": 99, "relative_path": "v1.csv"}),
        json.dumps(
            {"schema_version": POINTER_SCHEMA_VERSION, "relative_path": "v1.csv"}
        ),
        json.dumps(
            {
                "schema_version": 1,
                "path": "v1.csv",
                "sha256": "0" * 64,
                "coverage_start": "2021-08-30",
                "coverage_end": "2026-09-22",
            }
        ),
    ],
    ids=[
        "json_invalido",
        "raiz_no_objeto",
        "esquema_desconocido",
        "claves_faltantes",
        "esquema_1_rechazado",
    ],
)
def test_malformed_pointer_fails_explicitly(tmp_path, pointer_text) -> None:
    _write_version(tmp_path / "versions")
    (tmp_path / "CURRENT.json").write_text(pointer_text, encoding="utf-8")
    with pytest.raises(FirmsSourceError):
        _resolve(tmp_path)


def test_pointer_sha_mismatch_fails_instead_of_falling_back(tmp_path) -> None:
    _write_version(tmp_path / "versions")
    _write_pointer(tmp_path / "CURRENT.json", sha256="0" * 64)
    with pytest.raises(FirmsSourceError, match="sha256"):
        _resolve(tmp_path)


def test_pointer_to_missing_file_fails(tmp_path) -> None:
    (tmp_path / "versions").mkdir()
    _write_pointer(tmp_path / "CURRENT.json", sha256="0" * 64)
    with pytest.raises(FirmsSourceError, match="inexistente"):
        _resolve(tmp_path)


@pytest.mark.parametrize(
    "escape", ["../fuera.csv", "sub/v1.csv", str(Path("/tmp/abs.csv").resolve())]
)
def test_pointer_cannot_escape_versions_dir(tmp_path, escape) -> None:
    sha = _write_version(tmp_path / "versions")
    (tmp_path / "fuera.csv").write_text("x\n", encoding="utf-8")
    _write_pointer(tmp_path / "CURRENT.json", relative_path=escape, sha256=sha)
    with pytest.raises(FirmsSourceError, match="fuera de"):
        _resolve(tmp_path)


def test_pointer_without_valid_created_at_fails(tmp_path) -> None:
    sha = _write_version(tmp_path / "versions")
    _write_pointer(tmp_path / "CURRENT.json", sha256=sha, created_at="ayer")
    with pytest.raises(FirmsSourceError, match="incompleto"):
        _resolve(tmp_path)


def test_baseline_sha_constant_matches_reproducibility_snapshot() -> None:
    """El snapshot del Hito 1 está versionado en git: fija la constante que
    el refresco usa para verificar la línea base antes de extenderla."""
    assert (
        hashlib.sha256(FIRMS_REPRODUCIBILITY_CSV.read_bytes()).hexdigest()
        == FIRMS_BASELINE_SHA256
    )


def test_pointer_with_reversed_coverage_fails(tmp_path) -> None:
    sha = _write_version(tmp_path / "versions")
    _write_pointer(
        tmp_path / "CURRENT.json",
        sha256=sha,
        coverage_start="2026-09-22",
        coverage_end="2021-08-30",
    )
    with pytest.raises(FirmsSourceError, match="coverage_end"):
        _resolve(tmp_path)


def test_prototype_service_maps_firms_source_error_to_unavailable(monkeypatch) -> None:
    import src.inference.prototype_service as svc

    def _raise(**_kwargs):
        raise FirmsSourceError("puntero roto")

    monkeypatch.setattr(svc, "resolve_firms_source", _raise)
    meteo_row = pd.Series({"forecast_time": pd.Timestamp("2026-09-01", tz="UTC")})
    with pytest.raises(
        svc.PrototypeUnavailableError, match="Fuente FIRMS inválida: puntero roto"
    ):
        svc.build_feature_matrix(pd.Timestamp("2026-09-01", tz="UTC"), meteo_row)


def test_prototype_service_reports_missing_resolved_file(monkeypatch, tmp_path) -> None:
    import src.inference.prototype_service as svc
    from src.procesamiento.firms_source import FirmsSource

    missing = FirmsSource(
        path=tmp_path / "no_existe.csv",
        origin="baseline",
        coverage_start=date(2021, 8, 30),
        coverage_end=date(2026, 8, 30),
    )
    monkeypatch.setattr(svc, "resolve_firms_source", lambda **_kwargs: missing)
    meteo_row = pd.Series({"forecast_time": pd.Timestamp("2026-09-01", tz="UTC")})
    with pytest.raises(
        svc.PrototypeUnavailableError, match="No existe el histórico FIRMS"
    ):
        svc.build_feature_matrix(pd.Timestamp("2026-09-01", tz="UTC"), meteo_row)


def test_no_hardcoded_firms_baseline_path_outside_firms_source() -> None:
    """La ruta de la línea base FIRMS vive SOLO en firms_source.py.
    `verify_reproducibility.py` queda exceptuado a propósito: su lista de
    rutas es el dato que verifica (inventario del manifest del Hito 1)."""
    allowed = {
        REPO_ROOT / "src" / "procesamiento" / "firms_source.py",
        REPO_ROOT / "scripts" / "verify_reproducibility.py",
        Path(__file__).resolve(),
    }
    # Solo literales de string ("...csv" / '...csv'); las menciones en
    # docstrings/comentarios (entre backticks) describen, no leen.
    literal = re.compile(re.escape(BASELINE_FILENAME) + r"""["']""")
    offenders = []
    for folder in ("src", "scripts", "app", "tools", "tests"):
        for path in (REPO_ROOT / folder).rglob("*.py"):
            if path.resolve() in allowed:
                continue
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if literal.search(line):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
    assert offenders == []


def test_firms_source_has_no_legacy_imports() -> None:
    result = validate_pipeline_isolation(
        [REPO_ROOT / "src" / "procesamiento" / "firms_source.py"],
        forbidden=FORBIDDEN_LEGACY_REFERENCES,
    )
    assert result.status == "PASS", result.detail
