"""Contrato de lectura del Centro de Control: respuesta del bridge → vista validada.

Un solo adaptador canónico alimenta el panel y la vista previa de alerta:

    respuesta de GET /score (GridScoreResult serializado por tools/n8n_bridge)
      → `canonical_result`  (lista blanca, forma del bridge, sin campos extra)
      ├─ validación de presentación de este módulo
      └─ `src.notifications.alert_payload.build_alert` (misma entrada canónica)
      → `DashboardView` (celdas del panel + `AlertPreview`)

Si cualquiera de las dos validaciones rechaza el resultado, el estado es
INVALID_RESULT para ambos: nunca hay un panel "válido" con una alerta que diga
otra cosa. El rank, el cell_id y el score del backend no se tocan ni se reordenan.

Máquina de estados (exactamente uno por vista):

    DEMO · LOADING · LIVE_READY · DATA_UNAVAILABLE · PROTOTYPE_UNAVAILABLE
    · INVALID_RESULT · NETWORK_ERROR

DEMO solo sale de `load_demo()` (fixture local explícita). Una respuesta en vivo
con marca sintética es INVALID_RESULT: el modo demo nunca se activa solo. Los
mensajes de error upstream no se muestran nunca (solo se extraen de ellos, por
patrón estricto, la fecha y el desfase FIRMS cuando el servicio bloquea).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.parse import urlsplit

from src.geo.grid import COLS, ROWS, all_cells

DEMO, LOADING, LIVE_READY = "DEMO", "LOADING", "LIVE_READY"
DATA_UNAVAILABLE, PROTOTYPE_UNAVAILABLE = "DATA_UNAVAILABLE", "PROTOTYPE_UNAVAILABLE"
INVALID_RESULT, NETWORK_ERROR = "INVALID_RESULT", "NETWORK_ERROR"
STATES = (
    DEMO,
    LOADING,
    LIVE_READY,
    DATA_UNAVAILABLE,
    PROTOTYPE_UNAVAILABLE,
    INVALID_RESULT,
    NETWORK_ERROR,
)

# Modo de la vista (qué se pidió), distinto del estado (qué se obtuvo).
MODE_DEMO, MODE_LIVE = "DEMO", "LIVE"
# Conexión en vivo, medida SOLO en la última consulta (no es un estado permanente).
CONN_CONNECTED, CONN_UNAVAILABLE, CONN_INVALID = (
    "CONNECTED",
    "UNAVAILABLE",
    "INVALID_RESPONSE",
)

DEMO_FIXTURE = (
    Path(__file__).resolve().parent.parent / "data" / "demo_score_synthetic.json"
)
GRID = {c["cell_id"]: c for c in all_cells()}  # geometría oficial (src/geo/grid.py)
EXPECTED_CELL_IDS = tuple(GRID)
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
_GEOMETRY_KEYS = ("min_lon", "min_lat", "max_lon", "max_lat")
_GEOMETRY_TOLERANCE = 1e-4  # grados; el bridge redondea a 4-5 decimales
# Mensaje de `classify_firms_lag` cuando FIRMS supera el desfase máximo upstream
# (prototype_service.FIRMS_LAG_MAX_DAYS). Solo se extraen fecha y número.
_FIRMS_BLOCKED_MSG = re.compile(
    r"El histórico FIRMS termina el (\d{4}-\d{2}-\d{2}), (\d{1,4}) días antes"
)

# Campos de primer nivel que el adaptador copia (forma de tools/n8n_bridge/app.py).
_TOP_LEVEL = (
    "status",
    "model_version",
    "model_status",
    "forecast_time",
    "horizon_hours",
    "station_id",
    "station_name",
    "weather_timestamp",
    "age_hours",
    "freshness",
    "firms_origin",
    "firms_coverage_end",
    "firms_lag_days",
    "firms_status",
    "inputs_fingerprint",
)
_CELL_FIELDS = ("cell_id", "score", "rank", "display_rank", "tie_group_size")


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
class AlertPreview:
    """Lo que SAPI generaría como notificación. Nunca se envía desde el panel."""

    status: str  # READY | UNAVAILABLE | INVALID (vocabulario de alert_payload)
    text: str
    fingerprint: Optional[str] = None
    scoring_time: Optional[str] = None
    firms_coverage_end: Optional[str] = None
    top: tuple[tuple[int, int, str, float], ...] = ()  # (rank, display_rank, id, score)


@dataclass(frozen=True)
class DashboardView:
    state: str
    mode: str = MODE_LIVE
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
    alert: Optional[AlertPreview] = None
    fetched_at: Optional[str] = None  # hora de la consulta de VISTA (UTC ISO)
    endpoint: Optional[str] = None  # host:puerto/ruta, sin credenciales ni query

    @property
    def top(self) -> tuple[Cell, ...]:
        return self.cells[:TOP_N]

    @property
    def has_ranking(self) -> bool:
        return self.state in (LIVE_READY, DEMO) and len(self.cells) == len(
            EXPECTED_CELL_IDS
        )

    @property
    def firms_warning(self) -> bool:
        return self.has_ranking and self.firms.get("status") == FIRMS_STALE

    @property
    def alert_text(self) -> Optional[str]:
        return self.alert.text if self.alert else None

    @property
    def connection(self) -> Optional[str]:
        """Resultado de la última consulta en vivo; None en demo."""
        if self.mode != MODE_LIVE or self.state == LOADING:
            return None
        if self.state == NETWORK_ERROR:
            return CONN_UNAVAILABLE
        if self.state == INVALID_RESULT:
            return CONN_INVALID
        return CONN_CONNECTED  # el servicio respondió según contrato

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


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_endpoint(url: str) -> str:
    """host:puerto/ruta para mostrar; nunca usuario, clave, query ni fragmento."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or "?"
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return "endpoint inválido"
    return f"{host}{port}{parts.path}"


