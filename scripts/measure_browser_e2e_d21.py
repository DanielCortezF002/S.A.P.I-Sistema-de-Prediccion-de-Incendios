"""Test E2E de navegador para medición real de latencia y ranking visible en Streamlit (CA4 / Directiva 26).

Cierre definitivo de hallazgos Astra:
1. Monotónico antes del clic: t_start se toma inmediatamente antes de despachar el clic.
2. Captura de estado previo: captura el timestamp exacto del DOM antes del clic.
3. Despacho del clic y espera de señal posterior discriminante (cambio de timestamp en DOM).
4. Cero tolerancia a DOM antiguo: si ocurre timeout sin cambio demostrado de timestamp,
   el test FALLA con TimeoutError. No existe fallback a DOM antiguo.
5. Prueba negativa obligatoria: demuestra que si el DOM no cambia, el arnés falla (FAIL).
6. Verificación real de 50 celdas: valida el conteo contra el contrato JSON del backend
   (/api/v1/ranking) y el KPI strip del DOM, eliminando cualquier constante hardcodeada ('return 50').
7. Registro de identidades: SHA, tree, fecha UTC, URL, y parámetros del stack.
8. Salida a carpeta de evidencia designada (artifacts/hito2/d26).
9. Evidencia discriminante por captura: SHA-256 del PNG y tipo de navegación del
   navegador; RUN-04 no asume `content_verified=True`, exige grilla visible.

SAPI-137 (HU-90.T2) amplía el arnés para medir n muestras por escenario sin
medir nada por sí mismo: --repetitions, --warmup (registrado aparte y fuera del
percentil), --order blocks|interleaved, percentil nearest_rank y lineal
(ambos se calculan siempre), samples.csv escrito fila a fila con cada fallo y
timeout como fila, --expand-method current|legacy (current mide por evento en
el navegador sin sleep de Python; legacy usa un intervalo idéntico al de
f8c5218), columnas timing_source y timing_resolution con la resolución
declarada de cada escenario, y el chequeo del KPI contra .sapi-card-kpi.
Los valores por defecto de esas opciones son PROVISIONALES: ver el bloque
"VALORES POR DEFECTO PROVISIONALES" más abajo.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.edge.options import Options
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    webdriver = None
    Options = None
    EC = None
    WebDriverWait = None


def get_git_identities(repo_root: Path) -> tuple[str, str]:
    """Obtiene commit SHA y tree SHA del repositorio."""
    try:
        commit_res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True
        )
        tree_res = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True
        )
        return commit_res.stdout.strip(), tree_res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT", "UNKNOWN_TREE"


def get_container_identities(project_name: str = "sapi-v2") -> dict[str, str]:
    """Obtiene nombres e IDs de imágenes de los contenedores del stack."""
    cmd = ["docker", "compose", "-p", project_name, "ps", "--format", "json"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0 and res.stdout.strip():
            containers = []
            out = res.stdout.strip()
            if out.startswith("["):
                containers = json.loads(out)
            else:
                for line in out.splitlines():
                    if line.strip():
                        containers.append(json.loads(line))
            return {
                c.get("Service", c.get("service", "unknown")): c.get("Image", c.get("image", "unknown"))
                for c in containers
            }
    except Exception:
        pass
    return {}


_GRID_SELECTOR = "div[data-testid='stDataFrame'], [data-testid='stTable']"


def sha256_file(path: Path) -> str:
    """SHA-256 en mayúsculas del archivo indicado (evidencia reproducible)."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def get_browser_navigation_type(driver: webdriver.Edge) -> str:
    """Tipo de navegación del documento actual ('navigate', 'reload', 'unknown').

    Permite distinguir una recarga real de navegador (RUN-03) de un rerun de
    Streamlit disparado por un botón (RUN-02), que no crea una nueva entrada de
    navegación.
    """
    script = (
        "const nav = performance.getEntriesByType('navigation')[0];"
        "return nav && nav.type ? nav.type : 'unknown';"
    )
    try:
        value = driver.execute_script(script)
    except Exception:
        return "unknown"
    return str(value) if value else "unknown"


def _is_displayed(element) -> bool:
    try:
        return bool(element.is_displayed())
    except Exception:
        return False


def verify_expanded_grid(driver: webdriver.Edge) -> tuple[bool, str]:
    """Verifica que la grilla expandida esté realmente visible.

    No asume True por haber encontrado el expander: exige al menos un
    stDataFrame/stTable visible. Devuelve (ok, detalle).
    """
    try:
        grids = driver.find_elements("css selector", _GRID_SELECTOR)
    except Exception as ex:
        return False, f"Error comprobando grilla: {ex}"
    visible = [grid for grid in grids if _is_displayed(grid)]
    if not visible:
        return False, f"Grillas encontradas={len(grids)}, visibles=0"
    return True, f"Grillas visibles={len(visible)} de {len(grids)}"


_IN_VIEWPORT_JS = (
    "const r = arguments[0].getBoundingClientRect();"
    "return r.top >= 0 && r.bottom <= window.innerHeight && r.height > 0;"
)


def scroll_grid_into_view(driver) -> tuple[bool, str]:
    """D-03: lleva la grilla visible al viewport y comprueba que quedó dentro.

    Una captura solo demuestra la tabla si la tabla está en pantalla al
    capturar. Devuelve (ok, detalle); ok=False si no hay grilla visible o si,
    tras desplazarla, no queda completamente dentro del viewport.
    """
    try:
        grids = [g for g in driver.find_elements("css selector", _GRID_SELECTOR) if _is_displayed(g)]
    except Exception as ex:
        return False, f"Error buscando grilla: {ex}"
    if not grids:
        return False, "Sin grilla visible que desplazar"
    grid = grids[0]
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'start'});", grid)
        in_view = bool(driver.execute_script(_IN_VIEWPORT_JS, grid))
    except Exception as ex:
        return False, f"Error desplazando grilla: {ex}"
    if not in_view:
        return False, "Grilla fuera del viewport tras desplazar"
    return True, "Grilla dentro del viewport"


def create_driver() -> webdriver.Edge:
    if webdriver is None or Options is None:
        raise RuntimeError("Selenium no está instalado en este entorno.")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1600,1000")
    options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    driver = webdriver.Edge(options=options)
    driver.set_page_load_timeout(45)
    return driver


_DETAIL_TS_PATTERN = re.compile(
    r"obtenido\s+(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<hh>\d{2}):(?P<mm>\d{2}):(?P<ss>\d{2})\s+UTC"
)
_HEADER_TS_PATTERN = re.compile(
    r"Obtenido del backend:\s*(?P<hh>\d{2}):(?P<mm>\d{2})\s+UTC"
)


@dataclass(frozen=True)
class BackendTimestamp:
    """Marca temporal de obtención extraída del DOM, con precisión y origen explícitos.

    precision='second' proviene del expander detallado (fecha + hora + segundos);
    precision='minute' proviene del header compacto (solo hora:minuto, sin fecha).
    Las dos precisiones NUNCA se consideran comparables entre sí (Directiva 28 /
    Defecto A): un timestamp truncado a minutos no es prueba suficiente frente a uno
    con segundos, aunque ambos puedan representar la misma obtención real.
    """

    raw: str
    precision: str
    date: str | None
    hour: int
    minute: int
    second: int | None


