"""Protege `artifacts/hito1/reproducibility/manifest.json` (auditoria de
reproducibilidad, 09-09-2026, ver docs/deploy.md). No descarga ni regenera
nada -- solo verifica que el manifest es coherente y, si los artefactos que
describe existen localmente, que sus hashes siguen coincidiendo."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_reproducibility import ALWAYS_EXPECTED, CHECKED_ARTIFACTS, REPO_ROOT, _dig, sha256_of

MANIFEST_PATH = REPO_ROOT / "artifacts" / "hito1" / "reproducibility" / "manifest.json"


def test_the_four_minimum_r3_artifacts_are_always_present() -> None:
    """Los 4 artefactos minimos para R3 (inference_reproducibility) estan
    versionados en git desde la formalizacion de reproducibilidad del
    09-09-2026: Modelo D, snapshot DMC (2 archivos), snapshot FIRMS,
    snapshot DEM derivado -- a diferencia de data/raw|processed
    operacional, NUNCA deberian faltar en un clon que efectivamente clono
    el repo completo."""
    assert len(ALWAYS_EXPECTED) == 5, "se esperaban 5 archivos: modelo + 2 DMC + FIRMS + DEM"
    for rel_path in ALWAYS_EXPECTED:
        full_path = REPO_ROOT / rel_path
        assert full_path.exists(), (
            f"{rel_path} deberia estar siempre presente (versionado en git) "
            "-- si falta, revisar .gitignore o si el clon esta incompleto."
        )


def test_manifest_exists_and_is_valid_json() -> None:
    assert MANIFEST_PATH.exists(), f"No existe {MANIFEST_PATH}"
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert "cadena_de_proveniencia" in manifest
    assert "reproducibilidad_por_dimension" in manifest


def test_manifest_declares_all_four_dimensions() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    dims = manifest["reproducibilidad_por_dimension"]
    for key in (
        "R1_environment_reproducibility",
        "R2_build_test_reproducibility",
        "R3_inference_reproducibility",
        "R4_scientific_retraining_reproducibility",
    ):
        assert key in dims, f"Falta {key} en reproducibilidad_por_dimension"
        assert dims[key].startswith(("VERIFIED", "PARTIAL", "NOT_VERIFIED")), (
            f"{key} tiene un valor inesperado: {dims[key]!r}"
        )


def test_locally_present_artifacts_match_manifest_hash() -> None:
    """No falla si el artefacto no existe (es normal, ver .gitignore) --
    SOLO falla si existe y su hash difiere del manifest, que es la
    regresion real que esta prueba busca detectar."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    mismatches = []
    for rel_path, key_path in CHECKED_ARTIFACTS:
        full_path = REPO_ROOT / rel_path
        if not full_path.exists():
            continue
        expected = _dig(manifest, key_path)
        actual = sha256_of(full_path)
        if actual != expected:
            mismatches.append((rel_path, expected, actual))
    assert not mismatches, (
        "Artefactos locales que ya NO coinciden con "
        f"artifacts/hito1/reproducibility/manifest.json: {mismatches}"
    )


def test_corrupted_artifact_is_detected(tmp_path) -> None:
    """No corrompe ningun archivo real -- crea uno de prueba en tmp_path,
    calcula su hash 'esperado', luego lo modifica y confirma que
    sha256_of() detecta el cambio. Protege la logica de deteccion en si,
    no un archivo del repo."""
    fake_artifact = tmp_path / "fake_model.pkl"
    fake_artifact.write_bytes(b"contenido original del artefacto de prueba")
    original_hash = sha256_of(fake_artifact)

    fake_artifact.write_bytes(b"contenido CORROMPIDO -- un solo byte distinto")
    corrupted_hash = sha256_of(fake_artifact)

    assert corrupted_hash != original_hash, (
        "sha256_of() no detecto una corrupcion evidente -- la logica de "
        "verificacion de scripts/verify_reproducibility.py no protegeria nada."
    )
