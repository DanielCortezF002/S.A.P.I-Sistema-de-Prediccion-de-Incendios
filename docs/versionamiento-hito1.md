# Versionamiento — Sprint 1 / Hito 1

**Estado:** documento de trabajo, auditoría del estado real de Git — no
modifica el repositorio. Arquitectura/Testing/Trazabilidad/Atributos de
Calidad/Riesgos permanecen CONGELADOS. Fecha de esta fase: **07-09-2026**.

## 1. Propósito

Evaluar el criterio "Versionamiento" (8%) de la rúbrica de Hito 1 con
evidencia real de `git log`/`git branch`/`git tag`, sin asumir que una
rama, tag o convención existió porque un documento dijera que debía
existir. No se crea ningún tag, commit ni rama en esta fase.

## 2. Estado del repositorio

Ver `artifacts/hito1/versioning/git-status.txt` (captura textual, sin
editar). Rama actual: `main`, adelantada a `origin/main` por 7 commits
locales aún no empujados. Sin cambios pendientes en `src/`, `app/`,
`tests/`, `data/` (los únicos archivos sin trackear son la documentación
nueva de este Hito, `.claude/`, `artifacts/`, `tools/`).

## 3. Historial de commits

Fuente: `artifacts/hito1/versioning/git-log.txt` (captura completa,
`git log --all`).

| Métrica | Valor |
|---|---|
| Commits en `main` | 68 (`git log main --oneline \| wc -l`) |
| Commits totales (`--all`, incluye ramas de trabajo) | 73 |
| Primer commit (main) | 2026-06-20, `6fcffa0` |
| Último commit (main) | 2026-09-07, `9f07617` |
| Autores distintos (identidades Git) | 4 (ver sección 3.2) |

### 3.1 Distribución temporal real

```
2026-06-20  20 commits   <- arranque del proyecto (pipeline legacy)
2026-06-25   2 commits
2026-07-06   1 commit
                          <- brecha de 53 días sin commits (07-06 a 08-28)
2026-08-28   2 commits
2026-08-30   1 commit
2026-08-31  10 commits   <- día de cierre planificado de Sprint 1
2026-09-01   6 commits
2026-09-02   5 commits
2026-09-03   2 commits
2026-09-04   4 commits
2026-09-05   8 commits
2026-09-07   7 commits   <- día del Hito 1
```

**Hallazgo real, no oculto:** existe una brecha de 53 días (06-07-2026 a
28-08-2026) sin ningún commit en `main`. La actividad se concentra
fuertemente en dos ventanas: el arranque (20-06-2026, 20 commits el
mismo día) y los 8 días previos/posteriores al cierre de Sprint 1
(28-08 a 07-09-2026, 45 de los 68 commits de `main`).

### 3.2 Autores (identidades Git reales)

```
    47  danie <danie@example.com>
    22  Daniel Gonzalo Cortez Fierro <d.cortezfierro@uandresbello.edu>
     3  Daniel Cortez <daniel.cortez@duocuc.cl>
     1  Daniel Gonzalo Cortez Fierro <128172594+DanielCortezF002@users.noreply.github.com>
```

**Hallazgo real:** una sola persona (Daniel Cortez), pero con **4
identidades Git distintas** a lo largo del proyecto (una genérica de
entorno local, dos institucionales de universidades distintas, y una de
GitHub noreply). No es evidencia de trabajo en equipo — es una
inconsistencia de configuración de Git, no de autoría real.

## 4. Calidad de mensajes

Prefijos usados en `main` (68 commits):

| Prefijo | Commits |
|---|---|
| `feat:` | 23 |
| `fix:` | 23 |
| `docs:` | 10 |
| `checkpoint:` | 3 |
| `test:` | 2 |
| `ui:` | 2 |
| `chore:` | 2 |
| `refactor:` | 1 |

66/68 commits (97%) usan un prefijo identificable de tipo de cambio.
**No se afirma "Conventional Commits" en sentido estricto** — no hay
`BREAKING CHANGE:`, scopes siempre entre paréntesis, ni un `CHANGELOG`
generado desde el historial — pero el patrón `tipo(scope): descripción`
es consistente y real (ejemplos verificados: `fix(ingesta): corregir
endpoint DMC y agregar credenciales/estaciones reales`,
`feat(sapi-30): pipeline DEM real + corrección de métricas fabricadas`,
`test(coverage): ampliar suite a gate 80% (SAPI-45)`).

