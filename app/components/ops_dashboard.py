"""Render HTML del Centro de Control de solo lectura (sin Streamlit, testeable).

Usa los tokens de `app/theme/tokens.py` (variables `--sapi-*` del stylesheet
existente, Public Sans y el navy institucional). **No usa el semáforo de
riesgo:** sus niveles traen umbrales en porcentaje, y este panel presenta
solo prioridad relativa. El acento codifica el score relativo, nunca una
probabilidad. Todo estado se comunica con texto + símbolo, no solo color.

Todo valor dinámico pasa por `html.escape`. Solo se leen campos ya validados
de `DashboardView`. La geometría del mapa es la grilla oficial
(`src.geo.grid.all_cells`), no la que venga en la respuesta.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from html import escape

from app.theme import tokens as t
from app.utils.cell_zones import ZONE_LABELS, zone_for_col
from app.utils.score_contract import (
    DATA_UNAVAILABLE,
    DEMO,
    EXPECTED_CELL_IDS,
    FIRMS_STALE,
    CONN_CONNECTED,
    CONN_INVALID,
    CONN_UNAVAILABLE,
    GRID_SHAPE,
    INVALID_RESULT,
    LIVE_READY,
    MODE_DEMO,
    MODE_REPLAY,
    NETWORK_ERROR,
    PROTOTYPE_UNAVAILABLE,
    REPLAY_READY,
    SRC_AVAILABLE,
    SRC_BLOCKED,
    SRC_CURRENT,
    SRC_UNAVAILABLE,
    SRC_UNKNOWN,
    SRC_WARNING,
    TOP_N,
    Cell,
    DashboardView,
)
from src.geo.grid import all_cells

CLARIFICATION = (
    "El score representa prioridad relativa dentro de las celdas evaluadas. "
    "No corresponde a una probabilidad calibrada ni confirma la existencia de un incendio."
)
FIRMS_NOTE = "FIRMS reporta anomalías térmicas satelitales."
NOT_IN_RESPONSE = "NO DISPONIBLE EN RESPUESTA"
NO_RANKING_NOTE = "La ausencia de ranking no indica que la situación sea segura."
FORBIDDEN_PHRASES = (
    "probabilidad de incendio",
    "% de probabilidad",
    "incendio confirmado",
    "incendio detectado",
    "predicción segura",
    "riesgo bajo",
    "sin incendios",
    "todo normal",
    "enviar alerta",
)
LIMITATIONS = (
    "Ranking exploratorio de prioridad relativa (Modelo D, prototipo). El score no es una "
    "probabilidad calibrada y solo compara las 50 celdas de esta evaluación entre sí.",
    "FIRMS reporta anomalías térmicas satelitales; no confirma la existencia de un incendio.",
    "La validación disponible es histórica; no existe validación operacional point-in-time "
    "con datos FIRMS NRT.",
    "Este panel es de solo lectura: no actualiza fuentes, no publica resultados y no envía "
    "notificaciones.",
)

# Estado del sistema: (etiqueta, explicación, tono). Vocabulario cerrado; nunca
# "seguro", "sin incendios" ni niveles de riesgo.
STATE_COPY: dict[str, tuple[str, str, str]] = {
    LIVE_READY: (
        "OPERATIVO",
        "Ranking vigente de la última evaluación del servicio de score.",
        "ok",
    ),
    REPLAY_READY: (
        "REPLAY",
        "Reproducción verificada de una corrida aceptada y capturada. No es una consulta "
        "en vivo: muestra exactamente el resultado capturado.",
        "replay",
    ),
    DEMO: (
        "DEMO",
        "Ranking sintético para presentación. No es una evaluación del modelo.",
        "demo",
    ),
    DATA_UNAVAILABLE: (
        "DATOS NO DISPONIBLES",
        "No hay datos suficientes para generar la evaluación actual: un insumo "
        "(meteorología DMC o FIRMS) no está disponible o es ilegible. "
        f"{NO_RANKING_NOTE}",
        "warn",
    ),
    PROTOTYPE_UNAVAILABLE: (
        "EVALUACIÓN NO DISPONIBLE",
        "El servicio de evaluación no está disponible: respondió, pero no pudo generar "
        "el ranking. No se muestra ningún resultado anterior ni estimado. "
        f"{NO_RANKING_NOTE}",
        "warn",
    ),
    INVALID_RESULT: (
        "RESULTADO INVÁLIDO",
        "La respuesta del servicio no cumple el contrato esperado y se descartó completa. "
        "No se muestran celdas para evitar un ranking engañoso.",
        "error",
    ),
    NETWORK_ERROR: (
        "SERVICIO NO DISPONIBLE",
        "No fue posible consultar el servicio SAPI. Revise que el bridge esté en "
        f"ejecución y vuelva a actualizar la vista. {NO_RANKING_NOTE}",
        "error",
    ),
}
_TIMEOUT_TEXT = (
    "No fue posible consultar el servicio SAPI: no respondió dentro del tiempo de espera. "
    f"No se muestra ningún resultado. {NO_RANKING_NOTE}"
)
_FIRMS_BLOCKED_TEXT = (
    "El servicio no generó el ranking porque el histórico FIRMS supera el desfase "
    f"máximo que SAPI acepta para puntuar. {NO_RANKING_NOTE}"
)

# Conexión en vivo (solo la última consulta) → (texto, tono)
CONNECTION_COPY: dict[str, tuple[str, str]] = {
    CONN_CONNECTED: ("CONECTADO", "ok"),
    CONN_UNAVAILABLE: ("NO DISPONIBLE", "error"),
    CONN_INVALID: ("RESPUESTA INVÁLIDA", "error"),
}
# Identidad única: ops/n8n/policy.js usa (y verifica) este mismo alert fingerprint.
N8N_IDENTITY_NOTE = (
    "notification_identity de n8n = alert fingerprint (misma receta, verificada)"
)

# Estado de fuente → (símbolo, texto, tono)
SOURCE_BADGE: dict[str, tuple[str, str, str]] = {
    SRC_CURRENT: ("✓", "AL DÍA", "ok"),
    SRC_AVAILABLE: ("●", "DISPONIBLE", "ok"),
    SRC_WARNING: ("▲", "CON AVISO", "warn"),
    SRC_BLOCKED: ("■", "BLOQUEADO", "error"),
    SRC_UNAVAILABLE: ("✕", "NO DISPONIBLE", "error"),
    SRC_UNKNOWN: ("?", "DESCONOCIDO", "muted"),
}

# Colores propios del panel (fuera del semáforo a propósito).
_DEMO_FILL, _DEMO_STRIPE, _DEMO_TEXT = "#f4e6bd", "#ead7a0", "#4a3700"
_WARN_FILL, _WARN_TEXT = "#fbeed9", "#5e3500"
_ERR_FILL, _ERR_TEXT = "#f9e2de", "#6e1a10"
_OK_FILL, _OK_TEXT = "#e3eef8", "#173a5e"
_REPLAY_FILL, _REPLAY_TEXT = "#e6e1f3", "#34245e"


def dashboard_css() -> str:
    return f"""