# ── Adaptador canónico ─────────────────────────────────────────────────────────
def canonical_result(data: Mapping) -> dict:
    """Respuesta del bridge → dict con SOLO los campos de la lista blanca.

    Es la única entrada tanto del panel como de `build_alert`. No cambia
    valores: copia rank, display_rank, tie_group_size, cell_id y score tal
    como vienen (y la geometría, si viene, para contrastarla con la grilla).
    """
    out = {k: data[k] for k in _TOP_LEVEL if k in data}
    meteo = data.get("meteo_actual")
    if isinstance(meteo, Mapping):
        out["meteo_actual"] = {
            k: meteo[k]
            for k in ("temperatura", "humedad_relativa", "velocidad_viento_kmh")
            if k in meteo
        }
    cells = data.get("cells")
    if isinstance(cells, list):
        canon = []
        for c in cells:
            if not isinstance(c, Mapping):
                canon.append(c)  # la validación lo rechaza
                continue
            cell = {k: c[k] for k in _CELL_FIELDS if k in c}
            geometry = c.get("geometry")
            if isinstance(geometry, Mapping):
                cell["geometry"] = {k: geometry.get(k) for k in _GEOMETRY_KEYS}
            canon.append(cell)
        out["cells"] = canon
    elif "cells" in data:
        out["cells"] = cells
    return out


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


def _geometry_matches_grid(c: Mapping) -> bool:
    g = c.get("geometry")
    if g is None:
        return True  # opcional: el mapa usa siempre la grilla oficial
    ref = GRID[c["cell_id"]]
    return all(
        _is_finite(g.get(k)) and abs(g[k] - ref[k]) <= _GEOMETRY_TOLERANCE
        for k in _GEOMETRY_KEYS
    )


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
        elif not _geometry_matches_grid(c):
            r.append("geometry_mismatch_with_grid")
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


def build_alert_preview(canonical: Mapping) -> tuple[Optional[AlertPreview], list[str]]:
    """(vista previa, motivos de rechazo de alert_payload). Nunca envía nada."""
    from src.notifications.alert_payload import build_alert, render_text

    try:
        payload = build_alert(canonical)
        text = render_text(payload)
    except Exception:  # noqa: BLE001 -- una plantilla rota nunca rompe el panel
        return None, ["alert_render_failed"]
    top = tuple(
        (c["rank"], c["display_rank"], c["cell_id"], c["score"])
        for c in payload.get("top_cells", [])
    )
    firms = payload.get("firms") or {}
    preview = AlertPreview(
        status=payload["status"],
        text=text,
        fingerprint=payload.get("alert_fingerprint"),
        scoring_time=payload.get("scoring_time"),
        firms_coverage_end=firms.get("coverage_end"),
        top=top,
    )
    return preview, list(payload.get("reasons") or [])


def _from_error(data: Mapping, base: dict) -> DashboardView:
    kind = data.get("error_type")
    canonical = {"status": "error", "error_type": kind}
    if kind == "data_unavailable":
        alert, _ = build_alert_preview(canonical)
        return DashboardView(DATA_UNAVAILABLE, reasons=(kind,), alert=alert, **base)
    if kind not in ("prototype_unavailable", "internal_error"):
        return DashboardView(INVALID_RESULT, reasons=("unknown_error_type",), **base)
    alert, _ = build_alert_preview(canonical)
    match = _FIRMS_BLOCKED_MSG.search(str(data.get("message", "")))
    if kind == "prototype_unavailable" and match:
        return DashboardView(
            PROTOTYPE_UNAVAILABLE,
            reasons=(kind, "firms_lag_exceeds_upstream_max"),
            firms={"coverage_end": match.group(1), "lag_days": int(match.group(2))},
            firms_blocked=True,
            alert=alert,
            **base,
        )
    return DashboardView(PROTOTYPE_UNAVAILABLE, reasons=(kind,), alert=alert, **base)


