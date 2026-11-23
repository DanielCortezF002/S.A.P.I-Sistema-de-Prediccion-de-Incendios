# S.A.P.I. — Problema, objetivos y metas (Hito 3)

Artefacto A1 de la rúbrica del Hito 3 (profesor Matías, 10-11-2026). Subtarea HU-92.T6 (SAPI-173). Versión 0.1 del 22-11-2026.

> **Sello.** Este archivo fija las metas del Hito 3 **antes de medir**. Las mediciones anteriores conservan su fecha original y van marcadas como **«medición previa al sellado»**. Donde todavía no hay un valor acordado, dice **«meta pendiente de Daniel»**: no se mide ese KPI hasta que el valor quede commiteado.

## 1. Problema

Fuente: Informe del Hito 2, §4.1 y §4.3.

- **Enunciado:** integrar y exponer, de forma reproducible y comprensible, un ordenamiento relativo por celda geográfica a partir de datos satelitales (NASA FIRMS), meteorológicos (DMC) y topográficos (DEM), preservando la procedencia temporal y la identidad de cada ejecución.
- **Actores:** personal de análisis territorial y coordinación de emergencias. Para el Hito 3 el usuario de validación es el Cuerpo de Bomberos de La Cruz (HU-79). Ninguna institución ha adoptado el sistema.
- **Causas** (Informe del Hito 2, §4.4): datos heterogéneos, desfase de las fuentes, integración sin contrato, trazabilidad sin identidad de ejecución, interpretación del score y evaluación con pocos positivos.
- **Consecuencias:** cuesta justificar y reproducir una priorización espacial, y existe el riesgo de que el score relativo se confunda con una probabilidad de ignición.

## 2. Hipótesis

**Pendiente de Daniel.** El Informe del Hito 2 no formula una hipótesis de solución que conecte la intervención con un resultado medible: solo dice que la necesidad «se plantea como hipótesis» por validar con usuarios. Este documento no la redacta en su lugar.

## 3. Objetivo general

Diseñar e implementar un vertical slice reproducible de S.A.P.I. que produzca, persista y presente un ranking relativo de 50 celdas para un horizonte de 6 horas, con trazabilidad de insumos y versiones, verificable mediante pruebas funcionales, de integración y extremo a extremo (Informe del Hito 2, §5.1).

## 4. Objetivos específicos

| OE | Enunciado | Requerimientos (`docs/requerimientos.md`) |
|---|---|---|
| OE1 | Desacoplar la inferencia de la presentación mediante servicios con contrato | RF-01, RF-02, RNF-02 |
| OE2 | Persistir cada ejecución de forma idempotente y trazable en PostGIS | RF-03, RNF-01 |
| OE3 | Representar el score y sus empates con una semántica explícitamente relativa, y comprobar que el usuario lo entiende así | RF-01, RF-04, RF-09, RF-11, RNF-05 |
| OE4 | Disponer de un entorno reproducible desde un clon limpio, con un release etiquetado y verificado | RNF-03, RNF-04, RNF-07, RNF-08 |
| OE5 | **Analizar comparativamente el enfoque algorítmico:** evaluar el Modelo D frente al Modelo A y a bases ingenuas con datos reales y un protocolo temporal causal, aceptando «no concluyente» como resultado válido. No se plantea como un logro predictivo | RF-05, RF-06, RF-07, RF-08, RF-10 |

El nuevo enunciado de OE5 responde a la observación SHOULD de César en su revisión del Hito 2: «replantear OE5 como evaluación del enfoque, no como logro predictivo». **Daniel debe confirmarlo.**

## 5. Indicadores (KPI) del Hito 3

Las definiciones y las mediciones anteriores vienen del Informe del Hito 2 (Tablas 10 y 53).

