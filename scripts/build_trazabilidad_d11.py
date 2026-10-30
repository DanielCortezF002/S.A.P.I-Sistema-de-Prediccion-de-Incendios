"""D11 (F2): reconstruye docs/hito2/TRAZABILIDAD_HU_CA_EVIDENCIAS.md.

Fuentes: Jira (export TSV de solo lectura del 30-10-2026,
docs/hito2/fuentes/jira_sprint2_20261030.tsv) para título, SP, estado y sprint;
docs/hito2/requerimientos-sprint2.md §3 para los criterios de aceptación; el árbol del
candidato para comprobar que cada verificación o evidencia citada existe.
Uso: python scripts/build_trazabilidad_d11.py <repo> <jira.tsv> <sha_base>
"""

import csv
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

repo, jira_tsv, base_sha = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
req = (repo / "docs/hito2/requerimientos-sprint2.md").read_text(encoding="utf-8")

jira = {}
with open(jira_tsv, encoding="utf-8") as fh:
    for row in csv.DictReader(fh, delimiter="\t"):
        sp = re.search(r"'value': (\d+)", row["sp"])
        in_s2 = "'name': 'Sprint 2'" in row["sprints"]
        jira[row["key"]] = {
            "title": row["summary"],
            "sp": int(sp.group(1)) if sp else None,
            "status": row["status"],
            "sprint2": in_s2,
            "resolved": row["resolutiondate"],
        }