def parse_backend_timestamp(content: str) -> BackendTimestamp | None:
    """Parsea el timestamp de obtención del backend desde el texto plano del DOM.

    Prioriza el patrón detallado (con segundos); si no aparece, intenta el header
    compacto (solo minutos). Nunca mezcla ambos orígenes en una sola lectura.
    """
    m_detail = _DETAIL_TS_PATTERN.search(content)
    if m_detail:
        return BackendTimestamp(
            raw=m_detail.group(0).strip(),
            precision="second",
            date=m_detail.group("date"),
            hour=int(m_detail.group("hh")),
            minute=int(m_detail.group("mm")),
            second=int(m_detail.group("ss")),
        )

    m_hdr = _HEADER_TS_PATTERN.search(content)
    if m_hdr:
        return BackendTimestamp(
            raw=m_hdr.group(0).strip(),
            precision="minute",
            date=None,
            hour=int(m_hdr.group("hh")),
            minute=int(m_hdr.group("mm")),
            second=None,
        )
    return None


def is_confirmed_update(pre: BackendTimestamp | None, post: BackendTimestamp | None) -> bool:
    """Determina si `post` demuestra, sin ambigüedad, una obtención posterior a `pre`.

    Regla central (Directiva 28 / Defecto A): solo se comparan timestamps del MISMO
    origen/precisión. Un cambio de precisión (minuto -> segundos o viceversa) NUNCA
    cuenta como prueba de actualización, porque ambos pueden representar la misma
    obtención real comparada de forma superficial como cadenas. Ante ambigüedad el
    llamador debe seguir esperando y, si expira el tiempo, fallar (nunca PASS).
    """
    if pre is None or post is None:
        return False
    if pre.precision != post.precision:
        return False
    if pre.precision == "second":
        return (pre.date, pre.hour, pre.minute, pre.second) != (post.date, post.hour, post.minute, post.second)
    return (pre.hour, pre.minute) != (post.hour, post.minute)


def extract_backend_timestamp(driver: webdriver.Edge) -> BackendTimestamp | None:
    """Extrae y parsea el timestamp de obtención del backend renderizado en el DOM."""
    try:
        content = driver.execute_script("return document.body.textContent || '';")
    except Exception:
        return None
    return parse_backend_timestamp(content)


_KPI_CARDS_JS = (
    "return Array.from(document.querySelectorAll('div.sapi-card-kpi')).map(function (k) {"
    "  var l = k.querySelector('.sapi-card-kpi__label');"
    "  var v = k.querySelector('.sapi-card-kpi__val');"
    "  return [l ? l.textContent.trim() : null, v ? v.textContent.trim() : null];"
    "});"
)

KPI_CELLS_LABEL = "Celdas evaluadas"


def read_kpi_cards(driver) -> list[tuple[str | None, str | None]]:
    """Pares (etiqueta, valor) de cada tarjeta ``div.sapi-card-kpi`` del panel.

    El panel actual (``app/components/ranking_backend_view.py``) renderiza la
    etiqueta en ``.sapi-card-kpi__label`` *antes* del valor ``.sapi-card-kpi__val``.
    El chequeo anterior buscaba ``div.sapi-v2-kpi`` (ya no existe) o el texto
    ``"50 Celdas evaluadas"`` (orden que el DOM no tiene).
    """
    raw = driver.execute_script(_KPI_CARDS_JS) or []
    cards = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            cards.append((item[0], item[1]))
    return cards


def kpi_cells_ok(cards, expected: int = 50) -> bool:
    """True solo si alguna tarjeta tiene exactamente la etiqueta y el valor esperados."""
    for label, value in cards:
        if label is None or value is None:
            continue
        if label.strip() == KPI_CELLS_LABEL and value.strip() == str(expected):
            return True
    return False


