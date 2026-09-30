"""Explicit store/code roots for Attempt 2 collectors.

Avoid WIP/junction assumptions. Defaults follow project layout relative to repo:

  data/processed/nasa_firms_2021-08-30_2026-08-30.csv  (FIRMS baseline)
  models/prototype_model_d.pkl
  data/processed/firms/CURRENT.json
  data/processed/dmc/<station>/CURRENT.json
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from src.procesamiento.firms_source import (
    FIRMS_BASELINE_CSV,
    FIRMS_REPRODUCIBILITY_CSV,
    REPO_ROOT as _FIRMS_REPO_ROOT,
)

# The FIRMS baseline path lives ONLY in src/procesamiento/firms_source.py
# (tests/test_firms_source.py guard); derive the repo-relative forms from it.
FIRMS_BASELINE_REL = FIRMS_BASELINE_CSV.relative_to(_FIRMS_REPO_ROOT)
FIRMS_BASELINE_REPRO_REL = FIRMS_REPRODUCIBILITY_CSV.relative_to(_FIRMS_REPO_ROOT)
MODEL_REL = Path("models") / "prototype_model_d.pkl"
FIRMS_STORE_REL = Path("data") / "processed" / "firms"
DMC_STORE_REL = Path("data") / "processed" / "dmc"


@dataclass(frozen=True)
class StoreRoots:
    """Canonical operational roots (may differ from code checkout)."""

    code_root: Path
    data_root: Path
    models_root: Path

    @classmethod
    def from_repo(
        cls,
        repo: Path,
        *,
        data_root: Path | None = None,
        models_root: Path | None = None,
    ) -> StoreRoots:
        repo = Path(repo)
        env_data = os.environ.get("SAPI_ATTEMPT2_DATA_ROOT")
        env_models = os.environ.get("SAPI_ATTEMPT2_MODELS_ROOT")
        return cls(
            code_root=repo,
            data_root=Path(data_root or env_data or (repo / "data")),
            models_root=Path(models_root or env_models or (repo / "models")),
        )

    def firms_baseline_candidates(self) -> list[Path]:
        """Deterministic candidate list — no store crawling."""
        # Prefer data_root layout matching firms_source.FIRMS_BASELINE_CSV
        processed = self.data_root / "processed" / FIRMS_BASELINE_REL.name
        # If data_root already IS repo/data, processed path is data/processed/...
        if self.data_root.name == "data":
            primary = self.data_root / "processed" / FIRMS_BASELINE_REL.name
        else:
            primary = self.data_root / FIRMS_BASELINE_REL
        # Also allow explicit env override
        env = os.environ.get("SAPI_ATTEMPT2_FIRMS_BASELINE")
        out: list[Path] = []
        if env:
            out.append(Path(env))
        out.append(primary)
        if processed not in out:
            out.append(processed)
        out.append(self.code_root / FIRMS_BASELINE_REL)
        out.append(self.code_root / FIRMS_BASELINE_REPRO_REL)
        # de-dupe preserving order
        seen: set[str] = set()
        uniq: list[Path] = []
        for p in out:
            key = str(p.resolve()) if p.exists() else str(p)
            if key not in seen:
                seen.add(key)
                uniq.append(p)
        return uniq

    def model_path(self) -> Path:
        env = os.environ.get("SAPI_ATTEMPT2_MODEL_PATH")
        if env:
            return Path(env)
        if self.models_root.name == "models":
            return self.models_root / MODEL_REL.name
        return self.models_root / MODEL_REL

    def firms_store(self) -> Path:
        if self.data_root.name == "data":
            return self.data_root / "processed" / "firms"
        return self.data_root / FIRMS_STORE_REL

    def dmc_store(self, station_id: str = "330007") -> Path:
        if self.data_root.name == "data":
            return self.data_root / "processed" / "dmc" / station_id
        return self.data_root / DMC_STORE_REL / station_id

    def dmc_lock(self) -> Path:
        # The DMC writer locks the whole dmc root, not a station (DmcPaths.lock).
        return self.dmc_store().parent / ".refresh.lock"
