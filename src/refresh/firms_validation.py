"""Read-only v3 publication gate. Rebuilds from hashed source windows offline.

Never downloads, publishes, rolls back, cleans up or writes a validation file.
The failed Attempt 1 validator/evidence remains unchanged.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.ingesta.firms_schema import parse_source_csv, project_base
from src.procesamiento.firms_source import (
    resolve_firms_source,
    PROJECTED_POINTER_SCHEMA_VERSION,
)
from src.refresh.atomic import sha256_bytes
from src.refresh.firms_refresh import FirmsPaths, build_version_bytes


def validate_publication(paths: FirmsPaths) -> dict:
    """Raises ValueError on invalid v3 publication; paths may point to tmp fixtures."""
    if paths.lock.exists():
        raise ValueError("FIRMS lock presente")
    source = resolve_firms_source(
        reproducibility=False,
        pointer_path=paths.pointer,
        versions_dir=paths.versions_dir,
        baseline_csv=paths.baseline_csv,
    )
    if source.origin != "current":
        raise ValueError("CURRENT FIRMS ausente")
    pointer = json.loads(paths.pointer.read_text(encoding="utf-8"))
    if pointer["schema_version"] != PROJECTED_POINTER_SCHEMA_VERSION:
        raise ValueError("Este gate requiere pointer v3")
    baseline = paths.baseline_csv.read_bytes()
    if sha256_bytes(baseline) != paths.baseline_sha256:
        raise ValueError("Hash baseline inválido")
    if pointer["base_origin"] == "baseline":
        if pointer["base_relative_path"] is not None:
            raise ValueError("Referencia baseline inválida")
        base = baseline
    else:
        name = pointer["base_relative_path"]
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or not name.endswith(".csv")
        ):
            raise ValueError("Referencia base fuera de versions")
        base_path = (paths.versions_dir / name).resolve()
        if base_path.parent != paths.versions_dir.resolve():
            raise ValueError("Referencia base fuera de versions")
        base = base_path.read_bytes()
    if sha256_bytes(base) != pointer["base_sha256"]:
        raise ValueError("Hash base inválido")
    if sha256_bytes(project_base(base)) != pointer["projected_base_sha256"]:
        raise ValueError("Hash proyección base inválido")
    # Coverage is requested coverage, never inferred from detections (empty days exist).
    if pointer["base_origin"] == "baseline":
        from src.procesamiento.firms_source import FIRMS_BASELINE_COVERAGE

        base_start, previous_end = FIRMS_BASELINE_COVERAGE
    else:
        prior = json.loads(base_path.with_suffix(".json").read_text(encoding="utf-8"))
        if prior["sha256"] != pointer["base_sha256"] or prior["relative_path"] != name:
            raise ValueError("Sidecar base inválido")
        base_start = date.fromisoformat(prior["coverage_start"])
        previous_end = date.fromisoformat(prior["coverage_end"])
    if source.coverage_start != base_start or source.coverage_end <= previous_end:
        raise ValueError("Extensión de cobertura inválida")
    frames, covered, seen = [], set(), set()
    for item in pointer["raw_artifacts"]:
        raw = Path(item["path"]).resolve()
        if not raw.is_relative_to(paths.raw_dir.resolve()) or raw in seen:
            raise ValueError("Referencia raw fuera del store o duplicada")
        seen.add(raw)
        data = raw.read_bytes()
        if sha256_bytes(data) != item["sha256"]:
            raise ValueError("Hash raw inválido")
        start, end = (date.fromisoformat(x) for x in raw.stem.split("_"))
        if (
            not previous_end < start <= end <= source.coverage_end
            or (end - start).days >= 5
        ):
            raise ValueError("Ventana raw inválida")
        frames.append(
            parse_source_csv(data.decode("utf-8"), raw.parent.name, start, end)
        )
        covered.update(start + timedelta(days=i) for i in range((end - start).days + 1))
    expected_days = {
        previous_end + timedelta(days=i + 1)
        for i in range((source.coverage_end - previous_end).days)
    }
    if covered != expected_days:
        raise ValueError("Cobertura raw incompleta")
    # build_version_bytes validates and reconciles all source observations using
    # the same explicit precedence as the writer, before operational projection.
    rows = pd.concat(frames, ignore_index=True)
    rebuilt, added = build_version_bytes(base, rows, previous_end, source.coverage_end)
    if rebuilt != source.path.read_bytes() or added != pointer["new_rows"]:
        raise ValueError("Publicación no coincide con base y raw verificados")
    sidecar = json.loads(source.path.with_suffix(".json").read_text(encoding="utf-8"))
    if sidecar != pointer:
        raise ValueError("Sidecar y CURRENT difieren")
    history = [
        json.loads(line)
        for line in paths.history.read_text(encoding="utf-8").splitlines()
    ]
    if (
        not history
        or history[-1].get("event") not in ("publish", "rollback")
        or any(history[-1].get(key) != value for key, value in pointer.items())
    ):
        raise ValueError("History no acredita CURRENT")
    return {
        "result": "FIRMS ACCEPTED",
        "schema_version": pointer["schema_version"],
        "sha256": pointer["sha256"],
        "row_count": pointer["row_count"],
        "new_rows": added,
        "raw_files_verified": len(seen),
        "baseline_sha256": paths.baseline_sha256,
    }
