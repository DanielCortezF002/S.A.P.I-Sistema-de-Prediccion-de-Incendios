"""Genera seed SQL expandido para PostGIS (prototipo demo: 50 celdas)."""

from __future__ import annotations

import random
from pathlib import Path

random.seed(42)

ROWS: list[str] = []
BASE_LON, BASE_LAT = -71.58, -33.08
STEP = 0.01
DATES = ["2020-02-15", "2021-01-20", "2022-03-10", "2023-01-15", "2024-02-03", "2025-06-01"]
idx = 1

for row in range(5):
    for col in range(10):
        lon = round(BASE_LON + col * STEP, 4)
        lat = round(BASE_LAT + row * STEP, 4)
        lon2 = round(lon + STEP, 4)
        lat2 = round(lat + STEP, 4)
        prob = round(random.uniform(0.1, 0.95), 2)
        nivel = "bajo" if prob < 0.33 else ("medio" if prob < 0.66 else "alto")
        temp = round(random.uniform(18, 36), 1)
        hum = round(random.uniform(15, 70), 1)
        wind = round(random.uniform(5, 42), 1)
        regla = 1 if temp > 30 and hum < 30 and wind > 30 else 0
        fecha = DATES[idx % len(DATES)]
        wkt = (
            f"POLYGON(({lon} {lat}, {lon2} {lat}, "
            f"{lon2} {lat2}, {lon} {lat2}, {lon} {lat}))"
        )
        cell_id = f"VP-{idx:03d}"
        geom = f"ST_SetSRID(ST_GeomFromText('{wkt}'), 4326)"
        ROWS.append(
            f"('{cell_id}', '{fecha}'::date, {prob}, '{nivel}', {temp}, {hum}, {wind}, "
            f"{regla}, {geom})"
        )
        idx += 1

lines = [
    "-- Seed expandido: 50 celdas demo Región de Valparaíso (2020-2025)",
    "-- Ejecutado por db-postgis al iniciar via docker-entrypoint-initdb.d",
    "",
    "INSERT INTO predicciones_riesgo (cell_id, fecha, probabilidad, nivel_riesgo, "
    "temperatura, humedad_relativa, velocidad_viento, regla_30_30_30, geom)",
    "VALUES",
    ",\n".join(ROWS) + ";",
    "",
    "INSERT INTO staging_incendios (fecha, latitud, longitud, fuente, geom) VALUES",
]

for i in range(1, 11):
    lat = round(-33.05 - i * 0.005, 4)
    lon = round(-71.55 - i * 0.003, 4)
    suffix = "," if i < 10 else ";"
    lines.append(
        f"('2024-02-03'::timestamptz, {lat}, {lon}, 'conaf_seed', "
        f"ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)){suffix}"
    )

lines.extend(["", "INSERT INTO staging_meteo (fecha, temperatura, humedad_relativa, "
              "velocidad_viento, estacion_id, geom) VALUES"])
for i in range(1, 11):
    suffix = "," if i < 10 else ";"
    lines.append(
        f"(NOW() - INTERVAL '{i} hours', {28 + i % 5}, {35 - i % 10}, {15 + i % 12}, "
        f"'VTM', ST_SetSRID(ST_MakePoint(-71.55, -33.05), 4326)){suffix}"
    )

lines.extend([
    "",
    "INSERT INTO observability_logs (componente, evento, detalle, nivel)",
    "VALUES ('seed', 'init', 'Seed expandido Valparaiso 50 celdas cargado', 'INFO');",
    "",
])

out = Path(__file__).parent.parent / "docker" / "initdb" / "04_seed_valparaiso.sql"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Generated {len(ROWS)} cells -> {out}")