| KPI | OE | Métrica | Línea base (origen) | Meta H3 | Método | Resultado H3 |
|---|---|---|---|---|---|---|
| KPI-01 | OE1, OE3 | % de ejecuciones verificadas con 50/50 celdas, rank 1–50 y metadatos de modelo y origen | Cumplido en la ejecución id=1 (16-10-2026) y en IT-02/IT-04 (28-10-2026). **Medición previa al sellado** | **meta pendiente de Daniel** | Prueba de contrato y consulta SQL por ejecución | Por medir |
| KPI-02 | OE2 | Filas duplicadas al repetir una ejecución con iguales insumos | 0 en el replay del 16-10-2026 y en IT-05 del 28-10-2026. **Medición previa al sellado** | **meta pendiente de Daniel** | Replay y conteo SQL | Por medir |
| KPI-03 | OE4 | Latencia visible p95 por escenario | **Línea base histórica del Hito 2**, medida el 28-10-2026 con n = 30: carga en frío **1.330,1 ms**; actualizar **1.919,1 ms**; recarga 938,9 ms; expandir tabla 615,8 ms. **Medición previa al sellado.** La meta «p95 ≤ 2.000 ms» del Hito 2 se fijó el 29-10-2026, después de medir, y **no se usa como meta cumplida** | **Sellada el 23-11-2026, decidido por Daniel Cortez:** p95 ≤ 2.000 ms **en cada escenario por separado** (carga en frío, actualizar, recarga, expandir tabla). Ver §5.1 | Arnés Selenium `2a9bcf9` (rama de la PR #54), con el protocolo de §5.2: calentamiento más 30 rondas intercaladas (HU-90.T2, CP-90-02) | Por medir |
| KPI-04 | OE4 | Suite sin fallos y cobertura en el SHA de entrega | En `main` el 28-10-2026: 2138 aprobadas, 1 fallida, cobertura 86,32 %, lint v2 FAIL (Informe del Hito 2, Tabla 53). **Medición previa al sellado** | **meta pendiente de Daniel** | pytest y Maven en CI sobre el SHA del tag `hito3` | Por medir |
| KPI-05 | OE5 | Mejora sobre las bases en particiones con soporte ADEQUATE | 1 partición ADEQUATE (2024); no se alcanzó. **Medición previa al sellado** | **meta pendiente de Daniel**: con OE5 comparativo puede tener que reformularse | Walk-forward por año | Por medir |
| KPI-06 | OE3 | Proporción de participantes que interpreta el score como relativo | Sin línea base: no hubo estudio con usuarios (Informe del Hito 2, Tabla 53) | **meta pendiente de Daniel** (según el Hito 2, se define con el docente) | Protocolo con usuarios (HU-91.T3, HU-79) | Por medir |

### 5.1. Meta de KPI-03 (sellada el 23-11-2026, decidido por Daniel Cortez)

Decisión registrada para la nueva evaluación del Hito 3. Se sella **antes** de cualquier medición de KPI-03 del Hito 3.

- **Meta:** p95 de la latencia visible ≤ 2.000 ms, evaluado **por separado** en cada uno de los cuatro escenarios: carga en frío, actualizar, recarga y expandir tabla. Un escenario que supera 2.000 ms no se compensa con los demás.
- **Tamaño de muestra:** 30 rondas por escenario, después de un ciclo de calentamiento (protocolo en §5.2).
- **Cálculo del percentil:** rango más cercano, posición ⌈0,95·n⌉ (§5.2). El método que produjo la línea base del 28-10-2026 no está documentado.
- **Criterios de entrada:** candidato identificado por SHA, stack operativo durante toda la corrida y sin cargas concurrentes en la máquina. Si alguno no se cumple, la corrida se anula y se registra.
- **Integridad de los datos:** se conservan las muestras crudas, los errores y los timeouts. No se descartan resultados desfavorables ni se ajusta la meta después de medir.
- **Línea base:** la medición histórica del 28-10-2026 queda **«solo reportada»**. Su método difiere del de esta meta (§5.2, punto 13) y no cuenta como cumplimiento.
- **Alcance:** latencia visible con **un usuario**. No acredita capacidad bajo concurrencia.

### 5.2. Protocolo de medición de KPI-03 (aprobado por Daniel Cortez el 23-11-2026)

Se sella **antes** de cualquier medición de KPI-03 del Hito 3. Arnés: `scripts/measure_browser_e2e_d21.py` en `2a9bcf949e9b2479191c1311f2e93634d5c0bf2e` (rama de la PR #54: `a3d08ee` → `961c879`, que agrega el preset `--protocol kpi03-h3` → `8819140`, que cambia la medición de expandir tabla → `2a9bcf9`, que corrige M-1). SAPI-Auditor dio GO para medir con este arnés (`kpi03-arnes-2a9bcf9-20261123.md`, ver punto 16). Las líneas citadas son de `2a9bcf9` y se volvieron a verificar el 23-11-2026; el preset está en las líneas 563–576.

1. **Meta:** p95 de la latencia visible ≤ 2.000 ms **en cada escenario**: carga en frío, actualizar, recarga y expandir tabla.
2. **Percentil:** rango más cercano (*nearest rank*). Se ordenan las n muestras de menor a mayor y se toma la posición ⌈0,95·n⌉, contando desde 1. Con n = 30 es la **posición 29** (preset: `percentile_method = nearest_rank`).
3. **Calentamiento:** un ciclo completo de los 4 escenarios, separado y **fuera** de las muestras oficiales (preset: `warmup = 1`; rol `warmup`, que no entra en el percentil). **Un calentamiento no ok anula la corrida, y ahora lo aplica el propio arnés:** marca `annulled=true` y deja el veredicto global y el de cada escenario en `NO_EVALUABLE` (líneas 962–980 y 1011–1014). El veredicto que habría salido sin anular se guarda aparte (`verdict_without_annulment`), solo como dato. La corrida anulada se conserva y se documenta sin reemplazar muestras, y se hace una corrida nueva desde cero.
4. **Rondas:** después del calentamiento, **30 rondas** con los 4 escenarios intercalados (preset: `order = interleaved`, `repetitions = 30`). Orden fijo registrado de antemano: **carga en frío → actualizar → recarga → expandir tabla** (el orden de `SCENARIOS`, línea 512). El arnés escribe `schedule.csv` antes de la primera muestra. En total, 120 muestras oficiales.
5. **Sin agrupar:** cada escenario conserva sus 30 muestras y su propio p95. No se combinan escenarios.
6. **Fallos:** un fallo, un timeout o la ausencia del evento final cuentan como **+∞** y quedan dentro de las 30 (preset: `failure_policy = as_infinite`). Una muestra fallida **no se reemplaza** con un nuevo intento.
7. **Condición adicional de cumplimiento:** **cero fallos por escenario**. Un escenario con algún fallo no cumple, aunque su p95 sea finito.
8. **Inicio y fin de cada medición, según el arnés:**
   - **Expandir tabla:** método fijado en **`--expand-method current`**, que el preset exige explícito. el inicio es `t_click = performance.now()` en un listener de clic en **fase de captura** sobre el `<summary>`; el fin es `t_visible = performance.now()` (línea 1134) en la primera comprobación (MutationObserver o requestAnimationFrame) que ve la grilla **realmente visible** dentro del `<details>`. Desde `8819140`, «visible» exige tres cosas: `details.open`, `checkVisibility()` (que respeta content-visibility, visibility y opacity) y **área visible > 0** después de recortar la caja de la grilla por cada ancestro con `overflow` distinto de `visible`. Así no cuenta una grilla todavía oculta por la animación de apertura (`_GRID_VISIBLE_FN_JS`, líneas 1052–1083). Si el navegador no tiene `checkVisibility`, se usa el criterio de caja. El listener del clic en fase de captura está en las líneas 1149–1153 y el bloque `_EXPAND_ARM_JS` en las líneas 1101–1158. Antes del clic se espera el reposo del expansor (`wait_for_expander_ready`, línea 1294). Los dos instantes salen del reloj del navegador y no hay `sleep` en Python.
   - **Carga en frío, actualizar y recarga:** el arnés **no** usa `performance.now`. Mide con `time.perf_counter` de Python y sondea cada 50 ms (resolución declarada de ±50 ms; `TIMING_INFO`, líneas 594–611; sondeo en las líneas 393 y 441). Actualizar incluye un `sleep(0.2)` fijo dentro del intervalo (línea 419). Las tres líneas son las mismas que en `a3d08ee`. Esto se declara como limitación del método.
9. **Plazos de timeout auditados** (constantes de las líneas 537–540):

   | Escenario | Plazo |
   |---|---|
   | Carga en frío | `COLD_TIMEOUT_S = 35.0` s |
   | Recarga | `RELOAD_TIMEOUT_S = 30.0` s |
   | Actualizar | `UPDATE_TIMEOUT_S = 30.0` s |
   | Expandir | `EXPAND_TIMEOUT_S = 5.0` s |

   Además, `set_page_load_timeout(45)` (línea 199). Una grilla que aparece después del plazo cuenta como timeout (línea 1124).
10. **Precondiciones:** el candidato está identificado por su SHA; el stack (Docker Compose) está operativo durante toda la corrida; es la única carga en la máquina. Si alguna no se cumple, la corrida se anula y se registra.
11. **Estado de caché y sesión por escenario:**
    - **Carga en frío:** navegador Edge nuevo en **cada** ronda (`create_driver()` por muestra y `quit()` al terminar), que restablece su condición inicial. El calentamiento **no** la convierte en carga caliente.
    - **Actualizar, recarga y expandir:** sesión compartida del navegador (`_get_session`), con caché y estado de esa sesión. Recarga usa `driver.refresh()` en esa misma sesión.
12. **Lo que se conserva:** las muestras crudas (CSV o JSON de filas, incluidos los fallos), el orden de ejecución (`seq`), la fecha, las versiones (Edge, Selenium, Python, Docker), el SHA del sistema candidato y el SHA del arnés (`2a9bcf9`). Cada fila del CSV lleva `harness_commit_sha` y `harness_dirty`, y la identidad verificable es `harness_commit_sha` con `harness_dirty=false`.
13. **Comparación con el Hito 2:** el método histórico **difiere**. Aquel arnés usaba n = 1 por escenario y `sleep(0.5)` en expandir, el percentil no estaba documentado y las muestras crudas no se localizaron. Por eso la línea base del 28-10-2026 queda **«solo reportada»**: no se compara estadísticamente con el resultado del Hito 3.
14. **Alcance:** un solo usuario. No acredita capacidad bajo concurrencia.
15. **Comando oficial:**

    ```powershell
    python scripts\measure_browser_e2e_d21.py --protocol kpi03-h3 `
      --candidate-sha a3d08eeeb8ead8f4be8d0d9611c4b9c44e8fa5d9 `
      --expand-method current `
      --url http://127.0.0.1:8501 --backend-url http://127.0.0.1:8080 `
      --project-name <proyecto_compose> `
      --artifacts-dir <carpeta_nueva_fuera_del_repo>
    ```

    `--protocol kpi03-h3` fija los valores de los puntos 2 a 7 y rechaza con exit 2 cualquier flag que los contradiga. El exit code es 0 solo si el veredicto global es PASS. Las URL son las que propuso UX; el proyecto Compose y la carpeta de artefactos se fijan al medir.

    **Sistema candidato:** `a3d08eeeb8ead8f4be8d0d9611c4b9c44e8fa5d9`. Es el árbol del que Plataforma construyó el stack medido (proyecto Compose `sapi-kpi03-a3d08ee`; informe de Plataforma `reports/orden09-kpi03-stack/README.md`, SHA-256 `6c9eaec5d7e976520a67b4a6808785709bcaff0c523c5e86ee0b3030bfaa2e51`). Sus `app/` y `services/` son idénticos a los de la PR #48 (`f8c5218805f94eaa3cbec3572a7825efc6c79bf2`): `git diff f8c5218 a3d08ee` solo cambia archivos de `scripts/` y `tests/` (verificado el 23-11-2026). El arnés (`2a9bcf9`) es una herramienta de medición y no forma parte del sistema candidato.

16. **Condición del Auditor (opción b, informe `kpi03-arnes-2a9bcf9-20261123.md`, SHA-256 `978c694e9d55679fe2a6fe980632cb79914004edd657cd7da5fd2501dd39fcf6`):** el arnés no marca la muestra que sigue a un fallo ni comprueba que el sistema esté en reposo antes de `t0` en actualizar y recarga. Expandir sí espera el reposo (línea 1294) y la carga en frío abre un navegador nuevo. Por eso:
    - una corrida con **algún fallo** en las muestras oficiales **no cumple** (FAIL o NO_EVALUABLE, punto 7);
    - su p95 **no se reinterpreta ni se corrige** (no se excluyen ni se recalculan muestras);
    - el informe señala como **posiblemente afectadas** las muestras que siguen a un fallo en la misma sesión (actualizar y recarga).

**KPI-01, KPI-02, KPI-04, KPI-05 y KPI-06 siguen NO APROBADAS** («meta pendiente de Daniel»).

**Validación por un stakeholder:** cada resultado medido se presentará en la sesión de HU-79. Su aprobación queda con nombre, rol y fecha en el ticket. **Al 22-11-2026 no hay ninguna aprobación registrada.**

**Otra medición anterior, no usada como línea base:** un borrador del 15-11-2026, fuera del repositorio, cita 6,9 s en frío y 3,7 s al actualizar (24-10-2026, commit `2a71c7e`). No se re-verificó. Como línea base se usa la del Informe del Hito 2 (28-10-2026, n = 30).

## 6. Mediciones previas al sellado

| Medición | Commit | Fecha UTC | Preregistro propio | ¿Tiene meta asociada? |
|---|---|---|---|---|
| HU-83 R2–R6 (evaluación del Modelo D con datos reales) | `2175742` (rama `ml/sapi-83-preregistro`) | 2026-11-22T06:02:42Z | Criterio `c15993c` (2026-11-22 01:16 -0300) y sello `71722ef` (2026-11-22T04:27:43Z) | No: «meta pendiente de Daniel». Ningún valor se fijó después de medir |

**El plan general se escribió 5 minutos después de esta ejecución; se declara como brecha, no se modifica ninguna fecha.** Fechas de commit verificadas con `git log` el 22-11-2026: la medición es `2175742` (2026-11-22T06:02:42Z) y el plan general es `f7c340d` (2026-11-22T06:08:00Z).

Esta brecha no cambia ninguna meta de la sección 5: al 22-11-2026 todas seguían como «meta pendiente de Daniel». La meta de KPI-03 se selló después, el 23-11-2026 (§5.1), y no tiene relación con esta medición de HU-83.
