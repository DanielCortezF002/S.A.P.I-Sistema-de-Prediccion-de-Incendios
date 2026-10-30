"""D3 (F2): genera el expediente de autorización de las excepciones F4, uno por archivo.

Lee `F4_AUTHORIZED_EXCEPTIONS` y `BASELINE` de `scripts/freeze_check.py` y, para cada ruta
congelada, contrasta los pins con Git (baseline, commit autorizado, HEAD del candidato),
guarda el diff frente al baseline y lista las pruebas que ejercitan el cambio. No modifica
`freeze_check.py` ni los archivos congelados. La decisión (autorizar o rechazar) queda en
blanco para el responsable del proyecto.

Uso: python scripts/build_f4_expediente.py <directorio_salida>
"""

import hashlib
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1])

spec = importlib.util.spec_from_file_location(
    "freeze_check", REPO / "scripts/freeze_check.py"
)
freeze_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freeze_check)
BASELINE = freeze_check.BASELINE
EXCEPTIONS = freeze_check.F4_AUTHORIZED_EXCEPTIONS


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True
    ).stdout


def blob(rev: str, path: str) -> str:
    return git("rev-parse", f"{rev}:{path}").strip()


def content_sha256(rev: str, path: str) -> str:
    raw = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "blob", f"{rev}:{path}"],
        capture_output=True,
        check=True,
    ).stdout
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def tests_touching(path: str, scope: str) -> list[str]:
    module = path[:-3].replace("/", ".")
    symbols = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", scope)) - {"L154", "L166"}
    hits = []
    for test in sorted(git("ls-files", "tests").splitlines()):
        if not test.endswith(".py"):
            continue
        text = (REPO / test).read_text(encoding="utf-8", errors="ignore")
        if module in text and any(s in text for s in symbols):
            hits.append(test)
    return hits


OUT.mkdir(parents=True, exist_ok=True)
head = git("rev-parse", "HEAD").strip()
index = []
for n, (path, pin) in enumerate(EXCEPTIONS.items(), start=1):
    slug = f"{n:02d}_{Path(path).stem}"
    diff = git("diff", BASELINE, head, "--", path)
    (OUT / f"{slug}.diff").write_text(diff, encoding="utf-8", newline="\n")
    stat = git("diff", "--numstat", BASELINE, head, "--", path).split()
    since_auth = git(
        "diff", "--numstat", pin["authorized_commit"], head, "--", path
    ).strip()
    checks = {
        "Blob en el commit autorizado = pin": blob(pin["authorized_commit"], path)
        == pin["blob_sha"],
        "Blob en el candidato (HEAD) = pin": blob(head, path) == pin["blob_sha"],
        "SHA-256 (LF) en el candidato = pin": content_sha256(head, path)
        == pin["content_sha256"],
        "Sin cambios desde el commit autorizado": since_auth == "",
        "Evidencia citada existe": all(
            (
                REPO / "docs/evidence" / Path(e.strip()).parent.name / "README.md"
            ).exists()
            or (REPO / e.strip()).exists()
            for e in re.split(r" y ", pin["evidence"])
        ),
    }
    tests = tests_touching(path, pin["scope"])
    lines = [
        f"# Expediente F4 {n}/4 — `{path}`",
        "",
        "**Estado:** PENDIENTE DE FIRMA. Este expediente no autoriza nada por sí mismo.",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Defecto(s) | {pin['defect_id']} |",
        f"| Motivo declarado | {pin['reason']} |",
        f"| Alcance declarado | {pin['scope']} |",
        f"| Commit autorizado | `{pin['authorized_commit']}` |",
        "| Autoridad citada en el código | Directiva OCC-003A (orquestador), "
        f"autor {pin['author']} |",
        f"| Baseline del freeze | `{BASELINE}` |",
        f"| Candidato evaluado | `{head}` |",
        f"| Blob baseline → candidato | `{blob(BASELINE, path)}` → `{blob(head, path)}` |",
        f"| SHA-256 (LF) pin | `{pin['content_sha256']}` |",
        f"| Cambio frente al baseline | +{stat[0]} / −{stat[1]} líneas (`{slug}.diff`) |",
        f"| Evidencia citada | {pin['evidence']} |",
        "",
        "## Comprobaciones automáticas",
        "",
        "| Comprobación | Resultado |",
        "|---|---|",
        *[f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in checks.items()],
        "",
        "## Pruebas que ejercitan esta ruta y el alcance declarado",
        "",
        *(
            [f"- `{t}`" for t in tests]
            or ["- Ninguna encontrada por nombre de módulo y símbolo."]
        ),
        "- `tests/test_freeze_f4_exceptions.py` (pruebas negativas y positivas del mecanismo)",
        "",
        "Los resultados de estas pruebas sobre el candidato están en el informe F2.",
        "",
        "## Revisión que debe hacer quien firma",
        "",
        f"1. Leer `{slug}.diff` y confirmar que el cambio se limita al alcance declarado.",
        "2. Confirmar que el defecto citado existía y que la evidencia lo demuestra.",
        "3. Confirmar que el cambio no altera features, target, modelo ni semántica del score.",
        "",
        "## Decisión",
        "",
        "- [ ] Autorizo esta excepción F4",
        "- [ ] Rechazo esta excepción F4 (el archivo debe volver al contenido del baseline)",
        "",
        "Firma: ______________________  Fecha: ____________",
        "",
    ]
    (OUT / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    index.append((slug, path, pin["defect_id"], all(checks.values())))

summary = [
    "# Expediente de autorización de excepciones F4 (resolución D3)",
    "",
    f"Generado por `scripts/build_f4_expediente.py` sobre el candidato `{head}`. "
    "Un expediente por archivo congelado. **Ninguna excepción está autorizada hasta que el "
    "responsable del proyecto firme cada expediente.**",
    "",
    "| Expediente | Archivo | Defecto(s) | Pins y evidencia |",
    "|---|---|---|---|",
    *[
        f"| `{s}.md` | `{p}` | {d} | {'PASS' if ok else 'FAIL'} |"
        for s, p, d, ok in index
    ],
    "",
    "Contexto: las excepciones se añadieron a `scripts/freeze_check.py` en la misma PR (#39) "
    "que el control evalúa, citando una directiva del orquestador de agentes y no una firma "
    "del PO. Por eso GB-04 sigue abierto hasta esta firma.",
    "",
]
(OUT / "README.md").write_text("\n".join(summary), encoding="utf-8", newline="\n")
print("\n".join(summary))