def from_payload(
    data: Any,
    *,
    demo: bool = False,
    fetched_at: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> DashboardView:
    """Respuesta del bridge (éxito o error) → vista.

    `demo=True` solo lo usa `load_demo()` para la fixture local explícita.
    """
    base = {
        "mode": MODE_DEMO if demo else MODE_LIVE,
        "fetched_at": fetched_at,
        "endpoint": endpoint,
    }
    if not isinstance(data, Mapping):
        return DashboardView(INVALID_RESULT, reasons=("response_not_object",), **base)
    if not data:
        return DashboardView(INVALID_RESULT, reasons=("empty_response",), **base)
    marked = "_synthetic" in data
    if marked != demo:
        # Nunca datos sintéticos por la vía en vivo, ni fixture sin su marca.
        reason = (
            "synthetic_marker_in_live_response" if marked else "demo_marker_missing"
        )
        return DashboardView(INVALID_RESULT, reasons=(reason,), **base)
    if data.get("status") == "error":
        return _from_error(data, base)

    canonical = canonical_result(data)
    reasons = validate(canonical)
    alert, alert_reasons = build_alert_preview(canonical)
    if alert is None or alert.status != "READY":
        reasons += [f"alert:{r}" for r in alert_reasons] or ["alert:not_ready"]
    if reasons:
        return DashboardView(
            INVALID_RESULT, reasons=tuple(sorted(set(reasons))), synthetic=demo, **base
        )
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
        for c in sorted(canonical["cells"], key=lambda c: c["rank"])
    )
    assert alert is not None
    dashboard_top = tuple(
        (c.rank, c.display_rank, c.cell_id, c.score) for c in cells[:TOP_N]
    )
    if alert.top != dashboard_top:  # defensa: ambas salidas deben ser el mismo ranking
        return DashboardView(
            INVALID_RESULT,
            reasons=("alert_dashboard_mismatch",),
            synthetic=demo,
            **base,
        )
    return DashboardView(
        state=DEMO if demo else LIVE_READY,
        cells=cells,
        scoring_time=canonical["forecast_time"],
        inputs_fingerprint=canonical["inputs_fingerprint"],
        firms={
            k: canonical[f"firms_{k}"]
            for k in ("origin", "coverage_end", "lag_days", "status")
        },
        model_version=canonical.get("model_version"),
        model_status=canonical.get("model_status"),
        meteo_freshness=canonical.get("freshness"),
        synthetic=demo,
        dmc=_dmc(canonical),
        identity=_identity(data),
        alert=alert,
        **base,
    )


def load_demo() -> DashboardView:
    """Única entrada al modo DEMO: la fixture local marcada como sintética."""
    data = json.loads(DEMO_FIXTURE.read_text(encoding="utf-8"))
    return from_payload(data, demo=True, fetched_at=now_utc_iso())


def fetch_live(
    url: str, *, timeout: tuple[float, float] = (3.0, 90.0), session=None
) -> DashboardView:
    """Solo GET de lectura al endpoint de score. Nunca POST/PUT/DELETE."""
    import requests

    http = session or requests
    base = {"fetched_at": now_utc_iso(), "endpoint": safe_endpoint(url)}
    try:
        response = http.get(
            url, timeout=timeout, headers={"Accept": "application/json"}
        )
    except requests.Timeout:
        return DashboardView(NETWORK_ERROR, reasons=("timeout",), **base)
    except requests.RequestException:
        return DashboardView(NETWORK_ERROR, reasons=("connection_failed",), **base)
    if getattr(response, "content", None) == b"":
        return DashboardView(INVALID_RESULT, reasons=("empty_response",), **base)
    try:
        data = response.json()
    except ValueError:
        return DashboardView(INVALID_RESULT, reasons=("response_not_json",), **base)
    if response.status_code == 200:
        return from_payload(data, **base)
    is_error_body = isinstance(data, Mapping) and data.get("status") == "error"
    if response.status_code in (500, 503) and is_error_body:
        return from_payload(data, **base)
    return DashboardView(
        INVALID_RESULT, reasons=(f"http_{response.status_code}",), **base
    )


GRID_SHAPE = (ROWS, COLS)
