# S.A.P.I. — Plan de pruebas del Sprint 3 (Hito 3)

Artefacto A5 (plan) de la rúbrica del Hito 3. Subtarea HU-92.T5 (SAPI-172). Versión 0.1 del 22-11-2026.

> **Orden de integración** (decisión del Director, 22-11-2026, a partir del hallazgo M-3 del Auditor): este plan se integra en `main` **antes que cualquier reporte** de HU-83, HU-89, HU-90, HU-91 y HU-85.T7. La fecha de su commit es la prueba de que existía antes. Puede haber ejecuciones en curso con preregistro propio, como HU-83 (`ml/sapi-83-preregistro`, sello `71722ef`), pero sus reportes no se integran antes que este plan.

## 1. Alcance

- **Incluye:** las 15 HU del Sprint 3 (sprint id 37) y sus subtareas de prueba.
- **Excluye en este ciclo** (según los tickets): E3, Modelo D v2, cualquier reentrenamiento del D desplegado, la corrección del DEM salvo que SAPI-119 decida otra cosa, el rediseño general del frontend y el despliegue cloud (SAPI-68).
- **Bloqueado:** HU-64, la parte temporal de HU-65, y HU-93 (RNN/GRU/LSTM) hasta la respuesta escrita de César (SAPI-165). Sus casos quedan planificados como **«no ejecutable — bloqueado»** y cuentan en el cumplimiento con ese motivo.

## 2. Niveles, herramientas y casos

Requerimientos según `docs/requerimientos.md`. Los IDs `CP-…` son del plan; entre paréntesis, la subtarea de Jira. Un caso marcado **(propuesto)** no figura en los CA de Jira: lo propone Gobernanza y debe confirmarlo el responsable de la HU.

| HU (MoSCoW) | Req. | Nivel | Casos | Caso negativo o de borde | Herramienta |
|---|---|---|---|---|---|
| HU-83 (Must) | RF-06 | Unitaria y reproducción | CP-83-01: umbral p90 calculado solo con años de entrenamiento. CP-83-02: reproduce las PR-AUC de `reports/experiment_abcd_h6_results.json` (SAPI-97) | CP-83-N1: fuga de umbral (año de prueba) → falla. CP-83-N2: resultado de reproducción alterado → la evaluación se detiene | pytest (`tests/test_sapi83_evaluacion_modelo_d.py`) |
| HU-64 (Must, **bloqueada**) | RF-07 | Unitaria | CP-64-01: las ventanas se construyen en orden cronológico (SAPI-101) | CP-64-N1: una ventana que cruza la frontera entre entrenamiento y prueba → la prueba falla (HU-64 CA2) | pytest |
| HU-65 (Must) | RF-08 | Reproducibilidad | CP-65-01: la tabla comparativa se reproduce (SAPI-108) | CP-65-N1: protocolo alterado → falla | pytest / script |
| HU-76 (Should) | RF-10 | Unitaria (fixture sintético en CI) | CP-76-01..03: sello, partición y UTF-8 (SAPI-116) | CP-76-N1: protocolo modificado después del sello → se niega a ejecutar. CP-76-N2: partición alterada → no coincide | pytest |
| HU-88 (Must) | RF-11, RNF-05 | Unitaria y aceptación | CP-88-01: `scripts/explicar_modelo_d.py` informa el número de árboles, 25 variables y el hash del artefacto (SAPI-110). CP-88-02: modificación en vivo y re-ejecución (SAPI-112) | CP-88-N1 **(propuesto)**: con un artefacto cuyo hash no coincide con el desplegado, el script se niega a generar el reporte (HU-88 CA1 exige el «hash verificado del artefacto») | pytest; ensayo de defensa |
| HU-80 (Should) | RF-01, RF-04 | Interfaz | CP-80-01: primera pantalla a 1366×768, aviso único y subtítulo sin sprint (SAPI-123) | CP-80-N1 **(propuesto)**: con una tarjeta sin dato, la prueba falla si la tarjeta se muestra vacía | pytest de interfaz |
| HU-86 (Must) | RF-01 | Interfaz | CP-86-01: tarjetas con valor y antigüedad, o con un motivo explícito (SAPI-120) | CP-86-N1: reaparece «no informado por el backend» → falla | pytest de interfaz |
| HU-93 (Could, **bloqueada**) | RF-09 | Interfaz | CP-93-01: rótulo «Experimental — no validado» (SAPI-126) | CP-93-N1: se elimina el rótulo → falla | pytest de interfaz |
| HU-91 (Must) | RNF-05, RNF-07 | Integración y aceptación | CP-91-01..n: matriz «falla → comportamiento esperado → resultado» (SAPI-145/146). CP-91-02: 3 tareas guiadas (SAPI-147) | CP-91-Nx: un negativo por cada falla de la matriz | pytest; protocolo de usabilidad |
| HU-75 (Must) | RNF-07 | Integración y carga | CP-75-01: `RankingDatabaseUnavailableIT` en `mvn verify` (SAPI-129). CP-75-02: A1, P1b y S1 según la preinscripción sellada (SAPI-130) | CP-75-N1: base caída (A1) → 100 % `500 internal_error` en menos de 10 s | Maven + Testcontainers; `tools/d05r2` |
| HU-89 (Must) | RNF-06 | Seguridad | CP-89-01: vulnerabilidades (SAPI-132). CP-89-02: secretos (SAPI-133) | CP-89-N1: un secreto de prueba en una rama temporal → el escaneo falla y bloquea la PR | Escáner por definir en SAPI-132/133 |
| HU-90 (Must) | RNF-08, RNF-03 | E2E y carga | CP-90-01: desde un clon limpio, `docker compose` levanta el stack y los health checks dan 200 (SAPI-136). CP-90-02: p95 con n declarado frente a la línea base (SAPI-137) | CP-90-N1 **(propuesto)**: con una variable de entorno obligatoria ausente, el arranque falla con un mensaje claro y no levanta un servicio a medias. CP-90-N2 **(propuesto)**: con un servicio detenido, la verificación de health checks falla | docker compose; arnés Selenium |
| HU-85 (Must) | RNF-04 | E2E y CI | CP-85-01: IT-13 (SAPI-140). CP-85-02: E2E correlacionado (HTTP, logs, SQL y captura) sobre el SHA del tag (SAPI-169) | CP-85-N1: un cambio que rompe una IT → el gate falla y bloquea el merge | `scripts/merge_gate.py`; CI |
| HU-92 (Must) | — (proceso) | Aceptación | CP-92-01: auditoría en vivo de 3 cadenas (SAPI-177) | CP-92-N1: se rompe un requisito y su prueba falla | Revisión manual con evidencia |
| HU-79 (Must) | — (aceptación) | Aceptación | CP-79-01: acta firmada (SAPI-155/156) | n/a (sesión con usuario) | Acta |
| Todas | — | Aceptación | CP-xx-V: subtarea `.V` de cada HU (15) | — | Sesión de HU-79 |

