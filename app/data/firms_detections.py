"""Detecciones NASA FIRMS del incendio del 2024-02-03 en el corredor.

Capa de referencia histórica del mapa. Son focos reales medidos por satélite
(VIIRS), no salida del modelo: el escenario del dashboard es 2025-02-09 a
2025-02-15, así que esta capa va rotulada y apagable, nunca mezclada con las
probabilidades del seed.

El archivo vive acá y no en `data/processed/` porque ese directorio está en
`.gitignore`: una capa del dashboard que desaparece en un clon limpio o en
Streamlit Cloud no sirve. Son 348 filas (~11 KB), extraídas del volcado
completo `data/processed/nasa_firms_2021-08-30_2026-08-30.csv`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

EVENT_DATE = "2024-02-03"
EVENT_LABEL = "Focos reales 2024-02-03 (referencia histórica)"

_ASSET_PATH = Path(__file__).with_name("incendio_2024-02-03.csv")
_COLUMNS = ["latitude", "longitude", "frp", "acq_time", "confidence", "satellite"]


@lru_cache(maxsize=1)
def _read_asset() -> pd.DataFrame:
    """Lee el CSV una sola vez por proceso."""
    if not _ASSET_PATH.exists():
        return pd.DataFrame(columns=_COLUMNS)
    return pd.read_csv(_ASSET_PATH)


def load_event_detections() -> pd.DataFrame:
    """Focos del evento, ordenados de mayor a menor FRP.

    Devuelve una copia para que quien la reciba pueda filtrarla o anotarla
    sin corromper la caché. Si el asset falta, devuelve un DataFrame vacío
    con las columnas esperadas: la capa del mapa simplemente no se dibuja.
    """
    df = _read_asset()
    if df.empty:
        return df.copy()
    return df.sort_values("frp", ascending=False).reset_index(drop=True)
