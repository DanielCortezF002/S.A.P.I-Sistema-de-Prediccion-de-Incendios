# Auditoría de CI y pruebas omitidas

## 1. CI (`.github/workflows/ci.yml`, 6 jobs vía `scripts/merge_gate.py`)

freeze · python · backend-unit · sql-migration-validation · flyway-integration · container-smoke. No existe job E2E (el
comentario del workflow lo difiere a SAPI-66): **la cadena completa nunca corre en CI**. `backend-unit` ejecuta `mvn test`
(sin `*IT`; los Testcontainers no corren en este job según lo observado en surefire: solo clases `*Tests`).
Artefactos gate de `150837e` y `569c898` versionados en `artifacts/hito2/ci/gate/`.

## 2. Reconciliación de números

| Fuente | Total | Ok | Omitidas | Fallos |
|---|---:|---:|---:|---:|
| Expediente previo (merge sintético, PR #36) | 2292 | 2178 | 114 | 0 |
| Esta sesión, `0ac6c05`, Linux sin Docker/pwsh/playwright | **2292** | 2154 | **138** | 0 |

Total idéntico (2292); +24 omitidas aquí = diferencia de entorno, verificada por diff de JUnit: 16+7 PowerShell ausente y 1
Docker ausente (CA8 dinámico). Consistente con que en CI esas 24 corran (runner con Docker y pwsh), **pero no verificable**: el JUnit versionado de `150837e` (114 omitidas) es anterior a la introducción de `test_f1_ca8_...` (commit `7dcd0b6`) y de los artefactos del merge sintético (2292) no hay copia en el repo; la lista de 114 de §3 sale de `150837e`, por tanto es la causa observada en ese commit, no una medición del merge sintético. Maven (162, 4 omitidas) no
está en el 2292 (que es pytest).

## 3. Las 114 omisiones de CI, por causa real (de `pytest-junit.xml` de `150837e`)

| N | Causa literal | Archivos | Clase | Riesgo |
|---:|---|---|---|---|
| 65 | manifiesto real de Data/Output ausente | `test_convergence_data_adapter_contract` 57, `..._output_acceptance` 3, `TestRealManifestAcceptance` 5 | Dependencia externa (plano de datos del Omen) | **Alto**: el contrato adaptador↔datos reales no se prueba nunca en CI |
| 26 | `data/raw`/`data/processed` no versionados (parquet, DMC) | `test_temporal_dataset_integration` 9, `test_prototype_service` 9, `test_data_loader_golden` 2, `test_megaevento_report` 2, y 1 c/u `nan_journey`, `pipeline_validators`, `row_explainer`, `scoring_inputs` | Dependencia externa / esperado | Medio: reproducibilidad científica solo en máquina con datos |
| 12 | `playwright` no instalado | `test_control_center_browser` 9, `test_ops_dashboard` 3 | **Cobertura faltante**: no está en `requirements-dev.txt`, así que CI *siempre* omite | Medio: UI del centro de control sin prueba de navegador en CI |
| 9 | Solo Windows (junctions, rutas case-insensitive) | `test_workspace_safety` 6, `test_operational_workspace` 2, `test_firms_baseline_guard` 1 | Esperado por plataforma | Bajo/Medio: se prueba solo en Omen |
| 2 | Solo dentro de la imagen Docker (`/app`) | `test_docker_build_hygiene` | Esperado | Bajo |
| **114** | | | | |

Más 4 omisiones Java (`RankingRealMlServiceTests`, sin `SAPI_IT_ML_BASE_URL`): **cobertura faltante con defecto latente**
(ver `E2E_VERIFICATION_REPORT.md` §3). **No** puede afirmarse que todas las omisiones sean inocuas: las 65 + 4 ocultan
verificaciones de integración real, y 12 son un hueco evitable.

## 4. CA8 (SAPI-43.CA8): lo que se puede y no afirmar

- Qué prueba `test_f1_ca8_operational_overlay_dynamic`: stack Compose real + contenedor-sonda cuyo `SAPI_ML_BASE_URL` apunta a
  un stub en el host (`host.docker.internal` + `--add-host host-gateway`); espera **500 `internal_error`** para
  `baseline`/`reproducibility`, 200 para `current`, 0 escrituras en rechazo. Se omite sin Docker.
- Mapeo del backend (`RankingService.interpret`): origen no permitido → `INTERNAL_ERROR` **500**; si el ML es inalcanzable →
  `UPSTREAM_UNAVAILABLE` **503**; 503 del ML con `error_type` conocido → se propaga.
- **Hipótesis (no verificada)** sobre el 503 vs 500 del experimento Linux: el sondeo no alcanzó el stub del host (firewall del
  puente Docker en Linux, bind/ruta de `host.docker.internal`), con lo que el backend devolvió `upstream_unavailable` 503 en vez
  de evaluar la política. Si es así, no es regresión de la política sino de alcanzabilidad del entorno de prueba, y la prueba
  debería distinguir "stub inalcanzable" de "política violada" (hoy ambos aparecen como fallo de `status == 500`).
- **No determinable aquí**: el commit del experimento CA8 no está en este repositorio ni hay Docker. La comparación 503/500 con
  logs del backend (`ml_predict`, campos `ml_responded`, `outcome`) es la prueba decisiva: `ml_responded=false` ⇒ hipótesis cierta.
- Diferencia entre commits de CI versionados: `569c898` (SAPI-57) → `150837e` (SAPI-60): +60 archivos, persistencia/compose; ninguno
  contiene el test CA8 dinámico (se añade en `7dcd0b6`), así que **ningún artefacto versionado muestra su resultado en CI**. Para la candidata definitiva: ejecutar el test en Linux **con** Docker y exigir
  que el log pruebe `ml_responded=true` antes de aceptar el 500.

## 5. Recomendaciones

1. Añadir `playwright` (o marcar explícitamente) para eliminar 12 omisiones evitables.
2. Aplicar el parche de `RankingRealMlServiceTests` y ejecutarlo en CI/Omen con un ML vivo.
3. Job E2E real en CI (Compose) cuando SAPI-66 se cierre.
4. En el gate, convertir omisiones por "manifest absent" en un recuento visible por causa (hoy solo número total).