def verify_50_cells_integrity(
    driver: webdriver.Edge,
    backend_url: str | None = None
) -> tuple[bool, str]:
    """Verifica la integridad de las 50 celdas a través de contrato y DOM real.

    NO utiliza constantes fijas ('return 50') ni asume 50 filas tr en Glide Data Grid.
    Comprueba:
    1. Contrato JSON real del backend (/api/v1/ranking): exactamente 50 celdas.
    2. Tarjeta KPI ``div.sapi-card-kpi`` con etiqueta 'Celdas evaluadas' y valor '50'
       (SAPI-137: sustituye el selector obsoleto ``div.sapi-v2-kpi``).
    """
    contract_ok = False
    contract_cells = 0
    if backend_url:
        try:
            req = urllib.request.Request(f"{backend_url}/api/v1/ranking", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                cells = data.get("cells", [])
                contract_cells = len(cells)
                contract_ok = (contract_cells == 50)
        except Exception as ex:
            return False, f"Fallo al consultar contrato backend: {ex}"

    try:
        cards = read_kpi_cards(driver)
    except Exception as ex:
        return False, f"Error comprobando KPI en DOM: {ex}"
    kpi_ok = kpi_cells_ok(cards)

    msg_parts = []
    if backend_url:
        msg_parts.append(f"Contrato JSON: {contract_cells} celdas (PASS={contract_ok})")
    msg_parts.append(
        f"KPI .sapi-card-kpi '{KPI_CELLS_LABEL}'=50: PASS={kpi_ok} (tarjetas={len(cards)})"
    )

    overall = kpi_ok and (contract_ok if backend_url else True)
    return overall, "; ".join(msg_parts)


def wait_for_ranking_visible(
    driver: webdriver.Edge,
    timeout: float = 35.0,
    clock=time.perf_counter,
    sleep=time.sleep,
) -> tuple[float, str]:
    """Espera la aparición inicial visible del ranking y componentes clave de v2."""
    t_start = clock()
    end_time = t_start + timeout

    while clock() < end_time:
        try:
            chips = driver.find_elements("css selector", "span.sapi-v2-chip, div.sapi-v2-panel")
            for el in chips:
                if el.is_displayed():
                    txt = el.text
                    if re.search(r"VP-\d{3}", txt, re.IGNORECASE) or "grupo prioritario" in txt.lower() or "celda seleccionada" in txt.lower():
                        t_visible = clock()
                        return (t_visible - t_start) * 1000.0, txt

            els = driver.find_elements("xpath", "//*[contains(text(), 'VP-')]")
            for el in els:
                if el.is_displayed():
                    t_visible = clock()
                    return (t_visible - t_start) * 1000.0, el.text or "VP"
        except Exception:
            pass
        sleep(0.05)

    raise TimeoutError(f"No se detectó el ranking visible tras {timeout} s")


def wait_for_ranking_update_cycle(
    driver: webdriver.Edge,
    pre_timestamp: BackendTimestamp | None,
    t_start_pre_click: float,
    timeout: float = 30.0,
) -> tuple[float, str, str]:
    """Espera y mide el ciclo completo de actualización post-clic.

    REQUISITOS ESTRICTOS DIRECTIVA 28 (Defecto A):
    - t_start_pre_click fue tomado INMEDIATAMENTE ANTES del clic.
    - Requiere confirmación inequívoca de nuevo timestamp, comparando únicamente
      marcas de IGUAL precisión/origen (is_confirmed_update). Un cambio de formato
      (p. ej. minutos -> segundos) NUNCA se acepta como prueba de actualización.
    - Espera a que el widget de estado/spinner de Streamlit termine.
    - Si timeout expira sin cambio demostrado y comparable, LANZA TimeoutError (FAIL).
      Cero aceptación de DOM viejo o de comparaciones ambiguas entre precisiones.

    Retorna: (latencia_ms, timestamp_post_raw, detalle)
    """
    end_time = t_start_pre_click + timeout

    time.sleep(0.2)  # Breve margen para que el navegador procese el evento del clic

    while time.perf_counter() < end_time:
        is_running = driver.execute_script("""
            const widget = document.querySelector('[data-testid="stStatusWidget"]');
            if (widget && widget.innerText && widget.innerText.includes('Running')) return true;
            const spinner = document.querySelector('.stSpinner');
            if (spinner) return true;
            return false;
        """)

        current_ts = extract_backend_timestamp(driver)
        if is_confirmed_update(pre_timestamp, current_ts) and not is_running:
            t_end = time.perf_counter()
            latency_ms = (t_end - t_start_pre_click) * 1000.0
            pre_raw = pre_timestamp.raw if pre_timestamp else "N/D"
            detail = (
                f"Actualización confirmada (precisión={current_ts.precision}): "
                f"'{pre_raw}' -> '{current_ts.raw}'"
            )
            return latency_ms, current_ts.raw, detail

        time.sleep(0.05)

    # Si expiró el tiempo sin un timestamp comparable y estrictamente NUEVO: FAIL CLOSED
    current_ts = extract_backend_timestamp(driver)
    pre_raw = pre_timestamp.raw if pre_timestamp else "N/D"
    current_raw = current_ts.raw if current_ts else "N/D"
    raise TimeoutError(
        f"FAIL: Timeout de {timeout}s expiró sin confirmar una nueva obtención comparable. "
        f"Timestamp pre-clic: '{pre_raw}', timestamp actual: '{current_raw}'. "
        "El DOM antiguo o un mero cambio de precisión/formato fue RECHAZADO por la política "
        "anti falsos positivos (Directiva 28 / Defecto A)."
    )


def run_negative_test_stale_dom():
    """PRUEBA NEGATIVA OBLIGATORIA (Directiva 26 Criterio 7):

    Simula un DOM estancado donde el timestamp nunca cambia tras el clic.
    Demuestra que wait_for_ranking_update_cycle lanza TimeoutError y NO retorna PASS.
    """
    print("\n--- [PRUEBA NEGATIVA CA4] Verificación de rechazo de DOM estancado ---")

    class MockDriverStaleDOM:
        def __init__(self, fixed_timestamp: str):
            self.fixed_timestamp = fixed_timestamp

        def execute_script(self, script):
            # Simula que Streamlit no está corriendo y el DOM contiene el timestamp fijo
            if "textContent" in script:
                return f"obtenido {self.fixed_timestamp} (cache)"
            return False

    mock_driver = MockDriverStaleDOM("2026-10-15 12:00:00 UTC")
    pre_ts = parse_backend_timestamp(mock_driver.execute_script("return document.body.textContent || '';"))
    t_start = time.perf_counter()

    try:
        # Timeout corto de 1.5 segundos para la prueba unitaria negativa
        wait_for_ranking_update_cycle(mock_driver, pre_ts, t_start, timeout=1.5)
        raise AssertionError("ERROR: El arnés aceptó un DOM estancado! La prueba negativa falló.")
    except TimeoutError as ex:
        print("[PASS NEGATIVE TEST] El arnés rechazó exitosamente el DOM estancado con TimeoutError:")
        print(f"                     Mensaje: {ex}")
        return True


# =====================================================================
# SAPI-137 (HU-90.T2): repeticiones, percentiles y registro sin descartes
# =====================================================================
#
# VALORES POR DEFECTO PROVISIONALES. Ninguno es una decisión metodológica:
# las preguntas P-1..P-6 del plan de medición siguen abiertas para el
# Director. Cada uno es una opción explícita de la línea de comandos y queda
# escrito en run_manifest.json de cada corrida.
#   P-1 calentamiento ............ --warmup 0
#   P-2 fallas en el percentil ... se informan SIEMPRE las dos variantes
#                                  (fallas como +inf y solo muestras ok);
#                                  --failure-policy elige cuál es "primaria"
#                                  y es OBLIGATORIA con --repetitions > 1
#   P-3 carga en frío ............ navegador nuevo por muestra (única opción
#                                  implementada; no reinicia web-v2)
#   P-4 sleep(0.5) de expandir ... --expand-method current (medida por evento en el
#                                  navegador, sin sleep de Python; legacy = intervalo
#                                  idéntico a f8c5218)
#   P-5 orden .................... --order blocks
#   P-6 n ........................ --repetitions 1
# Método de percentil: se calculan SIEMPRE nearest-rank y lineal;
# --percentile-method elige el primario y es OBLIGATORIO con --repetitions > 1.

SCENARIOS = ("cold", "update", "reload", "expand")
SCENARIO_LABELS = {
    "cold": "Carga en frío",
    "update": "Actualizar ranking",
    "reload": "Recarga",
    "expand": "Expandir tabla",
}
ORDERS = ("blocks", "interleaved")
PERCENTILE_METHODS = ("nearest_rank", "linear")
FAILURE_POLICIES = ("as_infinite", "ok_only")
EXPAND_METHODS = ("current", "legacy")
# legacy = intervalo idéntico a f8c5218:scripts/measure_browser_e2e_d21.py:617-623
LEGACY_WAIT_TIMEOUT_S = 5
SCREENSHOT_MODES = ("first", "all", "none")

STATUS_OK = "ok"
STATUS_TIMEOUT = "timeout"
STATUS_ERROR = "error"
STATUS_UNVERIFIED = "content_unverified"
STATUSES = (STATUS_OK, STATUS_TIMEOUT, STATUS_ERROR, STATUS_UNVERIFIED)

ROLE_WARMUP = "warmup"
ROLE_MEASURE = "measure"

LEGACY_EXPAND_SLEEP_S = 0.5
COLD_TIMEOUT_S = 35.0
RELOAD_TIMEOUT_S = 30.0
UPDATE_TIMEOUT_S = 30.0
EXPAND_TIMEOUT_S = 5.0
UPDATE_CLOCK_GAP_S = 1.3

SAMPLE_FIELDS = [
    "seq", "scenario", "role", "iteration", "status", "ui_visible_latency_ms",
    "start_time_iso", "end_time_iso", "pre_timestamp", "post_timestamp",
    "content_verified", "element_verified", "action", "browser_navigation_type",
    "method_detail", "error_type", "error_message", "commit_sha", "tree_sha",
    "candidate_sha", "screenshot", "screenshot_sha256", "notes",
    "timing_source", "timing_resolution",
]

# Fuente del reloj y resolución declarada de cada escenario (Auditor, Orden 09).
# Las dos columnas se escriben en cada fila, también en las de falla.
TIMING_SOURCE_PY = "python_perf_counter"
TIMING_SOURCE_BROWSER = "browser_performance_now"
TIMING_INFO = {
    "cold": (TIMING_SOURCE_PY,
             "sondeo cada 50 ms (+ costo de find_elements); resolución ±50 ms"),
    "reload": (TIMING_SOURCE_PY,
               "sondeo cada 50 ms (+ costo de find_elements); resolución ±50 ms"),
    "update": (TIMING_SOURCE_PY,
               "sleep(0.2) fijo y luego sondeo cada 50 ms; resolución ±50 ms"),
    ("expand", "current"): (
        TIMING_SOURCE_BROWSER,
        "evento en el navegador: clic (listener en captura) y MutationObserver o "
        "requestAnimationFrame; ≤ 1 cuadro (~16,7 ms a 60 Hz); sin sleep en Python",
    ),
    ("expand", "legacy"): (
        TIMING_SOURCE_PY,
        "sleep(0.5) fijo y luego WebDriverWait(driver, 5) con sondeo cada 0,5 s "
        "(igual a f8c5218); resolución +0/+500 ms",
    ),
}


def timing_info(scenario: str, expand_method: str = "current") -> tuple[str, str]:
    """(timing_source, timing_resolution) declarados para un escenario."""
    if scenario == "expand":
        if expand_method not in EXPAND_METHODS:
            raise ValueError(f"--expand-method desconocido: {expand_method!r}")
        return TIMING_INFO[("expand", expand_method)]
    if scenario not in TIMING_INFO:
        raise ValueError(f"Escenario desconocido: {scenario!r}")
    return TIMING_INFO[scenario]


# ---------------------------------------------------------------- percentiles
def _validate_percentile_input(values, p: float) -> list[float]:
    vals = [float(v) for v in values]
    if not vals:
        raise ValueError("No hay muestras para calcular el percentil")
    if any(math.isnan(v) for v in vals):
        raise ValueError("Las muestras no pueden contener NaN")
    if not (0 < p <= 100):
        raise ValueError(f"Percentil fuera de rango (0, 100]: {p}")
    return sorted(vals)


def percentile_nearest_rank(values, p: float) -> float:
    """Percentil por rango más cercano: x_(k) con k = ceil(p/100 · n), índice desde 1.

    Equivale a ``numpy.percentile(x, p, method="inverted_cdf")``. Con n = 30 y
    p = 95, k = 29 (la segunda muestra más alta). Se calcula con aritmética
    exacta (Fraction) para que 0,95 · 20 dé 19 y no 19,000000000000004.
    """
    vals = _validate_percentile_input(values, p)
    k = math.ceil(Fraction(str(p)) * len(vals) / 100)
    return vals[max(k, 1) - 1]


def percentile_linear(values, p: float) -> float:
    """Percentil lineal (``numpy.percentile`` por omisión, ``method="linear"``).

    h = (n - 1) · p / 100; interpola entre x_floor(h) y x_ceil(h). Admite +inf:
    si alguno de los dos vecinos que pesan es +inf, el resultado es +inf.
    """
    vals = _validate_percentile_input(values, p)
    h = (len(vals) - 1) * Fraction(str(p)) / 100
    lo = math.floor(h)
    frac = float(h - lo)
    lower = vals[lo]
    if frac == 0 or lo + 1 >= len(vals):
        return lower
    upper = vals[lo + 1]
    if math.isinf(lower) or math.isinf(upper):
        return math.inf
    return lower + frac * (upper - lower)


PERCENTILE_FUNCS = {
    "nearest_rank": percentile_nearest_rank,
    "linear": percentile_linear,
}


def compute_percentile(values, p: float, method: str) -> float:
    if method not in PERCENTILE_FUNCS:
        raise ValueError(f"Método de percentil desconocido: {method!r}")
    return PERCENTILE_FUNCS[method](values, p)


# ---------------------------------------------------------------- calendario
@dataclass(frozen=True)
class PlannedSample:
    scenario: str
    role: str
    iteration: int


def build_schedule(
    scenarios, repetitions: int, warmup: int, order: str
) -> list[PlannedSample]:
    """Orden de las muestras. Nada se reordena después ni se elimina.

    blocks: por escenario, primero sus ``warmup`` calentamientos y luego sus
    ``repetitions`` muestras. interleaved: ``warmup`` rondas de calentamiento
    y luego ``repetitions`` rondas, cada ronda con un intento por escenario.
    """
    scenarios = tuple(scenarios)
    if not scenarios:
        raise ValueError("Se requiere al menos un escenario")
    unknown = [s for s in scenarios if s not in SCENARIOS]
    if unknown:
        raise ValueError(f"Escenarios desconocidos: {unknown}")
    if len(set(scenarios)) != len(scenarios):
        raise ValueError("Escenarios repetidos")
    if repetitions < 1:
        raise ValueError("--repetitions debe ser >= 1")
    if warmup < 0:
        raise ValueError("--warmup debe ser >= 0")
    if order not in ORDERS:
        raise ValueError(f"Orden desconocido: {order!r}")

    plan: list[PlannedSample] = []
    if order == "blocks":
        for s in scenarios:
            plan += [PlannedSample(s, ROLE_WARMUP, i) for i in range(1, warmup + 1)]
            plan += [PlannedSample(s, ROLE_MEASURE, i) for i in range(1, repetitions + 1)]
    else:
        for i in range(1, warmup + 1):
            plan += [PlannedSample(s, ROLE_WARMUP, i) for s in scenarios]
        for i in range(1, repetitions + 1):
            plan += [PlannedSample(s, ROLE_MEASURE, i) for s in scenarios]
    return plan


# ---------------------------------------------------------------- registro crudo
class IncrementalSampleWriter:
    """CSV de muestras crudas que se escribe fila a fila (flush + fsync).

    Si un escenario falla o el proceso se interrumpe, las filas ya escritas
    quedan en disco. Nunca reescribe ni borra filas.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError(f"{self.path} ya existe: no se sobrescriben muestras")
        self._fh = self.path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=SAMPLE_FIELDS)
        self._writer.writeheader()
        self._sync()
        self.rows: list[dict] = []

    def _sync(self) -> None:
        self._fh.flush()
        try:
            os.fsync(self._fh.fileno())
        except OSError:
            pass

    def write(self, row: dict) -> None:
        clean = {k: row.get(k, "") for k in SAMPLE_FIELDS}
        extra = set(row) - set(SAMPLE_FIELDS)
        if extra:
            raise ValueError(f"Campos no declarados en la fila: {sorted(extra)}")
        self._writer.writerow(clean)
        self._sync()
        self.rows.append(clean)

    def close(self) -> None:
        if not self._fh.closed:
            self._sync()
            self._fh.close()


@dataclass
class SampleOutcome:
    """Lo que devuelve un escenario medido. Si hay excepción, no hay outcome."""

    latency_ms: float
    content_verified: bool
    element_verified: str = ""
    action: str = ""
    browser_navigation_type: str = ""
    pre_timestamp: str = ""
    post_timestamp: str = ""
    method_detail: str = ""
    screenshot: str = ""
    screenshot_sha256: str = ""
    notes: str = ""


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_exception(ex: BaseException) -> str:
    """timeout para TimeoutError y para el TimeoutException de Selenium (que no
    hereda de TimeoutError); error para cualquier otra excepción."""
    if isinstance(ex, TimeoutError) or type(ex).__name__ == "TimeoutException":
        return STATUS_TIMEOUT
    return STATUS_ERROR


def execute_schedule(
    plan,
    sample_fn,
    writer: IncrementalSampleWriter,
    identity: dict | None = None,
    on_failure=None,
    log=print,
    timing_fn=None,
) -> list[dict]:
    """Ejecuta cada muestra planificada y escribe una fila por intento.

    ``sample_fn(planned) -> SampleOutcome``. Un ``TimeoutError`` se registra
    como ``timeout``, cualquier otra ``Exception`` como ``error``; una muestra
    con latencia pero sin contenido verificado, como ``content_unverified``.
    Ninguna fila se descarta y un fallo no detiene las muestras siguientes.
    ``on_failure(planned, ex)`` permite al llamador reiniciar su sesión.
    ``timing_fn(planned) -> (timing_source, timing_resolution)`` rellena las
    columnas de resolución en todas las filas, incluidas las de falla.
    """
    identity = identity or {}
    for seq, planned in enumerate(plan, start=1):
        row = {
            "seq": seq,
            "scenario": planned.scenario,
            "role": planned.role,
            "iteration": planned.iteration,
            "start_time_iso": _utc_iso(),
            "commit_sha": identity.get("commit_sha", ""),
            "tree_sha": identity.get("tree_sha", ""),
            "candidate_sha": identity.get("candidate_sha", ""),
        }
        if timing_fn is not None:
            row["timing_source"], row["timing_resolution"] = timing_fn(planned)
        try:
            out = sample_fn(planned)
        except Exception as ex:  # noqa: BLE001 - toda falla queda como fila
            row.update({
                "status": classify_exception(ex),
                "ui_visible_latency_ms": "",
                "content_verified": False,
                "error_type": type(ex).__name__,
                "error_message": str(ex)[:2000],
            })
            row["end_time_iso"] = _utc_iso()
            writer.write(row)
            log(f"[{row['status'].upper()}] #{seq} {planned.scenario}/{planned.role}"
                f"#{planned.iteration}: {type(ex).__name__}: {ex}")
            if on_failure is not None:
                on_failure(planned, ex)
            continue

        row.update({
            "status": STATUS_OK if out.content_verified else STATUS_UNVERIFIED,
            "ui_visible_latency_ms": repr(float(out.latency_ms)),
            "content_verified": bool(out.content_verified),
            "element_verified": out.element_verified,
            "action": out.action,
            "browser_navigation_type": out.browser_navigation_type,
            "pre_timestamp": out.pre_timestamp,
            "post_timestamp": out.post_timestamp,
            "method_detail": out.method_detail,
            "screenshot": out.screenshot,
            "screenshot_sha256": out.screenshot_sha256,
            "notes": out.notes,
            "error_type": "",
            "error_message": "",
        })
        row["end_time_iso"] = _utc_iso()
        writer.write(row)
        log(f"[{row['status'].upper()}] #{seq} {planned.scenario}/{planned.role}"
            f"#{planned.iteration}: {float(out.latency_ms):.1f} ms")
    return writer.rows


# ---------------------------------------------------------------- resumen
def _row_latency(row: dict) -> float | None:
    raw = row.get("ui_visible_latency_ms", "")
    if raw in ("", None):
        return None
    return float(raw)


def summarize_rows(rows, percentile: float, primary_method: str | None,
                   failure_policy: str | None) -> dict:
    """Resumen por escenario. Los calentamientos se cuentan aparte y no entran
    al percentil. Se informan siempre ambos métodos y ambas políticas de fallas.
    """
    if primary_method is not None and primary_method not in PERCENTILE_METHODS:
        raise ValueError(f"Método de percentil desconocido: {primary_method!r}")
    if failure_policy is not None and failure_policy not in FAILURE_POLICIES:
        raise ValueError(f"Política de fallas desconocida: {failure_policy!r}")

    out: dict = {
        "percentile": percentile,
        "primary_method": primary_method,
        "failure_policy": failure_policy,
        "nearest_rank_formula": "x_(k), k = ceil(p/100 * n), índice desde 1",
        "linear_formula": "numpy linear: h = (n-1)*p/100, interpolación entre vecinos",
        "failure_policies": {
            "as_infinite": "timeout, error y content_unverified se ordenan como +inf",
            "ok_only": "solo muestras con status=ok",
        },
        "scenarios": {},
    }
    pkey = f"p{percentile:g}"
    out["percentile_key"] = pkey
    scenarios = [s for s in SCENARIOS if any(r["scenario"] == s for r in rows)]
    for s in scenarios:
        srows = [r for r in rows if r["scenario"] == s]
        measure = [r for r in srows if r["role"] == ROLE_MEASURE]
        warm = [r for r in srows if r["role"] == ROLE_WARMUP]
        counts = {st: sum(1 for r in measure if r["status"] == st) for st in STATUSES}
        ok_vals = [_row_latency(r) for r in measure if r["status"] == STATUS_OK]
        inf_vals = ok_vals + [math.inf] * (len(measure) - len(ok_vals))

        def _pcts(vals):
            return {
                m: {
                    "p50": compute_percentile(vals, 50, m) if vals else None,
                    pkey: compute_percentile(vals, percentile, m) if vals else None,
                }
                for m in PERCENTILE_METHODS
            }

        entry = {
            "label": SCENARIO_LABELS[s],
            "n_attempted": len(measure),
            "n_ok": counts[STATUS_OK],
            "n_timeout": counts[STATUS_TIMEOUT],
            "n_error": counts[STATUS_ERROR],
            "n_content_unverified": counts[STATUS_UNVERIFIED],
            "n_warmup": len(warm),
            "warmup_statuses": [r["status"] for r in warm],
            "warmup_latencies_ms": [_row_latency(r) for r in warm],
            "min_ok_ms": min(ok_vals) if ok_vals else None,
            "max_ok_ms": max(ok_vals) if ok_vals else None,
            "mean_ok_ms": (sum(ok_vals) / len(ok_vals)) if ok_vals else None,
            "as_infinite": _pcts(inf_vals),
            "ok_only": _pcts(ok_vals),
        }
        if primary_method and failure_policy:
            entry["primary"] = {
                "method": primary_method,
                "failure_policy": failure_policy,
                **entry[failure_policy][primary_method],
            }
        out["scenarios"][s] = entry
    return out


def _json_safe(obj):
    if isinstance(obj, float) and math.isinf(obj):
        return "Infinity"
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def exit_code_for(rows) -> int:
    """0 solo si todos los intentos (medición y calentamiento) dieron ok."""
    if not rows:
        return 1
    return 0 if all(r["status"] == STATUS_OK for r in rows) else 1


# ---------------------------------------------------------------- escenarios
_EXPANDER_XPATH = "//summary[contains(., 'Ver ranking completo')]"
_DETAILS_OPEN_JS = (
    "var d = arguments[0].closest('details'); return d ? d.open : null;"
)
_GRID_IN_DETAILS_JS = (
    "var d = arguments[0].closest('details'); if (!d) return null;"
    "return Array.from(d.querySelectorAll(arguments[1])).some(function (g) {"
    "  return g.getClientRects().length > 0 && g.offsetHeight > 0; });"
)


def _any_grid_visible(driver) -> bool:
    try:
        grids = driver.find_elements("css selector", _GRID_SELECTOR)
    except Exception:
        return False
    return any(_is_displayed(g) for g in grids)


# --- current: medida por evento en el navegador ------------------------------
# _EXPAND_ARM_JS se ejecuta ANTES del clic (fuera del intervalo). Registra un
# listener de clic en fase de captura sobre el <summary> (t_click =
# performance.now() al recibir el evento real del clic nativo de WebDriver), un
# MutationObserver sobre el <details> y, desde el clic, un bucle
# requestAnimationFrame. La primera comprobación que ve una grilla visible
# DENTRO del <details> fija t_visible = performance.now(). Ambos instantes son
# del mismo reloj del navegador: no entra la latencia de ida y vuelta de
# WebDriver ni ningún sleep de Python.
_EXPAND_ARM_JS = r"""
var summary = arguments[0], sel = arguments[1];
var d = summary && summary.closest ? summary.closest('details') : null;
if (!d) { return {armed: false, reason: 'sin <details> alrededor del <summary>'}; }
var st = {t_click: null, t_visible: null, via: null, done: false, cb: null, mo: null};
function visible() {
  return Array.from(d.querySelectorAll(sel)).some(function (g) {
    return g.getClientRects().length > 0 && g.offsetHeight > 0;
  });
}
function snapshot(timedOut) {
  return {t_click: st.t_click, t_visible: st.t_visible, via: st.via, timed_out: !!timedOut};
}
function finish(via) {
  if (st.done) { return; }
  st.t_visible = performance.now();
  st.via = via;
  st.done = true;
  if (st.mo) { st.mo.disconnect(); }
  if (st.cb) { var cb = st.cb; st.cb = null; cb(snapshot(false)); }
}
function check(via) {
  if (st.t_click !== null && !st.done && visible()) { finish(via); }
}
function frame() {
  if (st.done) { return; }
  check('raf');
  if (!st.done) { requestAnimationFrame(frame); }
}
st.snapshot = snapshot;
summary.addEventListener('click', function () {
  if (st.t_click !== null) { return; }
  st.t_click = performance.now();
  requestAnimationFrame(frame);
}, {capture: true, once: true});
st.mo = new MutationObserver(function () { check('mutation'); });
st.mo.observe(d, {subtree: true, childList: true, attributes: true, characterData: true});
window.__sapiExpand = st;
return {armed: true};
"""

# _EXPAND_WAIT_JS (execute_async_script) solo ENTREGA el resultado: los
# instantes ya quedaron fijados por los eventos. El plazo se cuenta desde el clic.
_EXPAND_WAIT_JS = r"""
var timeoutMs = arguments[0], done = arguments[arguments.length - 1];
var st = window.__sapiExpand;
if (!st) { done({error: 'medición no armada'}); return; }
if (st.done) { done(st.snapshot(st.t_visible === null)); return; }
var elapsed = st.t_click === null ? 0 : performance.now() - st.t_click;
var tid = setTimeout(function () {
  st.cb = null;
  st.done = true;
  if (st.mo) { st.mo.disconnect(); }
  done(st.snapshot(true));
}, Math.max(0, timeoutMs - elapsed));
st.cb = function (res) { clearTimeout(tid); done(res); };
"""


def _read_pre_state(driver, summary) -> tuple[object, object, str]:
    pre_open = driver.execute_script(_DETAILS_OPEN_JS, summary)
    pre_grid = driver.execute_script(_GRID_IN_DETAILS_JS, summary, _GRID_SELECTOR)
    return pre_open, pre_grid, f"details.open={pre_open!r}; grilla_visible_previa={pre_grid!r}"


def _measure_expand_current(driver, summary, pre_state: str, timeout: float,
                            clock=time.perf_counter) -> tuple[float, str]:
    armed = driver.execute_script(_EXPAND_ARM_JS, summary, _GRID_SELECTOR)
    if not isinstance(armed, dict) or not armed.get("armed"):
        reason = armed.get("reason") if isinstance(armed, dict) else repr(armed)
        raise RuntimeError(f"No se pudo armar la medición por evento: {reason}")
    driver.set_script_timeout(timeout + 5.0)
    t_py0 = clock()
    summary.click()
    res = driver.execute_async_script(_EXPAND_WAIT_JS, int(round(timeout * 1000)))
    wall_ms = (clock() - t_py0) * 1000.0
    if not isinstance(res, dict) or res.get("error"):
        detail = res.get("error") if isinstance(res, dict) else repr(res)
        raise RuntimeError(f"Resultado inválido de la medición por evento: {detail}")
    t_click, t_visible = res.get("t_click"), res.get("t_visible")
    if t_click is None:
        raise RuntimeError("El navegador no registró el clic en el expander "
                           f"(expand_method=current; {pre_state})")
    if res.get("timed_out") or t_visible is None:
        raise TimeoutError(f"Grilla no visible dentro del expander tras {timeout} s "
                           f"(expand_method=current; {pre_state})")
    latency = float(t_visible) - float(t_click)
    if latency < 0:
        raise RuntimeError(f"Marcas incoherentes: t_visible < t_click ({res!r})")
    detail = (f"expand_method=current; via={res.get('via')}; "
              f"t_click={float(t_click):.3f}; t_visible={float(t_visible):.3f} "
              f"(performance.now); wall_python_ms={wall_ms:.1f}; {pre_state}")
    return latency, detail


def _legacy_wait_factory():
    if WebDriverWait is None or EC is None:
        raise RuntimeError("--expand-method legacy requiere Selenium (WebDriverWait)")
    return WebDriverWait, EC


def _measure_expand_legacy(driver, summary, pre_state: str, clock=time.perf_counter,
                           sleep=time.sleep, wait_factory=None) -> tuple[float, str]:
    """Intervalo idéntico al del padre f8c5218 (scripts/measure_browser_e2e_d21.py:617-623):

        t0 = perf_counter(); click(); sleep(0.5)
        WebDriverWait(driver, 5).until(EC.visibility_of_element_located((CSS, grilla)))
        t = (perf_counter() - t0) * 1000

    Mismo plazo (5 s contados DESPUÉS de la pausa), mismo sondeo por omisión de
    WebDriverWait (0,5 s), mismo localizador global (primer elemento que
    coincide, no "cualquiera visible"). El TimeoutException de Selenium se
    convierte en TimeoutError para clasificarlo como timeout.
    """
    wait_cls, ec = (wait_factory or _legacy_wait_factory)()
    t0 = clock()
    summary.click()
    sleep(LEGACY_EXPAND_SLEEP_S)
    try:
        wait_cls(driver, LEGACY_WAIT_TIMEOUT_S).until(
            ec.visibility_of_element_located(("css selector", _GRID_SELECTOR))
        )
    except Exception as ex:
        if type(ex).__name__ == "TimeoutException":
            raise TimeoutError(
                f"Grilla no visible (legacy, WebDriverWait {LEGACY_WAIT_TIMEOUT_S} s "
                f"tras sleep {LEGACY_EXPAND_SLEEP_S} s; {pre_state})"
            ) from ex
        raise
    latency = (clock() - t0) * 1000.0
    return latency, f"expand_method=legacy (intervalo de f8c5218); {pre_state}"


def measure_expand(driver, expand_method: str, timeout: float = EXPAND_TIMEOUT_S,
                   clock=time.perf_counter, sleep=time.sleep,
                   wait_factory=None) -> tuple[float, str]:
    """Mide la apertura del expander «Ver ranking completo».

    current: exige antes del clic el ``<details>`` cerrado y sin grilla visible
    (si no, la muestra es un error registrado). Mide por evento en el
    navegador: del clic a la primera grilla visible DENTRO de ese expander,
    ambos con ``performance.now()``; ningún sleep de Python dentro del intervalo.
    legacy: intervalo idéntico al arnés padre f8c5218 (ver
    ``_measure_expand_legacy``). El estado previo se informa, pero no invalida.
    """
    if expand_method not in EXPAND_METHODS:
        raise ValueError(f"--expand-method desconocido: {expand_method!r}")
    summaries = driver.find_elements("xpath", _EXPANDER_XPATH)
    if not summaries:
        raise RuntimeError("No se encontró el expander 'Ver ranking completo'")
    summary = summaries[0]
    pre_open, pre_grid, pre_state = _read_pre_state(driver, summary)
    if expand_method == "current":
        if pre_open is not False or pre_grid:
            raise RuntimeError(f"Estado previo inválido del expander ({pre_state})")
        return _measure_expand_current(driver, summary, pre_state, timeout, clock=clock)
    return _measure_expand_legacy(driver, summary, pre_state, clock=clock, sleep=sleep,
                                  wait_factory=wait_factory)


class BrowserScenarioRunner:
    """Ejecuta una muestra de cada escenario contra el panel real.

    cold usa un navegador nuevo por muestra (P-3, provisional). update, reload
    y expand comparten una sesión que se abre sin medir; si una muestra falla,
    la sesión se cierra y la siguiente muestra abre otra (queda en notes).
    """

    def __init__(self, target_url: str, backend_url: str | None, artifacts_dir: Path,
                 expand_method: str, screenshots: str, driver_factory=None,
                 clock=time.perf_counter, sleep=time.sleep, wait_factory=None):
        self.target_url = target_url
        self.backend_url = backend_url
        self.artifacts_dir = Path(artifacts_dir)
        self.expand_method = expand_method
        self.wait_factory = wait_factory
        self.screenshots = screenshots
        self.driver_factory = driver_factory or create_driver
        self.clock = clock
        self.sleep = sleep
        self._session = None
        self._session_resets = 0
        self._shot_taken: set[str] = set()

    # -- sesión compartida
    def _get_session(self):
        if self._session is None:
            drv = self.driver_factory()
            try:
                drv.get(self.target_url)
                wait_for_ranking_visible(drv, timeout=COLD_TIMEOUT_S, clock=self.clock,
                                         sleep=self.sleep)
            except Exception:
                self._quit(drv)
                raise
            self._session = drv
        return self._session

    @staticmethod
    def _quit(drv) -> None:
        try:
            drv.quit()
        except Exception:
            pass

    def reset_session(self, planned=None, ex=None) -> None:
        if self._session is not None:
            self._quit(self._session)
            self._session = None
            self._session_resets += 1

    def close(self) -> None:
        self.reset_session()

    def _screenshot(self, drv, planned) -> tuple[str, str]:
        if self.screenshots == "none":
            return "", ""
        if self.screenshots == "first" and planned.scenario in self._shot_taken:
            return "", ""
        if self.screenshots == "first" and planned.role != ROLE_MEASURE:
            return "", ""
        name = f"{planned.scenario}_{planned.role}_{planned.iteration:03d}.png"
        path = self.artifacts_dir / name
        drv.save_screenshot(str(path))
        self._shot_taken.add(planned.scenario)
        return name, sha256_file(path)

    def __call__(self, planned) -> SampleOutcome:
        handler = {
            "cold": self._cold,
            "update": self._update,
            "reload": self._reload,
            "expand": self._expand,
        }[planned.scenario]
        return handler(planned)

    def _cold(self, planned) -> SampleOutcome:
        drv = self.driver_factory()
        try:
            t0 = self.clock()
            drv.get(self.target_url)
            wait_for_ranking_visible(drv, timeout=COLD_TIMEOUT_S, clock=self.clock,
                                     sleep=self.sleep)
            latency = (self.clock() - t0) * 1000.0
            kpi_ok, kpi_msg = verify_50_cells_integrity(drv, backend_url=self.backend_url)
            body = drv.find_element("tag name", "body").text.lower()
            has_cell = bool(re.search(r"vp-\d{3}", body))
            has_priority = "grupo prioritario" in body
            ts = extract_backend_timestamp(drv)
            nav = get_browser_navigation_type(drv)
            shot, shot_sha = self._screenshot(drv, planned)
            return SampleOutcome(
                latency_ms=latency,
                content_verified=has_cell and has_priority and kpi_ok,
                element_verified=(
                    f"Celda VP={has_cell}; Grupo prioritario={has_priority}; {kpi_msg}"
                ),
                action="driver.get (navegador nuevo)",
                browser_navigation_type=nav,
                post_timestamp=ts.raw if ts else "N/D",
                method_detail="cold=new_browser_per_sample",
                screenshot=shot, screenshot_sha256=shot_sha,
            )
        finally:
            self._quit(drv)

    def _update(self, planned) -> SampleOutcome:
        drv = self._get_session()
        self.sleep(UPDATE_CLOCK_GAP_S)  # fuera del intervalo: asegura un segundo UTC nuevo
        pre = extract_backend_timestamp(drv)
        if not pre:
            raise RuntimeError("No se pudo obtener timestamp pre-clic en el DOM.")
        buttons = drv.find_elements("xpath", "//button[contains(., 'Actualizar ranking')]")
        if not buttons:
            raise RuntimeError("No se encontró el botón 'Actualizar ranking' en la interfaz.")
        t_click = time.perf_counter()
        drv.execute_script("arguments[0].click();", buttons[0])
        latency, post_raw, detail = wait_for_ranking_update_cycle(
            drv, pre, t_click, timeout=UPDATE_TIMEOUT_S
        )
        kpi_ok, kpi_msg = verify_50_cells_integrity(drv, backend_url=self.backend_url)
        shot, shot_sha = self._screenshot(drv, planned)
        return SampleOutcome(
            latency_ms=latency,
            content_verified=kpi_ok and post_raw != pre.raw,
            element_verified=f"{detail}; {kpi_msg}",
            action="click:Actualizar ranking",
            browser_navigation_type="n/a (rerun Streamlit, sin navegación)",
            pre_timestamp=pre.raw, post_timestamp=post_raw,
            method_detail="update=sleep(0.2) dentro del intervalo (wait_for_ranking_update_cycle)",
            screenshot=shot, screenshot_sha256=shot_sha,
            notes=f"session_resets={self._session_resets}",
        )

    def _reload(self, planned) -> SampleOutcome:
        drv = self._get_session()
        pre = extract_backend_timestamp(drv)
        t0 = self.clock()
        drv.refresh()
        wait_for_ranking_visible(drv, timeout=RELOAD_TIMEOUT_S, clock=self.clock,
                                 sleep=self.sleep)
        latency = (self.clock() - t0) * 1000.0
        nav = get_browser_navigation_type(drv)
        ts = extract_backend_timestamp(drv)
        kpi_ok, kpi_msg = verify_50_cells_integrity(drv, backend_url=self.backend_url)
        shot, shot_sha = self._screenshot(drv, planned)
        return SampleOutcome(
            latency_ms=latency,
            content_verified=kpi_ok and nav == "reload",
            element_verified=kpi_msg,
            action="driver.refresh",
            browser_navigation_type=nav,
            pre_timestamp=pre.raw if pre else "N/D",
            post_timestamp=ts.raw if ts else "N/D",
            method_detail="reload=driver.refresh en la sesión compartida",
            screenshot=shot, screenshot_sha256=shot_sha,
            notes=f"session_resets={self._session_resets}",
        )

    def _expand(self, planned) -> SampleOutcome:
        drv = self._get_session()
        # Preparación sin medir: recarga para partir del expander cerrado.
        drv.refresh()
        wait_for_ranking_visible(drv, timeout=RELOAD_TIMEOUT_S, clock=self.clock,
                                 sleep=self.sleep)
        latency, detail = measure_expand(drv, self.expand_method, clock=self.clock,
                                         sleep=self.sleep, wait_factory=self.wait_factory)
        grid_ok, grid_msg = verify_expanded_grid(drv)
        kpi_ok, kpi_msg = verify_50_cells_integrity(drv, backend_url=self.backend_url)
        view_ok, view_msg = scroll_grid_into_view(drv)
        shot, shot_sha = self._screenshot(drv, planned)
        return SampleOutcome(
            latency_ms=latency,
            content_verified=grid_ok and kpi_ok and view_ok,
            element_verified=f"stDataFrame ({grid_msg}; {view_msg}); {kpi_msg}",
            action="click:Ver ranking completo",
            browser_navigation_type="n/a (expander, sin navegación)",
            method_detail=detail,
            screenshot=shot, screenshot_sha256=shot_sha,
            notes=f"session_resets={self._session_resets}",
        )


# ---------------------------------------------------------------- orquestación
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Medición E2E en navegador (CA4 / SAPI-137). Los valores por defecto de "
            "--repetitions, --warmup, --order y --expand-method son PROVISIONALES "
            "(preguntas P-1..P-6 abiertas); con --repetitions > 1 son obligatorios "
            "--percentile-method y --failure-policy."
        )
    )
    parser.add_argument("--url", default="http://127.0.0.1:18509", help="URL de Streamlit")
    parser.add_argument("--backend-url", default="http://127.0.0.1:18099",
                        help="URL de backend Spring Boot")
    parser.add_argument("--artifacts-dir", default=r"artifacts\hito2\d26",
                        help="Directorio de artefactos (debe no contener samples.csv)")
    parser.add_argument("--project-name", default="sapi-astra",
                        help="Nombre del proyecto Docker Compose (solo se registra)")
    parser.add_argument("--candidate-sha", default="",
                        help="SHA candidato declarado; se registra y se compara con HEAD")
    parser.add_argument("--negative-only", action="store_true",
                        help="Ejecutar únicamente la prueba negativa")
    parser.add_argument("--scenarios", default=",".join(SCENARIOS),
                        help="Lista separada por comas: cold,update,reload,expand")
    parser.add_argument("--repetitions", type=int, default=1,
                        help="Muestras medidas por escenario (provisional: 1; P-6)")
    parser.add_argument("--warmup", type=int, default=0,
                        help="Calentamientos por escenario, registrados y excluidos del "
                             "percentil (provisional: 0; P-1)")
    parser.add_argument("--order", choices=ORDERS, default="blocks",
                        help="blocks o interleaved (provisional: blocks; P-5)")
    parser.add_argument("--percentile", type=float, default=95.0,
                        help="Percentil a informar además de p50 (por omisión 95)")
    parser.add_argument("--percentile-method", choices=PERCENTILE_METHODS, default=None,
                        help="Método primario: nearest_rank o linear. Se calculan ambos. "
                             "Obligatorio con --repetitions > 1")
    parser.add_argument("--failure-policy", choices=FAILURE_POLICIES, default=None,
                        help="Variante primaria del percentil frente a fallas (P-2). Se "
                             "calculan ambas. Obligatorio con --repetitions > 1")
    parser.add_argument("--expand-method", choices=EXPAND_METHODS, default="current",
                        help="current: medida por evento en el navegador (clic y "
                             "MutationObserver/requestAnimationFrame con performance.now), "
                             "sin ningún sleep de Python en el intervalo; grilla dentro del "
                             "expander. legacy: intervalo idéntico a f8c5218 (sleep(0.5) + "
                             "WebDriverWait(driver, 5), sondeo 0,5 s). Provisional: current; P-4")
    parser.add_argument("--screenshots", choices=SCREENSHOT_MODES, default="first",
                        help="Capturas fuera del intervalo medido: first, all o none")
    return parser


def validate_args(args) -> list[str]:
    """Errores de configuración; lista vacía si la configuración es válida."""
    errors = []
    if args.repetitions < 1:
        errors.append("--repetitions debe ser >= 1")
    if args.warmup < 0:
        errors.append("--warmup debe ser >= 0")
    if not (0 < args.percentile <= 100):
        errors.append("--percentile debe estar en (0, 100]")
    scen = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    if not scen:
        errors.append("--scenarios vacío")
    bad = [s for s in scen if s not in SCENARIOS]
    if bad:
        errors.append(f"--scenarios desconocidos: {bad}")
    if len(set(scen)) != len(scen):
        errors.append("--scenarios repetidos")
    if args.repetitions > 1 and args.percentile_method is None:
        errors.append("--percentile-method es obligatorio con --repetitions > 1 "
                      "(no hay método por omisión)")
    if args.repetitions > 1 and args.failure_policy is None:
        errors.append("--failure-policy es obligatorio con --repetitions > 1 "
                      "(no hay política por omisión)")
    return errors


def _tool_versions() -> dict:
    versions = {"python": sys.version.split()[0], "platform": platform.platform()}
    try:
        import selenium  # noqa: F401

        versions["selenium"] = getattr(selenium, "__version__", "unknown")
    except ImportError:
        versions["selenium"] = None
    return versions


def run_measurement(args, artifacts_dir: Path, sample_fn=None, log=print) -> int:
    """Corre el calendario completo y devuelve el código de salida.

    Escribe en ``artifacts_dir``: run_manifest.json (al inicio), samples.csv
    (fila a fila) y summary.json (al final, también si hubo fallas o una
    interrupción). ``sample_fn`` se inyecta en las pruebas unitarias; si es
    None se usa el navegador real.
    """
    errors = validate_args(args)
    if errors:
        raise ValueError("; ".join(errors))

    if not run_negative_test_stale_dom():
        raise RuntimeError("La prueba negativa obligatoria de CA4 falló. Abortando.")

    repo_root = Path(__file__).resolve().parents[1]
    commit_sha, tree_sha = get_git_identities(repo_root)
    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    plan = build_schedule(scenarios, args.repetitions, args.warmup, args.order)

    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    identity = {"commit_sha": commit_sha, "tree_sha": tree_sha,
                "candidate_sha": args.candidate_sha}
    manifest = {
        "started_utc": _utc_iso(),
        "argv": sys.argv,
        "config": {
            "url": args.url, "backend_url": args.backend_url,
            "project_name": args.project_name, "scenarios": scenarios,
            "repetitions": args.repetitions, "warmup": args.warmup, "order": args.order,
            "percentile": args.percentile, "percentile_method": args.percentile_method,
            "failure_policy": args.failure_policy, "expand_method": args.expand_method,
            "screenshots": args.screenshots, "cold_mode": "new_browser_per_sample",
        },
        "provisional_defaults_note": (
            "repetitions=1, warmup=0, order=blocks, expand_method=current y "
            "cold_mode=new_browser_per_sample son provisionales (P-1..P-6 abiertas)"
        ),
        "identity": identity,
        "candidate_matches_head": (
            (args.candidate_sha == commit_sha) if args.candidate_sha else None
        ),
        "containers": get_container_identities(args.project_name),
        "tools": _tool_versions(),
        "planned_samples": len(plan),
    }
    (artifacts_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    writer = IncrementalSampleWriter(artifacts_dir / "samples.csv")
    runner = None
    if sample_fn is None:
        runner = BrowserScenarioRunner(
            args.url, args.backend_url, artifacts_dir, args.expand_method, args.screenshots)
        sample_fn = runner
    rows: list[dict] = []
    interrupted = None
    try:
        rows = execute_schedule(
            plan, sample_fn, writer, identity=identity,
            on_failure=runner.reset_session if runner else None, log=log,
            timing_fn=lambda planned: timing_info(planned.scenario, args.expand_method))
    except BaseException as ex:  # interrupción: se conserva lo escrito
        interrupted = f"{type(ex).__name__}: {ex}"
        rows = writer.rows
        raise
    finally:
        writer.close()
        if runner is not None:
            runner.close()
        summary = summarize_rows(rows, args.percentile, args.percentile_method,
                                 args.failure_policy)
        summary.update({
            "finished_utc": _utc_iso(),
            "planned_samples": len(plan),
            "recorded_samples": len(rows),
            "interrupted": interrupted,
            "samples_csv": "samples.csv",
            "samples_csv_sha256": sha256_file(artifacts_dir / "samples.csv"),
            "exit_code": 1 if interrupted else exit_code_for(rows),
        })
        (artifacts_dir / "summary.json").write_text(
            json.dumps(_json_safe(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    return exit_code_for(rows) if len(rows) == len(plan) else 1


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.negative_only:
        ok = run_negative_test_stale_dom()
        sys.exit(0 if ok else 1)

    errors = validate_args(args)
    if errors:
        parser.error("; ".join(errors))

    artifacts_path = Path(args.artifacts_dir)
    if not artifacts_path.is_absolute():
        artifacts_path = Path(__file__).resolve().parents[1] / artifacts_path

    sys.exit(run_measurement(args, artifacts_path))


if __name__ == "__main__":
    main()
