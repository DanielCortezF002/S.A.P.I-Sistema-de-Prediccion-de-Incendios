"""Corrige geometrías incorrectas en predicciones_riesgo para fechas > 2025-02-15."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.geo.grid import BASE_LAT, BASE_LON, CELL_RADIUS_METERS, STEP_LAT, STEP_LON

BUFFER = CELL_RADIUS_METERS

lines = []
idx = 1
for row in range(5):
    for col in range(10):
        lon = round(BASE_LON + col * STEP_LON, 5)
        lat = round(BASE_LAT + row * STEP_LAT, 5)
        cell_id = f"VP-{idx:03d}"
        geom = (
            f"ST_Buffer(ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)::geography, {BUFFER})::geometry"
        )
        lines.append(
            f"UPDATE predicciones_riesgo SET geom = {geom} "
            f"WHERE cell_id = '{cell_id}' AND fecha > '2025-02-15';"
        )
        idx += 1

sql = "\n".join(lines)
with open("docker/fix_geom.sql", "w", encoding="utf-8") as f:
    f.write(sql)
print(f"Generadas {idx-1} sentencias UPDATE -> docker/fix_geom.sql")
