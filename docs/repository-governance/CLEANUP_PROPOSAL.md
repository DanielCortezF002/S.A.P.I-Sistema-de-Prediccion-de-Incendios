# S.A.P.I. — Propuesta de Limpieza y Reorganización Estructural
**Documento de Control:** `CLEANUP_PROPOSAL.md`
**Fecha de Elaboración:** 2026-10-18
**Autoridad:** Repository Maintainer & Security Auditor
**Directiva de Referencia:** Directiva R1 — Repository Governance & Structural Cleanup

---

## 1. Principio Rector y Estrategia No Destructiva

El repositorio de **S.A.P.I.** contiene tanto código productivo de alta criticidad como evidencia científica e histórica irreemplazable, sujeta a evaluación académica rigurosa. Por ello, cualquier proceso de ordenamiento debe regirse por las siguientes directrices inmutables:

1. **Cero Pérdida de Información:** No se elimina código, datasets congelados, manifiestos ni documentación.
2. **Preservación de Rutas Críticas:** No alterar nombres de directorios ni archivos consumidos por scripts de importación de Python, dependencias Maven, migraciones Flyway o compose files.
3. **Fases Graduales:** Distinguir claramente lo que puede implementarse de inmediato (documentación, índices, guías, ignores preventivos) de lo que requiere aprobación colegiada previa (movimiento de archivos en git, poda de ramas remotas, activación de reglas de protección).

---

## 2. Fase A: Mejoras Inmediatas y Seguras (Implementadas en R1)

Estas acciones se implementan directamente en la presente directiva al no impactar el runtime ni el historial:

1. **Creación del Índice Central de Documentación (`docs/README.md`):**
   Provee un mapa navegable de la totalidad de documentos técnicos, científicos, regulatorios y docentes del proyecto.
2. **Creación de la Guía de Contribución (`CONTRIBUTING.md`):**
   Estandariza el flujo de trabajo para nuevos ingenieros e investigadores, detallando la nomenclatura de ramas, commits convencionales, invariantes científicos y protocolo de evidencias.
3. **Actualización Estructural del `README.md` Principal:**
   Enriquece el mapa del repositorio con la totalidad de carpetas reales y enlaza la gobernanza sin eliminar un solo párrafo de la especificación técnica actual.
4. **Endurecimiento Específico de `.gitignore`:**
   Adición de patrones preventivos verificados que no colisionan con archivos rastreados:
   - Directorio de compilación Maven de Spring Boot: `target/` (aplica a la raíz y recursivamente a `services/backend/target/` sin redundancia).
   - Entornos de desarrollo integrados: `.idea/`, `*.swp`, e ignorado selectivo de `.vscode/*` admitiendo configuraciones de extensiones compartidas (`!.vscode/extensions.json`).
   - Caché de tipos: `.mypy_cache/`.

---

## 3. Fase B: Reorganización de Archivos Físicos (Requiere PR Dedicado)

Se propone consolidar los siguientes elementos para un PR de reorganización estructural no destructiva posterior:

### 3.1. Reubicación de Activos Gráficos Sueltos en Raíz
Actualmente existen 5 imágenes en el directorio raíz que fueron agregadas para documentación o aprobación:

| Archivo Actual en Raíz | Destino Propuesto | Justificación |
|---|---|---|
| `approval_live.png` | `docs/evidence/ui_approvals/approval_live.png` | Captura de validación visual de interfaz. |
| `sapi-ops-layout-approval.png` | `docs/evidence/ui_approvals/sapi-ops-layout-approval.png` | Evidencia de layout de Centro de Control. |
| `sapi-ops-layout-map.png` | `docs/evidence/ui_approvals/sapi-ops-layout-map.png` | Captura de vista territorial. |
| `figura_curva_roc.png` | `docs/img/figura_curva_roc.png` | Gráfico científico de desempeño exploratorio. |
| `figura_latencia_comparativa.png` | `docs/img/figura_latencia_comparativa.png` | Gráfico de tiempos de respuesta por capa. |

*Protocolo de Ejecución:* Ejecutar `git mv`, buscar y actualizar cualquier enlace en archivos Markdown que apunte a la ruta anterior antes de fusionar.

### 3.2. Consolidación de Reportes y Documentos
- `SAPI_SPRINT2_CLOSEOUT_REPORT.md` (en raíz) → Proponer mover a `docs/hito2/SAPI_SPRINT2_CLOSEOUT_REPORT.md` manteniendo un enlace simbólico o nota en el índice.
- `README_AI_KIT.md` (en raíz) → Consolidar con `docs/ai/README.md`.
- `locustfile.py` (en raíz) → Reubicar en `tests/load/locustfile.py` o `tools/locust/locustfile.py`.

