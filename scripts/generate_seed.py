"""Genera seed SQL demo: 50 celdas x N días con microclimas y geometría circular ~1 km²."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

# Corredor Viña del Mar – Quilpué – Villa Alemana (interfaz urbano-forestal)
# Coordenadas reales alineadas con el informe académico S.A.P.I. 2026
#
# Grilla COMPACTA 5 filas × 10 columnas = 50 celdas adyacentes (~1 km² cada una)
# Las celdas se tocan entre sí formando una red continua de monitoreo.
#
# Centro del corredor (zona de interfaz urbano-forestal de los incendios 2024):
#   Lat centro: -33.040  (Quilpué / Viña del Mar sector cerros)
#   Lon centro: -71.490  (entre costa y sector urbano)
#
# Cobertura total: ~9.3 km E-O  x  ~4.5 km N-S
BASE_LON = -71.535  # Extremo oeste (inicio grilla, sector costero Viña)
BASE_LAT = -33.062  # Extremo sur del bloque
COLS = 10
ROWS = 5
STEP_LON = 0.010    # ~930 m por columna  → celdas casi contiguas E-O
STEP_LAT = 0.009    # ~1000 m por fila    → celdas casi contiguas N-S
BUFFER_METERS = 490  # Radio ~490 m → celdas se tocan sin solapar
DEMO_START = date(2025, 2, 9)
DEMO_END = date(2025, 2, 15)
DEMO_DAYS = (DEMO_END - DEMO_START).days + 1
REGLA_CELLS = (38, 49)

ZONAS = {
    "costa": {"temp": (16.0, 23.0), "hr": (62.0, 88.0), "viento": (18.0, 38.0)},
    "urbano": {"temp": (19.0, 27.0), "hr": (42.0, 62.0), "viento": (8.0, 28.0)},
    "precordillera": {"temp": (22.0, 31.0), "hr": (22.0, 48.0), "viento": (6.0, 35.0)},
}


def _zone_for_col(col: int) -> str:
    # Alineado con app/utils/cell_zones.py
    # Cols 0-1: Costa litoral Viña del Mar
    # Cols 2-6: Urbano-forestal (Quilpué / Villa Alemana)
    # Cols 7-9: Precordillera / cerros orientales
    if col <= 1:
        return "costa"
    if col <= 6:
        return "urbano"
    return "precordillera"


def _day_progress(day_index: int) -> float:
    """0.0 primer día → 1.0 día crítico."""
    if DEMO_DAYS <= 1:
        return 1.0
    return day_index / (DEMO_DAYS - 1)


def _interp(zone: str, col: int, spread: float, progress: float) -> tuple[float, float, float]:
    z = ZONAS[zone]
    t_mid = (z["temp"][0] + z["temp"][1]) / 2
    h_mid = (z["hr"][0] + z["hr"][1]) / 2
    t = t_mid + spread + progress * 4.0
    h = h_mid - spread * 2 - progress * 12.0
    w = (z["viento"][0] + z["viento"][1]) / 2 + col * 0.4 + progress * 3.0
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


def _prob_from_meteo(
    temp: float, hr: float, viento: float, regla: int, zone: str
) -> float:
    if regla:
        return 0.97
    base = {"costa": 0.20, "urbano": 0.44, "precordillera": 0.58}
    score = base[zone]
    score += max(0, (temp - 20) / 120)
    score += max(0, (48 - hr) / 250)
    score += min(0.06, viento / 400)
    caps = {"costa": 0.32, "urbano": 0.62, "precordillera": 0.64}
    return round(min(caps[zone], max(0.10, score)), 2)


def _circle_wkt(lon: float, lat: float) -> str:
    return (
        f"ST_Buffer(ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)::geography, "
        f"{BUFFER_METERS})::geometry"
    )


def _generate_rows_for_day(fecha: date, day_index: int, is_peak: bool) -> list[str]:
    progress = _day_progress(day_index)
    rows: list[str] = []
    idx = 1
    for row in range(ROWS):
        for col in range(COLS):
            zone = _zone_for_col(col)
            lon = round(BASE_LON + col * STEP_LON, 5)
            lat = round(BASE_LAT + row * STEP_LAT, 5)
            spread = (row - ROWS / 2) * 0.12
            temp, hr, viento = _interp(zone, col, spread, progress)

            if is_peak and idx in REGLA_CELLS:
                temp, hr, viento = 32.5, 24.0, 34.0

            regla = _regla_30_30_30(temp, hr, viento)
            prob = _prob_from_meteo(temp, hr, viento, regla, zone)
            nivel = _nivel(prob)
            cell_id = f"VP-{idx:03d}"
            geom = _circle_wkt(lon, lat)
            rows.append(
                f"('{cell_id}', '{fecha.isoformat()}'::date, {prob}, '{nivel}', "
                f"{temp}, {hr}, {viento}, {regla}, {geom})"
            )
            idx += 1
    assert idx == 51
    return rows


def main() -> None:
    all_rows: list[str] = []
    summary_days: list[dict] = []

    for day_index in range(DEMO_DAYS):
        fecha = DEMO_START + timedelta(days=day_index)
        is_peak = fecha == DEMO_END
        day_rows = _generate_rows_for_day(fecha, day_index, is_peak)
        all_rows.extend(day_rows)
        altos = sum(1 for r in day_rows if ", 'alto'," in r or " 'alto'," in r)
        reglas = sum(1 for r in day_rows if ", 1, ST_Buffer" in r)
        summary_days.append(
            {"fecha": fecha.isoformat(), "altos": altos, "regla_30_30_30": reglas}
        )

    lines = [
        "-- Seed demo corredor Viña–Quilpué–Villa Alemana: 50 celdas x ventana multi-día",
        f"-- Rango: {DEMO_START.isoformat()} .. {DEMO_END.isoformat()} ({DEMO_DAYS} días)",
        "-- Generado por scripts/generate_seed.py",
        "",
        "TRUNCATE predicciones_riesgo RESTART IDENTITY CASCADE;",
        "",
        "INSERT INTO predicciones_riesgo (cell_id, fecha, probabilidad, nivel_riesgo, "
        "temperatura, humedad_relativa, velocidad_viento, regla_30_30_30, geom)",
        "VALUES",
        ",\n".join(all_rows) + ";",
        "",
        "INSERT INTO staging_incendios (fecha, latitud, longitud, fuente, geom) VALUES",
    ]

    for i in range(1, 11):
        lat = round(-33.04 - i * 0.003, 5)
        lon = round(-71.48 - i * 0.004, 5)
        suffix = "," if i < 10 else ";"
        lines.append(
            f"('{DEMO_END.isoformat()}'::timestamptz, {lat}, {lon}, 'conaf_seed', "
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
            f"(TIMESTAMP '{DEMO_END.isoformat()} 12:00:00+00' - INTERVAL '{i} hours', "
            f"{20 + i % 4}, {50 - i % 8}, {12 + i % 10}, "
            f"'VTM', ST_SetSRID(ST_MakePoint(-71.50, -33.04), 4326)){suffix}"
        )

    lines.extend(
        [
            "",
            "INSERT INTO observability_logs (componente, evento, detalle, nivel)",
            "VALUES ('seed', 'init', "
            f"'Seed multi-día {DEMO_START}..{DEMO_END}: {len(all_rows)} filas', 'INFO');",
            "",
        ]
    )

    root = Path(__file__).parent.parent
    sql_path = root / "docker" / "initdb" / "04_seed_valparaiso.sql"
    sql_path.write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "start": DEMO_START.isoformat(),
        "end": DEMO_END.isoformat(),
        "days": DEMO_DAYS,
        "rows_total": len(all_rows),
        "cells_per_day": 50,
        "by_day": summary_days,
    }
    reports_dir = root / "reports"
    reports_dir.mkdir(exist_ok=True)
    (reports_dir / "seed_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Generated {len(all_rows)} rows ({DEMO_DAYS} days x 50 cells) -> {sql_path}")


if __name__ == "__main__":
    main()
