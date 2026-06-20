"""Valida distribución del seed demo multi-día (ejecutar tras generate_seed.py)."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SQL_PATH = Path(__file__).parent.parent / "docker" / "initdb" / "04_seed_valparaiso.sql"
SUMMARY_PATH = Path(__file__).parent.parent / "reports" / "seed_summary.json"
PATTERN = re.compile(
    r"\('(VP-\d+)', '(\d{4}-\d{2}-\d{2})'::date, (\d+\.\d+), '(bajo|medio|alto)', "
    r"([\d.]+), ([\d.]+), ([\d.]+), (\d),"
)
DEMO_START = "2025-02-09"
DEMO_END = "2025-02-15"
EXPECTED_DAYS = 7
EXPECTED_CELLS = 50


def col_of(vp: str) -> int:
    return (int(vp.split("-")[1]) - 1) % 10


def main() -> int:
    text = SQL_PATH.read_text(encoding="utf-8")
    rows = PATTERN.findall(text)
    expected_total = EXPECTED_DAYS * EXPECTED_CELLS

    if len(rows) != expected_total:
        print(f"FAIL: esperadas {expected_total} filas, hay {len(rows)}")
        return 1

    by_date: dict[str, list] = defaultdict(list)
    for r in rows:
        by_date[r[1]].append(r)

    errors: list[str] = []
    if len(by_date) != EXPECTED_DAYS:
        errors.append(f"Esperados {EXPECTED_DAYS} días, hay {len(by_date)}")

    first_day = by_date.get(DEMO_START, [])
    peak_day = by_date.get(DEMO_END, [])

    if len(first_day) != EXPECTED_CELLS:
        errors.append(f"Día inicial: {len(first_day)} celdas")
    if len(peak_day) != EXPECTED_CELLS:
        errors.append(f"Día pico: {len(peak_day)} celdas")

    first_altos = sum(1 for r in first_day if r[3] == "alto")
    if first_altos != 0:
        errors.append(f"Día {DEMO_START}: {first_altos} altos (esperado 0)")

    peak_regla = [r[0] for r in peak_day if r[7] == "1"]
    peak_altos = sum(1 for r in peak_day if r[3] == "alto")
    if len(peak_regla) != 2:
        errors.append(f"Día pico regla: {peak_regla} (esperadas 2)")
    if peak_altos != 2:
        errors.append(f"Día pico altos: {peak_altos} (esperado 2)")

    costa_first = [r for r in first_day if col_of(r[0]) <= 2]
    if costa_first and max(float(r[4]) for r in costa_first) > 24:
        errors.append("Costa día inicial con T > 24°C")

    print(f"Filas totales: {len(rows)}")
    print(f"Días: {sorted(by_date.keys())}")
    print(f"Día {DEMO_START}: altos={first_altos}")
    print(f"Día {DEMO_END}: altos={peak_altos}, regla={peak_regla}")

    if SUMMARY_PATH.exists():
        summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        print(f"Resumen JSON: {SUMMARY_PATH}")

    if errors:
        print("ERRORES:")
        for e in errors:
            print(" -", e)
        return 1
    print("OK: seed multi-día coherente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