<style>
  .sapi-ops {{ --ops-navy: {t.SURFACE_SIDEBAR}; --ops-on-navy: {t.TEXT_ON_SIDEBAR};
    --ops-on-navy-muted: {t.TEXT_ON_SIDEBAR_MUTED}; --ops-rule: {t.SIDEBAR_RULE};
    --ops-hair: var(--sapi-border-subtle); font-family: {t.FONT_STACK};
    color: var(--sapi-text-primary); font-variant-numeric: tabular-nums; }}
  .sapi-ops :focus-visible {{ outline: 2px solid var(--sapi-accent); outline-offset: 2px; }}
  .ops-band {{ background: var(--ops-navy); color: var(--ops-on-navy);
    border-radius: var(--sapi-radius-banner); padding: 16px 20px 14px;
    box-shadow: 0 6px 18px -10px rgba(16,28,42,.55); }}
  .ops-band--demo {{ border: 4px dashed {_DEMO_FILL}; }}
  .ops-band--replay {{ border: 4px double {_REPLAY_FILL}; }}
  .ops-pill--replay {{ color: {_REPLAY_TEXT}; background: {_REPLAY_FILL};
    border-color: {_REPLAY_TEXT}; }}
  .ops-chip.ops-chip--replay {{ background: {_REPLAY_FILL}; color: {_REPLAY_TEXT};
    border-color: {_REPLAY_TEXT}; font-weight: 800; letter-spacing: .06em; }}
  .ops-band__top {{ display: flex; flex-wrap: wrap; align-items: center;
    justify-content: space-between; gap: 8px 16px; }}
  .sapi-ops .ops-band h1 {{ margin: 0 !important; padding: 0 !important; font-size: 22px !important;
    line-height: 28px !important; font-weight: 700 !important; color: var(--ops-on-navy) !important;
    letter-spacing: -0.01em; }}
  .sapi-ops .ops-band h1 span {{ font-weight: 500; color: var(--ops-on-navy-muted) !important; }}
  .ops-status {{ display: flex; align-items: center; gap: 10px; }}
  .ops-status__label {{ font-size: 11px; font-weight: 600; letter-spacing: .08em;
    text-transform: uppercase; color: var(--ops-on-navy-muted); }}
  .ops-pill {{ display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px;
    border-radius: 999px; font-size: 15px; font-weight: 800; letter-spacing: .05em;
    border: 1px solid currentColor; }}
  .ops-pill--ok {{ color: {_OK_TEXT}; background: {_OK_FILL}; border-color: {_OK_FILL}; }}
  .ops-pill--demo {{ color: {_DEMO_TEXT}; background: {_DEMO_FILL}; border-color: {_DEMO_TEXT}; }}
  .ops-pill--warn {{ color: {_WARN_TEXT}; background: {_WARN_FILL}; border-color: {_WARN_FILL}; }}
  .ops-pill--error {{ color: {_ERR_TEXT}; background: {_ERR_FILL}; border-color: {_ERR_FILL}; }}
  .ops-meta {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 10px 20px; margin: 14px 0 0; padding: 12px 0 0; border-top: 1px solid var(--ops-rule); }}
  .ops-meta dt {{ font-size: 11px; line-height: 15px; font-weight: 600; letter-spacing: .06em;
    text-transform: uppercase; color: var(--ops-on-navy-muted); margin: 0 0 2px; }}
  .ops-meta dd {{ margin: 0; font-size: 15px; line-height: 21px; font-weight: 600;
    color: var(--ops-on-navy); overflow-wrap: anywhere; }}
  .ops-meta dd small {{ display: block; font-size: 12px; line-height: 16px; font-weight: 500;
    color: var(--ops-on-navy-muted); }}
  .ops-modeline {{ display: flex; flex-wrap: wrap; gap: 6px 8px; margin: 12px 0 0; }}
  .ops-chip {{ display: inline-flex; align-items: center; gap: 6px; font-size: 12px;
    line-height: 16px; font-weight: 600; padding: 3px 10px; border-radius: 999px;
    background: rgba(255,255,255,.08); color: var(--ops-on-navy);
    border: 1px solid var(--ops-rule); }}
  .ops-chip small {{ font-weight: 500; opacity: .8; }}
  .ops-chip--live, .ops-chip--demo {{ font-weight: 800; letter-spacing: .06em; }}
  .ops-chip--demo {{ background: {_DEMO_FILL}; color: {_DEMO_TEXT};
    border-color: {_DEMO_TEXT}; }}
  .ops-chip--ok {{ background: {_OK_FILL}; color: {_OK_TEXT}; border-color: {_OK_FILL}; }}
  .ops-chip--error {{ background: {_ERR_FILL}; color: {_ERR_TEXT};
    border-color: {_ERR_FILL}; }}
  .ops-chip--muted {{ background: var(--sapi-surface-muted); color: var(--sapi-text-primary);
    border-color: var(--sapi-border-card); }}
  .ops-alert {{ border: 1px dashed var(--sapi-border-card);
    border-radius: var(--sapi-radius-card); padding: 12px 14px; font-size: 14px;
    line-height: 20px; }}
  .ops-alert__head {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
  .ops-alert__meta {{ display: flex; flex-wrap: wrap; gap: 6px 24px; margin: 0 0 8px; }}
  .ops-alert__meta dt {{ font-size: 11px; font-weight: 700; letter-spacing: .06em;
    text-transform: uppercase; opacity: .75; }}
  .ops-alert__meta dd {{ margin: 0; font-weight: 700; }}
  .ops-alert__top {{ margin: 0 0 8px; padding-left: 0; list-style: none; }}
  .ops-alert__top li {{ padding: 2px 0; }}
  .sapi-ops p.ops-alert__note {{ margin: 0; font-size: 13px !important; opacity: .85; }}
  .is-presentation .ops-alert {{ font-size: 17px; line-height: 25px; }}
  .ops-demo {{ margin: 12px 0 0; padding: 14px 18px; border-radius: var(--sapi-radius-card);
    color: {_DEMO_TEXT}; border: 2px solid {_DEMO_TEXT};
    background: repeating-linear-gradient(135deg, {_DEMO_FILL} 0 14px, {_DEMO_STRIPE} 14px 28px);
    font-size: 14px; line-height: 20px; }}
  .ops-demo strong {{ display: block; font-size: 26px; line-height: 32px; font-weight: 900;
    letter-spacing: .08em; }}
  .ops-strip {{ margin: 12px 0 0; padding: 10px 16px; border-radius: var(--sapi-radius-card);
    font-size: 14px; line-height: 20px; }}
  .ops-strip--warn {{ background: {_WARN_FILL}; color: {_WARN_TEXT};
    border-left: 6px solid {_WARN_TEXT}; }}
  .sapi-ops p.ops-note {{ margin: 12px 0 18px; font-size: 14px !important;
    line-height: 20px !important;
    color: var(--sapi-text-primary); max-width: 100ch; }}
  .ops-main {{ display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: 20px;
    align-items: start; }}
  .ops-panel {{ background: var(--sapi-surface-card); border: 1px solid var(--sapi-border-card);
    border-radius: var(--sapi-radius-card); padding: 16px 18px 18px; }}
  .ops-panel + .ops-panel, .ops-section {{ margin-top: 20px; }}
  .ops-main {{ margin-bottom: 20px; }}
  .sapi-ops > .ops-panel {{ margin-bottom: 20px; }}
  .ops-main > .ops-panel {{ margin-top: 0; }}
  .sapi-ops .ops-panel h2 {{ margin: 0 0 4px !important; padding: 0 !important;
    font-size: 18px !important;
    line-height: 24px !important; font-weight: 700 !important; }}
  .sapi-ops .ops-panel p.ops-sub {{ margin: 0 0 14px; font-size: 13px !important;
    line-height: 18px !important; opacity: .8; }}
  .ops-top {{ list-style: none; margin: 0; padding: 0; }}
  .ops-top li {{ display: grid; grid-template-columns: 56px minmax(0, 1fr); gap: 4px 14px;
    padding: 12px 0; border-top: 1px solid var(--ops-hair); }}
  .ops-top li:first-child {{ border-top: 0; padding-top: 2px; }}
  .ops-rank {{ grid-row: span 2; font-size: 30px; line-height: 34px; font-weight: 800;
    color: var(--sapi-accent); letter-spacing: -0.02em; }}
  .ops-rank small {{ font-size: 16px; font-weight: 700; }}
  .ops-cellid {{ font-size: 17px; line-height: 22px; font-weight: 700; display: flex;
    flex-wrap: wrap; gap: 4px 10px; align-items: baseline; }}
  .ops-tie {{ font-size: 12px; line-height: 16px; font-weight: 600; padding: 1px 8px;
    border-radius: 999px; background: var(--sapi-surface-muted); color: var(--sapi-text-primary); }}
  .ops-bar {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center;
    gap: 10px; }}
  .ops-bar__track {{ height: 8px; border-radius: 4px; background: var(--sapi-surface-muted);
    overflow: hidden; }}
  .ops-bar__fill {{ height: 100%; border-radius: 4px; background: var(--sapi-accent); }}
  .ops-bar__value {{ font-size: 14px; line-height: 18px; font-weight: 600; min-width: 11ch;
    text-align: right; }}
  .ops-bar__value small {{ font-weight: 500; opacity: .75; }}
  .sapi-ops p.ops-after {{ margin: 10px 0 0; font-size: 13px !important;
    line-height: 18px !important; opacity: .85; }}
  .ops-map svg {{ width: 100%; height: auto; display: block; }}
  .ops-map .cell {{ stroke: var(--sapi-surface-card); stroke-width: 1.5; }}
  .ops-map .cell--top {{ stroke: var(--ops-navy); stroke-width: 3.5; }}
  .ops-map text {{ font-family: {t.FONT_STACK}; pointer-events: none; }}
  .ops-map .lbl {{ font-size: 13px; font-weight: 800; }}
  .ops-map .sub {{ font-size: 10px; font-weight: 600; }}
  .ops-map .axis {{ font-size: 10px; fill: var(--sapi-text-primary); opacity: .75; }}
  .ops-map .zone {{ font-size: 11px; font-weight: 700; fill: var(--sapi-text-primary);
    opacity: .85; }}
  .ops-map .rule {{ stroke: var(--sapi-text-primary); stroke-opacity: .35; stroke-width: 1; }}
  .ops-legend {{ display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 8px;
    align-items: center; margin: 10px 0 4px; font-size: 12px; line-height: 16px; }}
  .ops-legend__ramp {{ height: 8px; border-radius: 4px;
    background: linear-gradient(90deg,
      color-mix(in srgb, var(--sapi-accent) 8%, var(--sapi-surface-card)),
      var(--sapi-accent)); }}
  .sapi-ops p.ops-caption {{ margin: 6px 0 0; font-size: 12px !important;
    line-height: 16px !important; opacity: .8; }}
  .ops-sources {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
  .ops-src {{ border: 1px solid var(--sapi-border-card); border-radius: var(--sapi-radius-card);
    padding: 12px 14px; background: var(--sapi-surface-card); }}
  .ops-src h3 {{ margin: 0 0 8px; font-size: 12px; font-weight: 800; letter-spacing: .1em; }}
  .ops-badge {{ display: inline-flex; gap: 6px; align-items: center; font-size: 13px;
    font-weight: 800;
    letter-spacing: .04em; padding: 2px 10px; border-radius: 999px; margin-bottom: 8px; }}
  .ops-badge--ok {{ background: {_OK_FILL}; color: {_OK_TEXT}; }}
  .ops-badge--warn {{ background: {_WARN_FILL}; color: {_WARN_TEXT}; }}
  .ops-badge--error {{ background: {_ERR_FILL}; color: {_ERR_TEXT}; }}
  .ops-badge--muted {{ background: var(--sapi-surface-muted); color: var(--sapi-text-primary); }}
  .ops-src dl {{ margin: 0; display: grid; grid-template-columns: auto minmax(0, 1fr);
    gap: 3px 10px;
    font-size: 13px; line-height: 18px; }}
  .ops-src dt {{ opacity: .75; }}
  .ops-src dd {{ margin: 0; font-weight: 600; overflow-wrap: anywhere; }}
  .ops-src .na {{ font-size: 12px; font-weight: 700; letter-spacing: .04em; opacity: .7; }}
  .ops-table-wrap {{ overflow-x: auto; }}
  .ops-table {{ width: 100%; border-collapse: collapse; font-size: 14px; line-height: 20px;
    min-width: 520px; }}
  .ops-table th {{ text-align: left; font-size: 12px; font-weight: 700; letter-spacing: .04em;
    text-transform: uppercase; padding: 8px 10px; border-bottom: 2px solid var(--sapi-border-card);
    background: var(--sapi-surface-card); }}
  .ops-table td {{ padding: 7px 10px; border-bottom: 1px solid var(--ops-hair);
    vertical-align: middle; }}
  .ops-table tr.is-top td {{ background: color-mix(in srgb, var(--sapi-accent) 8%, transparent); }}
  .ops-table td.num {{ font-weight: 800; width: 6ch; }}
  .ops-table td.cid {{ white-space: nowrap; font-weight: 600; }}
  .ops-table td.score {{ width: 45%; }}
  .ops-limits {{ margin: 0; padding-left: 20px; font-size: 14px; line-height: 21px; }}
  .ops-limits li + li {{ margin-top: 4px; }}
  .ops-tech {{ margin: 0; display: grid; grid-template-columns: minmax(12ch, auto) minmax(0, 1fr);
    gap: 6px 16px; font-size: 13px; line-height: 18px; }}
  .ops-tech dt {{ font-weight: 700; }}
  .ops-tech dd {{ margin: 0; overflow-wrap: anywhere;
    font-family: ui-monospace, Consolas, monospace; }}
  .ops-state {{ margin: 16px 0 20px; padding: 22px 24px; border-radius: var(--sapi-radius-card); }}
  .ops-state--warn {{ background: {_WARN_FILL}; color: {_WARN_TEXT}; }}
  .ops-state--error {{ background: {_ERR_FILL}; color: {_ERR_TEXT}; }}
  .sapi-ops .ops-state h2 {{ margin: 0 0 6px !important; font-size: 20px !important;
    line-height: 26px !important;
    font-weight: 800 !important; letter-spacing: .02em; color: inherit !important; }}
  .ops-state p {{ margin: 0; max-width: 80ch; font-size: 15px; line-height: 22px; }}
  .ops-skel {{ border-radius: var(--sapi-radius-card); background: var(--sapi-surface-muted);
    position: relative; overflow: hidden; }}
  .ops-skel::after {{ content: ""; position: absolute; inset: 0; transform: translateX(-100%);
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.55), transparent);
    animation: ops-sheen 1.2s ease-out infinite; }}
  @keyframes ops-sheen {{ to {{ transform: translateX(100%); }} }}
  @media (prefers-reduced-motion: reduce) {{ .ops-skel::after {{ animation: none; }} }}
  .is-presentation .ops-band h1 {{ font-size: 30px !important; line-height: 36px !important; }}
  .is-presentation .ops-pill {{ font-size: 20px; padding: 8px 18px; }}
  .is-presentation .ops-meta dd {{ font-size: 19px; line-height: 26px; }}
  .is-presentation .ops-meta dt {{ font-size: 13px; }}
  .is-presentation p.ops-note {{ font-size: 18px !important; line-height: 27px !important; }}
  .is-presentation .ops-panel h2 {{ font-size: 24px !important; line-height: 30px !important; }}
  .is-presentation .ops-rank {{ font-size: 44px; line-height: 48px; }}
  .is-presentation .ops-cellid {{ font-size: 24px; line-height: 30px; }}
  .is-presentation .ops-bar__value {{ font-size: 18px; }}
  .is-presentation .ops-top li {{ grid-template-columns: 76px minmax(0, 1fr); padding: 16px 0; }}
  .is-presentation .ops-bar__track {{ height: 12px; }}
  .is-presentation .ops-limits {{ font-size: 17px; line-height: 26px; }}
  .is-presentation .ops-src dl {{ font-size: 15px; line-height: 21px; }}
  @media (max-width: 1100px) {{ .ops-sources {{ grid-template-columns: repeat(2, minmax(0, 1fr));
    }} }}
  @media (max-width: 900px) {{ .ops-main {{ grid-template-columns: minmax(0, 1fr); }} }}
  @media (max-width: 520px) {{ .ops-band {{ padding: 14px; }} .ops-rank {{ font-size: 24px; }}
    .ops-sources {{ grid-template-columns: minmax(0, 1fr); }}
    .ops-table {{ min-width: 0; }} .ops-table .opt {{ display: none; }}
    .ops-bar__value small {{ display: none; }} .ops-bar__value {{ min-width: 7ch; }}
    .ops-top li {{ grid-template-columns: 44px minmax(0, 1fr); }} }}
