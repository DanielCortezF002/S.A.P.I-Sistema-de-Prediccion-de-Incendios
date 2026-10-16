"""SAPI F1 (D1/IA-P1-02, Astra A3): control automatizado de unidad de despliegue.

No reemplaza la revisión humana; es una red mínima para que un conjunto
incompleto (migración V004 sin el gate del backend, o viceversa) falle la
suite estática en vez de promocionarse en silencio.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = REPO_ROOT / "db" / "migration"
V004 = MIGRATIONS / "V004__add_firms_origin.sql"
FIRMS_ORIGIN_POLICY = (
    REPO_ROOT
    / "services/backend/src/main/java/cl/sapi/backend/ranking/persistence/FirmsOriginPolicy.java"
)
RANKING_PERSISTENCE_SERVICE = (
    REPO_ROOT
    / "services/backend/src/main/java/cl/sapi/backend/ranking/persistence/RankingPersistenceService.java"
)
COMPOSE = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_v004_migration_and_backend_gate_are_present_together() -> None:
    """Si V004 existe, el gate de procedencia del backend debe existir también (y viceversa)."""
    v004_present = V004.exists()
    gate_present = FIRMS_ORIGIN_POLICY.exists()
    assert v004_present == gate_present, (
        "V004 (migración de firms_origin) y FirmsOriginPolicy (gate del backend) "
        "son una sola unidad de despliegue (IA-P1-02): no pueden promocionarse por separado. "
        f"V004 presente={v004_present}, gate presente={gate_present}"
    )


def test_persistence_service_consults_the_policy_before_the_repository() -> None:
    """A3 completo: persist() debe usar el mismo bean de política, no solo RankingService."""
    if not RANKING_PERSISTENCE_SERVICE.exists():
        return
    source = RANKING_PERSISTENCE_SERVICE.read_text(encoding="utf-8")
    assert "FirmsOriginPolicy" in source, (
        "RankingPersistenceService debe inyectar FirmsOriginPolicy -- una llamada directa a "
        "persist() que bypasee RankingService no debe poder evadir la política (Astra A1)."
    )


def test_compose_backend_declares_the_persistence_policy_when_v004_exists() -> None:
    """Si V004 existe, docker-compose.yml debe fijar la política de procedencia del backend."""
    if not V004.exists():
        return
    backend_env = COMPOSE["services"]["backend"]["environment"]
    assert "SAPI_PERSISTENCE_ALLOWED_FIRMS_ORIGINS" in backend_env, (
        "V004 existe pero docker-compose.yml no declara la política de procedencia del "
        "backend -- unidad de despliegue incompleta (IA-P1-02)."
    )
