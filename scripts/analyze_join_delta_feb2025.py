"""Análisis de delta_minutos y huecos DMC para join feb-2025."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.procesamiento.meteo_fire_joiner import ignition_timestamp
from src.procesamiento.raw_parser import parse_dmc_json

GAP_THRESHOLD_MIN = 15


def main() -> None:
    pq = Path("data/processed/fires_meteo_join_2025-02.parquet")
    df = pd.read_parquet(pq)
    matched = df[df["join_status"] == "matched"].copy()
    d = matched["delta_minutos"].astype(float)

    print("=== DELTA_MINUTOS (164 matched) ===")
    print(f"count: {len(d)}")
    print(f"min:    {d.min():.4f}")
    print(f"p25:    {d.quantile(0.25):.4f}")
    print(f"median: {d.median():.4f}")
    print(f"p75:    {d.quantile(0.75):.4f}")
    print(f"p90:    {d.quantile(0.90):.4f}")
    print(f"p95:    {d.quantile(0.95):.4f}")
    print(f"max:    {d.max():.4f}")
    print(f"mean:   {d.mean():.4f}")
    print(f"std:    {d.std():.4f}")

    bins = [0, 1, 2, 3, 5, 7, 10, 12, 15, 16]
    labels = ["0-1", "1-2", "2-3", "3-5", "5-7", "7-10", "10-12", "12-15", ">15"]
    hist = pd.cut(d, bins=bins, labels=labels, right=False)
    print("\nHistograma (minutos):")
    print(hist.value_counts().sort_index().to_string())

    edge_10_15 = int(((d >= 10) & (d <= 15)).sum())
    edge_10_15_open = int(((d > 10) & (d <= 15)).sum())
    at_15 = int((d == 15).sum())
    print(f"\nEntre 10-15 min (inclusive): {edge_10_15}")
    print(f"Entre 10-15 min (10 < d <= 15): {edge_10_15_open}")
    print(f"Exactamente 15.0 min: {at_15}")

    meteo = parse_dmc_json("data/raw/dmc_historico_330007_2025-02.json")
    meteo["momento"] = pd.to_datetime(meteo["momento"], utc=True)
    meteo = meteo.sort_values("momento").reset_index(drop=True)
    cadence = meteo["momento"].diff().dt.total_seconds() / 60.0

    print("\n=== DMC 330007 FEB-2025 (cadencia) ===")
    print(f"registros parseados: {len(meteo)}")
    print(f"primer momento: {meteo.momento.min()}")
    print(f"ultimo momento: {meteo.momento.max()}")
    print(f"cadencia mediana (min): {cadence.median():.2f}")
    print(f"cadencia p95 (min): {cadence.quantile(0.95):.2f}")
    print(f"cadencia max (min): {cadence.max():.2f}")

    gaps = cadence[cadence > GAP_THRESHOLD_MIN].dropna()
    print(f"\nHuecos > {GAP_THRESHOLD_MIN} min entre lecturas consecutivas: {len(gaps)}")
    if len(gaps):
        rows = []
        for idx in gaps.index:
            rows.append(
                {
                    "before": meteo.loc[idx - 1, "momento"],
                    "after": meteo.loc[idx, "momento"],
                    "gap_min": float(cadence.loc[idx]),
                }
            )
        gap_df = pd.DataFrame(rows).sort_values("gap_min", ascending=False)
        print("Top 15 huecos:")
        for _, r in gap_df.head(15).iterrows():
            print(f"  {r.before} -> {r.after}  ({r.gap_min:.1f} min = {r.gap_min / 60:.2f} h)")

    gaps_1h = cadence[cadence > 60].dropna()
    print(f"\nHuecos > 60 min (cortes serios): {len(gaps_1h)}")

    fires = pd.read_csv("data/processed/nasa_firms_2021-08-30_2026-08-30.csv")
    fires_feb = fires[fires["acq_date"].astype(str).str.startswith("2025-02")].copy()
    fires_feb["ignition_ts"] = fires_feb.apply(
        lambda r: ignition_timestamp(str(r["acq_date"]), r["acq_time"]),
        axis=1,
    )

    fires_in_gaps = 0
    if len(gaps):
        for idx in gaps.index:
            t0 = meteo.loc[idx - 1, "momento"]
            t1 = meteo.loc[idx, "momento"]
            inside = fires_feb[(fires_feb["ignition_ts"] > t0) & (fires_feb["ignition_ts"] < t1)]
            if len(inside):
                fires_in_gaps += len(inside)
                print(
                    f"  ignición en hueco {t0} .. {t1} "
                    f"(gap={cadence.loc[idx]:.0f} min, n={len(inside)})"
                )
    print(f"\nIgniciones cuyo instante cae DENTRO de un hueco DMC (>15 min): {fires_in_gaps}")

    total_span_min = (meteo.momento.max() - meteo.momento.min()).total_seconds() / 60
    gap_minutes_total = float(gaps.sum()) if len(gaps) else 0.0
    print(f"\nCobertura temporal DMC: {total_span_min:.0f} min de ventana")
    if total_span_min:
        pct = 100 * gap_minutes_total / total_span_min
        print(f"Tiempo total en huecos >15min: {gap_minutes_total:.0f} min ({pct:.2f}% del mes)")

    # Sensibilidad: ¿cuántas igniciones quedarían out_of_tolerance si el hueco fuera el problema?
    # Para cada ignición, delta al reading más cercano sin filtro de 15 min
    meteo_ts = meteo["momento"]
    nearest_raw = []
    for ts in fires_feb["ignition_ts"]:
        deltas_raw = (meteo_ts - ts).dt.total_seconds().abs() / 60.0
        nearest_raw.append(float(deltas_raw.min()))
    fires_feb["delta_nearest_raw"] = nearest_raw
    would_fail = int((fires_feb["delta_nearest_raw"] > GAP_THRESHOLD_MIN).sum())
    print(f"\nIgniciones con lectura DMC más cercana > {GAP_THRESHOLD_MIN} min (sin ventana): {would_fail}")
    if would_fail:
        worst = fires_feb.nlargest(5, "delta_nearest_raw")[
            ["acq_date", "acq_time", "delta_nearest_raw"]
        ]
        print("Peores 5:")
        print(worst.to_string(index=False))


if __name__ == "__main__":
    main()
