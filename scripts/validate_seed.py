"""Valida distribución del seed demo (ejecutar tras generate_seed.py)."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

SQL_PATH = Path(__file__).parent.parent / "docker" / "initdb" / "04_seed_valparaiso.sql"
PATTERN = re.compile(
    r"\('(VP-\d+)'.*?, (\d+\.\d+), '(bajo|medio|alto)', "
    r"([\d.]+), ([\d.]+), ([\d.]+), (\d),"
)


def main() -> int:
    text = SQL_PATH.read_text(encoding="utf-8")
    rows = PATTERN.findall(text)
    if len(rows) != 50:
        print(f"FAIL: esperadas 50 celdas, hay {len(rows)}")
        return 1

    niveles = Counter(r[2] for r in rows)
    regla_cells = [r[0] for r in rows if r[6] == "1"]
    costa = [r for r in rows if int(r[0].split("-")[1]) % 10 <= 3]  # cols 0-2 approx wrong

    # cols from id: (n-1) % 10
    def col_of(vp: str) -> int:
        return (int(vp.split("-")[1]) - 1) % 10

    costa_cells = [r for r in rows if col_of(r[0]) <= 2]
    precord = [r for r in rows if col_of(r[0]) >= 7]

    errors: list[str] = []
    if niveles.get("bajo", 0) < 10:
        errors.append(f"Pocas celdas bajo: {niveles.get('bajo', 0)} (esperado ~15 costa)")
    if len(regla_cells) != 2:
        errors.append(f"Regla 30-30-30: {len(regla_cells)} celdas, esperadas 2")
    for r in costa_cells:
        if float(r[3]) > 24:
            errors.append(f"{r[0]} costa con T={r[3]}°C > 24")
        if r[2] == "alto":
            errors.append(f"{r[0]} costa marcada alto")
    alto_sin_regla = [r[0] for r in rows if r[2] == "alto" and r[6] == "0"]
    if len(alto_sin_regla) > 3:
        errors.append(f"Demasiados alto sin regla: {alto_sin_regla}")

    print("Niveles:", dict(niveles))
    print("Regla activa:", regla_cells)
    print("Costa T max:", max(float(r[3]) for r in costa_cells))
    if errors:
        print("ERRORES:")
        for e in errors:
            print(" -", e)
        return 1
    print("OK: seed coherente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