**Control:** las 12 HU Must tienen al menos un caso negativo planificado (HU-79 es aceptación de usuario y no aplica). Los negativos **(propuestos)** de HU-88 y HU-90 cierran el hallazgo M-1 del Auditor, pendientes de que el responsable de cada HU los confirme.

## 3. Criterios de entrada

1. Este plan está integrado antes de cualquier reporte de HU-83, HU-89, HU-90, HU-91 y HU-85.T7.
2. Para KPI, carga, fiabilidad y usabilidad: las metas están selladas en `docs/objetivos.md` y `docs/requerimientos.md` antes de medir. Una meta que dice «meta pendiente de Daniel» no se mide.
3. **HU-83:** `scripts/evaluacion_modelo_d.py` y `docs/dias_prueba_seleccionados.csv` ya están versionados en `ml/sapi-83-preregistro` (commits `9f7b023` y `3a8f45c`; sello `7c8498b`; re-sello `71722ef`, con GO del Auditor). El dataset `14b36ad8…` se verifica por hash justo antes de cada corrida.
4. **Carga:** es la única carga en la máquina y el stack está arriba durante toda la corrida; si no se cumple, la corrida se anula (HU-75 CA6).
5. **Casos bloqueados:** hay respuesta escrita de César en SAPI-165.

## 4. Criterios de salida

1. Cada Must tiene al menos un caso ejecutado y aprobado, más su negativo, **o** un motivo de no ejecución registrado como deuda técnica.
2. 0 defectos críticos abiertos.
3. El cumplimiento se informa como **casos ejecutados / casos planificados** (objetivo ≥ 95 %, criterio 3a de la rúbrica de Matías). Cada caso no ejecutado lleva su motivo.
4. Cobertura de líneas: ≥ 70 % en la lógica de negocio (criterio 3b) y ≥ 80 % en la suite Python (gate de `pytest.ini`). Se informan por separado.
5. Cada reporte lo genera la herramienta, con fecha y ligado a un SHA.

## 5. Registro de defectos

| ID | Descripción (fuente) | Estado documentado al 22-11-2026 | Subtarea |
|---|---|---|---|
| D-01 | Lint v2: `70c29f9` ya está en `main` | Pasa en `main` según la CI run 41932911572 (dossier de Plataforma, 22-11). Pendiente de que el Auditor lo certifique | SAPI-141 |
| D-02 | `test_stylesheet_sets_touch_targets_without_dataframe_checkbox_hack` | Pasa en `main` según la misma run. Pendiente de certificación | SAPI-167 |
| D-03 | El arnés de capturas RUN-04 no desplaza la tabla antes de capturar | Abierto | SAPI-170 |
| D-04 | El 504 por timeout no está documentado en el contrato | Abierto | SAPI-171 |
| D-05 | Fallo rápido con la base caída o el pool saturado | NO GO a 3000 ms y a 5000 ms (histórico); el cambio de backend no está en ninguna ref | SAPI-128..130 |
| D-06 | Celdas sin DEM (con B-13 y B-17) | Abierto; decisión de César pendiente | SAPI-119 |
| D-07 | **Descripción no encontrada** en las fuentes | Por documentar | — |

La severidad queda **por asignar**, porque no figura en los tickets.

## 6. Informe de resultados

Al cierre se redacta `docs/pruebas/informe-resultados.md`. Por tipo de prueba explica qué se probó, qué resultó, qué significa, qué falló y qué se decidió.
