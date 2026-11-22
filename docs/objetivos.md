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
| KPI-03 | OE4 | Latencia visible p95 por escenario | **Línea base histórica del Hito 2**, medida el 28-10-2026 con n = 30: carga en frío **1.330,1 ms**; actualizar **1.919,1 ms**; recarga 938,9 ms; expandir tabla 615,8 ms. **Medición previa al sellado.** La meta «p95 ≤ 2.000 ms» del Hito 2 se fijó el 29-10-2026, después de medir, y **no se usa como meta cumplida** | **meta pendiente de Daniel** | Arnés Selenium repetido, mismo método, n declarado (HU-90.T2) | Por medir |
| KPI-04 | OE4 | Suite sin fallos y cobertura en el SHA de entrega | En `main` el 28-10-2026: 2138 aprobadas, 1 fallida, cobertura 86,32 %, lint v2 FAIL (Informe del Hito 2, Tabla 53). **Medición previa al sellado** | **meta pendiente de Daniel** | pytest y Maven en CI sobre el SHA del tag `hito3` | Por medir |
| KPI-05 | OE5 | Mejora sobre las bases en particiones con soporte ADEQUATE | 1 partición ADEQUATE (2024); no se alcanzó. **Medición previa al sellado** | **meta pendiente de Daniel**: con OE5 comparativo puede tener que reformularse | Walk-forward por año | Por medir |
| KPI-06 | OE3 | Proporción de participantes que interpreta el score como relativo | Sin línea base: no hubo estudio con usuarios (Informe del Hito 2, Tabla 53) | **meta pendiente de Daniel** (según el Hito 2, se define con el docente) | Protocolo con usuarios (HU-91.T3, HU-79) | Por medir |

**Validación por un stakeholder:** cada resultado medido se presentará en la sesión de HU-79. Su aprobación queda con nombre, rol y fecha en el ticket. **Al 22-11-2026 no hay ninguna aprobación registrada.**

**Otra medición anterior, no usada como línea base:** un borrador del 15-11-2026, fuera del repositorio, cita 6,9 s en frío y 3,7 s al actualizar (24-10-2026, commit `2a71c7e`). No se re-verificó. Como línea base se usa la del Informe del Hito 2 (28-10-2026, n = 30).

## 6. Mediciones previas al sellado

| Medición | Commit | Fecha UTC | Preregistro propio | ¿Tiene meta asociada? |
|---|---|---|---|---|
| HU-83 R2–R6 (evaluación del Modelo D con datos reales) | `2175742` (rama `ml/sapi-83-preregistro`) | 2026-11-22T06:02:42Z | Criterio `c15993c` (2026-11-22 01:16 -0300) y sello `71722ef` (2026-11-22T04:27:43Z) | No: «meta pendiente de Daniel». Ningún valor se fijó después de medir |

**El plan general se escribió 5 minutos después de esta ejecución; se declara como brecha, no se modifica ninguna fecha.** Fechas de commit verificadas con `git log` el 22-11-2026: la medición es `2175742` (2026-11-22T06:02:42Z) y el plan general es `f7c340d` (2026-11-22T06:08:00Z).

Esta brecha no cambia ninguna meta de la sección 5: todas siguen como «meta pendiente de Daniel».
