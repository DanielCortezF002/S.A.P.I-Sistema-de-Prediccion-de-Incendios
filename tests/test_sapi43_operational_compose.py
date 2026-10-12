
"""SAPI-43 prep. TEST_FIXTURE_ONLY. OPERATIONAL_CURRENT_USED=NO.

Overlay operacional mínimo: modo 0, datos en solo lectura y volumen de
PostGIS distinto del reproducible. `docker compose config` no arranca
contenedores ni lee CURRENT.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

TEST_FIXTURE_ONLY = True
OPERATIONAL_CURRENT_USED = "NO"

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_FILE = REPO_ROOT / "docker-compose.yml"
OVERLAY_FILE = REPO_ROOT / "docker-compose.operational.yml"
CONFIG_PASSWORD = "sapi43-config-fixture"


class _Loader(yaml.SafeLoader):
    """Acepta el tag !override de Compose y devuelve la secuencia."""


def _override(loader: yaml.SafeLoader, node: yaml.Node) -> list:
    return loader.construct_sequence(node)


_Loader.add_constructor("!override", _override)


def _load(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)


def _compose_config(*files: str) -> dict:
    env = os.environ.copy()
    env["SAPI_DB_PASSWORD"] = CONFIG_PASSWORD

    command = ["docker", "compose"]
    for name in files:
        command.extend(["-f", name])
    command.append("config")

    result = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    loaded = yaml.safe_load(result.stdout)
    assert isinstance(loaded, dict)
    return loaded


def _volume_targets(service: dict) -> list[tuple[str, str, bool]]:
    """(source, target, read_only) de cada montaje ya resuelto."""
    found = []

    for mount in service.get("volumes") or []:
        if isinstance(mount, str):
            source, target, *rest = mount.split(":")
            found.append((source, target, "ro" in rest))
            continue

        found.append(
            (
                str(mount.get("source")),
                str(mount.get("target")),
                bool(mount.get("read_only")),
            )
        )

    return found


def test_module_is_labeled_fixture_only() -> None:
    text = Path(__file__).read_text(encoding="utf-8")

    assert TEST_FIXTURE_ONLY is True
    assert OPERATIONAL_CURRENT_USED == "NO"
    assert "TEST_FIXTURE_ONLY" in text
    assert "OPERATIONAL_CURRENT_USED=NO" in text


def test_base_compose_stays_reproducible() -> None:
    base = _load(BASE_FILE)
    ml = base["services"]["ml-api"]

    assert ml["environment"]["SAPI_REPRODUCIBILITY_MODE"] == "1"
    assert "volumes" not in ml

    assert base["services"]["db-v2"]["volumes"] == [
        "sapi_v2_pgdata:/var/lib/postgresql/data"
    ]

    assert "sapi_v2_operational_pgdata" not in BASE_FILE.read_text(
        encoding="utf-8"
    )


def test_overlay_is_minimal_and_read_only() -> None:
    overlay = _load(OVERLAY_FILE)
    services = overlay["services"]

    assert set(services) == {"ml-api", "db-v2"}

    assert services["ml-api"]["environment"] == {
        "SAPI_REPRODUCIBILITY_MODE": "0"
    }

    assert services["ml-api"]["volumes"] == [
        "./data:/app/data:ro"
    ]

    assert services["db-v2"]["volumes"] == [
        "sapi_v2_operational_pgdata:/var/lib/postgresql/data"
    ]

    assert "sapi_v2_operational_pgdata" in overlay["volumes"]
    assert "sapi_v2_pgdata" not in overlay["volumes"]

    text = OVERLAY_FILE.read_text(encoding="utf-8")

    assert 'SAPI_REPRODUCIBILITY_MODE: "1"' not in text
    assert ":/app/data\n" not in text
    assert ":/app/data:" not in text or ":/app/data:ro" in text


def test_docker_compose_config_keeps_the_base_reproducible() -> None:
    resolved = _compose_config("docker-compose.yml")

    ml = resolved["services"]["ml-api"]
    db = resolved["services"]["db-v2"]

    assert str(
        ml["environment"]["SAPI_REPRODUCIBILITY_MODE"]
    ) == "1"

    assert _volume_targets(ml) == []

    sources = [item[0] for item in _volume_targets(db)]

    assert len(sources) == 1
    assert sources[0].endswith("sapi_v2_pgdata")
    assert not sources[0].endswith("sapi_v2_operational_pgdata")

    volume_names = " ".join(resolved.get("volumes", {}))

    assert "sapi_v2_operational_pgdata" not in volume_names


def test_docker_compose_config_isolates_the_operational_environment() -> None:
    resolved = _compose_config(
        "docker-compose.yml",
        "docker-compose.operational.yml",
    )

    ml = resolved["services"]["ml-api"]
    db = resolved["services"]["db-v2"]

    assert str(
        ml["environment"]["SAPI_REPRODUCIBILITY_MODE"]
    ) == "0"

    data_mounts = [
        item
        for item in _volume_targets(ml)
        if item[1] == "/app/data"
    ]

    assert data_mounts, _volume_targets(ml)

    source, _target, read_only = data_mounts[0]

    # Compatibilidad multiplataforma:
    # Windows: C:\SAPI-43-PREP\data
    # Linux:   /workspace/data
    normalized_source = source.replace("\\", "/").rstrip("/")

    assert normalized_source.endswith("/data")
    assert read_only is True

    sources = [item[0] for item in _volume_targets(db)]

    assert sources == [
        source
        for source in sources
        if source.endswith("sapi_v2_operational_pgdata")
    ]

    assert len(sources) == 1

    assert resolved["services"]["backend"]["environment"][
        "SAPI_PERSISTENCE_ENABLED"
    ] in (True, "true")


def test_operational_mode_stays_on_the_ml_service() -> None:
    overlay = _load(OVERLAY_FILE)

    assert set(overlay["services"]) == {"ml-api", "db-v2"}

    resolved = _compose_config(
        "docker-compose.yml",
        "docker-compose.operational.yml",
    )

    backend_env = (
        resolved["services"]["backend"].get("environment") or {}
    )

    assert "SAPI_REPRODUCIBILITY_MODE" not in backend_env

    assert str(
        resolved["services"]["ml-api"]["environment"][
            "SAPI_REPRODUCIBILITY_MODE"
        ]
    ) == "0"
