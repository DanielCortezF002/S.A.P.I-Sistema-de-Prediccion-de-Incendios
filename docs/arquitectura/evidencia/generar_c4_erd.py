"""Genera el diagrama C4 de contenedores desde `docker compose config` y el ERD desde db/migration.

Uso (desde la raíz del repo):
    py -I docs/arquitectura/evidencia/generar_c4_erd.py > docs/arquitectura/c4-contenedores-y-erd-generados.md

Entradas:
- docs/arquitectura/evidencia/compose-config-518c0b5.json: salida de
  `docker compose -p sapi-h3-518c0b5 -f docker-compose.yml --profile presentation config --format json`,
  con SAPI_DB_PORT=15432, SAPI_ML_PORT=18000, SAPI_BACKEND_PORT=18080 y SAPI_WEB_PORT=18501 (los del stack h3),
  con las rutas absolutas del equipo reemplazadas por rutas relativas.
- db/migration/V*.sql: migraciones Flyway, en orden de versión.
- docs/arquitectura/evidencia/esquema-vivo-h3.txt (opcional): columnas y restricciones
  leídas de information_schema en la base del stack h3, para cotejar.

Solo dibuja lo que está en esas entradas. No agrega componentes.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVID = ROOT / "docs" / "arquitectura" / "evidencia"
COMPOSE = EVID / "compose-config-518c0b5.json"
LIVE = EVID / "esquema-vivo-h3.txt"
MIGRATIONS = sorted((ROOT / "db" / "migration").glob("V*.sql"))


# ---------- C4 contenedores ----------

def c4_containers() -> list[str]:
    cfg = json.loads(COMPOSE.read_text(encoding="utf-8"))
    svcs = cfg["services"]
    out = ["```mermaid", "flowchart LR", '    host["Equipo anfitrión<br/>(navegador, k6, curl)"]']
    nets = sorted({n for s in svcs.values() for n in (s.get("networks") or {})})
    for net in nets:
        out.append(f'    subgraph {net.replace("-", "_")}["red {net}"]')
        for name, s in sorted(svcs.items()):
            if net not in (s.get("networks") or {}):
                continue
            tech = s.get("image") or f'build {s["build"]["context"]}' + (
                f' · {s["build"].get("dockerfile")}' if s["build"].get("dockerfile") else "")
            cmd = s.get("command") or []
            cmd_txt = (" ".join(cmd) if isinstance(cmd, list) else str(cmd)) if name != "web-v2" else " ".join(cmd[:5])
            cmd_txt = f"<br/>{cmd_txt}" if cmd_txt else ""
            prof = f'<br/>profile: {",".join(s["profiles"])}' if s.get("profiles") else ""
            shape = ('[("', '")]') if name.startswith("db") else ('["', '"]')
            out.append(f'      {name.replace("-", "_")}{shape[0]}{name}<br/>{tech}{cmd_txt}{prof}{shape[1]}')
        out.append("    end")
    for name, s in sorted(svcs.items()):
        for p in s.get("ports") or []:
            out.append(f'    host -- "{p.get("host_ip", "0.0.0.0")}:{p["published"]} → {p["target"]}" --> {name.replace("-", "_")}')
    for name, s in sorted(svcs.items()):
        for dep, d in sorted((s.get("depends_on") or {}).items()):
            out.append(f'    {name.replace("-", "_")} -. "depends_on: {d.get("condition")}" .-> {dep.replace("-", "_")}')
    # Llamadas de red declaradas en variables de entorno (URL a otro servicio por nombre).
    for name, s in sorted(svcs.items()):
        for k, v in sorted((s.get("environment") or {}).items()):
            for target in svcs:
                if isinstance(v, str) and re.search(rf"//{re.escape(target)}:\d+", v):
                    out.append(f'    {name.replace("-", "_")} -- "{k}" --> {target.replace("-", "_")}')
    out.append("```")

    rows = ["", "| Servicio | Imagen o build | Puertos en el anfitrión | Volúmenes | Red | depends_on |",
            "|---|---|---|---|---|---|"]
    for name, s in sorted(svcs.items()):
        tech = s.get("image") or f'`{s["build"]["context"]}` ({s["build"].get("dockerfile", "Dockerfile")})'
        ports = ", ".join(f'{p.get("host_ip", "0.0.0.0")}:{p["published"]}→{p["target"]}' for p in s.get("ports") or [])
        vols = ", ".join(f'{v["source"]}→{v["target"]}{" (ro)" if v.get("read_only") else ""}'
                         for v in s.get("volumes") or [])
        deps = ", ".join(f"{k} ({v.get('condition')})" for k, v in (s.get("depends_on") or {}).items())
        rows.append(f"| {name} | {tech} | {ports or '—'} | {vols or '—'} | {', '.join(s.get('networks') or {})} | {deps or '—'} |")
    return out + rows


# ---------- ERD ----------

def strip_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def split_top(body: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def parse_migrations():
    tables: dict[str, dict] = {}
    for path in MIGRATIONS:
        sql = strip_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"CREATE TABLE (\w+) \((.*?)\n\);", sql, re.S):
            name, body = m.group(1), m.group(2)
            t = {"cols": [], "pk": set(), "uk": set(), "fks": [], "origen": path.name}
            for item in split_top(body):
                head = item.split()[0].upper()
                if head == "CONSTRAINT":
                    pk = re.search(r"PRIMARY KEY \(([^)]*)\)", item)
                    uk = re.search(r"UNIQUE \(([^)]*)\)", item)
                    fk = re.search(r"FOREIGN KEY \(([^)]*)\)\s+REFERENCES (\w+) \(([^)]*)\)", item)
                    if pk:
                        t["pk"].update(c.strip() for c in pk.group(1).split(","))
                    if uk:
                        t["uk"].update(c.strip() for c in uk.group(1).split(","))
                    if fk:
                        t["fks"].append(([c.strip() for c in fk.group(1).split(",")], fk.group(2),
                                         item.split()[1]))
                    continue
                col, typ = item.split()[0], item.split()[1]
                typ = re.sub(r"\(.*", "", typ)
                if " ".join(item.split()[1:3]).lower() == "double precision":
                    typ = "double_precision"
                t["cols"].append((col, typ, path.name))
                if "PRIMARY KEY" in item.upper():
                    t["pk"].add(col)
            tables[name] = t
        for m in re.finditer(r"ALTER TABLE (\w+) ADD COLUMN (\w+) (\w+)", sql):
            tables[m.group(1)]["cols"].append((m.group(2), m.group(3), path.name))
    return tables


def erd(tables) -> list[str]:
    out = ["```mermaid", "erDiagram"]
    for name, t in tables.items():
        out.append(f"    {name} {{")
        fk_cols = {c for cols, _, _ in t["fks"] for c in cols}
        for col, typ, origen in t["cols"]:
            keys = [k for k, s in (("PK", t["pk"]), ("FK", fk_cols), ("UK", t["uk"])) if col in s]
            out.append(f'        {typ} {col}{" " + ",".join(keys) if keys else ""} "{origen}"')
        out.append("    }")
    for name, t in tables.items():
        for cols, ref, cname in t["fks"]:
            out.append(f'    {ref} ||--o{{ {name} : "{cname} ({", ".join(cols)})"')
    out.append("```")
    return out


def cotejo(tables) -> list[str]:
    if not LIVE.exists():
        return ["", "Sin archivo de esquema vivo: no se cotejó."]
    live_cols, live_con = {}, set()  # live_con: (tabla, nombre, tipo)
    for line in LIVE.read_text(encoding="utf-8").splitlines():
        p = line.split("|")
        if p[0] == "COL":
            live_cols.setdefault(p[1], []).append(p[2])
        elif p[0] == "CON":
            live_con.add((p[1], p[2], p[3]))
    out = ["", "| Tabla | Columnas según migraciones | Columnas en la base h3 | ¿Iguales y en el mismo orden? |",
           "|---|---|---|---|"]
    ok = True
    for name, t in tables.items():
        mig = [c for c, _, _ in t["cols"]]
        same = mig == live_cols.get(name)
        ok &= same
        out.append(f"| {name} | {len(mig)} | {len(live_cols.get(name, []))} | {'Sí' if same else 'No'} |")
    fks_mig = sum(len(t["fks"]) for t in tables.values())
    fks_live = sum(1 for _, _, k in live_con if k == "FOREIGN KEY")
    out.append("")
    out.append(f"Claves foráneas: {fks_mig} según migraciones, {fks_live} en la base h3. "
               f"Resultado del cotejo: **{'coinciden' if ok and fks_mig == fks_live else 'NO coinciden'}**.")
    return out


def main() -> None:
    tables = parse_migrations()
    lines = [
        "# C4 de contenedores y ERD generados (no editar a mano)",
        "",
        "Generado por [evidencia/generar_c4_erd.py](evidencia/generar_c4_erd.py) desde "
        "[evidencia/compose-config-518c0b5.json](evidencia/compose-config-518c0b5.json) y "
        f"`db/migration/` ({', '.join(p.name for p in MIGRATIONS)}). "
        "Para regenerarlo: `py -I docs/arquitectura/evidencia/generar_c4_erd.py > docs/arquitectura/c4-contenedores-y-erd-generados.md`.",
        "",
        "## C4 nivel 2 · contenedores según `docker compose config` (profile `presentation`)",
        "",
        "Las flechas de llamada salen de las variables de entorno que apuntan a otro servicio por nombre; "
        "las punteadas, de `depends_on`; las del anfitrión, de `ports`.",
        "",
        *c4_containers(),
        "",
        "## ERD · desde `db/migration`",
        "",
        "Cada columna lleva la migración que la crea. PK, FK y UK según las restricciones declaradas.",
        "",
        *erd(tables),
        "",
        "### Cotejo con la base del stack `sapi-h3-518c0b5`",
        "",
        "Fuente: [evidencia/esquema-vivo-h3.txt](evidencia/esquema-vivo-h3.txt) (information_schema y `flyway_schema_history`).",
        *cotejo(tables),
    ]
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