tracked = set(
    subprocess.run(
        ["git", "-C", str(repo), "ls-files"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
)
tracked_names = {Path(p).stem for p in tracked}
test_sources = "\n".join(
    (repo / p).read_text(encoding="utf-8", errors="ignore")
    for p in tracked
    if p.startswith("tests/") and p.endswith(".py")
)


def check_token(tok: str) -> str:
    """'sí', 'no' o '' (no verificable automáticamente) para un elemento citado."""
    tok = tok.strip().split(" ")[0].rstrip(",;:")
    if tok.startswith("/") or (tok.startswith("./") and "/" not in tok[2:]):
        return ""  # endpoint HTTP o comando (p. ej. `/health`, `./mvnw`), no un archivo
    if "/" in tok and not tok.startswith(("http", "GET", "POST")):
        path = tok.lstrip("./").rstrip("/")
        if "<" in path:  # plantilla, p. ej. artifacts/hito2/e2e/<ts>/
            prefix = path.split("<")[0]
            return "sí" if any(p.startswith(prefix) for p in tracked) else "no"
        if "*" in path:
            return "sí" if fnmatch.filter(tracked, path) else "no"
        if path in tracked or any(p.startswith(path + "/") for p in tracked):
            return "sí"
        return "no"
    if re.fullmatch(r"[A-Z][A-Za-z0-9]+Tests?", tok):
        return "sí" if tok in tracked_names else "no"
    if re.fullmatch(r"test_[a-z0-9_]+", tok):
        return "sí" if f"def {tok}" in test_sources or tok in tracked_names else "no"
    return ""


def verify(cell: str) -> str:
    marks = [check_token(t) for t in re.findall(r"`([^`]+)`", cell)]
    marks = [m for m in marks if m]
    if not marks:
        return "manual"
    return "presente" if all(m == "sí" for m in marks) else (
        "ausente" if not any(m == "sí" for m in marks) else "parcial"
    )


ca_rows = {}
for line in req.splitlines():
    m = re.match(r"^\| (SAPI-\d+)\.(CA\d+) \|(.*)$", line)
    if not m:
        continue
    cells = [c.strip() for c in m.group(3).rstrip("|").split("|")]
    while len(cells) < 5:
        cells.append("")
    crit, rn, verif, evid, estado = cells[:5]
    ca_rows.setdefault(m.group(1), []).append(
        (f"{m.group(1)}.{m.group(2)}", crit, rn, verif, evid, estado, verify(verif + " " + evid))
    )

# Backlog comprometido y congelado (requerimientos §2): una fila por HU con SP numérico.
# La fila «SAPI-64, 65, 68 … Won't» no tiene SP y queda fuera por construcción.
backlog = {}
in_s2_table = False
for line in req.splitlines():
    if line.startswith("## 2."):
        in_s2_table = True
    elif line.startswith("## 3."):
        break
    m = re.match(r"^\| (SAPI-\d+) \|(?:[^|]*\|){3} (\d+) \|", line)
    if in_s2_table and m:
        backlog[m.group(1)] = int(m.group(2))

# Ajustes conocidos en F2 (verificados en este candidato); no reemplazan el estado de 08-10.
F2_NOTES = {
    "SAPI-61.CA2": "F2/D2: la UI ya no consulta la API de DMC; nueva regla en "
    "`tests/test_architecture.py`. PENDIENTE: la franja meteorológica aún lee la última "
    "ingesta en `data/raw` sin pasar por el backend (deuda S3).",
    "SAPI-61.CA3": "F2/D15: selector «Vista del mapa» restaurado; prueba original de main "
    "repuesta en `tests/test_sapi61_http_stub.py`.",
    "SAPI-61.CA5": "F2/D15: modos Prioridades y Todas las celdas cubiertos en "
    "`tests/test_ranking_backend_view.py`.",
    "SAPI-66.CA5": "F2/D4: IT-13 PASS en entorno limpio sin `.env` sobre el candidato "
    "(Windows local; falta CI Linux). Ver acta F2.",
}

s2 = [k for k, v in jira.items() if v["sprint2"]]
s2_sp = sum(jira[k]["sp"] or 0 for k in s2)
out = []
w = out.append
w("# Trazabilidad HU → CA → Verificación → Evidencia — Sprint 2 / Hito 2")
w("")
w(f"**Versión:** F2, 30-10-2026, reconstruida sobre el candidato `release/s2-baseline` "
  f"(base `{base_sha[:7]}`). **Resolución:** D11.")
w("")
w("**Fuentes y reglas:**")
w("- Título, story points, estado y sprint: **Jira** (proyecto SAPI, lectura del 30-10-2026). "
  "No se escribió en Jira.")
w("- Criterios de aceptación, reglas de negocio y verificación prevista: "
  "`docs/hito2/requerimientos-sprint2.md` §3 (literal de Jira, 08-10-2026).")
w("- *Estado registrado* es el que figura en `requerimientos-sprint2.md` a esa fecha; no se "
  "recertificó cada criterio en esta reconstrucción.")
w("- *Verificación en el candidato* comprueba de forma automática que los archivos, clases o "
  "pruebas citados existen en este árbol (`presente`, `parcial`, `ausente`); `manual` indica "
  "una verificación sin artefacto comprobable por nombre.")
w("- La versión anterior de este archivo (commit `8c0f4a2`) se retiró por títulos y SP que no "
  "coinciden con Jira; queda archivada en `docs/hito2/historico/` y en el historial de Git.")
w("")
w("## 1. Conciliación con Jira")
w("")
only_backlog = sorted(set(backlog) - set(s2), key=lambda k: int(k.split("-")[1]))
only_sprint = sorted(set(s2) - set(backlog), key=lambda k: int(k.split("-")[1]))
w("Se conservan dos cifras distintas, ambas válidas para lo que miden:")
w("")
w("| Cifra | Historias | SP | Fuente |")
w("|---|---:|---:|---|")
w(f"| Backlog comprometido y congelado | {len(backlog)} | {sum(backlog.values())} | "
  "`requerimientos-sprint2.md` §2 (08-10-2026); base de las cifras del Informe Hito 2 |")
w(f"| Contenido efectivo del Sprint 2 cerrado | {len(s2)} | {s2_sp} | Jira, Sprint 2 (id 36), "
  "cerrado el 16-10-2026, todas en *Finalizado* |")
w("")
diff_txt = ", ".join(f"{k} ({backlog[k]} SP, {jira[k]['status']})" for k in only_backlog)
w(f"Diferencia: en el backlog congelado pero no en el sprint cerrado: {diff_txt or 'ninguna'}. "
  f"En el sprint cerrado pero no en el backlog: {', '.join(only_sprint) or 'ninguna'}. "
  "Ninguna de las dos cifras reemplaza a la otra.")
w("")
w("| HU | Título (Jira) | SP | Estado Jira | En Sprint 2 | CA en requerimientos §3 |")
w("|---|---|---:|---|---|---:|")
for key in sorted(jira, key=lambda k: int(k.split("-")[1])):
    v = jira[key]
    w(f"| {key} | {v['title']} | {v['sp'] if v['sp'] is not None else '—'} | {v['status']} | "
      f"{'sí' if v['sprint2'] else 'no'} | {len(ca_rows.get(key, []))} |")
w("")
w("**Discrepancias detectadas:**")
w("- La versión retirada coincidía en el total del backlog congelado (14 historias, 58 SP), pero "
  "no en su composición: incluía SAPI-64 como «Marco de testing "
  "E2E» (3 SP) y SAPI-55 como «Freeze científico». En Jira, SAPI-64 es «Ejecutar experimento "
  "RNN/LSTM» (8 SP, Por hacer, fuera del sprint) y SAPI-55 es «Exponer Modelo D mediante "
  "microservicio FastAPI»; SAPI-56 tiene 3 SP, no 5.")
w("- SAPI-49 y SAPI-63 figuran en `requerimientos-sprint2.md` §2 como «Could — congelado, Por "
  "hacer», pero Jira las registra en Sprint 2 como Finalizado (resueltas el 16-10-2026). "
  "SAPI-49 no tiene criterios de aceptación en Jira ni en §3. Esta diferencia debe resolverla el "
  "responsable del proyecto; este documento no la corrige.")
w("- SAPI-67 (3 SP) está en PENDIENTE A VALIDACION y fuera de Sprint 2 (decisión D8 pendiente).")
w("")
w("## 2. Criterios de aceptación por historia")
for key in sorted(ca_rows, key=lambda k: int(k.split("-")[1])):
    v = jira.get(key, {})
    w("")
    w(f"### {key} — {v.get('title', '(no está en el export de Jira)')} "
      f"({v.get('sp', '—')} SP · {v.get('status', '—')})")
    w("")
    w("| CA | Criterio | RN | Verificación prevista | Evidencia | Estado registrado (08-10) | "
      "Verificación en el candidato |")
    w("|---|---|---|---|---|---|---|")
    for ca, crit, rn, verif, evid, estado, check in ca_rows[key]:
        note = F2_NOTES.get(ca)
        estado_txt = estado + (f"<br>**{note}**" if note else "")
        w(f"| {ca} | {crit} | {rn} | {verif} | {evid} | {estado_txt} | {check} |")
w("")
w("## 3. Historias de Sprint 2 sin criterios en §3")
w("")
S2_EXTRA = {
    "SAPI-63": "Jira define 5 criterios (ventanas causales sin información posterior a T; "
    "separación walk-forward; shape documentado; positivos por fold; conclusión de viabilidad "
    "LSTM con desbalance 1:3393). Artefactos presentes en el candidato: "
    "`experiments/sapi63/temporal_sequences.py`, `tests/test_temporal_sequences.py`, "
    "`notebooks/sapi63_lstm_viability.ipynb`, `reports/sapi63_lstm_viability_report.json`, "
    "`docs/evidence/sapi63-reproduction-20261015/README.md`.",
    "SAPI-49": "Spike sin criterios de aceptación en Jira. Resultado del spike presente en el "
    "candidato: `docs/spikes/SAPI-49-CONAF-historical-source.md`.",
}
for key in s2:
    if key not in ca_rows:
        w(f"- **{key}** ({jira[key]['title']}): sin tabla de CA en `requerimientos-sprint2.md` "
          f"§3. {S2_EXTRA.get(key, '')}")
w("")
totals = {"presente": 0, "parcial": 0, "ausente": 0, "manual": 0}
for rows in ca_rows.values():
    for r in rows:
        totals[r[6]] += 1
w("## 4. Resumen de verificación en el candidato")
w("")
w("| Resultado | CA |")
w("|---|---:|")
for k, n in totals.items():
    w(f"| {k} | {n} |")
w(f"| **Total** | **{sum(totals.values())}** |")
w("")
w("Un `ausente` o `parcial` significa que el artefacto citado no está en este árbol con ese "
  "nombre (por ejemplo, evidencia ignorada por Git o generada fuera del repositorio). No implica "
  "por sí solo que el criterio no se cumpla.")
w("")
w("**Referencias rotas confirmadas a mano** (el documento fuente cita archivos que no existen en "
  "el candidato; se corrigen en `requerimientos-sprint2.md` solo con autorización):")
w("- SAPI-61.CA3 cita `tests/test_ranking_view.py`; la cobertura vigente está en "
  "`tests/test_ranking_backend_view.py` y `tests/test_sapi61_http_stub.py`.")
w("- SAPI-66.CA5 cita `scripts/e2e_slice.py`; no existe. La suite E2E vigente es `tests/e2e/`.")
sys.stdout.reconfigure(encoding="utf-8")
print("\n".join(out))