**Clasificación: FUERTE.** Mensajes descriptivos, identificables (tipo +
módulo/scope + qué cambió), y mayoritariamente coherentes con el diff
real que introducen (verificado por muestreo contra el contenido de los
commits auditados en fases anteriores — p. ej. `60f9fa7 checkpoint:
temporal pipeline audit and reproducibility guards` corresponde
efectivamente a la auditoría del pipeline temporal).

## 5. Estrategia de ramas observada

Ver `artifacts/hito1/versioning/git-branches.txt`.

| Rama | Última actividad | Rol observable |
|---|---|---|
| `main` | 2026-09-07 | Rama principal, integra todo el trabajo |
| `origin/develop` | 2026-06-20 (sin actividad desde entonces) | Existe en remoto, pero congelada desde el primer día — no se usó como rama de integración activa |
| `feature/dmc-live-card` | 2026-09-05 | Rama de feature real, con contraparte en remoto |
| `experiment/real-cells-map-preview` | 2026-09-05 | Rama de experimento, solo local |
| `design/direccion-b-institucional` | 2026-09-05 | Rama de exploración de diseño, solo local |
| `wt-design-b-work`, `worktree-gleaming-meandering-pudding` | 2026-09-02/04 | Worktrees de trabajo paralelo, no ramas de feature convencionales |

**No se afirma GitFlow.** Existe una rama `develop` en el remoto, lo que
sugiere una intención de seguir un flujo tipo GitFlow, pero no hay
evidencia de que se haya usado activamente (0 commits después del
inicial, ningún merge documentado desde `feature/*` hacia `develop`).
El patrón real observable es: **trabajo directo sobre `main`** con
ramas de `feature/`/`experiment/`/`design/` usadas puntualmente para
exploración, no como parte de un flujo de integración formal
documentado.

**BRANCHING_STRATEGY: PARTIAL** — hay nomenclatura consistente
(`feature/`, `experiment/`, `design/`) y una rama `develop` remota, pero
sin evidencia de un flujo de integración (PRs, merges documentados)
seguido de forma consistente.

## 6. Tags / versiones

Ver `artifacts/hito1/versioning/git-tags.txt`.

| Tag | Fecha | Mensaje |
|---|---|---|
| `v1.0.0-data` | 2026-06-20 | Línea de base del pipeline de datos e ingesta |
| `v2.0.0-baseline` | 2026-06-20 | Línea de base del motor analítico (RF preliminar) |
| `v3.0.0-final-release` | 2026-06-20 | Versión final del prototipo (entrega anterior) |
| `v3.2.0-demo-professional` | 2026-06-20 | Demo profesional 7 días |
| **`v1.0.0-sprint1-verified`** | **2026-08-31** | **"SAPI Sprint 1 — cierre con trazabilidad verificada (Hito 1)"** |
| `v1.1.0-corredor-verified` | 2026-09-05 | Grilla del corredor verificada + sistema de diseño |

**SPRINT_CLOSE_TAG: FOUND.**

### 6.1 Autenticidad y tipo del tag (verificación forense, 07-09-2026)

`git cat-file -t v1.0.0-sprint1-verified` devuelve `tag` (no `commit`) —
es un **objeto tag anotado (ANNOTATED)**, no un lightweight tag. Un
lightweight tag no tendría objeto propio ni tagger, y `git cat-file -t`
devolvería directamente `commit`.

| Campo | Valor |
|---|---|
| `TAG_TYPE` | ANNOTATED |
| `TAG_OBJECT` | objeto tag Git real (verificado con `git cat-file -p`) |
| `TARGET_COMMIT` | `5388c55f21b0af805023659ec18f2e65555f1a75` |
| `TARGET_COMMIT_AUTHOR_DATE` | 2026-08-31 23:02:47 -0400 |
| `TARGET_COMMIT_COMMITTER_DATE` | 2026-08-31 23:02:47 -0400 |
| `TAGGER_NAME` | danie |
| `TAGGER_EMAIL` | danie@example.com |
| `TAGGER_DATE` | 2026-08-31 23:09:39 -0400 |