---

## 4. Fase C: Ciclo de Vida de Ramas y Worktrees

### 4.1. Auditoría de Ramas Remotas en GitHub
El repositorio remoto cuenta con 24 ramas en `origin`. De ellas, 21 corresponden a Pull Requests que ya fueron formalmente fusionados a `main`:

- `origin/sprint-1` (Merged en PR #1)
- `origin/sprint-2` (Merged en PR #2)
- `origin/feat/SAPI-69-centralize-firms-dmc-guard` (Merged en PR #3)
- `origin/feat/SAPI-70-docker-build-hardening` (Merged en PR #4)
- `origin/feat/SAPI-71-n8n-bridge` (Merged en PR #5)
- `origin/feat/SAPI-71-firms-baseline-guard` (Merged en PR #6)
- `origin/feat/SAPI-71-firms-refresh-v2` (Merged en PR #7)
- `origin/feat/SAPI-71-dmc-refresh` (Merged en PR #8)
- `origin/feat/SAPI-71-dmc-validation` (Merged en PR #9)
- `origin/feat/SAPI-71-scoring-inputs-final` (Merged en PR #10)
- `origin/feat/sapi-operational-readiness` (Merged en PR #11)
- `origin/code/rc1-convergence-contract-fix` (Merged en PR #12)
- `origin/ci/postgis-tcp-readiness` (Merged en PR #15)
- `origin/feat/SAPI-57-ranking-ml-client` (Merged en PR #24)
- `origin/feat/SAPI-59-persist-ranking-postgis` (Merged en PR #25)
- `origin/feat/SAPI-60-docker-compose-v2` (Merged en PR #26)
- `origin/feat/SAPI-61-streamlit-backend-rest` (Merged en PR #27)
- `origin/feat/sprint2-publicacion-segura` (Merged en PR #28)
- `origin/feat/ui-academic-defense-hardening` (Merged en PR #29)

**Recomendación de Higiene:**
Una vez cerrada la entrega académica y verificado el respaldo íntegro de la historia en `main`, el mantenedor del repositorio podrá podar de manera segura las ramas remotas ya fusionadas mediante `git push origin --delete <rama>`, reduciendo la sobrecarga cognitiva sin perder historial ni commits.

### 4.2. Auditoría y Racionalización de Worktrees Locales
Actualmente existen 10 worktrees registrados en el entorno del mantenedor:
- `C:/SAPI-PUBLICACION-SEGURA-20261016` (en rama `feat/ui-bidirectional-table-map-navigation`, asociada al **PR #30** activo).
- Worktrees de auditorías de tickets concluidos (`C:/SAPI-hito2-sapi43`, `C:/SAPI-hito2-sapi66`, `C:/SAPI-hito2-sapi71`, `C:/SAPI-mw011-hotfix`).

**Procedimiento Recomendado:**
Al concluir y fusionar el PR #30, se sugiere retirar los worktrees temporales utilizando:
```bash
git worktree remove <ruta-worktree>
git branch -d <nombre-rama-local>
```
Conservando exclusivamente el repositorio raíz (`C:\SAPI`) y el entorno de agentes (`C:\SAPI-AI-ENV`).

---

## 5. Fase D: Gobernanza Remota de GitHub y CI/CD

Se recomienda presentar al equipo líder de desarrollo la aprobación de los siguientes estándares de configuración remota:

### 5.1. Reglas de Protección de Rama `main` (Branch Protection)
Configurar en GitHub (`Settings > Branches > Branch protection rules` para `main`):
- [x] **Require a pull request before merging:** Exigir siempre la integración vía PR.
- [x] **Require approvals:** Al menos 1 aprobación formal por revisión de pares o revisión de arquitectura.
- [x] **Dismiss stale pull request approvals when new commits are pushed.**
- [x] **Require status checks to pass before merging:** Obligar que el check `CI` termine exitosamente.
- [x] **Do not allow bypassing the above settings:** Aplicar las reglas a administradores para evitar errores involuntarios.
- [x] **Require linear history / Squash and merge:** Mantener un historial legible y correlacionado con Jira.

### 5.2. Activación del Pipeline de CI
Verificar que `.github/workflows/ci.yml` se active en los eventos:
```yaml
on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]
```
Asegurando que cada PR verifique automáticamente:
- `black --check .` (estilo de código)
- `flake8` (análisis estático de linting)
- `pytest` (suite de pruebas con gate de cobertura mínima de 80%)
- Validación de especificaciones OpenAPI v0.
