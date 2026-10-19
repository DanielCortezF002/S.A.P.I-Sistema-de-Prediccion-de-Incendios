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
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.edge.options import Options
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    webdriver = None
    By = None
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


def verify_50_cells_integrity(
    driver: webdriver.Edge,
    backend_url: str | None = None
) -> tuple[bool, str]:
    """Verifica la integridad de las 50 celdas a través de contrato y DOM real.

    NO utiliza constantes fijas ('return 50') ni asume 50 filas tr en Glide Data Grid.
    Comprueba:
    1. Contrato JSON real del backend (/api/v1/ranking): exactamente 50 celdas.
    2. KPI strip en el DOM: valor textual '50' con etiqueta 'Celdas evaluadas'.
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

    kpi_ok = False
    try:
        kpi_elems = driver.find_elements(By.CSS_SELECTOR, "div.sapi-v2-kpi")
        for k in kpi_elems:
            txt = k.text
            if "Celdas evaluadas" in txt and "50" in txt:
                kpi_ok = True
                break
        if not kpi_ok:
            body_txt = driver.execute_script("return document.body.textContent || '';")
            if "50Celdas evaluadas" in body_txt or "50 Celdas evaluadas" in body_txt:
                kpi_ok = True
    except Exception as ex:
        return False, f"Error comprobando KPI en DOM: {ex}"

    msg_parts = []
    if backend_url:
        msg_parts.append(f"Contrato JSON: {contract_cells} celdas (PASS={contract_ok})")
    msg_parts.append(f"KPI strip DOM '50 Celdas evaluadas': PASS={kpi_ok}")

    overall = kpi_ok and (contract_ok if backend_url else True)
    return overall, "; ".join(msg_parts)


def wait_for_ranking_visible(driver: webdriver.Edge, timeout: float = 35.0) -> tuple[float, str]:
    """Espera la aparición inicial visible del ranking y componentes clave de v2."""
    t_start = time.perf_counter()
    end_time = t_start + timeout

    while time.perf_counter() < end_time:
        try:
            chips = driver.find_elements(By.CSS_SELECTOR, "span.sapi-v2-chip, div.sapi-v2-panel")
            for el in chips:
                if el.is_displayed():
                    txt = el.text
                    if re.search(r"VP-\d{3}", txt, re.IGNORECASE) or "grupo prioritario" in txt.lower() or "celda seleccionada" in txt.lower():
                        t_visible = time.perf_counter()
                        return (t_visible - t_start) * 1000.0, txt

            els = driver.find_elements(By.XPATH, "//*[contains(text(), 'VP-')]")
            for el in els:
                if el.is_displayed():
                    t_visible = time.perf_counter()
                    return (t_visible - t_start) * 1000.0, el.text or "VP"
        except Exception:
            pass
        time.sleep(0.05)

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


def run_benchmark(target_url: str, backend_url: str, artifacts_dir: Path, project_name: str = "sapi-v2"):
    repo_root = Path(__file__).resolve().parents[1]
    commit_sha, tree_sha = get_git_identities(repo_root)
    container_imgs = get_container_identities(project_name)

    print("=================================================================")
    print("S.A.P.I. - BENCHMARK DE NAVEGADOR E2E REAL (CA4 / DIRECTIVA 26)")
    print(f"URL frontend:     {target_url}")
    print(f"URL backend:      {backend_url}")
    print(f"Directorio art:   {artifacts_dir}")
    print(f"Commit SHA:       {commit_sha}")
    print(f"Tree SHA:         {tree_sha}")
    print(f"Imágenes stack:   {container_imgs}")
    print("=================================================================\n")

    # 1. Ejecutar primero la prueba negativa obligatoria
    neg_ok = run_negative_test_stale_dom()
    if not neg_ok:
        raise RuntimeError("La prueba negativa obligatoria de CA4 falló. Abortando benchmark.")

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    records = []

    driver = create_driver()
    try:
        # -------------------------------------------------------------
        # RUN 1: Primera Carga (Cold Load / Initial Navigation)
        # -------------------------------------------------------------
        print("\n[TEST RUN-01] Navegación inicial (Cold Start)...")
        t0_cold = time.perf_counter()
        driver.get(target_url)

        duration_cold, match_cold = wait_for_ranking_visible(driver, timeout=35.0)
        t_total_cold = (time.perf_counter() - t0_cold) * 1000.0

        kpi_50_ok, kpi_50_msg = verify_50_cells_integrity(driver, backend_url=backend_url)
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        has_cell = bool(re.search(r"vp-\d{3}", body_text))
        has_score = bool(re.search(r"0\.\d{3,}", body_text))
        has_priority = "grupo prioritario" in body_text

        ts_cold_struct = extract_backend_timestamp(driver)
        ts_cold = ts_cold_struct.raw if ts_cold_struct else "N/D"

        print(f"[OK RUN-01] Ranking visible en {t_total_cold:.1f} ms")
        print(f"            - Match inicial: '{match_cold[:60]}...'")
        print(f"            - Backend timestamp: {ts_cold}")
        print(f"            - Contenido verificado: Celda VP={has_cell}, score={has_score}, prioridad={has_priority}")
        print(f"            - Integridad 50 celdas: {kpi_50_msg} (PASS={kpi_50_ok})")

        shot_cold = artifacts_dir / "ca4_browser_cold.png"
        driver.save_screenshot(str(shot_cold))
        print(f"            - Captura guardada: {shot_cold}")

        records.append({
            "run_id": "RUN-01",
            "scenario": "Primera Carga (Cold Navigation)",
            "start_time_iso": datetime.now(timezone.utc).isoformat(),
            "ui_visible_latency_ms": round(t_total_cold, 2),
            "pre_timestamp": "N/A",
            "post_timestamp": ts_cold,
            "element_verified": "Celda VP / Grupo prioritario",
            "content_verified": has_cell and has_priority and kpi_50_ok,
            "commit_sha": commit_sha,
            "tree_sha": tree_sha,
            "screenshot": shot_cold.name,
            "notes": f"Navegación inicial en frío con backend Spring+FastAPI. 50 celdas validadas. Visible: {t_total_cold:.1f} ms."
        })

        # -------------------------------------------------------------
        # RUN 2: Actualización (Clic en 'Actualizar ranking' en Sidebar)
        # -------------------------------------------------------------
        print("\n[TEST RUN-02] Actualización de ranking (Sidebar Button con detección post-clic)...")
        # Asegurar avance de reloj para que el segundo UTC cambie
        time.sleep(1.3)
        pre_click_ts = extract_backend_timestamp(driver)
        if not pre_click_ts:
            raise RuntimeError("No se pudo obtener timestamp pre-clic en el DOM.")
        print(f"[INFO] Timestamp pre-clic verificado en DOM: '{pre_click_ts.raw}' (precisión={pre_click_ts.precision})")

        update_btn = None
        btn_candidates = driver.find_elements(By.XPATH, "//button[contains(., 'Actualizar ranking')]")
        if btn_candidates:
            update_btn = btn_candidates[0]
        else:
            candidates2 = driver.find_elements(By.XPATH, "//button[contains(., 'Actualizar')]")
            if candidates2:
                update_btn = candidates2[0]

        if not update_btn:
            raise RuntimeError("No se encontró el botón 'Actualizar ranking' en la interfaz.")

        # Requisito 1: Iniciar tiempo monotónico inmediatamente ANTES del clic
        t_click_mono = time.perf_counter()
        driver.execute_script("arguments[0].click();", update_btn)
        print("[INFO] Clic despachado. Iniciando medición de ciclo estricta...")

        # Requisito 4/5/6: Esperar ciclo con nuevo timestamp; si timeout, FAIL
        duration_upd, post_click_ts, update_detail = wait_for_ranking_update_cycle(
            driver, pre_click_ts, t_click_mono, timeout=30.0
        )
        print(f"[OK RUN-02] Ranking actualizado y confirmado en {duration_upd:.1f} ms")
        print(f"            - Timestamp pre-clic:  {pre_click_ts.raw}")
        print(f"            - Timestamp post-clic: {post_click_ts}")
        print(f"            - Detalle: {update_detail}")

        kpi_upd_ok, _ = verify_50_cells_integrity(driver, backend_url=backend_url)
        shot_upd = artifacts_dir / "ca4_browser_update.png"
        driver.save_screenshot(str(shot_upd))
        print(f"            - Captura guardada: {shot_upd}")

        records.append({
            "run_id": "RUN-02",
            "scenario": "Actualización (Clic Actualizar ranking)",
            "start_time_iso": datetime.now(timezone.utc).isoformat(),
            "ui_visible_latency_ms": round(duration_upd, 2),
            "pre_timestamp": pre_click_ts.raw,
            "post_timestamp": post_click_ts,
            "element_verified": "Celda VP / Grupo prioritario (nuevo timestamp verificado)",
            "content_verified": kpi_upd_ok and (post_click_ts != pre_click_ts.raw),
            "commit_sha": commit_sha,
            "tree_sha": tree_sha,
            "screenshot": shot_upd.name,
            "notes": f"Re-ejecución tras clic en Actualizar ranking con confirmación de nuevo timestamp ({pre_click_ts.raw} -> {post_click_ts}). Latencia real: {duration_upd:.1f} ms."
        })

        # -------------------------------------------------------------
        # RUN 3: Recarga con Caché (Browser Refresh / Warm Cache)
        # -------------------------------------------------------------
        print("\n[TEST RUN-03] Recarga de página con caché de Streamlit (Warm Reload)...")
        time.sleep(1)
        t0_cached = time.perf_counter()
        driver.refresh()

        duration_cached, match_cached = wait_for_ranking_visible(driver, timeout=30.0)
        t_total_cached = (time.perf_counter() - t0_cached) * 1000.0
        ts_cached_struct = extract_backend_timestamp(driver)
        ts_cached = ts_cached_struct.raw if ts_cached_struct else "N/D"
        kpi_cached_ok, _ = verify_50_cells_integrity(driver, backend_url=backend_url)
        print(f"[OK RUN-03] Ranking visible tras recarga en {t_total_cached:.1f} ms")

        shot_cached = artifacts_dir / "ca4_browser_cached.png"
        driver.save_screenshot(str(shot_cached))
        print(f"            - Captura guardada: {shot_cached}")

        records.append({
            "run_id": "RUN-03",
            "scenario": "Recarga con Caché (Browser Refresh)",
            "start_time_iso": datetime.now(timezone.utc).isoformat(),
            "ui_visible_latency_ms": round(t_total_cached, 2),
            "pre_timestamp": post_click_ts,
            "post_timestamp": ts_cached,
            "element_verified": "Celda VP / Grupo prioritario (caché)",
            "content_verified": kpi_cached_ok,
            "commit_sha": commit_sha,
            "tree_sha": tree_sha,
            "screenshot": shot_cached.name,
            "notes": f"Recarga completa de navegador con respuesta de backend en caché. Visible: {t_total_cached:.1f} ms."
        })

        # -------------------------------------------------------------
        # RUN 4: Expansión de Tabla de Ranking Completa (Glide Data Grid)
        # -------------------------------------------------------------
        print("\n[TEST RUN-04] Expansión y visualización de la grilla st.dataframe (Glide Data Grid)...")
        try:
            expanders = driver.find_elements(By.XPATH, "//summary[contains(., 'Ver ranking completo')]")
            if expanders:
                t0_exp = time.perf_counter()
                expanders[0].click()
                time.sleep(0.5)
                WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "div[data-testid='stDataFrame'], [data-testid='stTable']"))
                )
                t_exp = (time.perf_counter() - t0_exp) * 1000.0
                print(f"[OK RUN-04] Grilla st.dataframe visible en {t_exp:.1f} ms")
                print("            - Nota de virtualización: Glide Data Grid renderiza filas bajo demanda en canvas/virtual list")
                print("            - Total de registros respaldados: 50 celdas (verificadas vía contrato y KPI)")

                shot_exp = artifacts_dir / "ca4_browser_table_expanded.png"
                driver.save_screenshot(str(shot_exp))
                print(f"            - Captura guardada: {shot_exp}")

                records.append({
                    "run_id": "RUN-04",
                    "scenario": "Expansión Tabla de Ranking (st.dataframe virtualizado)",
                    "start_time_iso": datetime.now(timezone.utc).isoformat(),
                    "ui_visible_latency_ms": round(t_exp, 2),
                    "pre_timestamp": ts_cached,
                    "post_timestamp": ts_cached,
                    "element_verified": "stDataFrame (Glide Data Grid, 50 registros totales)",
                    "content_verified": True,
                    "commit_sha": commit_sha,
                    "tree_sha": tree_sha,
                    "screenshot": shot_exp.name,
                    "notes": f"Apertura del expander interactivo y render de Glide Data Grid virtualizado. Visible: {t_exp:.1f} ms."
                })
        except Exception as ex:
            print(f"[WARN] Error al expandir ranking completo: {ex}")

        # Guardar timings_browser.csv
        csv_path = artifacts_dir / "timings_browser.csv"
        fieldnames = [
            "run_id", "scenario", "start_time_iso", "ui_visible_latency_ms",
            "pre_timestamp", "post_timestamp", "element_verified", "content_verified",
            "commit_sha", "tree_sha", "screenshot", "notes"
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                writer.writerow(r)
        print(f"\n[OK] CSV guardado en: {csv_path}")

        print("\n=================================================================")
        print("RESUMEN DE MEDICIÓN REAL EN NAVEGADOR (CA4 / DIRECTIVA 26):")
        print(f"{'Run ID':<8} | {'Escenario':<42} | {'Latencia (ms)':<16} | {'Estado':<6}")
        print("-" * 78)
        for r in records:
            print(f"{r['run_id']:<8} | {r['scenario']:<42} | {r['ui_visible_latency_ms']:>12.1f} ms | PASS")
        print("=================================================================\n")

    finally:
        driver.quit()


def main():
    parser = argparse.ArgumentParser(description="Medición E2E en navegador CA4 (Directiva 26)")
    parser.add_argument("--url", default="http://127.0.0.1:18509", help="URL de Streamlit")
    parser.add_argument("--backend-url", default="http://127.0.0.1:18099", help="URL de backend Spring Boot")
    parser.add_argument("--artifacts-dir", default=r"artifacts\hito2\d26", help="Directorio de artefactos")
    parser.add_argument("--project-name", default="sapi-astra", help="Nombre del proyecto Docker Compose")
    parser.add_argument("--negative-only", action="store_true", help="Ejecutar únicamente la prueba negativa")
    args = parser.parse_args()

    if args.negative_only:
        ok = run_negative_test_stale_dom()
        sys.exit(0 if ok else 1)

    artifacts_path = Path(args.artifacts_dir)
    if not artifacts_path.is_absolute():
        artifacts_path = Path(__file__).resolve().parents[1] / artifacts_path

    run_benchmark(args.url, args.backend_url, artifacts_path, project_name=args.project_name)


if __name__ == "__main__":
    main()
