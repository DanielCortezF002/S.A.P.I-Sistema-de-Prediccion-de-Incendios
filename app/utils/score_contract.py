"""Contrato de lectura del Centro de Control: respuesta del bridge → estado de vista.

Puro (sin Streamlit ni red, salvo `fetch_live`, que solo hace GET). Consume el
mismo contrato que expone `tools/n8n_bridge/app.py` en `GET /score`; no calcula
ni reordena scores. Toda respuesta termina en exactamente uno de estos estados:

    READY · DEMO · DATA_UNAVAILABLE · PROTOTYPE_UNAVAILABLE · INVALID · NETWORK_ERROR
    (LOADING lo maneja la página mientras espera)

Nunca se muestra un ranking parcial: si algo del contrato falla, el estado
es INVALID y no hay celdas. Solo se copian campos de una lista blanca; los
mensajes de error upstream no se muestran nunca (solo se extraen de ellos,
por patrón estricto, la fecha y el desfase FIRMS cuando el servicio bloquea).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional

from src.geo.grid import COLS, ROWS, all_cells

LOADING, READY, DEMO = "LOADING", "READY", "DEMO"
DATA_UNAVAILABLE, PROTOTYPE_UNAVAILABLE = "DATA_UNAVAILABLE", "PROTOTYPE_UNAVAILABLE"
INVALID, NETWORK_ERROR = "INVALID", "NETWORK_ERROR"
STATES = (
    LOADING,
    READY,
    DEMO,
    DATA_UNAVAILABLE,
    PROTOTYPE_UNAVAILABLE,
    INVALID,
    NETWORK_ERROR,
)

DEMO_FIXTURE = (
    Path(__file__).resolve().parent.parent / "data" / "demo_score_synthetic.json"
)
EXPECTED_CELL_IDS = tuple(c["cell_id"] for c in all_cells())
TOP_N = 5  # mismo corte "Top-5" documentado en src/inference/prototype_service.py

# Valores que hoy emite SAPI (prototype_service / firms_source); se presentan,
# no se reinterpretan: el panel no decide frescura ni define umbrales.
FIRMS_CURRENT, FIRMS_STALE = "FIRMS AL DÍA", "FIRMS DESACTUALIZADO"
FIRMS_STATUSES = (FIRMS_CURRENT, FIRMS_STALE)
FIRMS_ORIGINS = ("current", "baseline", "reproducibility")
METEO_RECENT = "DATOS RECIENTES"
METEO_FRESHNESS = (
    METEO_RECENT,
    "DATOS CON RETRASO",
    "DATOS HISTÓRICOS / DESACTUALIZADOS",
)

# Estado de cada insumo en el panel "Estado de datos" (texto + símbolo, nunca solo color).
SRC_CURRENT, SRC_AVAILABLE, SRC_WARNING = "CURRENT", "AVAILABLE", "WARNING"
SRC_BLOCKED, SRC_UNAVAILABLE, SRC_UNKNOWN = "BLOCKED", "UNAVAILABLE", "UNKNOWN"
SOURCES: tuple[str, ...] = ("FIRMS", "DMC", "TOPOGRAFÍA", "MODELO")

_HEX64 = re.compile(r"[0-9a-f]{64}")
_ISO_TZ = re.compile(r"\d{4}-\d{2}-\d{2}T[0-9:.]+(Z|[+-]\d{2}:\d{2})")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_LABEL = re.compile(r"[A-Za-z0-9 ._/()ÁÉÍÓÚÑáéíóúñ-]{1,64}")
_STATION_ID = re.compile(r"[0-9]{1,12}")
# Mensaje de `classify_firms_lag` cuando FIRMS supera el desfase máximo upstream
# (prototype_service.FIRMS_LAG_MAX_DAYS). Solo se extraen fecha y número.
_FIRMS_BLOCKED_MSG = re.compile(
    r"El histórico FIRMS termina el (\d{4}-\d{2}-\d{2}), (\d{1,4}) días antes"
)


@dataclass(frozen=True)
class Cell:
    rank: int
    display_rank: int
    tie_group_size: int
    cell_id: str
    score: float
    grid_row: int  # 0 = sur (fila de la grilla de src.geo.grid)
    grid_col: int  # 0 = oeste


@dataclass(frozen=True)
class DashboardView:
    state: str
    cells: tuple[Cell, ...] = ()
    scoring_time: Optional[str] = None
    inputs_fingerprint: Optional[str] = None
    firms: Mapping[str, Any] = field(default_factory=dict)
    model_version: Optional[str] = None
    model_status: Optional[str] = None
    meteo_freshness: Optional[str] = None
    reasons: tuple[str, ...] = ()
    synthetic: bool = False
    dmc: Mapping[str, Any] = field(default_factory=dict)
    identity: Mapping[str, str] = field(default_factory=dict)
    firms_blocked: bool = False
    alert_text: Optional[str] = None

    @property
    def top(self) -> tuple[Cell, ...]:
        return self.cells[:TOP_N]

    @property
    def has_ranking(self) -> bool:
        return self.state in (READY, DEMO) and len(self.cells) == len(EXPECTED_CELL_IDS)

    @property
    def firms_warning(self) -> bool:
        return self.has_ranking and self.firms.get("status") == FIRMS_STALE

    def source_status(self) -> dict[str, str]:
        """Estado FIRMS / DMC / TOPOGRAFÍA / MODELO con semántica upstream."""
        if self.has_ranking:
            firms = (
                SRC_CURRENT
                if self.firms.get("status") == FIRMS_CURRENT
                else SRC_WARNING
            )
            fresh = self.dmc.get("freshness")
            if fresh is None:
                dmc = SRC_UNKNOWN
            else:
                dmc = SRC_CURRENT if fresh == METEO_RECENT else SRC_WARNING
            # Un ranking válido implica que el servicio cargó topografía y modelo.
            return {
                "FIRMS": firms,
                "DMC": dmc,
                "TOPOGRAFÍA": SRC_AVAILABLE,
                "MODELO": SRC_AVAILABLE,
            }
        if self.state == NETWORK_ERROR:
            return dict.fromkeys(SOURCES, SRC_UNAVAILABLE)
        out = dict.fromkeys(SOURCES, SRC_UNKNOWN)
        if self.firms_blocked:
            out["FIRMS"] = SRC_BLOCKED
        return out


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_iso(v) -> bool:
    if not (isinstance(v, str) and _ISO_TZ.fullmatch(v)):
        return False
    try:
        datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _grid_position(cell_id: str) -> tuple[int, int]:
    index = int(cell_id.split("-")[1]) - 1
    return index // COLS, index % COLS


def _validate_metadata(data: Mapping) -> list[str]:
    r: list[str] = []
    if data.get("status") != "ok":
        r.append("unexpected_status")
    if not _is_iso(data.get("forecast_time")):
        r.append("missing_or_invalid_scoring_time")
    fp = data.get("inputs_fingerprint")
    if not (isinstance(fp, str) and _HEX64.fullmatch(fp)):
        r.append("missing_or_invalid_inputs_fingerprint")
    if data.get("firms_origin") not in FIRMS_ORIGINS:
        r.append("invalid_firms_origin")
    if data.get("firms_status") not in FIRMS_STATUSES:
        r.append("invalid_firms_status")
    if not _is_int(data.get("firms_lag_days")):
        r.append("invalid_firms_lag_days")
    end = data.get("firms_coverage_end")
    if not (isinstance(end, str) and _ISO_DATE.fullmatch(end)):
        r.append("invalid_firms_coverage_end")
    for key in ("model_version", "model_status", "station_name"):
        value = data.get(key)
        if value is not None and not (
            isinstance(value, str) and _LABEL.fullmatch(value)
        ):
            r.append(f"invalid_{key}")
    if data.get("freshness") is not None and data["freshness"] not in METEO_FRESHNESS:
        r.append("invalid_freshness")
    station = data.get("station_id")
    if station is not None and not (
        isinstance(station, str) and _STATION_ID.fullmatch(station)
    ):
        r.append("invalid_station_id")
    if data.get("weather_timestamp") is not None and not _is_iso(
        data["weather_timestamp"]
    ):
        r.append("invalid_weather_timestamp")
    for key in ("age_hours", "horizon_hours"):
        if data.get(key) is not None and not _is_finite(data[key]):
            r.append(f"invalid_{key}")
    return r


def validate(data: Mapping) -> list[str]:
    """Motivos de rechazo (vacío = apto). Validación de presentación: lo mínimo
    para no mostrar un ranking engañoso (no replica la del backend)."""
    r = _validate_metadata(data)
    cells = data.get("cells")
    if not isinstance(cells, list) or not cells:
        return sorted(set(r + ["missing_cells"]))
    if len(cells) != len(EXPECTED_CELL_IDS):
        r.append("wrong_cell_count")
    for c in cells:
        if not isinstance(c, Mapping):
            r.append("invalid_cell")
            continue
        s = c.get("score")
        if not (_is_finite(s) and 0 <= s <= 1):
            r.append("invalid_score")
        if c.get("cell_id") not in EXPECTED_CELL_IDS:
            r.append("unknown_cell_id")
        for key in ("rank", "display_rank", "tie_group_size"):
            if not (_is_int(c.get(key)) and c[key] >= 1):
                r.append(f"invalid_{key}")
    if r:
        return sorted(set(r))
    ids, ranks = [c["cell_id"] for c in cells], [c["rank"] for c in cells]
    if len(set(ids)) != len(ids):
        r.append("duplicate_cell_id")
    if len(set(ranks)) != len(ranks):
        r.append("duplicate_rank")
    if sorted(ranks) != list(range(1, len(ranks) + 1)):
        r.append("rank_not_1_to_n")
    if r:
        return sorted(set(r))
    by_rank = sorted(cells, key=lambda c: c["rank"])
    if any(a["score"] < b["score"] for a, b in zip(by_rank, by_rank[1:])):
        r.append("rank_order_violation")
    scores = [c["score"] for c in cells]
    if any(
        c["display_rank"] != 1 + sum(s > c["score"] for s in scores)
        or c["tie_group_size"] != scores.count(c["score"])
        for c in cells
    ):
        r.append("tie_metadata_inconsistent")
    return sorted(set(r))


def _dmc(data: Mapping) -> dict[str, Any]:
    """Metadatos DMC seguros ya validados (estación, observación, frescura)."""
    keys = ("station_id", "station_name", "weather_timestamp", "age_hours", "freshness")
    out: dict[str, Any] = {k: data[k] for k in keys if data.get(k) is not None}
    meteo = data.get("meteo_actual")
    if isinstance(meteo, Mapping):
        for key in ("temperatura", "humedad_relativa", "velocidad_viento_kmh"):
            if _is_finite(meteo.get(key)):
                out[key] = float(meteo[key])
    return out


# nombre → (sección de scoring_inputs, clave, patrón; None = fecha ISO con zona)
_IDENTITY_FIELDS = {
    "model_sha256": ("model", "sha256", _HEX64),
    "firms_sha256": ("firms", "sha256", _HEX64),
    "firms_pointer_version": ("firms", "pointer_version", _LABEL),
    "dmc_manifest_sha256": ("dmc", "manifest_sha256", _HEX64),
    "dmc_coverage_end": ("dmc", "coverage_end", None),
    "dmc_pointer_version": ("dmc", "pointer_version", _LABEL),
    "topography_origin": ("topography", "origin", _LABEL),
    "topography_sha256": ("topography", "sha256", _HEX64),
}


def _identity(data: Mapping) -> dict[str, str]:
    """Identidades opcionales de `scoring_inputs` (manifest de ScoringInputs).

    El bridge actual no las serializa: si no vienen, el panel dice
    "NO DISPONIBLE EN RESPUESTA". Solo se aceptan hashes hex de 64, fechas ISO
    y etiquetas cortas; cualquier otro valor se ignora campo a campo.
    """
    si = data.get("scoring_inputs")
    if not isinstance(si, Mapping):
        return {}
    out: dict[str, str] = {}
    for name, (section, key, pattern) in _IDENTITY_FIELDS.items():
        block = si.get(section)
        value = block.get(key) if isinstance(block, Mapping) else None
        if pattern is None:
            ok = _is_iso(value)
        else:
            ok = isinstance(value, str) and bool(pattern.fullmatch(value))
        if ok:
            out[name] = str(value)
    return out


def _alert_text(data: Any) -> Optional[str]:
    """Texto de la alerta que SAPI generaría (módulo puro, nunca envía)."""
    try:
        from src.notifications.alert_payload import build_alert, render_text

        return render_text(build_alert(data))
    except Exception:  # noqa: BLE001 -- la vista previa nunca rompe el panel
        return None


def _from_error(data: Mapping) -> DashboardView:
    kind = data.get("error_type")
    alert = _alert_text(data)
    if kind == "data_unavailable":
        return DashboardView(DATA_UNAVAILABLE, reasons=(kind,), alert_text=alert)
    if kind not in ("prototype_unavailable", "internal_error"):
        return DashboardView(INVALID, reasons=("unknown_error_type",))
    match = _FIRMS_BLOCKED_MSG.search(str(data.get("message", "")))
    if kind == "prototype_unavailable" and match:
        return DashboardView(
            PROTOTYPE_UNAVAILABLE,
            reasons=(kind, "firms_lag_exceeds_upstream_max"),
            firms={"coverage_end": match.group(1), "lag_days": int(match.group(2))},
            firms_blocked=True,
            alert_text=alert,
        )
    return DashboardView(PROTOTYPE_UNAVAILABLE, reasons=(kind,), alert_text=alert)


def from_payload(data: Any, *, demo: bool = False) -> DashboardView:
    """Respuesta del bridge (éxito o error) → vista. `demo=True` solo para la fixture local."""
    if not isinstance(data, Mapping):
        return DashboardView(INVALID, reasons=("response_not_object",))
    if not data:
        return DashboardView(INVALID, reasons=("empty_response",))
    synthetic = demo or "_synthetic" in data
    if data.get("status") == "error":
        return _from_error(data)
    reasons = validate(data)
    if reasons:
        return DashboardView(INVALID, reasons=tuple(reasons), synthetic=synthetic)
    cells = tuple(
        Cell(
            c["rank"],
            c["display_rank"],
            c["tie_group_size"],
            c["cell_id"],
            float(c["score"]),
            *_grid_position(c["cell_id"]),
        )
        # orden del backend, sin re-rankear
        for c in sorted(data["cells"], key=lambda c: c["rank"])
    )
    return DashboardView(
        state=DEMO if synthetic else READY,
        cells=cells,
        scoring_time=data["forecast_time"],
        inputs_fingerprint=data["inputs_fingerprint"],
        firms={
            k: data[f"firms_{k}"]
            for k in ("origin", "coverage_end", "lag_days", "status")
        },
        model_version=data.get("model_version"),
        model_status=data.get("model_status"),
        meteo_freshness=data.get("freshness"),
        synthetic=synthetic,
        dmc=_dmc(data),
        identity=_identity(data),
        alert_text=_alert_text(data),
    )


def load_demo() -> DashboardView:
    return from_payload(json.loads(DEMO_FIXTURE.read_text(encoding="utf-8")), demo=True)


def fetch_live(
    url: str, *, timeout: tuple[float, float] = (3.0, 90.0), session=None
) -> DashboardView:
    """Solo GET de lectura al endpoint de score. Nunca POST/PUT/DELETE."""
    import requests

    http = session or requests
    try:
        response = http.get(
            url, timeout=timeout, headers={"Accept": "application/json"}
        )
    except requests.Timeout:
        return DashboardView(NETWORK_ERROR, reasons=("timeout",))
    except requests.RequestException:
        return DashboardView(NETWORK_ERROR, reasons=("connection_failed",))
    if getattr(response, "content", None) == b"":
        return DashboardView(INVALID, reasons=("empty_response",))
    try:
        data = response.json()
    except ValueError:
        return DashboardView(INVALID, reasons=("response_not_json",))
    if response.status_code == 200:
        return from_payload(data)
    is_error_body = isinstance(data, Mapping) and data.get("status") == "error"
    if response.status_code in (500, 503) and is_error_body:
        return from_payload(data)
    return DashboardView(INVALID, reasons=(f"http_{response.status_code}",))


GRID_SHAPE = (ROWS, COLS)
