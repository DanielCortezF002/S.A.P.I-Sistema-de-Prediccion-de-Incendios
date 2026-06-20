"""Genera seed SQL demo: 50 celdas con microclimas Valparaíso y geometría circular ~1 km².

Origen de datos:
- Geometría: grilla sintética 5×10 sobre corredor Viña del Mar–Quilpué–Villa Alemana (EPSG:4326).
- Meteo: perfiles zonales calibrados (costa / urbano / precordillera), no series en vivo.
  Referencia conceptual: estaciones DMC (p. ej. Quinta Normal VM) y patrones estivales
  costeros (mar de viento, menor T y mayor HR en litoral).
- Incendios staging: puntos ilustrativos tipo CONAF (conaf_historico_seed.json).
"""

from __future__ import annotations

import math
from pathlib import Path

# Corredor Viña–Quilpué–Villa Alemana; grilla 5×10 sobre interfaz urbano-forestal
BASE_LON = -71.52
BASE_LAT = -33.04
COLS = 10
ROWS = 5
STEP_LON = 0.008
STEP_LAT = 0.008
# Radio ~564 m → área circular ≈ 1 km²
BUFFER_METERS = 564
DEMO_FECHA = "2025-02-15"

# Perfiles microclimáticos (°C, HR %, viento km/h) — verano costero
ZONAS = {
    "costa": {"temp": (16.0, 23.0), "hr": (62.0, 88.0), "viento": (18.0, 38.0)},
    "urbano": {"temp": (19.0, 27.0), "hr": (42.0, 62.0), "viento": (8.0, 28.0)},
    "precordillera": {"temp": (22.0, 31.0), "hr": (22.0, 48.0), "viento": (6.0, 35.0)},
}


def _zone_for_row(row: int) -> str:
    if row == 0:
        return "costa"
    if row <= 2:
        return "urbano"
    return "precordillera"


def _interp(zone: str, col: int, spread: float = 0.0) -> tuple[float, float, float]:
    """Interpola meteo dentro del rango zonal con leve gradiente este-oeste."""
    z = ZONAS[zone]
    t = (z["temp"][0] + z["temp"][1]) / 2 + spread
    h = (z["hr"][0] + z["hr"][1]) / 2 - spread * 2
    w = (z["viento"][0] + z["viento"][1]) / 2 + col * 0.4
    t = max(z["temp"][0], min(z["temp"][1], round(t, 1)))
    h = max(z["hr"][0], min(z["hr"][1], round(h, 1)))
    w = max(z["viento"][0], min(z["viento"][1], round(w, 1)))
    return t, h, w


def _regla_30_30_30(temp: float, hr: float, viento: float) -> int:
    return 1 if temp > 30 and hr < 30 and viento > 30 else 0


def _nivel(prob: float) -> str:
    if prob < 0.33:
        return "bajo"
    if prob < 0.66:
        return "medio"
    return "alto"


def _prob_from_meteo(temp: float, hr: float, viento: float, regla: int) -> float:
    """Heurística demo alineada con mayor riesgo en precordillera seca y ventosa."""
    score = 0.25
    score += max(0, (temp - 18) / 40)
    score += max(0, (55 - hr) / 80)
    score += min(0.2, viento / 200)
    if regla:
        score += 0.25
    return round(min(0.97, max(0.08, score)), 2)


def _circle_wkt(lon: float, lat: float) -> str:
    return (
        f"ST_Buffer(ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)::geography, "
        f"{BUFFER_METERS})::geometry"
    )


def main() -> None:
    rows_sql: list[str] = []
    idx = 1
    for row in range(ROWS):
        zone = _zone_for_row(row)
        for col in range(COLS):
            lon = round(BASE_LON + col * STEP_LON, 5)
            lat = round(BASE_LAT + row * STEP_LAT, 5)
            spread = (col - COLS / 2) * 0.15
            temp, hr, viento = _interp(zone, col, spread)

            # Dos celdas precordillera con regla activa (demo defensa)
            if idx in (37, 43):
                temp, hr, viento = 32.5, 24.0, 34.0

            regla = _regla_30_30_30(temp, hr, viento)
            prob = _prob_from_meteo(temp, hr, viento, regla)
            nivel = _nivel(prob)
            cell_id = f"VP-{idx:03d}"
            geom = _circle_wkt(lon, lat)
            rows_sql.append(
                f"('{cell_id}', '{DEMO_FECHA}'::date, {prob}, '{nivel}', "
                f"{temp}, {hr}, {viento}, {regla}, {geom})"
            )
            idx += 1

    assert idx == 51, f"Se esperaban 50 celdas, se generaron {idx - 1}"

    lines = [
        "-- Seed demo corredor Viña–Quilpué–Villa Alemana: 50 celdas circulares (~1 km²)",
        f"-- Fecha única de snapshot: {DEMO_FECHA} | Generado por scripts/generate_seed.py",
        "",
        "TRUNCATE predicciones_riesgo RESTART IDENTITY CASCADE;",
        "",
        "INSERT INTO predicciones_riesgo (cell_id, fecha, probabilidad, nivel_riesgo, "
        "temperatura, humedad_relativa, velocidad_viento, regla_30_30_30, geom)",
        "VALUES",
        ",\n".join(rows_sql) + ";",
        "",
        "INSERT INTO staging_incendios (fecha, latitud, longitud, fuente, geom) VALUES",
    ]

    for i in range(1, 11):
        lat = round(-33.04 - i * 0.003, 5)
        lon = round(-71.48 - i * 0.004, 5)
        suffix = "," if i < 10 else ";"
        lines.append(
            f"('{DEMO_FECHA}'::timestamptz, {lat}, {lon}, 'conaf_seed', "
            f"ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)){suffix}"
        )

    lines.extend(
        [
            "",
            "INSERT INTO staging_meteo (fecha, temperatura, humedad_relativa, "
            "velocidad_viento, estacion_id, geom) VALUES",
        ]
    )
    for i in range(1, 11):
        suffix = "," if i < 10 else ";"
        lines.append(
            f"(TIMESTAMP '{DEMO_FECHA} 12:00:00+00' - INTERVAL '{i} hours', "
            f"{20 + i % 4}, {50 - i % 8}, {12 + i % 10}, "
            f"'VTM', ST_SetSRID(ST_MakePoint(-71.50, -33.04), 4326)){suffix}"
        )

    lines.extend(
        [
            "",
            "INSERT INTO observability_logs (componente, evento, detalle, nivel)",
            "VALUES ('seed', 'init', "
            "'Seed corredor Vina-Quilpue-Villa Alemana: 50 celdas, meteo zonal', 'INFO');",
            "",
        ]
    )

    out = Path(__file__).parent.parent / "docker" / "initdb" / "04_seed_valparaiso.sql"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {len(rows_sql)} cells (VP-001..VP-050) -> {out}")


if __name__ == "__main__":
    main()
