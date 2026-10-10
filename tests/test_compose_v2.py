"""Docker Compose de la arquitectura v2 (SAPI-60): verificaciones estáticas.

Leen `docker-compose.yml`, `.env.example` y `.gitignore` tal como están
versionados (ADR-004, ADR-008 y ADR-009). La verificación en ejecución (build,
health, Flyway, ranking, persistencia y la consulta psql) la hace
`scripts/compose_v2_preflight.py` con Docker; ver
`artifacts/hito2/testing/sapi-60/`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
SERVICES = COMPOSE["services"]
ENV_EXAMPLE = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")

V2_SERVICES = ("db-v2", "ml-api", "backend")
HITO1_PROFILES = {
    "db-postgis": "legacy",
    "analytics-backend": "legacy",
    "web-presentation": "legacy",
    "n8n-bridge": "ops",
}
# Puerto de SAPI-60.CA1 por servicio y la variable que permite moverlo.
CA1_PORTS = {
    "backend": ("SAPI_BACKEND_PORT", 8080),
    "ml-api": ("SAPI_ML_PORT", 8000),
    "db-v2": ("SAPI_DB_PORT", 5432),
}
INTERPOLATION = re.compile(r"\$\{([A-Z0-9_]+)")


def _strings(node) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for value in node.values() for s in _strings(value)]
    if isinstance(node, list):
        return [s for value in node for s in _strings(value)]
    return []


def _healthcheck_command(service: str) -> str:
    test = SERVICES[service]["healthcheck"]["test"]
    return " ".join(test) if isinstance(test, list) else test


def test_default_route_is_exactly_the_v2_services() -> None:
    default = sorted(
        name for name, spec in SERVICES.items() if not spec.get("profiles")
    )
    assert default == sorted(V2_SERVICES)


@pytest.mark.parametrize("service,profile", sorted(HITO1_PROFILES.items()))
def test_hito1_services_stay_out_of_the_v2_route(service: str, profile: str) -> None:
    assert SERVICES[service]["profiles"] == [profile]


@pytest.mark.parametrize("service", V2_SERVICES)
def test_ca1_ports_are_published_on_loopback(service: str) -> None:
    variable, port = CA1_PORTS[service]
    assert SERVICES[service]["ports"] == [f"127.0.0.1:${{{variable}:-{port}}}:{port}"]


@pytest.mark.parametrize("service", V2_SERVICES)
def test_ca2_every_v2_service_has_a_healthcheck(service: str) -> None:
    assert _healthcheck_command(service).split()[0] in ("CMD", "CMD-SHELL")
    assert not SERVICES[service]["healthcheck"].get("disable", False)


def test_healthchecks_probe_the_real_endpoints() -> None:
    # TCP: el servidor temporal de inicialización de la imagen solo usa socket Unix.
    assert "pg_isready -h 127.0.0.1 -p 5432" in _healthcheck_command("db-v2")
    assert "http://127.0.0.1:8000/health" in _healthcheck_command("ml-api")
    # -f: curl falla con cualquier código HTTP >= 400.
    assert SERVICES["backend"]["healthcheck"]["test"][:3] == ["CMD", "curl", "-fsS"]
    assert "http://127.0.0.1:8080/health" in _healthcheck_command("backend")


def test_ca3_database_password_has_no_default() -> None:
    required = re.compile(r"^\$\{SAPI_DB_PASSWORD:\?")
    assert required.match(SERVICES["db-v2"]["environment"]["POSTGRES_PASSWORD"])
    assert required.match(
        SERVICES["backend"]["environment"]["SPRING_DATASOURCE_PASSWORD"]
    )
    for service in V2_SERVICES:
        assert "sapi_secret" not in " ".join(_strings(SERVICES[service]))


def test_ca3_env_example_defines_every_variable_of_the_v2_services() -> None:
    used = {
        name
        for service in V2_SERVICES
        for value in _strings(SERVICES[service])
        for name in INTERPOLATION.findall(value)
    }
    defined = {
        line.split("=", 1)[0] for line in ENV_EXAMPLE.splitlines() if "=" in line
    }
    assert used, "los servicios v2 deberían leer su configuración de .env"
    assert sorted(used - defined) == []


def test_ca3_real_env_file_is_ignored_by_git() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in [line.strip() for line in gitignore]


def test_ca4_v2_database_uses_its_own_volume_without_legacy_initdb() -> None:
    assert SERVICES["db-v2"]["volumes"] == ["sapi_v2_pgdata:/var/lib/postgresql/data"]
    assert "sapi_v2_pgdata" in COMPOSE["volumes"]
    # H4: la base legacy sigue declarada y nadie de la ruta v2 la usa.
    assert "sapi_pgdata" in COMPOSE["volumes"]
    assert (
        "./docker/initdb:/docker-entrypoint-initdb.d:ro"
        in SERVICES["db-postgis"]["volumes"]
    )
    for service in V2_SERVICES:
        mounts = " ".join(SERVICES[service].get("volumes", []))
        assert "sapi_pgdata:" not in mounts
        assert "docker/initdb" not in mounts


def test_v2_database_image_is_the_one_used_by_the_persistence_its() -> None:
    image = SERVICES["db-v2"]["image"]
    it_source = (
        REPO_ROOT
        / "services/backend/src/test/java/cl/sapi/backend/ranking/persistence"
        / "RankingPersistenceIT.java"
    ).read_text(encoding="utf-8")
    assert image == "postgis/postgis:15-3.4"
    assert f'"{image}"' in it_source


def test_backend_reaches_ml_and_database_by_service_name() -> None:
    environment = SERVICES["backend"]["environment"]
    assert environment["SAPI_ML_BASE_URL"] == "http://ml-api:8000"
    assert environment["SPRING_DATASOURCE_URL"].startswith(
        "jdbc:postgresql://db-v2:5432/"
    )
    for value in _strings(environment):
        assert "localhost" not in value
        assert "127.0.0.1" not in value


def test_backend_runs_flyway_on_the_canonical_migrations_read_only() -> None:
    backend = SERVICES["backend"]
    assert backend["volumes"] == ["./db/migration:/app/db/migration:ro"]
    assert (
        backend["environment"]["SAPI_FLYWAY_LOCATIONS"]
        == "filesystem:/app/db/migration"
    )
    assert backend["environment"]["SAPI_PERSISTENCE_ENABLED"] == "true"


def test_backend_waits_for_a_healthy_database() -> None:
    depends_on = SERVICES["backend"]["depends_on"]
    assert depends_on["db-v2"]["condition"] == "service_healthy"
    assert depends_on["ml-api"]["condition"] == "service_started"


def test_ml_service_runs_in_reproducible_mode_from_the_image() -> None:
    ml = SERVICES["ml-api"]
    assert ml["environment"]["SAPI_REPRODUCIBILITY_MODE"] == "1"
    assert ml["build"] == {"context": ".", "dockerfile": "Dockerfile.ml-api"}
    # El snapshot de Hito 1 va dentro de la imagen: sin montajes del host.
    assert "volumes" not in ml
