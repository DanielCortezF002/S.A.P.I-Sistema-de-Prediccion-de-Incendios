# Criterio 4 · índice de evidencia · 25-11-2026

Rama `DanielCortezF002/plan-25-11-c4-c5` (commits locales, sin push). Stack medido: proyecto Compose `sapi-h3-518c0b5`, código `518c0b58e6b229317f51b1da56ac23346dc2ef74`. Ejecutado en el computador local (AMD Ryzen AI 7 350, 8 núcleos/16 hilos, 31 GB, Windows 11 Home 10.0.26200), no en ambiente desplegado.

| Punto del plan | Estado | Evidencia | Clasificación |
|---|---|---|---|
| 1a. Stack desde 518c0b5 en proyecto nuevo | Hecho el 25-11 01:06–01:08 Santiago; no se rehízo | [INFORME.md](../../reports/orden-25-11-h3/INFORME.md), punto 1; [identidad/](../../reports/orden-25-11-h3/identidad/) | Histórico (25-11, madrugada). Verificado hoy 08:03: los 4 contenedores de `sapi-h3-518c0b5` siguen Up |
| 1a. Desvío respecto del plan | El plan pedía **los mismos puertos** con `sapi` detenido (solo stop). Lo que se hizo fue **otros puertos** (15432/18000/18080/18501) y `sapi` **sigue arriba** (verificado hoy con `docker ps`: 4 contenedores Up 14 h en 5432/8000/8080/8501). Los digests de `sapi` sí están registrados (`identidad/stacks.txt`). a3d08ee conservado | `docker ps` de hoy, 08:03 | Verificado hoy |
| 1b. Recorrido Edge de 6 pasos, una vez | Hecho el 25-11 04:28–04:29 UTC; no se repitió. Pasos 3 y 4 comparten captura (B-3) | [recorrido-edge/MATRIZ.md](../../reports/orden-25-11-h3/recorrido-edge/MATRIZ.md) | Histórico |
| 1c. Seguridad | **No cumple** la medida declarada | [seguridad-c4-2026-11-25.md](seguridad-c4-2026-11-25.md) | Sondas: verificado hoy. Escáneres: histórico (25-11 madrugada) |
| 1c. Eficiencia (k6) | N=2 no se corrió, sustituida por RNF-03. Corrida RNF-03 a nivel API, 1 VU, 30 iteraciones: **no cumple** (1 fallo 503 de 30; p95 por rango más cercano 8.604,2 ms > 2.000 ms). No es KPI-03 ni acredita capacidad bajo concurrencia | [REPORTE-rnf03-1vu-2026-11-25.md](../../reports/orden-25-11-h3/k6/REPORTE-rnf03-1vu-2026-11-25.md); declaración N=2 en [eficiencia-k6-2026-11-25.md](eficiencia-k6-2026-11-25.md) | Corrida: histórico (25-11, 11:54–11:56 UTC). Cifras y logs del 503: verificado hoy. Causa de la muerte del worker: pendiente |
| 1c. Mantenibilidad (radon) | **No cumple** (3 funciones CC rango D) | [mantenibilidad-radon-2026-11-25.md](mantenibilidad-radon-2026-11-25.md) | Verificado hoy |

pytest: no se corrió ninguna suite para este criterio.

## Después del criterio 4

| Punto | Estado | Evidencia |
|---|---|---|
| 2. Fiabilidad | Meteorología faltante observada en el stack; ml-api, backend y base caídos y punto de quiebre NO_EVALUABLE | [fiabilidad-modo-degradado-2026-11-25.md](fiabilidad-modo-degradado-2026-11-25.md) |
| 3. Criterio 5 | C4 y ERD generados y cotejados | [../arquitectura/c5-cotejo-2026-11-25.md](../arquitectura/c5-cotejo-2026-11-25.md) |

Nota: `Invoke-K6Eficiencia.ps1` se guardó de nuevo con BOM UTF-8 después de la declaración (`1e4f26f`), para que Windows PowerShell 5.1 lea bien las tildes de la cabecera. No cambian N, duración, calentamiento ni criterio; `k6_ranking.js` no cambió.
