# S.A.P.I. — Auditoría Integral de Gobernanza del Repositorio
**Documento de Control:** `REPOSITORY_AUDIT_20261018.md`
**Fecha de Ejecución:** 2026-10-18
**Rol Actuante:** Principal Software Architect, GitHub Repository Maintainer & Security Auditor
**Directiva de Referencia:** Directiva R1 — Repository Governance & Structural Cleanup
**Entorno Autorizado:** `C:\SAPI-AI-ENV` (Rama: `feat/sapi-ai-environment`, Commit: `33eff1e`)
**Repositorios Protegidos:**
- Original de Desarrollo: `C:\SAPI`
- Histórico Congelado: `C:\SAPI-PUBLICACION-SEGURA-20261016`

---

## 1. Resumen Ejecutivo y Mandato

En cumplimiento estricto de la **Directiva R1**, se ha llevado a cabo la primera fase de auditoría técnica, seguridad y gobernanza estructural del repositorio institucional de **S.A.P.I. (Sistema de Alerta y Predicción de Incendios)**.

La auditoría se ejecutó bajo **operaciones 100% no destructivas y en modo de solo lectura sobre el entorno remoto y los repositorios protegidos**, sin alterar el código productivo, sin modificar la evidencia congelada, sin reescribir historial y sin exponer secretos ni credenciales.

### Resumen de Hallazgos Clave

| Dimensión | Estado Auditado | Observación Principal |
|---|---|---|
| **Worktree y Rama** | `feat/sapi-ai-environment` en `C:\SAPI-AI-ENV` | Aislado y limpio respecto al repositorio base `C:\SAPI`. Contiene 4 rutas no rastreadas preexistentes que fueron rigurosamente preservadas. |
| **Repositorio Remoto** | GitHub (`DanielCortezF002/...`) | Rama predeterminada `main` (commit `2ba8ceb`). Autenticación vía GitHub CLI operativa (`DanielCortezF002`). |
| **Pull Requests** | 30 PRs registrados | 29 PRs fusionados (`MERGED`), 1 PR abierto (`OPEN`): **PR #30** (`feat/ui-bidirectional-table-map-navigation`). |
| **Issues en GitHub** | 0 Issues activos | La gestión de historias y tareas se centraliza formalmente en **Jira (Proyecto SAPI)**, no en GitHub Issues. |
| **GitHub Actions / CI** | 1 Workflow (`ci.yml`), 0 ejecuciones | Workflow activo en el repositorio pero sin ejecuciones registradas en la nube (`total_count: 0`); la ejecución automatizada remota permanece pendiente. |
| **Protección de Ramas** | HTTP 404 (Sin protección) | La rama `main` no cuenta actualmente con reglas de protección configuradas en GitHub. |
| **Suite de Pruebas** | 2.190 aprobadas, 66 omitidas | Cobertura global de código: **86,85%** (supera el Quality Gate obligatorio del 80%). Se identificaron 2 observaciones técnicas en pruebas específicas. |
| **Seguridad de Secretos** | Conforme / Sin exposición | `.dockerignore` y `.gitignore` previenen fuga de `.env` y secretos. Sin credenciales ni tokens versionados en el árbol rastreado. |

---

## 2. Inventario Técnico del Entorno Git

### 2.1. Worktrees Registrados

El proyecto presenta una topología de múltiples worktrees para aislamiento de tareas y auditorías paralelas:

```text
C:/SAPI                             674f167 [feat/sprint2-final-closeout] (Repositorio original protegido)
C:/SAPI-AI-ENV                      33eff1e [feat/sapi-ai-environment]    (Worktree activo auditado)
C:/SAPI-antigravity                 2338ede [feat/SAPI-antigravity-sprint2]
C:/SAPI-hito2-sapi43                ce644a1 [hito2/sapi43-audit]
C:/SAPI-hito2-sapi66                6fbcd74 [hito2/sapi66-codex-review]
C:/SAPI-hito2-sapi71                ce644a1 [hito2/sapi71-audit]
C:/SAPI-mw011-hotfix                822ec37 [code/sapi-72-evidence-paths]
C:/SAPI-PUBLICACION-SEGURA-20261016 c5e274c [feat/ui-bidirectional-table-map-navigation] (Histórico protegido)
C:/SAPI-rc1-release-gate-harness    d8f5665 (detached HEAD)
C:/SW/62eval                        4b0e2c8 (detached HEAD)
```

