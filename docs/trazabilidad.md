# S.A.P.I.: matriz de trazabilidad del Hito 3 (A4)

Subtarea HU-92.T2 (SAPI-150). Versión 0.1, 22-11-2026, **antes del tag `hito3`**. Se actualiza al integrar cada PR.

Se lee en las dos direcciones. Desde un objetivo se llega a una prueba ejecutada con su evidencia. Desde un PR se vuelve al requisito y al objetivo. La columna **Resultado** dice la verdad: Aprobado, Parcial o No hecho, con su motivo. Los requisitos marcados como propuestos están en `docs/requerimientos.md`.

Para que «Aprobado» valga, también hacen falta la aprobación del stakeholder registrada en Jira (subtarea `.V`) y el PR integrado al tag. Mientras eso no exista, el resultado es **Parcial**.

## 1. Matriz

| Objetivo | Requisito | Modelo (A7) | HU | Sprint | Caso de prueba | Nivel | Evidencia | Resultado | PR / tag |
|---|---|---|---|---|---|---|---|---|---|
| OE1, OE3 | RF-01 Consultar el ranking de 50 celdas (Must) | C4 nivel 2: Streamlit → Spring Boot → FastAPI | SAPI-55/57/61 | S2 | `tests/test_backend_client.py`, `tests/test_sapi61_http_stub.py` | Unitaria e integración | Job `python` en `main`, run 41932911572 | Aprobado (S2) | `main` `9e70867` |
| OE1 | RF-02 Inferencia por HTTP con contrato (Must) | C4 nivel 2: ml-api | SAPI-55/56/57 | S2 | `tests/test_ml_api.py`, `tests/test_openapi_contracts.py` | Unitaria y contrato | Ídem | Aprobado (S2) | `main` |
| OE2 | RF-03 Persistir ejecuciones (Must) | Modelo de datos PostGIS (V001–V004) | SAPI-58/59 | S2 | Pruebas Flyway y SQL | Integración | Jobs `flyway-integration` y `sql-migration-validation` en `main` | Aprobado (S2) | `main` |
| OE3 | RF-04 Navegar el mapa y la tabla (Must) | C4 nivel 3: vista Streamlit | SAPI-61/66; HU-80 | S2, S3 | `tests/test_ranking_backend_view.py`; E2E de SAPI-66 | Unitaria y E2E | E2E del S2 solo en local (PR #41) | Parcial: el E2E no está repetido sobre el SHA de entrega (DT-01) | `main`; HU-80 sin PR |
| OE5 | RF-05 Insumos versionados (Must) | Flujo de insumos | SAPI-43/71 | S2 | Pruebas de SAPI-71 (139 sintéticas) | Unitaria | Job `python` en `main` | Aprobado (S2) | `main` |
| OE5 | RF-06 Evaluación con días reales (Must, propuesto) | Script `evaluacion_modelo_d.py` | HU-83 | S3 | `tests/test_sapi83_evaluacion_modelo_d.py` (57 casos, con negativos de fuga de umbral y reproducción) | Unitaria y científica | `reports/evaluacion_modelo_d_20261122.json`, `curva_ca1.json`, `docs/hito3/hu83_lectura_figuras.md`; CI 6/6 sobre `cc711e7` | Parcial: falta la aprobación de La Cruz (HU-83.V) y el merge | PR #47 |
| OE5 | RF-07 Red temporal (Must en Jira; bloqueado) | — | HU-64 | S3 | — | — | — | **No hecho**: bloqueado hasta la respuesta de César (SAPI-165) | — |
| OE5 | RF-08 Comparación D / A / temporal (Must, propuesto) | ADR D frente a A | HU-65 | S3 | — | — | Comparación A/B/C/D del H2 (`reports/experiment_abcd_h6_results.json`) | **No hecho** en el S3; la parte D frente a A existe desde el H2 | — |
| OE3 | RF-09 Predicción temporal en pantalla (Could; bloqueado) | — | HU-93 | S3 | — | — | — | **No hecho**: bloqueado (SAPI-165) | — |
| OE5 | RF-10 Trazabilidad científica (Should, propuesto) | `tools/science_trace/` | HU-76 | S3 | — | — | — | **No hecho**: CA5 bloqueado (archivo E2 no localizado) | — |
| OE3 | RF-11 Explicar el Modelo D (Must, propuesto) | Script `explicar_modelo_d.py` | HU-88 | S3 | `tests/test_hu88_explicar_modelo_d.py` (13 casos, entre ellos el tope de iteraciones y el hash antes y después) | Unitaria | `docs/modelo_d_una_pagina.md`; CI 6/6 sobre `a693a27` | Parcial: faltan La Cruz (HU-88.V) y el ensayo de la defensa (T3, T4) | PR #46 |
| OE2 | RNF-01 Replay sin duplicados (Must) | Modelo de datos | SAPI-58/59 | S2 | Replay e IT-05 | Integración | Informe del H2, Tabla 53 | Aprobado (S2) | `main` |
| OE1 | RNF-02 Contratos OpenAPI v0 (Must) | Contratos `contracts/openapi/` | SAPI-56/57; HU-91.T4 | S2, S3 | `tests/test_openapi_contracts.py`; IT-09, IT-09b, IT-09c | Contrato | Job `python` | Parcial: el 504 por timeout del ML no está documentado (D-04, HU-91.T4) | `main` |
| OE4 | RNF-03 Latencia p95 (Must) | C4 nivel 2 | HU-90 | S3 | CP-RNF-03 (Selenium, n declarado) | Eficiencia | Línea base del H2 en `docs/objetivos.md` (KPI-03) | **No hecho** en el S3: la meta sigue pendiente de Daniel | — |
| OE4 | RNF-04 Gate en verde en el SHA de entrega (Must) | CI | HU-85 | S3 | `scripts/merge_gate.py`, 6 jobs | Integración | `main` 6/6 (run 41932911572); `docs/hito3/gate-prs-ramas.md` | Parcial: IT-13 solo en Windows local; tag pendiente | PR #50 |
| OE3 | RNF-05 Score entendido como ranking relativo (Must) | Vista y documento de una página | HU-86, HU-88, HU-91 | S3 | `test_sapi86_*` (incluido el caso negativo del texto legado) | Unitaria y aceptación | CI de #48 | Parcial: falta la validación de comprensión con La Cruz (HU-91.V, HU-88.V) | PR #48, #46 |
| Transversal | RNF-06 Seguridad (Must) | Workflow `security.yml` | HU-89 | S3 | `tests/test_secret_scan.py` (8 casos, 2 negativos) | Seguridad | `docs/calidad/seguridad-sprint3.md`, `pip_audit_20261122.json` | Parcial: falta Trivy de imágenes (DT-02) y La Cruz (HU-89.V) | PR #49 |
| OE4 | RNF-07 Fallo rápido con la base caída (Must, propuesto) | Backend Spring Boot | HU-75 | S3 | `RankingDatabaseUnavailableIT`; A1, P1b, S1 | Fiabilidad | Corridas fuera del repositorio (`C:\SAPI-S3-D05-HARDEN-20261103`) | **No hecho**: el cambio no está commiteado (DT-05); la meta de M2 sigue pendiente | — |
| OE4 | RNF-08 Arranque con un comando (Must, propuesto) | Docker Compose | HU-90 | S3 | IT-13; health checks | E2E | Acta F2 (solo Windows) | **No hecho** en el S3: falta README y una corrida en Linux | — |

## 2. Controles de la rúbrica

| Control | Valor al 22-11-2026 | Comentario |
|---|---|---|
| Must sin prueba ejecutada | RF-07, RNF-03, RNF-07, RNF-08 | Declarados como No hecho, con su motivo |
| Pruebas sin requisito | 0 en las HU del S3 | Las pruebas heredadas del S1 y el S2 están en `docs/hito2/TRAZABILIDAD_HU_CA_EVIDENCIAS.md` |
| HU «Hechas» sin criterios o sin aprobación de un stakeholder | 0 | Ninguna HU del S3 está en Finalizado todavía |
| Must sin elemento del modelo | Pendiente | Depende del modelamiento del S3 (HU-92.T8) |
| HU sin sprint | 0 | Todas están en el sprint 37 de Jira |
| Riesgos sin requisito u objetivo afectado | 0 | Ver `docs/riesgos.md` |

## 3. Cómo verificar una fila

```bash
# PR que citan la HU (GitHub): is:pr SAPI-83
grep -rn "SAPI-83\|RF-06" tests/ docs/      # pruebas y documentos que la citan
git branch -r | grep -v "SAPI-"             # ramas sin ID de ticket (ver docs/hito3/gate-prs-ramas.md)
```
