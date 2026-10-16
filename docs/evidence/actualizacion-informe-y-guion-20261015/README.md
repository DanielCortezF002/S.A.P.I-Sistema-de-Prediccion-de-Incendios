# Actualización factual — Informe 2 y guion de presentación (Directiva 32 §4)

Los dos borradores fuente (`C:\SAPI-HITO2-FUENTES\10-esqueleto-informe-hito2.md`
y `11-guion-presentacion-hito2.md`) describen un estado **anterior** del
proyecto (era "RC1"/bridge n8n/Operations plane, placeholders
`[ATTEMPT2_RESULT]`, `[GATE_VERDICT]`, `[JIRA_STATUS]` sin resolver, narrativa
de "el camino está construido pero la demostración de punta a punta... está
pendiente"). El sistema avanzó sustancialmente desde esa fecha: hoy existe un
vertical slice real (Streamlit→Spring Boot→FastAPI→PostGIS) con gate
mayoritariamente verde. Reescribir el Informe 2 y el guion completos es una
tarea de redacción académica que excede el alcance de esta sesión de
ingeniería; este documento resuelve los placeholders factuales conocidos para
que esa reescritura no tenga que re-investigarlos.

## Placeholders resueltos con evidencia de esta sesión

| Placeholder | Valor correcto (15-10-2026) | Evidencia |
|---|---|---|
| `[GATE_VERDICT]` | **FAIL** (no PASS) — por excepciones explicadas, no por defectos nuevos: F1 origin/main (sin remoto real), F6/F9 (hashes preexistentes idénticos al origen inmutable), F4/SAPI-71 (autorizado, ver `docs/evidence/sapi71-f4-prep/`). Los 5 subgates restantes (python, backend-unit, sql-migration-validation, flyway-integration, container-smoke) **PASS real**. | `/c/sapi-gate/609f615ceca7/gate_summary.json` |
| `[ATTEMPT2_RESULT]` | No aplica al estado actual — ese concepto (Attempt2/bridge n8n) pertenece a la arquitectura anterior a Spring Boot/FastAPI. El vertical slice actual se valida con `merge_gate.py --job all`, no con "intentos" del bridge. | `docs/evidence/brechas-academicas-cerradas-20261015/README.md` §1 |
| `[JIRA_STATUS]` | 9/14 historias DONE (37/58 SP); 5 abiertas con estado real documentado (SAPI-43 PARTIAL/BLOCKED evitable, SAPI-49/63/67 recomendadas DONE, SAPI-66 con CA5 resuelto y resto pendiente) | Jira comentarios `10156`-`10160`; este paquete de evidencia |
| `[RUBRICA_HITO2]` | Matías 8 criterios/100% (`rubrica sprint 2 matias.md`); César 6 criterios/100% (`rubrica sprint 2 cesar.md`) — ambas localizadas y aplicadas en `docs/evidence/rubricas-hito2-verificadas-20261015/README.md` | Ídem |
| `[PR1_STATUS]` | No hay PR publicado para el candidato actual; `release/sprint2-closeout-candidate` permanece local, sin push ni merge autorizado | `git log`, `git status` de esta sesión |

## Narrativa corregida (reemplaza el párrafo de "Narrativa central" del guion)

> "Después del Sprint 1 pasé de demostrar que SAPI podía generar un ranking a
> construir y **verificar en vivo** la cadena completa: Streamlit consume la
> API REST de un backend Spring Boot, que a su vez orquesta un microservicio
> FastAPI con el Modelo D y persiste el resultado en PostgreSQL/PostGIS de
> forma correlacionada e idempotente. El gate de calidad corre hoy sobre el
> candidato final y pasa en 5 de 6 subgates; el sexto (freeze) falla solo por
> excepciones ya documentadas y autorizadas, no por defectos nuevos. Lo que
> sigue pendiente no es la arquitectura — es la ejecución operacional diaria
> con datos DMC/FIRMS en vivo, bloqueada hoy por una decisión humana de
> credenciales, no por ingeniería."

## Qué falta para un Informe 2 / guion definitivos (no ejecutado aquí)

1. Reescribir las secciones 5-9 del esqueleto (arquitectura, data plane,
   operations, output plane, Modelo D) contra el estado real descrito en
   `docs/evidence/brechas-academicas-cerradas-20261015/README.md` §1, no
   contra el delta de 29-09.
2. Añadir la sección formal de preguntas de investigación y estado del arte
   exigida por el syllabus de César (bibliografía IEEE/APA: Hernández
   Sampieri; Cruz Lemus et al.) — brecha de redacción pura, no de ingeniería.
3. Confirmar timing real de la demo (15+5 o 20 min) y ensayarla contra el
   candidato `bca136c` (o el SHA de merge posterior, si se autoriza).
