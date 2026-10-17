# S.A.P.I. — Contexto autoritativo de trabajo para agentes (snapshot orientativo)

**Proyecto:** S.A.P.I. — Sistema de Alerta y Predicción de Incendios. En fuentes académicas también aparece «... Incendios Forestales»; validar nombre legal/caratulado contra plantilla y documento oficial antes de modificar portada.
**Repositorio remoto:** https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios
**Rutas históricas Windows:** `C:\SAPI-PUBLICACION-SEGURA-20261016`, `C:\SAPI`, `C:\SAPI-RG`; NO asumir cuál es el checkout activo sin `git rev-parse`.
**Asignaturas:** Seminario de Licenciatura (docente César, INSW421) y Proyecto de Título (docente Matías). Son criterios de evaluación independientes; verificar entregables específicos.

## Estado conocido al 17-10-2026, NO verdad perpetua
- Jira Sprint 2 ID 36 aparece **closed**; objetivo: vertical slice local con DMC/FIRMS → FastAPI Modelo D → Spring Boot → PostgreSQL/PostGIS → Streamlit. El cierre del sprint en Jira NO implica automáticamente que todos sus alcances/documentos estén aprobados.
- `SAPI-71` refresh atómico/versionado, `SAPI-43` corrida diaria, `SAPI-66` E2E del vertical slice: Jira **Finalizado** al consultar. Obtener evidencias actuales antes de informar entrega.
- `SAPI-67`: pendiente de validación; `SAPI-68`: por hacer; `SAPI-64` y `SAPI-65`: por hacer. Revisar alcance concreto de sprint en los registros (no asumir comprometidos).
- PR #30: navegación bidireccional ranking↔mapa, **OPEN, Ready for review, NO MERGED** en última consulta; HEAD `c5e274cb7d48ab9c498e18b57bb52b8279f96067`; revisarlo otra vez antes de cualquier acción. Merge requiere autorización humana nueva.
- En reporte de Antigravity: 411 pruebas locales seleccionadas PASS y pruebas E2E Edge de clic directo sobre celdas. NO extrapolar esto a todo el repositorio ni a validación científica.

## Arquitectura efectiva reportada (verificar contra checkout)
- Frontend Streamlit + Folium: ranking territorial de malla 50 celdas, panel de detalle, prioridad relativa, selección tabla/mapa.
- Backend Spring Boot, ML API FastAPI / Modelo D, PostgreSQL/PostGIS, Docker Compose; n8n como orquestador separado.
- API de ranking v0 y contratos: no añadir campos no suministrados; meteo regional y detalle FIRMS por celda podrían no existir en contrato vigente.
- Capa de datos FIRMS/DMC: versionado y CURRENT con integridad, fallos controlados, no escritura de baseline congelado.
- Copernicus GLO-30 DEM: cobertura incompleta, N/D donde falta evidencia; no sustituir por cero, promedios o inferencia no declarada.

## Validez científica y riesgos críticos
- Score = orden relativo **NO** probabilidad calibrada. `scientific_model_validation=false`, F4 FAIL.
- Ausencia de validación externa concluyente frente a incendios históricos y calibración; falta aceptación formal de docentes/experto cuando aplique.
- No alegar operación CONAF/SENAPRED ni alertas en tiempo real.
- No transformar prototipo reproducible en sistema de decisión real mediante simples cambios de texto UI.

## Fuentes que hay que releer por tarea
1. Rama/SHA y PRs de GitHub; evidencia bajo `docs/evidence/`; pruebas ejecutadas y logs.
2. Jira SAPI, sprint y CA específicos (referir issue), sin cambiar estado por simple existencia de código.
3. Ambas rúbricas/formatos **originales**, syllabus, plantilla Informe 2 y feedback Hito 1; localizar, no adivinar rutas.
4. Model Card del Modelo D, ADRs de arquitectura, esquema PostGIS, contrato OpenAPI, QA-04 DEM, bitácoras del release gate.

No usar este archivo como fuente para fechas/estados después de la instantánea: revalidar siempre.