Por ser un tag **anotado** con `TAGGER_DATE = 31-08-2026`, sí puede
afirmarse con la fuerza que da Git: **Git registra el tag anotado con
fecha de creación/tagger 31-08-2026** — esta fecha no se infiere del
commit apuntado (que además coincide, a 7 minutos de diferencia), sino
que es un campo propio del objeto tag, firmado por su tagger.

**Mensaje del tag (texto completo, `git cat-file -p`):**

> SAPI Sprint 1 — cierre con trazabilidad verificada (Hito 1)
>
> Primera versión con trazabilidad verificada contra el código y tests
> automatizados reproducibles. [...] Evidencia de cierre (31-08-2026):
> Suite 188/188 PASS (Docker analytics-backend, Python 3.11); Cobertura
> 80.34%; SAPI-45 y R-COBERTURA-01 cerrados; SAPI-44 cerrado. Alcance
> explícitamente diferido: R-INTEGRACION-01, R-CONAF-01,
> inference_engine/persister/spatial_joiner.

### 6.2 Contraste con documentación histórica

`docs/acta-pruebas-aceptacion-usuario.md` (fila "Versión probada",
línea 22) ya contenía, antes de esta fase, la referencia literal:
*"Commit correspondiente al tag `v1.0.0-sprint1-verified`, confirmado
por la presencia del badge [...]"*.

**HISTORICAL_DOC_REFERENCES_TAG: YES.** Esto es evidencia adicional de
existencia histórica del tag (otro documento ya lo citaba antes de esta
verificación), pero **no sustituye** la distinción técnica
lightweight/annotated hecha en 6.1 — ambas líneas de evidencia (el
objeto Git anotado y la cita documental previa) son independientes y
convergentes.

**SPRINT_CLOSE_TAG_EVIDENCE: VERIFIED** (no solo `PARTIAL`) — tag
anotado real, con tagger date propio del 31-08-2026, target commit del
mismo día, mensaje detallado con evidencia técnica citada, y una
referencia documental independiente y anterior a esta fase. No se creó
ni se backdateó nada en esta verificación.

`v1.1.0-corredor-verified` (05-09-2026) es un segundo tag real, posterior
al cierre de Sprint 1, que documenta el avance de la corrección de la
grilla (R-GRILLA-01). **No existe ningún tag fechado el 07-09-2026**
(fecha de este Hito) — si se decide crear uno ahora (p. ej.
`hito1-evidence-2026-09-07`), sería un tag real del estado actual,
creado hoy, y debe describirse exactamente así: **tag de cierre
documental actual (07-09-2026)**, nunca como si hubiera existido al
cierre de Sprint 1 (31-08). **En esta fase no se crea ningún tag.**

## 7. Changelog / versiones de paquete

Búsqueda explícita: `CHANGELOG.md`, `VERSION`, `RELEASES.md`,
`pyproject.toml` — ninguno existe en el repositorio.

**CHANGELOG: NOT_FOUND.**

## 8. Trazabilidad Git ↔ Jira

Ver `artifacts/hito1/versioning/git-jira-links.txt`. Cálculo reproducible
sobre `main` (68 commits):

| Métrica | Valor |
|---|---|
| Commits con referencia explícita `SAPI-xx` | 7 |
| Commits con referencia legacy `#HU-xx`/`#TS-xx` | 3 |
| Total commits main | 68 |
| Tasa de trazabilidad explícita a Jira | 7/68 = **10.3%** |
| Tasa combinada (SAPI + legacy) | 10/68 = **14.7%** |

Los 7 commits con `SAPI-xx` corresponden exactamente a SAPI-28, SAPI-30,
SAPI-32 y SAPI-45 — consistentes con las HU/tareas ya verificadas en
`docs/trazabilidad-hito1.md`. **No se cuentan como "vinculados" commits
sin la referencia explícita**, aunque su contenido pudiera relacionarse
semánticamente con una HU (p. ej. los commits del pipeline temporal
`60f9fa7`, `99efd7a`, `46ceaec` no mencionan ningún ticket — son
**posiblemente relacionados** con el trabajo metodológico del Hito, pero
no cuentan como trazabilidad Git↔Jira real, consistente con
`TEMPORAL_PIPELINE_HU_LINK: GAP` ya documentado en Trazabilidad).