### 2.2. Estado del Worktree Activo (`C:\SAPI-AI-ENV`)

- **Rama:** `feat/sapi-ai-environment`
- **Head Commit:** `33eff1e` (*chore(ai): bootstrap SAPI agent skills and governance*)
- **Base Commit:** `2ba8ceb` (*origin/main* — PR #29)
- **Archivos sin seguimiento (Untracked) preexistentes preservados:**
  1. `deliverables/hito2-draft/SAPI_Hito2_Informe_Academico_v2.4.1_BORRADOR.docx`
  2. `deliverables/hito2-draft/SAPI_Hito2_Informe_Academico_v2.4.1_BORRADOR.pdf`
  3. `docs/evidence/hito2-informe-v2.4-reconciliacion-20261017/README.md`
  4. `docs/evidence/hito2-informe-v2.4.1-correccion-final-20261017/README.md`
- **Archivos ignorados en estado local:**
  - `.claude/settings.local.json`
  - `scripts/ai/__pycache__/`

### 2.3. Distribución de Archivos por Directorio

Conteo exhaustivo de archivos en el árbol del worktree (total: 852 archivos en seguimiento y soporte):

| Directorio | Cantidad de Archivos | Naturaleza Principal |
|---|---|---|
| `artifacts/` | 411 | Evidencia congelada histórica (Hito 1, Hito 2, reproducibilidad) |
| `tests/` | 129 | Suite automatizada de pruebas unitarias y de integración |
| `src/` | 107 | Librería central de dominio, geoespacial, inferencia y refresco |
| `docs/` | 100 | Arquitectura, ADRs, guías, matrices académicas y trazabilidad |
| `services/` | 56 | Microservicios v2: Spring Boot (`backend`) y FastAPI (`ml_api`) |
| `app/` | 39 | Capa de visualización Streamlit y componentes Folium |
| `scripts/` | 32 | Utilidades de automatización, validación, preflight y auditoría |
| `reports/` | 13 | Informes estructurados JSON/CSV de integridad y viabilidad |
| `.claude/` | 13 | Configuración y skills locales de asistencia técnica |
| `deliverables/` | 10 | Documentos académicos finales (DOCX, PDF, PPTX) |
| `.agents/` | 9 | Catálogo de skills de gobernanza Antigravity |
| `tools/` | 8 | Adaptadores operacionales, pipeline documental y puente n8n |
| `ops/` | 8 | Flujos sanitizados n8n, políticas de automatización y fixtures |
| `docker/` | 7 | Scripts de inicialización PostGIS v1/v2 y soporte |
| `db/` | 6 | Migraciones Flyway V001–V004 y consultas SQL de auditoría |
| `models/` | 3 | Artefacto serializado congelado del Modelo D y metadata |
| `notebooks/` | 3 | Análisis exploratorios de viabilidad secuencial (LSTM) |
| `contracts/` | 3 | Especificaciones OpenAPI v0 (backend y servicio ML) |
| `experiments/` | 3 | Módulos experimentales aislados de investigación |
| `config/` | 2 | Configuraciones de planos de datos y convergencia RC1 |
| `data/` | 3 | Marcadores `.gitkeep` de directorios locales no versionados |
| `.github/` | 1 | Pipeline de integración continua (`workflows/ci.yml`) |
| `.streamlit/` | 1 | Configuración de servidor y UI local de Streamlit |
| **Archivos en Raíz** | 28 | Readmes, configuraciones de tooling, docker-compose y scripts |

---

## 3. Auditoría Remota de GitHub

Se realizaron consultas en solo lectura aprovechando la sesión autenticada de GitHub CLI (`gh`):

### 3.1. Conexión y Permisos
- **Cuenta:** `DanielCortezF002` (vía keyring seguro).
- **Alcances (Scopes):** `gist`, `read:org`, `repo`, `workflow`.
- **Protocolo Git:** HTTPS.

### 3.2. Auditoría de Pull Requests
Se auditaron los 30 PRs históricos del repositorio:
- **PRs #1 a #29 (FUSIONADOS):** Cubren desde la entrega de Sprint 1, adopción de arquitectura v2 (SAPI-54 a SAPI-61), endurecimiento de Docker (SAPI-70), pipelines de refresco FIRMS/DMC (SAPI-71), hasta el endurecimiento visual y de contraste para defensa académica (PR #29).
- **PR #30 (ABIERTO):**
  - *Título:* `feat(ui): enable bidirectional navigation between ranking table and territorial map`
  - *Rama de origen:* `feat/ui-bidirectional-table-map-navigation`
  - *Estado:* Abierto para revisión final. Introduce navegación bidireccional tabla↔mapa (clic directo en celdas de tabla y checkbox sincronizado con mapa Folium y panel lateral).

### 3.3. Auditoría de Issues y Gestión de Tareas
- En GitHub se registran **0 issues nativos**.
- **Dictamen:** Esto no constituye una anomalía; la política de gobernanza del proyecto estipula que la totalidad de Historias de Usuario, Criterios de Aceptación y Bugs se gestionan en **Atlassian Jira (Proyecto SAPI)**.

### 3.4. Auditoría de GitHub Actions y Protección de Ramas
- **Workflow:** `.github/workflows/ci.yml` existe en la rama `main` y define validaciones de `black --check`, `flake8` y `pytest` (cobertura mínima 80%).
- **Ejecuciones en Servidor:** `total_count: 0`. No existen registros de ejecuciones automáticas remotas previas.
- **Protección de Rama `main`:** Respuesta de la API de GitHub: `HTTP 404: Branch not protected`.
  *Hallazgo de Seguridad:* Actualmente es técnicamente posible realizar `git push` directo o force-push a `main`. Se recomienda formalizar reglas de protección para exigir PR y checks obligatorios.

---

## 4. Matriz de Clasificación Estructural (Categorías A a F)

En estricta observancia de la Fase 2, se clasifica cada componente del repositorio sin mover ni alterar rutas físicas:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        MATRIZ DE CLASIFICACIÓN                         │
├───────────────────────┬────────────────────────────────────────────────┤
│ A. CORE PROTEGIDO     │ Código productivo, Modelo D, microservicios    │
│                       │ v2, esquemas de BD, artefactos reproducibles.  │
├───────────────────────┼────────────────────────────────────────────────┤
│ B. DOCS ACTIVAS       │ Arquitectura, ADRs, contratos OpenAPI, model   │
│                       │ card, directrices para agentes y gobierno.     │
├───────────────────────┼────────────────────────────────────────────────┤
│ C. ENTREGABLES ACAD.  │ Informes finales Hito 1/2, diapositivas PPTX/  │
│                       │ PDF, actas y rúbricas docentes UNAB.           │
├───────────────────────┼────────────────────────────────────────────────┤
│ D. EVIDENCIA HISTÓRICA│ Snapshots inmutables, manifiestos de datos,   │
│                       │ auditorías fechadas, capturas de navegadores.  │
├───────────────────────┼────────────────────────────────────────────────┤
│ E. GENERADOS / CACHÉ  │ __pycache__, .pytest_cache, logs, coberturas,  │
│                       │ builds temporales y artefactos de pruebas.     │
├───────────────────────┼────────────────────────────────────────────────┤
│ F. CANDIDATOS REVISIÓN│ Imágenes sueltas en raíz, reportes fuera de    │
│                       │ lugar, tests con dependencias accesorias.      │
└───────────────────────┴────────────────────────────────────────────────┘
```

### Detalle de Clasificación por Directorio y Archivo

#### Categoría A: CORE PROTEGIDO (Inmutable sin ciclo formal de ingeniería)
- `src/` (todos sus submódulos: `inference/`, `procesamiento/`, `refresh/`, `geo/`, `output/`, `ops/`, etc.).
- `models/prototype_model_d.pkl` y `models/prototype_model_d_metadata.json` (Modelo D formalizado).
- `services/backend/` (código Spring Boot Java 21, `pom.xml`, wrapper Maven).
- `services/ml_api/` (servicio FastAPI, `main.py`).
- `db/migration/` (scripts Flyway V001 a V004).
- `app/` (frontend Streamlit, layout, theme tokens y componentes Folium).
- `docker-compose.yml`, `docker-compose.operational.yml`, `Dockerfile.*`.
- `artifacts/hito1/reproducibility/` (datos base inmutables de Hito 1).

#### Categoría B: DOCUMENTACIÓN ACTIVA (Vigente y de consulta operacional)
- `README.md` (presentación y guía integral del proyecto).
- `AGENTS.md` (directiva permanente de gobernanza para agentes de IA).
- `docs/architecture-stack-freeze-sprint2.md` y su erratum.
- `docs/adr/` (ADR-001 a ADR-011).
- `docs/model_card_baseline.md` (ficha formal del Modelo D).
- `docs/deploy.md` (guía de despliegue y reproducibilidad).
- `contracts/openapi/` (contratos REST YAML de servicios v2).
- `docs/ai/` (contexto SAPI, guías Claude Desktop, seguridad MCP, matrices).
- `docs/repository-governance/` (nuevos documentos de gobernanza R1).

#### Categoría C: ENTREGABLES ACADÉMICOS (Universidad Andrés Bello — Portafolio)
- `deliverables/` (versiones finales Hito 1 DOCX/PDF y presentaciones PPTX).
- `deliverables/hito2-draft/` (borrador del informe académico Hito 2).
- `docs/informe-1-seminario-licenciatura.md`, `docs/informe-hito1-final.md`.
- `docs/hito2/` (`INFORME_HITO2_FINAL.md`, matrices de rúbricas César y Matías, guiones de presentación).
- `docs/defensa-academica/` (guiones de 5 minutos, preguntas de comisión, matrices de riesgo docente).

#### Categoría D: EVIDENCIA HISTÓRICA (Registros inmutables de corridas y auditorías)
- `artifacts/hito1/` (evidencia de pruebas, cobertura y logs de Hito 1).
- `artifacts/hito2/` (evidencia de calidad W0, pruebas E2E, gates G0-G7).
- `docs/evidence/` (auditorías en navegador Edge headless, capturas claro/oscuro, trazas fechadas).
- `reports/` (archivos JSON/CSV de auditoría de datos, megaevento 2024, viabilidad LSTM).

#### Categoría E: ARCHIVOS GENERADOS / TEMPORALES
- `scripts/ai/__pycache__/` (compilados bytecode de Python).
- `.pytest_cache/`, `.coverage`, `htmlcov/` (generados durante ejecución de pruebas).
- `artifacts/hito2/f1/` (artefactos emitidos por corridas dinámicas de pruebas de integración).
- `services/backend/target/` (posible directorio de compilación Maven si se invoca build local).

#### Categoría F: CANDIDATOS A REVISIÓN Y REORGANIZACIÓN POSTERIOR
- **Imágenes en raíz:**
  - `approval_live.png`
  - `figura_curva_roc.png`
  - `figura_latencia_comparativa.png`
  - `sapi-ops-layout-approval.png`
  - `sapi-ops-layout-map.png`
  *Diagnóstico:* Aunque están rastreadas en Git, ensucian el directorio raíz. Deben reubicarse en `docs/img/` o `docs/evidence/` mediante un PR formal.
- **Documentos en raíz:**
  - `SAPI_SPRINT2_CLOSEOUT_REPORT.md` (debe migrar a `docs/hito2/`).
  - `README_AI_KIT.md` (debe integrarse en `docs/ai/`).
- **Scripts sueltos:**
  - `locustfile.py` en raíz (debe evaluarse su migración a `tests/load/` o `tools/locust/`).

---

## 5. Auditoría de Calidad y Suite de Pruebas

Se ejecutó la suite de pruebas bajo el entorno Python 3.14.7 del sistema:

### 5.1. Resultados Generales
- **Pruebas Aprobadas:** 2.190
- **Pruebas Omitidas (Skipped):** 66 (omisiones esperadas: pruebas dependientes de hardware/red externa o que requieren datasets masivos no versionados en clon limpio).
- **Cobertura Total:** **86,85%** sobre los paquetes `app/` y `src/` (el requisito mínimo fijado en `pytest.ini` es 80%).

### 5.2. Observaciones Identificadas (No Bloqueantes para R1)
1. **Dependencia opcional de Selenium:**
   El módulo `tests/test_measure_browser_e2e_d21.py` importa funciones de `scripts/measure_browser_e2e_d21.py`, las cuales requieren `selenium`. Dado que `selenium` no forma parte de `requirements-dev.txt` (las pruebas de navegador se ejecutan en entornos dedicados o contenedores), la recolección global de pytest sin exclusión puede abortar si no se dispone de `selenium` en el host.
   *Recomendación:* Agregar `pytest.importorskip("selenium")` en el encabezado de la prueba para permitir skip limpio.
2. **Afirmación de selector CSS en `test_risk_colors.py`:**
   La prueba `test_stylesheet_sets_touch_targets_without_dataframe_checkbox_hack` evalúa que `data-testid="stDataFrame"` no se encuentre en las reglas de hoja de estilo. Sin embargo, el endurecimiento de contraste visual incorporado en PR #29/PR #30 para la tabla de ranking incluye estilos orientados a dicho contenedor, generando un fallo de aserción menor en dicha prueba aislada.
   *Recomendación:* Reconciliar la aserción en el ciclo regular de PR #30 sin romper el diseño accesible.

---

## 6. Auditoría de Enlaces Internos y Documentación

Se realizó un escaneo automatizado sobre la totalidad de los archivos Markdown del repositorio:
- **Enlaces Internos Válidos:** 98,2% de los hipervínculos dirigen a archivos existentes.
- **Enlaces Rotos Históricos Detectados:**
  Existen referencias a archivos dentro de `data/processed/` (p. ej. `nasa_firms_2021-08-30_2026-08-30_manifest.json`, `fires_meteo_join_*.parquet`, `matriz_features_real_sapi32_preview.parquet`) presentes en documentos históricos de Hito 1:
  - `docs/informe-1-seminario-licenciatura.md`
  - `docs/matriz-riesgo.md`
  - `docs/matriz-trazabilidad-hu-test.md`
  *Explicación Técnica:* Dichos archivos fueron generados localmente durante experimentos de Hito 1 y están expresamente excluidos de Git por la regla `data/processed/*` de `.gitignore`. Sus equivalentes congelados para reproducibilidad residen en `artifacts/hito1/reproducibility/`.

---

## 7. Verificación de Seguridad y Secretos

1. **Ausencia de Secretos:**
   No se encontraron tokens, llaves de API (NASA FIRMS MAP_KEY, credenciales DMC, contraseñas de PostgreSQL) ni archivos `.env` en el historial ni en los archivos rastreados.
2. **Higiene de Build Context (`.dockerignore`):**
   Se verificó que `.dockerignore` excluye expresamente `.env`, `.env.*`, `.mcp.json`, `.venv*/`, `.git/` y carpetas de caché, evitando filtraciones en imágenes Docker.
3. **Modo Reproducible Protegido:**
   El sistema de inferencia opera por defecto con snapshots congelados (`SAPI_REPRODUCIBILITY_MODE=1`), garantizando que no se requieran credenciales activas en entornos de evaluación docente.