</style>
"""


def _e(value) -> str:
    return escape("" if value is None else str(value), quote=True)


def _plural(n: int, one: str, many: str) -> str:
    return one if abs(n) == 1 else many


def _human_time(iso: str | None) -> str:
    """ISO con zona → "AAAA-MM-DD HH:MM UTC" (el valor exacto queda en el tooltip)."""
    try:
        moment = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        return str(iso)
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def short_hash(value: str | None, n: int = 12) -> str:
    return f"{value[:n]}…" if value else NOT_IN_RESPONSE


def state_copy(view: DashboardView) -> tuple[str, str, str]:
    label, text, tone = STATE_COPY[view.state]
    if view.state == NETWORK_ERROR and "timeout" in view.reasons:
        text = _TIMEOUT_TEXT
    if view.firms_blocked:
        text = _FIRMS_BLOCKED_TEXT
    return label, text, tone


def _pill(view: DashboardView) -> str:
    label, _, tone = state_copy(view)
    if view.state == DEMO:
        label = "DEMO · DATOS DEMOSTRATIVOS"
    elif view.state == REPLAY_READY:
        label = "REPLAY · CORRIDA ACEPTADA"
    return (
        '<div class="ops-status"><span class="ops-status__label">Estado del sistema</span>'
        f'<span class="ops-pill ops-pill--{tone}" role="status">{_e(label)}</span></div>'
    )


def _utc_clock(iso: str | None) -> str:
    """Hora de la consulta de vista (HH:MM:SS UTC); nunca se confunde con datos."""
    try:
        moment = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return "—"
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def mode_line(view: DashboardView, last_success: str | None = None) -> str:
    """MODO (DEMO / EN VIVO / REPLAY) y, en vivo, resultado de la ÚLTIMA consulta."""
    if view.mode == MODE_REPLAY:
        chips = ['<span class="ops-chip ops-chip--replay">MODO: REPLAY</span>']
        if view.data_origin == "SYNTHETIC":
            chips.append('<span class="ops-chip ops-chip--demo">SYNTHETIC</span>')
        if view.captured_at:
            chips.append(
                '<span class="ops-chip" title="Cuándo se capturó el artefacto. No es la hora '
                'de evaluación.">Capturado: '
                f'<b data-time="captured">{_e(_utc_clock(view.captured_at))}</b></span>'
            )
        if view.artifact_fingerprint:
            chips.append(
                '<span class="ops-chip">Artefacto: '
                f'<b data-artifact="{_e(view.artifact_fingerprint)}">'
                f"{_e(short_hash(view.artifact_fingerprint))}</b></span>"
            )
        chips.append(
            '<span class="ops-chip">Sin conexión: servicios no requeridos</span>'
        )
        return f'<div class="ops-modeline">{"".join(chips)}</div>'
    if view.mode == MODE_DEMO:
        chips = [
            '<span class="ops-chip ops-chip--demo">MODO: DEMO</span>',
            '<span class="ops-chip">Sin conexión al servicio: fixture local</span>',
        ]
    else:
        chips = ['<span class="ops-chip ops-chip--live">MODO: EN VIVO</span>']
        conn = view.connection
        if conn is not None:
            text, tone = CONNECTION_COPY[conn]
            chips.append(
                f'<span class="ops-chip ops-chip--{tone}" data-connection="{conn}">'
                f"CONEXIÓN: {text} <small>(última consulta)</small></span>"
            )
        if last_success and conn != CONN_CONNECTED:
            chips.append(
                f'<span class="ops-chip">Última consulta exitosa: {_e(_utc_clock(last_success))} '
                "(sus datos no se muestran)</span>"
            )
    chips.append(
        '<span class="ops-chip" title="Hora en que este panel leyó el servicio. '
        'No indica la frescura de los datos.">Última consulta de vista: '
        f'<b data-time="view">{_e(_utc_clock(view.fetched_at))}</b></span>'
    )
    return f'<div class="ops-modeline">{"".join(chips)}</div>'


def header(view: DashboardView, last_success: str | None = None) -> str:
    meta = ""
    if view.has_ranking:
        firms = view.firms
        lag = firms["lag_days"]
        items = [
            (
                "Hora de evaluación",
                f'<span data-time="scoring" title="{_e(view.scoring_time)}">'
                f"{_e(_human_time(view.scoring_time))}</span><small>momento puntuado</small>",
            ),
            (
                "Cobertura FIRMS hasta",
                f'<span data-time="firms">{_e(firms["coverage_end"])}</span>'
                f"<small>{_e(firms['status'])} · desfase {_e(lag)} "
                f"{_plural(lag, 'día', 'días')}</small>",
            ),
            ("Celdas evaluadas", f"{len(view.cells)} de {len(EXPECTED_CELL_IDS)}"),
            (
                "Meteorología DMC",
                _e(view.dmc.get("freshness", NOT_IN_RESPONSE))
                + (
                    f"<small>obs. {_e(_human_time(view.dmc['weather_timestamp']))}</small>"
                    if "weather_timestamp" in view.dmc
                    else ""
                ),
            ),
            (
                "Modelo",
                _e(view.model_version or NOT_IN_RESPONSE)
                + (
                    f"<small>{_e(view.model_status)}</small>"
                    if view.model_status
                    else ""
                ),
            ),
        ]
        meta = (
            '<dl class="ops-meta">'
            + "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in items)
            + "</dl>"
        )
    band_cls = {
        MODE_DEMO: "ops-band ops-band--demo",
        MODE_REPLAY: "ops-band ops-band--replay",
    }.get(view.mode, "ops-band")
    band = (
        f'<header class="{band_cls}"><div class="ops-band__top">'
        "<h1>S.A.P.I. <span>· Centro de Control</span></h1>"
        f"{_pill(view)}</div>{mode_line(view, last_success)}{meta}</header>"
    )
    demo = ""
    if view.mode == MODE_DEMO:
        demo = (
            '<div class="ops-demo" role="note"><strong>DATOS DEMOSTRATIVOS</strong>'
            "Fixture sintética (SYNTHETIC DEMO) para presentación y desarrollo de la interfaz. "
            "No son resultados del modelo, no provienen de incendios reales ni del servicio "
            "en vivo.</div>"
        )
    if view.mode == MODE_REPLAY and view.data_origin == "SYNTHETIC":
        demo = (
            '<div class="ops-demo" role="note"><strong>SYNTHETIC</strong>'
            "Artefacto capturado desde datos sintéticos (fixture de prueba). No son resultados "
            "operacionales ni provienen de incendios reales.</div>"
        )
    warn = ""
    if view.firms_warning:
        lag = view.firms["lag_days"]
        warn = (
            '<div class="ops-strip ops-strip--warn" role="alert"><strong>▲ '
            f"{_e(FIRMS_STALE)}</strong> · la cobertura FIRMS termina el "
            f"{_e(view.firms['coverage_end'])} ({_e(lag)} {_plural(lag, 'día', 'días')} de "
            "desfase). "
            "SAPI puntuó con aviso: el historial satelital reciente puede estar incompleto.</div>"
        )
    note = f'<p class="ops-note"><strong>Evaluación exploratoria.</strong> {CLARIFICATION}</p>'
    return band + demo + warn + note


def _bar(score: float) -> str:
    width = max(0.0, min(1.0, score)) * 100
    return (
        f'<div class="ops-bar" role="img" aria-label="Score relativo {score:.4f}">'
        f'<div class="ops-bar__track"><div class="ops-bar__fill" style="width:{width:.2f}%">'
        "</div></div>"
        f'<span class="ops-bar__value">{score:.4f} <small>score relativo</small></span></div>'
    )


def _tie(c: Cell) -> str:
    if c.tie_group_size <= 1:
        return ""
    return (
        f'<span class="ops-tie">Empate: {c.tie_group_size} celdas con el mismo score · '
        f"posición {c.display_rank}</span>"
    )


def top_list(view: DashboardView) -> str:
    rows = []
    for c in view.top:
        rows.append(
            f'<li data-rank="{c.rank}"><div class="ops-rank" aria-label="Rank {c.rank}">'
            f"<small>#</small>{c.rank}</div>"
            f'<div class="ops-cellid">Celda {_e(c.cell_id)} {_tie(c)}</div>{_bar(c.score)}</li>'
        )
    last = view.top[-1]
    beyond = sum(1 for c in view.cells[TOP_N:] if c.score == last.score)
    after = ""
    if beyond:
        verb = _plural(beyond, "celda más comparte", "celdas más comparten")
        after = (
            f'<p class="ops-after">+ {beyond} {verb} el score del rank {TOP_N} '
            "(misma posición compartida).</p>"
        )
    return (
        '<section class="ops-panel" aria-labelledby="ops-top-h">'
        f'<h2 id="ops-top-h">Top {TOP_N} · prioridades</h2>'
        f'<p class="ops-sub">Ranks 1 a {TOP_N} de {len(view.cells)}, en el orden entregado por el '
        "servicio. Los empates se indican sin alterar el rank.</p>"
        f'<ol class="ops-top">{"".join(rows)}</ol>{after}</section>'
    )


# ── Mapa geográfico (grilla oficial, sin mapa base) ────────────────────────────
_MAP_W, _PAD_L, _PAD_R, _PAD_T, _PAD_B = 720, 46, 12, 26, 44


def _projector():
    geo = all_cells()
    lon0 = min(c["min_lon"] for c in geo)
    lon1 = max(c["max_lon"] for c in geo)
    lat0 = min(c["min_lat"] for c in geo)
    lat1 = max(c["max_lat"] for c in geo)
    kx = math.cos(math.radians((lat0 + lat1) / 2))  # equirectangular local
    scale = (_MAP_W - _PAD_L - _PAD_R) / ((lon1 - lon0) * kx)
    height = _PAD_T + (lat1 - lat0) * scale + _PAD_B

    def xy(lon: float, lat: float) -> tuple[float, float]:
        return _PAD_L + (lon - lon0) * kx * scale, _PAD_T + (lat1 - lat) * scale

    return geo, xy, (lon0, lon1, lat0, lat1), height


def geo_map(view: DashboardView) -> str:
    geo, xy, (lon0, lon1, lat0, lat1), height = _projector()
    by_id = {c.cell_id: c for c in view.cells}
    top_score = max(c.score for c in view.cells) or 1.0
    shapes, labels = [], []
    for g in geo:
        c = by_id[g["cell_id"]]
        x0, y0 = xy(g["min_lon"], g["max_lat"])
        x1, y1 = xy(g["max_lon"], g["min_lat"])
        strength = 0.08 + 0.92 * (c.score / top_score)
        cls = "cell cell--top" if c.rank <= TOP_N else "cell"
        tip = f"Celda {c.cell_id} · rank {c.rank} · score relativo {c.score:.4f}"
        shapes.append(
            f'<rect class="{cls}" x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" '
            f'height="{y1 - y0:.1f}" style="fill:var(--sapi-accent);fill-opacity:{strength:.2f}">'
            f"<title>{_e(tip)}</title></rect>"
        )
        ink = "#ffffff" if strength > 0.55 else "var(--sapi-text-primary)"
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        labels.append(
            f'<text class="lbl" x="{cx:.1f}" y="{cy - 2:.1f}" text-anchor="middle" '
            f'style="fill:{ink}">#{c.rank}</text>'
            f'<text class="sub" x="{cx:.1f}" y="{cy + 12:.1f}" text-anchor="middle" '
            f'style="fill:{ink}">{_e(c.cell_id)}</text>'
        )
    axes = []
    rows, cols = GRID_SHAPE
    step_lon, step_lat = (lon1 - lon0) / cols, (lat1 - lat0) / rows
    for i in range(0, cols + 1, 2):
        x, y = xy(lon0 + i * step_lon, lat0)
        axes.append(
            f'<line class="rule" x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y + 4:.1f}"/>'
            f'<text class="axis" x="{x:.1f}" y="{y + 15:.1f}" '
            f'text-anchor="{"end" if i == cols else "start" if i == 0 else "middle"}">'
            f"{lon0 + i * step_lon:.2f}°</text>"
        )
    for j in range(0, rows + 1):
        x, y = xy(lon0, lat0 + j * step_lat)
        axes.append(
            f'<text class="axis" x="{x - 5:.1f}" y="{y + 3:.1f}" text-anchor="end">'
            f"{lat0 + j * step_lat:.2f}°</text>"
        )
    zones: dict[str, list[int]] = {}
    for col in range(cols):
        zones.setdefault(zone_for_col(col), []).append(col)
    for zone, zcols in zones.items():
        xa, _ = xy(lon0 + zcols[0] * step_lon, lat0)
        xb, yb = xy(lon0 + (zcols[-1] + 1) * step_lon, lat0)
        axes.append(
            f'<line class="rule" x1="{xa + 3:.1f}" y1="{yb + 24:.1f}" x2="{xb - 3:.1f}" '
            f'y2="{yb + 24:.1f}"/>'
            f'<text class="zone" x="{(xa + xb) / 2:.1f}" y="{yb + 37:.1f}" text-anchor="middle">'
            f"{_e(ZONE_LABELS[zone].split(' (')[0])}</text>"
        )
    nx, ny = _MAP_W - _PAD_R - 10, 6
    north = f'<text class="zone" x="{nx:.1f}" y="{ny + 12:.1f}" text-anchor="middle">N ↑</text>'
    svg = (
        f'<svg viewBox="0 0 {_MAP_W} {height:.0f}" role="img" '
        f'aria-label="Mapa de las {len(view.cells)} celdas coloreadas por score relativo">'
        + "".join(shapes)
        + "".join(labels)
        + "".join(axes)
        + north
        + "</svg>"
    )
    return (
        '<section class="ops-panel ops-map" aria-labelledby="ops-map-h">'
        '<h2 id="ops-map-h">Mapa de la grilla · corredor Viña del Mar – Quilpué</h2>'
        '<p class="ops-sub">Posición real de las 50 celdas (longitud / latitud, norte arriba). '
        "Etiqueta: rank y celda. Pase el cursor sobre una celda para ver su score relativo.</p>"
        f"{svg}"
        '<div class="ops-legend"><span>Menor score relativo</span><div class="ops-legend__ramp">'
        "</div>"
        "<span>Mayor score relativo</span></div>"
        '<p class="ops-caption">Intensidad proporcional al score relativo máximo de esta '
        "evaluación; "
        f"no es una probabilidad. Borde oscuro: ranks 1 a {TOP_N}. Geometría: grilla oficial de "
        "SAPI "
        "(src/geo/grid.py, EPSG:4326), sin mapa base para funcionar sin internet.</p></section>"
    )


# ── Estado de datos ────────────────────────────────────────────────────────────
def _src_card(name: str, status: str, rows: list[tuple[str, str]]) -> str:
    symbol, text, tone = SOURCE_BADGE[status]
    if all(
        v == _na() for _, v in rows
    ):  # nada informado: una sola línea, no N repeticiones
        rows = [("Datos", _na())]
    body = "".join(f"<dt>{_e(k)}</dt><dd>{v}</dd>" for k, v in rows)
    return (
        f'<article class="ops-src" data-source="{_e(name)}" data-status="{_e(status)}">'
        f"<h3>{_e(name)}</h3>"
        f'<span class="ops-badge ops-badge--{tone}"><span aria-hidden="true">{symbol}</span>'
        f"{_e(text)}</span><dl>{body}</dl></article>"
    )


def _na() -> str:
    return f'<span class="na">{NOT_IN_RESPONSE}</span>'


def _val(value) -> str:
    return _na() if value is None else _e(value)


def data_status(view: DashboardView, presentation: bool = False) -> str:
    st = view.source_status()
    f, d, ident = view.firms, view.dmc, view.identity
    lag = f.get("lag_days")
    firms_rows = [
        ("Origen", _val(f.get("origin"))),
        ("Cobertura hasta", _val(f.get("coverage_end"))),
        (
            "Desfase",
            _na() if lag is None else f"{_e(lag)} {_plural(lag, 'día', 'días')}",
        ),
        (
            "Estado upstream",
            _val(
                f.get("status")
                or ("DESFASE SOBRE EL MÁXIMO" if view.firms_blocked else None)
            ),
        ),
    ]
    dmc_rows = [
        (
            "Estación",
            (
                _na()
                if "station_id" not in d
                else _e(f"{d['station_id']} · {d.get('station_name', '')}".rstrip(" ·"))
            ),
        ),
        (
            "Observación",
            (
                _na()
                if "weather_timestamp" not in d
                else _e(_human_time(d["weather_timestamp"]))
            ),
        ),
        ("Antigüedad", _na() if "age_hours" not in d else f"{d['age_hours']:.1f} h"),
        ("Frescura", _val(d.get("freshness"))),
    ]
    if "temperatura" in d:
        extra = [f"{d['temperatura']:.1f} °C"]
        if "humedad_relativa" in d:
            extra.append(f"HR {d['humedad_relativa']:.0f}")
        if "velocidad_viento_kmh" in d:
            extra.append(f"viento {d['velocidad_viento_kmh']:.0f} km/h")
        dmc_rows.append(("Última obs.", _e(" · ".join(extra))))
    topo_rows = [
        ("Origen", _val(ident.get("topography_origin"))),
        (
            "Identidad",
            _val(
                ident.get("topography_sha256")
                and short_hash(ident["topography_sha256"])
            ),
        ),
    ]
    model_rows = [
        ("Versión", _val(view.model_version)),
        ("Estado", _val(view.model_status)),
        (
            "SHA-256",
            _val(ident.get("model_sha256") and short_hash(ident["model_sha256"])),
        ),
    ]
    if presentation:  # sin hashes de desarrollo en la pantalla principal
        topo_rows, model_rows = topo_rows[:1], model_rows[:2]
    cards = [
        _src_card("FIRMS", st["FIRMS"], firms_rows),
        _src_card("DMC", st["DMC"], dmc_rows),
        _src_card("TOPOGRAFÍA", st["TOPOGRAFÍA"], topo_rows),
        _src_card("MODELO", st["MODELO"], model_rows),
    ]
    return (
        '<section class="ops-panel" aria-labelledby="ops-src-h">'
        '<h2 id="ops-src-h">Estado de datos</h2>'
        '<p class="ops-sub">Solo se muestra lo que informa el servicio. Los estados FIRMS y DMC '
        "usan la clasificación de SAPI (no se redefinen umbrales en este panel).</p>"
        f'<div class="ops-sources">{"".join(cards)}</div></section>'
    )


# ── Ranking completo ───────────────────────────────────────────────────────────
def filter_cells(cells, query: str = "", order: str = "rank") -> list[Cell]:
    """Filtro/orden de VISTA. Nunca cambia `rank`; el orden por defecto es el del backend."""
    q = (query or "").strip().upper()
    out = [
        c
        for c in cells
        if not q or q in c.cell_id or q.lstrip("0") == c.cell_id[3:].lstrip("0")
    ]
    if order == "cell_id":
        out = sorted(out, key=lambda c: c.cell_id)
    return out


def ranking_table(view: DashboardView, cells=None, note: str = "") -> str:
    shown = list(view.cells if cells is None else cells)
    body = []
    for c in shown:
        tie = (
            f"×{c.tie_group_size} (pos. {c.display_rank})"
            if c.tie_group_size > 1
            else "—"
        )
        cls = ' class="is-top"' if c.rank <= TOP_N else ""
        body.append(
            f'<tr{cls}><td class="num">{c.rank}</td><td class="cid">{_e(c.cell_id)}</td>'
            f'<td class="score">{_bar(c.score)}</td><td class="opt">{tie}</td></tr>'
        )
    if not body:
        body.append(
            '<tr><td colspan="4">Ninguna celda coincide con la búsqueda.</td></tr>'
        )
    return (
        '<section class="ops-panel ops-table-wrap" aria-labelledby="ops-rank-h">'
        f'<h2 id="ops-rank-h">Ranking completo · {len(view.cells)} celdas</h2>'
        '<p class="ops-sub">Rank canónico entregado por el servicio (único, 1 a 50). '
        "La columna Empate indica celdas con el mismo score y su posición "
        f"compartida.{_e(note)}</p>"
        '<table class="ops-table"><thead><tr><th scope="col">Rank</th><th scope="col">Celda</th>'
        '<th scope="col">Score relativo</th><th scope="col" class="opt">Empate</th></tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></section>'
    )


# ── Limitaciones, detalle técnico, estados sin ranking ─────────────────────────
def limitations() -> str:
    items = "".join(f"<li>{_e(x)}</li>" for x in LIMITATIONS)
    return (
        '<section class="ops-panel" aria-labelledby="ops-lim-h">'
        '<h2 id="ops-lim-h">Limitaciones del sistema</h2>'
        f'<ul class="ops-limits">{items}</ul></section>'
    )


TECH_FIELDS = (
    ("inputs_fingerprint", "Inputs fingerprint"),
    ("alert_fingerprint", "Alert fingerprint"),
    ("artifact_fingerprint", "Artifact fingerprint"),
    ("model_sha256", "Modelo SHA-256"),
    ("firms_sha256", "FIRMS SHA-256"),
    ("dmc_manifest_sha256", "DMC manifest SHA-256"),
    ("topography_sha256", "Topografía SHA-256"),
)
_ALERT_NOT_READY = {
    "UNAVAILABLE": "SAPI no generaría una alerta de ranking: la evaluación no está disponible.",
    "INVALID": "SAPI no generaría una alerta: el resultado no es válido.",
}


def _alert_fingerprint(view: DashboardView) -> str | None:
    return view.alert.fingerprint if view.alert else None


def full_hashes(view: DashboardView) -> list[tuple[str, str]]:
    """(etiqueta, hash completo) disponibles, para copiar desde la página."""
    values = {
        "inputs_fingerprint": view.inputs_fingerprint,
        "alert_fingerprint": _alert_fingerprint(view),
        "artifact_fingerprint": view.artifact_fingerprint,
        **view.identity,
    }
    return [(label, values[k]) for k, label in TECH_FIELDS if values.get(k)]


def alert_panel(view: DashboardView) -> str:
    """Vista previa estructurada de la alerta, desde el MISMO resultado canónico."""
    alert = view.alert
    demo_chip = {
        MODE_DEMO: '<span class="ops-chip ops-chip--demo">DATOS DEMOSTRATIVOS</span>',
        MODE_REPLAY: '<span class="ops-chip ops-chip--replay">REPLAY</span>',
    }.get(view.mode, "")
    if view.mode == MODE_REPLAY and view.data_origin == "SYNTHETIC":
        demo_chip += '<span class="ops-chip ops-chip--demo">SYNTHETIC</span>'
    head = (
        '<div class="ops-alert__head"><span class="ops-chip ops-chip--muted">'
        f"NO ENVIADA · SOLO VISTA PREVIA</span>{demo_chip}</div>"
    )
    if alert is None or alert.status != "READY":
        status = alert.status if alert else "NONE"
        text = _ALERT_NOT_READY.get(status, _ALERT_NOT_READY["INVALID"])
        if view.state == NETWORK_ERROR:
            text = "Sin respuesta del servicio SAPI: no hay alerta que previsualizar."
        body = f"<p>{_e(text)} {_e(NO_RANKING_NOTE)}</p>"
        return f'<div class="ops-alert" data-alert-status="{_e(status)}">{head}{body}</div>'
    rows = []
    for rank, display, cid, score in alert.top:
        shared = (
            f" <small>(posición compartida {display})</small>"
            if display != rank
            else ""
        )
        rows.append(
            f'<li data-rank="{rank}"><b>#{rank}</b> Celda {_e(cid)} · '
            f"score relativo {score:.4f}{shared}</li>"
        )
    meta = (
        '<dl class="ops-alert__meta">'
        f"<div><dt>Hora de evaluación</dt><dd>{_e(_human_time(alert.scoring_time))}</dd></div>"
        f"<div><dt>Cobertura FIRMS hasta</dt><dd>{_e(alert.firms_coverage_end)}</dd></div>"
        f"<div><dt>Celdas priorizadas</dt><dd>{len(alert.top)} de {len(view.cells)}</dd></div>"
        "</dl>"
    )
    disclaimer = f'<p class="ops-alert__note">{_e(CLARIFICATION)} {_e(FIRMS_NOTE)}</p>'
    return (
        f'<div class="ops-alert" data-alert-status="READY">{head}{meta}'
        f'<ol class="ops-alert__top">{"".join(rows)}</ol>{disclaimer}</div>'
    )


def technical_details(
    view: DashboardView, read_at: str | None = None, last_success: str | None = None
) -> str:
    ident = view.identity
    conn = view.connection
    alert_fp = _alert_fingerprint(view)
    rows = [
        ("Modo", {MODE_DEMO: "DEMO", MODE_REPLAY: "REPLAY"}.get(view.mode, "EN VIVO")),
        ("Origen de datos", view.data_origin),
        ("Capturado", view.captured_at),
        (
            "Artifact fingerprint",
            (
                short_hash(view.artifact_fingerprint)
                if view.artifact_fingerprint
                else None
            ),
        ),
        ("Conexión (última consulta)", CONNECTION_COPY[conn][0] if conn else None),
        ("Endpoint", "fixture local" if view.mode == MODE_DEMO else view.endpoint),
        ("Estado interno", view.state),
        ("Motivos", ", ".join(view.reasons) or "—"),
        ("Última consulta de vista", view.fetched_at or read_at),
        ("Última consulta exitosa", last_success),
        ("Hora de evaluación (scoring)", view.scoring_time),
        ("Celdas evaluadas", len(view.cells) if view.cells else None),
        (
            "Inputs fingerprint",
            short_hash(view.inputs_fingerprint) if view.inputs_fingerprint else None,
        ),
        ("Alert fingerprint", short_hash(alert_fp) if alert_fp else None),
        ("Identidad n8n", N8N_IDENTITY_NOTE),
        ("Modelo", view.model_version),
        (
            "Modelo SHA-256",
            ident.get("model_sha256") and short_hash(ident["model_sha256"]),
        ),
        ("FIRMS origen", view.firms.get("origin")),
        ("FIRMS cobertura hasta", view.firms.get("coverage_end")),
        ("FIRMS desfase (días)", view.firms.get("lag_days")),
        ("FIRMS estado", view.firms.get("status")),
        ("FIRMS puntero", ident.get("firms_pointer_version")),
        (
            "FIRMS SHA-256",
            ident.get("firms_sha256") and short_hash(ident["firms_sha256"]),
        ),
        ("DMC estación", view.dmc.get("station_id")),
        ("DMC observación", view.dmc.get("weather_timestamp")),
        ("DMC frescura", view.dmc.get("freshness")),
        (
            "DMC manifest",
            ident.get("dmc_manifest_sha256")
            and short_hash(ident["dmc_manifest_sha256"]),
        ),
        ("DMC cobertura hasta", ident.get("dmc_coverage_end")),
        ("DMC puntero", ident.get("dmc_pointer_version")),
        ("Topografía origen", ident.get("topography_origin")),
        (
            "Topografía SHA-256",
            ident.get("topography_sha256") and short_hash(ident["topography_sha256"]),
        ),
    ]
    body = "".join(
        f"<dt>{_e(k)}</dt><dd>{_e(v) if v not in (None, '') else _na()}</dd>"
        for k, v in rows
    )
    return f'<dl class="ops-tech">{body}</dl>'


def state_panel(view: DashboardView) -> str:
    title, text, tone = state_copy(view)
    return (
        f'<section class="ops-state ops-state--{tone}" role="alert">'
        f"<h2>{_e(title)}</h2><p>{_e(text)}</p></section>"
    )


def loading() -> str:
    return (
        dashboard_css()
        + '<div class="sapi-ops" aria-busy="true"><div class="ops-skel" style="height:118px"></div>'
        '<p class="ops-note">Consultando la última evaluación…</p><div class="ops-main">'
        '<div class="ops-skel" style="height:340px"></div><div class="ops-skel" '
        'style="height:340px"></div>'
        "</div></div>"
    )


def wrap(inner: str, presentation: bool = False) -> str:
    """Contenedor de una sección. El CSS se inyecta una sola vez (`dashboard_css`)."""
    cls = "sapi-ops is-presentation" if presentation else "sapi-ops"
    return f'<div class="{cls}">{inner}</div>'


def render_overview(
    view: DashboardView, presentation: bool = False, last_success: str | None = None
) -> str:
    """Estado del sistema + Top 5 + mapa (o panel de estado si no hay ranking)."""
    parts = [header(view, last_success)]
    if view.has_ranking:
        parts += ['<div class="ops-main">', top_list(view), geo_map(view), "</div>"]
    else:
        parts.append(state_panel(view))
    return wrap("".join(parts), presentation)


def render(view: DashboardView, presentation: bool = False) -> str:
    """HTML completo del panel para un estado (excepto LOADING: ver `loading`)."""
    parts = [
        dashboard_css(),
        render_overview(view, presentation),
        wrap(data_status(view, presentation), presentation),
    ]
    if view.has_ranking and not presentation:
        parts.append(wrap(ranking_table(view), presentation))
    parts.append(wrap(alert_section(view), presentation))
    parts.append(wrap(limitations(), presentation))
    return "".join(parts)


def alert_section(view: DashboardView) -> str:
    return (
        '<section class="ops-panel" aria-labelledby="ops-alert-h">'
        '<h2 id="ops-alert-h">Vista previa de alerta</h2>'
        '<p class="ops-sub">Lo que SAPI generaría para una notificación futura, a partir del '
        "mismo resultado que muestra este panel. Nada se envía: no hay conexión con "
        f"Telegram ni n8n.</p>{alert_panel(view)}</section>"
    )
