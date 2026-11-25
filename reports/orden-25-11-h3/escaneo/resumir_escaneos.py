"""Resume los JSON de Trivy, pip-audit y OSV-Scanner de la orden 25-11 en Markdown.

Uso: py -I resumir_escaneos.py <carpeta_json>  > resumen.md
Solo lee los JSON; no consulta la red.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

src = Path(sys.argv[1])
SEV = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]


def trivy(path: Path) -> None:
    j = json.loads(path.read_text(encoding="utf-8-sig"))
    print(f"\n### {path.stem.replace('trivy-', '')}\n")
    print(f"SO base: {j['Metadata']['OS']['Family']} {j['Metadata']['OS']['Name']}. "
          f"Escaneo: {j['CreatedAt'][:19]}Z.\n")
    print("| Objetivo | Clase | " + " | ".join(SEV) + " | Total (únicas) |")
    print("|---|---|" + "---|" * (len(SEV) + 1))
    fixable = defaultdict(set)
    for r in j.get("Results", []):
        vulns = r.get("Vulnerabilities") or []
        uniq = {(v["PkgName"], v["InstalledVersion"], v["VulnerabilityID"]): v for v in vulns}
        c = Counter(v["Severity"] for v in uniq.values())
        print(f"| {r['Target'].split('/')[-1][:60]} | {r['Class']} | " + " | ".join(str(c.get(s, 0)) for s in SEV)
              + f" | {len(uniq)} |")
        for (pkg, ver, vid), v in uniq.items():
            if v["Severity"] in ("CRITICAL", "HIGH") and v.get("FixedVersion"):
                fixable[(pkg, ver, v["FixedVersion"].split(",")[0].strip())].add(v["Severity"])
    if fixable:
        print("\nCRITICAL/HIGH con versión corregida publicada (paquete, instalada -> corregida):\n")
        for (pkg, ver, fix), sev in sorted(fixable.items()):
            print(f"- `{pkg}` {ver} -> {fix} ({'/'.join(sorted(sev))})")


def pip_audit(path: Path) -> None:
    first = path.read_text(encoding="utf-8-sig").splitlines()[0]
    j = json.loads(first)
    vul = [d for d in j["dependencies"] if d.get("vulns")]
    print(f"\n### {path.stem.replace('pip-audit-', '')}\n")
    print(f"Paquetes auditados: {len(j['dependencies'])}. Con avisos: {len(vul)}.\n")
    for d in vul:
        fixes = sorted({f for v in d["vulns"] for f in v.get("fix_versions", [])})
        print(f"- `{d['name']}` {d['version']}: {len(d['vulns'])} avisos; corregida en {', '.join(fixes) or 'sin versión'}")


def osv(path: Path) -> None:
    j = json.loads(path.read_text(encoding="utf-8-sig"))
    print("\n### services/backend/pom.xml\n")
    for res in j.get("results", []):
        for p in res.get("packages", []):
            ids = [v["id"] for v in p.get("vulnerabilities", [])]
            print(f"- `{p['package']['name']}` {p['package']['version']}: {len(ids)} avisos ({', '.join(ids)})")


print("## Trivy (imágenes)")
for f in sorted(src.glob("trivy-*.json")):
    trivy(f)
print("\n## pip-audit (site-packages instalados en cada imagen)")
for f in sorted(src.glob("pip-audit-*.json")):
    pip_audit(f)
print("\n## OSV-Scanner (Maven)")
for f in sorted(src.glob("osv-*.json")):
    osv(f)
