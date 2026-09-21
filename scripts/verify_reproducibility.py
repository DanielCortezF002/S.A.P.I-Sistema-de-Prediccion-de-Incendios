"""Verifica el estado local de artefactos de datos/modelo contra
`artifacts/hito1/reproducibility/manifest.json`.

No descarga ni regenera nada. Si un artefacto no existe localmente, lo
reporta como AUSENTE (no es un error -- .gitignore los excluye a
proposito, ver docs/deploy.md). Si existe pero su hash no coincide con el
manifest, falla con codigo de salida distinto de cero: eso si es una
regresion real (el artefacto cambio sin que el manifest se actualizara).

Uso: python scripts/verify_reproducibility.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "artifacts" / "hito1" / "reproducibility" / "manifest.json"

# (ruta relativa al repo, clave dentro del manifest donde vive el sha256 esperado)
CHECKED_ARTIFACTS = [
    ("data/processed/nasa_firms_2021-08-30_2026-08-30.csv",
     ("cadena_de_proveniencia", "1_nasa_firms", "raw_output", "sha256_verificado_09-09-2026")),
    ("data/processed/temporal_dataset_h6.parquet",
     ("cadena_de_proveniencia", "4_procesamiento_y_dataset_temporal", "output", "sha256_verificado_09-09-2026")),
    ("models/prototype_model_d.pkl",
     ("cadena_de_proveniencia", "5_training_modelo_d", "output", "sha256_verificado_09-09-2026")),
    # Snapshots minimos de reproducibilidad (R3), agregados 09-09-2026:
    ("artifacts/hito1/reproducibility/dmc/dmc_historico_330007_2026-08.json",
     ("cadena_de_proveniencia", "2_dmc_330007", "snapshot_reproducibilidad_R3", "archivos", 0, "sha256")),
    ("artifacts/hito1/reproducibility/dmc/dmc_meteo_2026-09-01.json",
     ("cadena_de_proveniencia", "2_dmc_330007", "snapshot_reproducibilidad_R3", "archivos", 1, "sha256")),
    ("artifacts/hito1/reproducibility/firms/nasa_firms_2021-08-30_2026-08-30.csv",
     ("cadena_de_proveniencia", "1_nasa_firms", "snapshot_reproducibilidad_R3", "sha256")),
    ("artifacts/hito1/reproducibility/dem/grid_topography.csv",
     ("cadena_de_proveniencia", "3_copernicus_dem", "snapshot_reproducibilidad_R3", "sha256")),
]

# Artefactos que DEBEN existir siempre (versionados en git) -- si faltan, es
# una regresion real (alguien borro o no clono un archivo que si esta en git),
# a diferencia de data/raw|processed que faltan legitimamente en un clon limpio.
ALWAYS_EXPECTED = {
    "models/prototype_model_d.pkl",
    "artifacts/hito1/reproducibility/dmc/dmc_historico_330007_2026-08.json",
    "artifacts/hito1/reproducibility/dmc/dmc_meteo_2026-09-01.json",
    "artifacts/hito1/reproducibility/firms/nasa_firms_2021-08-30_2026-08-30.csv",
    "artifacts/hito1/reproducibility/dem/grid_topography.csv",
}


def _dig(d: dict, path: tuple[str, ...]):
    for key in path:
        d = d[key]
    return d


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not MANIFEST_PATH.exists():
        print(f"NO EXISTE {MANIFEST_PATH} -- nada que verificar.")
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    mismatches = []
    absent = []
    verified = []

    for rel_path, key_path in CHECKED_ARTIFACTS:
        full_path = REPO_ROOT / rel_path
        expected_hash = _dig(manifest, key_path)
        if not full_path.exists():
            absent.append(rel_path)
            continue
        actual_hash = sha256_of(full_path)
        if actual_hash != expected_hash:
            mismatches.append((rel_path, expected_hash, actual_hash))
        else:
            verified.append(rel_path)

    print(f"VERIFICADOS ({len(verified)}):")
    for p in verified:
        print(f"  OK  {p}")

    unexpected_absent = [p for p in absent if p in ALWAYS_EXPECTED]
    normal_absent = [p for p in absent if p not in ALWAYS_EXPECTED]

    print(f"\nAUSENTES ({len(normal_absent)}) -- normal si no se regeneraron localmente, ver .gitignore:")
    for p in normal_absent:
        print(f"  --  {p}")

    if unexpected_absent:
        print(
            f"\nFALTAN ARTEFACTOS QUE DEBERIAN ESTAR VERSIONADOS ({len(unexpected_absent)}):"
        )
        for p in unexpected_absent:
            print(f"  !!  {p} -- esperado siempre presente (git add ya realizado), no deberia faltar")
        mismatches.append(("(ausencia inesperada)", "presente", "ausente"))

    if mismatches:
        print(f"\nDISCREPANCIAS ({len(mismatches)}) -- el archivo existe pero su hash NO coincide con el manifest:")
        for p, expected, actual in mismatches:
            print(f"  !!  {p}\n      esperado: {expected}\n      actual:   {actual}")
        print(
            "\nEsto significa que el artefacto local cambio sin actualizar "
            "artifacts/hito1/reproducibility/manifest.json, o que el pipeline "
            "produjo un resultado distinto al oficial. No asumir que es seguro "
            "usarlo sin investigar la causa."
        )
        return 2

    print("\nSin discrepancias.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