## 9. Cronología Sprint 1

| Fecha | Evento verificable |
|---|---|
| 2026-06-20 | Primer commit del proyecto (pipeline legacy, tags v1.0.0-data a v3.2.0-demo-professional) |
| 2026-08-28 a 2026-08-31 | Corrección de endpoints reales (NASA FIRMS, DMC), 4 HU técnicas (SAPI-26/28/30/32 parcial), gate de cobertura 80% |
| **2026-08-31** | **Cierre planificado de Sprint 1** — tag real `v1.0.0-sprint1-verified` creado el mismo día |
| 2026-09-01 a 2026-09-05 | Trabajo posterior al cierre planificado: SAPI-30/32 avanzados, hallazgo R-GRILLA-01 y su corrección, sesión de aceptación de usabilidad móvil, tag `v1.1.0-corredor-verified` |
| 2026-09-06 a 2026-09-07 | Auditoría y construcción del pipeline temporal nuevo (fuera de Sprint 1 según Jira, dentro de la ventana de Hito 1) |
| **2026-09-07** | **Hito 1** — fecha de esta fase |

### 9.1 Partición temporal exacta de Sprint 1 (corrección 07-09-2026)

Base temporal usada de forma consistente: **fecha de commit
(`committerdate`, `%cd`)**, no fecha de autor — ambas coinciden en la
práctica para este repositorio (un solo autor real, sin rebases
detectados), pero se documenta cuál se usó para que el cálculo sea
reproducible exactamente.

| Ventana | Definición | Commits (main) |
|---|---|---|
| `PRE_SPRINT` | fecha < 03-08-2026 | 23 |
| `SPRINT_1_WINDOW` | 03-08-2026 ≤ fecha ≤ 31-08-2026 | 13 |
| `POST_PLANNED_CLOSE` | fecha > 31-08-2026 | 32 |
| **Total** | — | **68** |

`23 + 13 + 32 = 68` — partición completa y verificada, sin solapamiento
ni commits sin clasificar. **No se llama "commits durante el Sprint" a
los 36 commits anteriores al 31-08** (error de la versión previa de
este documento, que agrupaba `PRE_SPRINT` y `SPRINT_1_WINDOW` bajo una
sola cifra): de esos 36, solo **13** caen dentro de la ventana real
03-08 a 31-08-2026 — los otros 23 son commits del arranque del proyecto
(20-06 a 30-07-2026), anteriores a que Sprint 1 comenzara.

**32 de 68 commits de `main` (47%) ocurrieron después del 31-08-2026** —
se muestran explícitamente en la cronología de arriba, no se cuentan
silenciosamente como trabajo completado al cierre del Sprint.

## 10. Brechas

1. Brecha de 53 días sin commits (06-07 a 28-08-2026) — sin explicación
   verificable en el repositorio.
2. `BRANCHING_STRATEGY: PARTIAL` — rama `develop` remota sin uso activo;
   sin evidencia de un flujo de PR/merge documentado.
3. `CHANGELOG: NOT_FOUND`.
4. Solo 10.3% de los commits de `main` referencian un ticket Jira
   explícito — el 89.7% restante no es trazable a Jira desde el mensaje
   de commit por sí solo.
5. 4 identidades Git distintas para la misma persona — higiene de
   configuración, no un hallazgo de autoría múltiple.
6. `TEMPORAL_PIPELINE_HU_LINK: GAP` (heredado de Trazabilidad) se refleja
   aquí también: los commits más recientes y metodológicamente centrales
   (pipeline temporal) no referencian ningún ticket.

## 11. Evidencia reproducible

`artifacts/hito1/versioning/{git-status.txt, git-log.txt, git-branches.txt,
git-tags.txt, git-jira-links.txt}` — capturas textuales del estado real
al 07-09-2026, generadas con `git status`, `git log --all`,
`git for-each-ref`, `git shortlog -sne --all`, `git log main --oneline`.
Ningún archivo fue editado manualmente tras generarse.
