"""Recorrido Edge de una sola pasada sobre sapi-h3-518c0b5 (orden 25-11, punto 3).

Solo lectura: abre el panel, lee, selecciona una celda, pulsa «Actualizar ranking»
una vez y despliega la grilla. No para ni reinicia servicios. Un usuario, sin carga.
Ejecutado en el computador local, no en ambiente desplegado.

Uso: py recorrido_edge_h3.py [URL]   (por defecto http://127.0.0.1:18501/)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18501/"
steps: list[dict] = []


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record(page, name: str, focus=None) -> str:
    if focus is not None:
        focus.scroll_into_view_if_needed()
    page.screenshot(path=ROOT / f"{name}.png", timeout=15000)
    text = page.locator("body").inner_text()
    with (ROOT / f"{name}.txt").open("w", encoding="utf8") as log:
        print(now(), page.url, file=log)
        print(text, file=log)
    return text


def step(name: str, fn) -> None:
    started = now()
    try:
        observed = fn()
        steps.append({"paso": name, "inicio_utc": started, "fin_utc": now(), "ok": True, "observado": observed})
    except Exception as exc:  # se registra y se sigue: el informe marca FALLA
        steps.append({"paso": name, "inicio_utc": started, "fin_utc": now(), "ok": False,
                      "observado": f"{type(exc).__name__}: {str(exc).splitlines()[0][:300]}"})


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    page.set_default_timeout(45000)
    console_errors: list[str] = []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    meta = {"inicio_utc": now(), "edge": browser.version, "viewport": "1600x1000", "url": URL}

    selector = page.get_by_role("combobox", name="Seleccionar celda", exact=False)
    update = page.get_by_role("button", name="Actualizar ranking")

    def abrir():
        page.goto(URL, timeout=60000)
        selector.wait_for(timeout=90000)
        t = record(page, "01-abrir")
        return f"selector visible; traceback={'Traceback' in t}"

    def leer():
        d = page.locator(".sapi-v2-disclaimer").last
        t = record(page, "02-leer-ranking", d)
        return {"disclaimer": d.inner_text()[:400], "menciona_probabilidad_calibrada": "calibrada" in t,
                "menciona_historico": ("HISTÓRICO" in t.upper())}

    def seleccionar():
        selector.click()
        opts = page.get_by_role("option")
        chosen = opts.nth(1).inner_text()
        opts.nth(1).click()
        page.locator(".sapi-selected-cell-id").filter(has_text=chosen).wait_for()
        record(page, "03-seleccionar", selector)
        return f"celda elegida {chosen}"

    def datos():
        card = page.locator(".sapi-selected-cell-id").first
        record(page, "04-datos", card)
        return f"ficha {card.inner_text()}"

    def actualizar():
        side = page.get_by_role("button").filter(has_text="keyboard_double_arrow_right")
        if side.count() > 0 and side.first.is_visible():
            side.first.click()
        update.click()
        page.wait_for_timeout(2500)
        selector.wait_for(timeout=90000)
        record(page, "05-actualizar", update)
        return "pulsado una vez; selector visible tras la consulta"

    def grilla():
        page.locator("summary").filter(has_text="Ver ranking completo").click()
        grid = page.locator('[data-testid="stDataFrame"]').last
        grid.wait_for()
        t = record(page, "06-grilla", grid)
        return {"filtro_50": "50 celdas" in t}

    for name, fn in [("1. Abrir", abrir), ("2. Leer ranking", leer), ("3. Seleccionar", seleccionar),
                     ("4. Entender datos", datos), ("5. Actualizar", actualizar), ("6a. Abrir grilla", grilla)]:
        step(name, fn)
    meta["fin_utc"] = now()
    meta["errores_consola"] = console_errors[:20]
    browser.close()

(ROOT / "resultado.json").write_text(json.dumps({"meta": meta, "pasos": steps}, ensure_ascii=False, indent=2),
                                     encoding="utf8")
print(json.dumps({"meta": meta, "pasos": steps}, ensure_ascii=False, indent=2))
