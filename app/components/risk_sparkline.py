"""Evolución de riesgo: máximo diario de probabilidad en la ventana del seed."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from app.utils.demo_seed import get_all_demo_dates, get_demo_gdf


def daily_max_probability_series(
    dates: list[date] | None = None,
) -> pd.Series:
    """Serie indexada por fecha con max(probabilidad) del día en el seed."""
    days = dates if dates is not None else get_all_demo_dates()
    values: dict[date, float] = {}
    for d in days:
        gdf = get_demo_gdf(d)
        if gdf is None or gdf.empty:
            values[d] = 0.0
        else:
            values[d] = float(gdf["probabilidad"].max())
    series = pd.Series(values, name="prob_max")
    series.index = pd.Index([d.isoformat() for d in series.index], name="fecha")
    return series


def render_risk_sparkline(dates: list[date] | None = None) -> None:
    """Mini evolución de 7 días (ventana del seed), datos reales del demo."""
    series = daily_max_probability_series(dates)
    st.caption(
        "Evolución · máximo diario de probabilidad (escenario sembrado, no serie horaria)"
    )
    chart_df = series.mul(100).rename("Probabilidad máx. (%)").to_frame()
    st.line_chart(chart_df, height=180)
