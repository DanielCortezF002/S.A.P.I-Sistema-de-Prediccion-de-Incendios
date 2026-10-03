"""SAPI-58: verificaciones ESTÁTICAS de las migraciones v2 (db/migration/).

Nunca abren una conexión a PostgreSQL: la Release Gate puede tener una BD
legacy o compartida y estas migraciones no deben aplicarse sobre ella. La
migración viva se prueba aparte, en un PostGIS efímero dedicado
(scripts/sapi58_migration_integration.ps1).
"""

from __future__ import annotations

import re
import socket
from pathlib import Path

import pytest

from scripts.generate_celdas_geom_seed import SEED_PATH, render_seed_sql
from src.geo.grid import all_cells

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = REPO_ROOT / "db" / "migration"
V002 = MIGRATIONS / "V002__create_sapi_v2_schema.sql"


@pytest.fixture(autouse=True)
def _no_database_connections(monkeypatch):
    def _refuse(*_args, **_kwargs):
        raise AssertionError("los tests estáticos de SAPI-58 no abren conexiones")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)


def _sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _without_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _table_body(table: str) -> str:
    match = re.search(
        rf"CREATE TABLE {table} \((.*?)\n\);", _without_comments(_sql(V002)), re.S
    )
    assert match, f"no se encontró CREATE TABLE {table}"
    return re.sub(r"\s+", " ", match.group(1))


def test_migrations_are_versioned_in_order():
    names = sorted(p.name for p in MIGRATIONS.glob("*.sql"))
    assert names == [
        "V001__enable_postgis.sql",
        "V002__create_sapi_v2_schema.sql",
        "V003__seed_celdas_geom.sql",
    ]
    assert all(re.fullmatch(r"V\d{3}__[a-z0-9_]+\.sql", n) for n in names)


def test_v001_enables_postgis():
    assert "CREATE EXTENSION IF NOT EXISTS postgis" in _sql(
        MIGRATIONS / "V001__enable_postgis.sql"
    )


def test_no_probability_wording_in_migrations():
    for path in MIGRATIONS.glob("*.sql"):
        assert "probab" not in _sql(path).lower(), path.name


def test_v002_declares_the_three_v2_tables_only():
    tables = re.findall(r"CREATE TABLE (\w+)", _without_comments(_sql(V002)))
    assert tables == ["celdas_geom", "ejecuciones", "predicciones_celda"]


def test_celdas_geom_has_polygon_geometry_and_gist_index():
    body = _table_body("celdas_geom")
    assert "cell_id text PRIMARY KEY" in body
    assert "geom geometry(Polygon, 4326) NOT NULL" in body
    assert "CHECK (cell_id ~ '^VP-[0-9]{3}$')" in body
    assert "CREATE INDEX celdas_geom_geom_gist ON celdas_geom USING gist (geom)" in (
        _sql(V002)
    )


def test_ejecuciones_constraints_match_the_contract():
    body = _table_body("ejecuciones")
    assert "forecast_time timestamptz NOT NULL" in body
    assert "CHECK (inputs_fingerprint ~ '^[0-9a-f]{64}$')" in body
    assert "CHECK (score_semantics = 'relative_rank')" in body
    assert "CHECK (scientific_model_validation = false)" in body
    assert "UNIQUE (forecast_time, model_version, inputs_fingerprint)" in body
    assert "UNIQUE (id, forecast_time)" in body


def test_predicciones_celda_keys_checks_and_history_index():
    body = _table_body("predicciones_celda")
    assert "PRIMARY KEY (ejecucion_id, cell_id)" in body
    assert "UNIQUE (ejecucion_id, rank)" in body
    assert (
        "FOREIGN KEY (ejecucion_id, forecast_time) REFERENCES ejecuciones "
        "(id, forecast_time) ON DELETE CASCADE"
    ) in body
    assert "FOREIGN KEY (cell_id) REFERENCES celdas_geom (cell_id)" in body
    assert "CHECK (score >= 0 AND score <= 1)" in body
    assert "CHECK (rank BETWEEN 1 AND 50)" in body
    assert "CHECK (display_rank <= rank)" in body
    assert re.search(
        r"CREATE INDEX predicciones_celda_cell_time_idx\s+ON predicciones_celda "
        r"\(cell_id, forecast_time DESC\)",
        _sql(V002),
    )


def test_seed_is_generated_from_the_grid():
    assert _sql(SEED_PATH) == render_seed_sql(all_cells())


def test_seed_has_exactly_the_50_grid_cells():
    ids = re.findall(r"\('(VP-\d{3})', ST_MakeEnvelope\(", _sql(SEED_PATH))
    assert ids == [f"VP-{i:03d}" for i in range(1, 51)]
