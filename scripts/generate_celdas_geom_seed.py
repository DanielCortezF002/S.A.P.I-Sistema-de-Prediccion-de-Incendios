"""Genera db/migration/V003__seed_celdas_geom.sql desde src/geo/grid.py (SAPI-58).

La geometría de las celdas tiene una sola fuente: `all_cells()`. Esta
migración es generada; `tests/test_db_migrations_v2.py` verifica que el
archivo versionado sea idéntico a lo que este script produce.

Uso:
    python scripts/generate_celdas_geom_seed.py          # reescribe V003
    python scripts/generate_celdas_geom_seed.py --check  # exit 1 si difiere
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.geo.grid import all_cells  # noqa: E402

SEED_PATH = REPO_ROOT / "db" / "migration" / "V003__seed_celdas_geom.sql"

HEADER = (
    "-- SAPI-58 · V003: las 50 celdas de la grilla (VP-001..VP-050).\n"
    "-- GENERADO por scripts/generate_celdas_geom_seed.py desde\n"
    "-- src/geo/grid.py::all_cells(). No editar a mano: regenerar y verificar\n"
    "-- con tests/test_db_migrations_v2.py.\n"
)


def render_seed_sql(cells: list[dict]) -> str:
    rows = [
        f"    ('{c['cell_id']}', ST_MakeEnvelope({c['min_lon']!r}, {c['min_lat']!r}, "
        f"{c['max_lon']!r}, {c['max_lat']!r}, 4326))"
        for c in cells
    ]
    return (
        HEADER
        + "INSERT INTO celdas_geom (cell_id, geom) VALUES\n"
        + ",\n".join(rows)
        + ";\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    expected = render_seed_sql(all_cells())
    if args.check:
        current = SEED_PATH.read_text(encoding="utf-8") if SEED_PATH.exists() else ""
        if current != expected:
            print(f"{SEED_PATH} difiere de all_cells(); regenerar.", file=sys.stderr)
            return 1
        print("V003 coincide con all_cells().")
        return 0
    SEED_PATH.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Escrito {SEED_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
