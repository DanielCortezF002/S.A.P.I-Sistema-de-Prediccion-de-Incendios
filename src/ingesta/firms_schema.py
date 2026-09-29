"""Versioned FIRMS source contracts; no inference of hotspot classification.

Raw SP keeps type. The operational projection excludes that SP-only field;
the original baseline/raw files remain the authoritative classification source.
CSV tokens are retained verbatim (no numeric round-trip through pandas).
"""

from __future__ import annotations

import csv
import io
import math
import re
from datetime import date

import pandas as pd

NRT_SOURCE = "VIIRS_SNPP_NRT"
SP_SOURCE = "VIIRS_SNPP_SP"
CONTRACT = "viirs-snpp-common-v1"
COMMON_COLUMNS = (
    "latitude",
    "longitude",
    "bright_ti4",
    "scan",
    "track",
    "acq_date",
    "acq_time",
    "satellite",
    "instrument",
    "confidence",
    "version",
    "bright_ti5",
    "frp",
    "daynight",
)
PROVENANCE_COLUMNS = ("firms_source", "request_start_date")
OPERATIONAL_COLUMNS = COMMON_COLUMNS + PROVENANCE_COLUMNS
HISTORICAL_COLUMNS = COMMON_COLUMNS + ("type",) + PROVENANCE_COLUMNS


def _csv_frame(text: str) -> pd.DataFrame:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise ValueError("CSV FIRMS malformado") from exc
    if not rows or not rows[0] or len(set(rows[0])) != len(rows[0]):
        raise ValueError("Cabecera FIRMS vacía o duplicada")
    if any(len(row) != len(rows[0]) for row in rows[1:]):
        raise ValueError("CSV FIRMS con filas de ancho incorrecto")
    return pd.DataFrame(rows[1:], columns=rows[0])


def _columns(frame: pd.DataFrame, expected: tuple[str, ...]) -> None:
    actual = list(frame.columns)
    if len(actual) != len(set(actual)):
        raise ValueError("Columnas FIRMS duplicadas")
    missing, extra = sorted(set(expected) - set(actual)), sorted(
        set(actual) - set(expected)
    )
    if missing or extra:
        raise ValueError(f"Schema FIRMS inválido: faltan {missing}; extra {extra}")


def _values(frame: pd.DataFrame, source: str, *, require_type: bool) -> None:
    for row in frame.to_dict("records"):
        for column in COMMON_COLUMNS:
            if not isinstance(row[column], str) or not row[column].strip():
                raise ValueError(f"Valor FIRMS ausente: {column}")
        for column in (
            "latitude",
            "longitude",
            "bright_ti4",
            "scan",
            "track",
            "bright_ti5",
            "frp",
        ):
            try:
                number = float(row[column])
            except (ValueError, TypeError):
                raise ValueError(f"Número FIRMS inválido: {column}") from None
            limit = 90 if column == "latitude" else 180
            if (
                not math.isfinite(number)
                or (column in ("latitude", "longitude") and abs(number) > limit)
                or (column not in ("latitude", "longitude", "frp") and number <= 0)
                or (column == "frp" and number < 0)
            ):
                raise ValueError(f"Número FIRMS fuera de rango: {column}")
        day = row["acq_date"]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            raise ValueError("Fecha FIRMS inválida")
        date.fromisoformat(day)
        clock = row["acq_time"]
        if (
            not re.fullmatch(r"\d{1,4}", clock)
            or int(clock) // 100 > 23
            or int(clock) % 100 > 59
        ):
            raise ValueError("Hora FIRMS inválida")
        if row["satellite"] != "N" or row["instrument"] != "VIIRS":
            raise ValueError("Sensor FIRMS incompatible con S-NPP")
        if row["confidence"] not in ("l", "n", "h") or row["daynight"] not in (
            "D",
            "N",
        ):
            raise ValueError("Categoría FIRMS inválida")
        suffix = r"(?:NRT|RT|URT)" if source == NRT_SOURCE else ""
        if not re.fullmatch(r"\d+(?:\.\d+)?" + suffix, row["version"]):
            raise ValueError("Versión FIRMS incompatible con source")
        if require_type and row["type"] not in ("0", "1", "2", "3"):
            raise ValueError("Clasificación type SP inválida")


def parse_source_csv(text: str, source: str, start: date, end: date) -> pd.DataFrame:
    """Strict per-window validation BEFORE persistence/concatenation.

    Reordered headers are accepted and canonicalized; extras (including type on
    NRT and caller-supplied provenance) are rejected. RT/URT are documented
    variants delivered by the NRT endpoint and retain their original version.
    """
    if source not in (NRT_SOURCE, SP_SOURCE) or end < start:
        raise ValueError("Source o ventana FIRMS inválidos")
    frame = _csv_frame(text)
    expected = COMMON_COLUMNS + (("type",) if source == SP_SOURCE else ())
    _columns(frame, expected)
    _values(frame, source, require_type=source == SP_SOURCE)
    if any(not start <= date.fromisoformat(d) <= end for d in frame["acq_date"]):
        raise ValueError(
            "Detecciones fuera de ventana; no se reescriben días ya publicados"
        )
    frame = frame.loc[:, list(expected)].copy()
    frame["firms_source"] = source
    frame["request_start_date"] = start.isoformat()
    return frame


def project_frame(
    frame: pd.DataFrame, *, require_sp_type: bool = False
) -> pd.DataFrame:
    """Project explicit historical/operational schemas; never fill type.

    The mixed historical union may have a structurally empty type for NRT.
    That absence is accepted only when already present in historical input;
    SP classification is validated and preserved in its original source.
    """
    expected = HISTORICAL_COLUMNS if "type" in frame.columns else OPERATIONAL_COLUMNS
    _columns(frame, expected)
    # Callers passing typed frames retain their existing scalar serialization.
    frame = frame.copy().fillna("").astype(str)
    if not set(frame["firms_source"]).issubset({NRT_SOURCE, SP_SOURCE}):
        raise ValueError("Source FIRMS desconocido")
    if (
        require_sp_type
        and SP_SOURCE in set(frame["firms_source"])
        and "type" not in frame
    ):
        raise ValueError("Falta clasificación type del source SP")
    for source, group in frame.groupby("firms_source", sort=False):
        _values(group, source, require_type=source == SP_SOURCE and "type" in group)
        if source == NRT_SOURCE and "type" in group and group["type"].ne("").any():
            raise ValueError("NRT no puede tener clasificación type")
    for day, request_day in zip(frame["acq_date"], frame["request_start_date"]):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", request_day) or date.fromisoformat(
            request_day
        ) > date.fromisoformat(day):
            raise ValueError("Procedencia request_start_date inválida")
    return frame.loc[:, list(OPERATIONAL_COLUMNS)]


def serialize(frame: pd.DataFrame, *, header: bool = True) -> bytes:
    return frame.to_csv(index=False, header=header, lineterminator="\n").encode("utf-8")


def project_base(data: bytes) -> bytes:
    """Pure projection: same field values/order; original bytes never modified."""
    if not data.endswith(b"\n"):
        raise ValueError("La base FIRMS no termina en salto de línea")
    return serialize(project_frame(_csv_frame(data.decode("utf-8"))))


def validate_operational(data: bytes) -> pd.DataFrame:
    frame = _csv_frame(data.decode("utf-8"))
    if tuple(frame.columns) != OPERATIONAL_COLUMNS:
        raise ValueError("Cabecera operacional FIRMS no canónica")
    projected = project_frame(frame)
    if serialize(projected) != data:
        raise ValueError("Serialización operacional FIRMS no canónica")
    return projected
