# 02 — Cambios realizados y pruebas dirigidas

**Fecha:** 2026-10-24  
**Workspace:** `C:\SAPI-S2-RECOVERY-CODE-20261024`  
**HEAD:** `51ec3c06b67959d3daad6349c962a1be643906b4`  
**Tree:** `68da56fcf0e0dc3bbe9048a9faac4cfceec49ef0`  
**Entorno:** Python 3.14.7; pytest 9.1.1; Java 21.0.12.1; Maven Wrapper 3.9.16; Windows 11.

## 1. Resumen de cambios

Se hicieron **dos cambios de código** y se crearon los cuatro documentos de `recovery-evidence/`:

| Archivo | Cambio | Motivo | Prueba |
|---|---|---|---|
| `scripts/measure_browser_e2e_d21.py` | +82 / −5 líneas: hash SHA-256 de capturas, tipo de navegación, verificación real de grilla y estado no hardcodeado | Endurecer la evidencia CA4 y evitar que una captura o un `True` fijo se presenten como prueba | `tests/test_measure_browser_e2e_d21.py` (18 PASS) |
| `tests/test_measure_browser_e2e_d21.py` | +61 líneas: 5 pruebas nuevas; las 13 existentes no se modificaron | Cubrir los helpers nuevos y el caso “sin grilla visible” | idem |
| `recovery-evidence/01…04` | Documentos nuevos | Entregables de recuperación | n/a |

**No se modificó**: código de aplicación, `docker-compose*.yml`, migraciones, imágenes PNG, CSV históricos, el candidato protegido ni `C:\SAPI`. No se ejecutó Docker, build de imágenes, Testcontainers, D08, G1, L1, Jira, push ni merge.

### 1.1 Cambio en el arnés CA4

El arnés `scripts/measure_browser_e2e_d21.py` ya tenía la corrección de precisión de timestamp (Directiva 28 / Defecto A). Se añadió:

1. `sha256_file(path)`: calcula SHA-256 en mayúsculas de cada PNG y lo registra en la columna `screenshot_sha256`.
2. `get_browser_navigation_type(driver)`: lee `performance.getEntriesByType('navigation')[0].type`; RUN-03 solo se marca con `content_verified=True` si el tipo es `reload`.
3. `verify_expanded_grid(driver)`: exige al menos un `stDataFrame`/`stTable` visible; RUN-04 ya no usa `content_verified: True` fijo, sino `grid_ok and kpi_exp_ok`.
4. Columnas nuevas `action` y `browser_navigation_type` para distinguir `driver.get`, clic de Streamlit, `driver.refresh` y expansión de grilla.
5. El resumen final imprime `PASS` o `FAIL` según `content_verified`, en vez de imprimir `PASS` siempre.

**Alcance:** es un endurecimiento **prospectivo**. No se regeneraron CSV ni PNG históricos; por tanto, **no convierte CA4 en dos pruebas independientes** ni cambia el estado de Gate B. La evidencia histórica se sigue leyendo en `01-DIAGNOSTICO-CA.md`.

## 2. Pruebas Python dirigidas

Todas se ejecutaron desde la raíz del workspace. El `pytest.ini` del repo impone `--cov-fail-under=80`; para una corrida dirigida se usó `-o addopts=""`, que desactiva **solo** esa configuración de cobertura, no las aserciones ni los tests. No se ejecutó la batería completa.

| ID | Comando exacto | Exit | Archivo | Resultado | Revisión | Conclusión verificable |
|---|---|---:|---|---|---|---|
| P-01 | `python -m pytest tests/test_compose_v2.py -o addopts="" -q` | 0 | `tests/test_compose_v2.py` | **34 passed** en 0.29 s | `51ec3c06` | Ruta v2 por defecto, profile `presentation`, secreto y fail-closed estáticamente conformes |
| P-02a | `python -m pytest tests/test_measure_browser_e2e_d21.py -o addopts="" -q` | 0 | `tests/test_measure_browser_e2e_d21.py` | **13 passed** en 1.44 s | `51ec3c06` | Línea base del arnés antes del cambio; precisión y rechazo de DOM estancado |
| P-02b | `python -m pytest tests/test_measure_browser_e2e_d21.py -o addopts="" -q` | 0 | `tests/test_measure_browser_e2e_d21.py` | **18 passed** en 1.47 s | `51ec3c06` + cambio local | 13 pruebas originales + 5 nuevas; helpers de hash, navegación y grilla |
| P-03 | `python -m pytest tests/test_db_migrations_v2.py -o addopts="" -q` | 0 | `tests/test_db_migrations_v2.py` | **12 passed** en 0.23 s | `51ec3c06` | V001–V004, PostGIS, constraints, seed de 50 celdas y ausencia de lenguaje de probabilidad |
| P-04 | `python -m pytest tests/test_ml_api.py -o addopts="" -q` | 0 | `tests/test_ml_api.py` | **23 passed** en 21.71 s | `51ec3c06` | Contrato ML, modelo real, errores y campos de score relativo |
| P-05 | `python -m pytest tests/test_architecture.py -o addopts="" -q` | 0 | `tests/test_architecture.py` | **8 passed** en 13.75 s | `51ec3c06` | Ausencia de dependencia transitiva del pipeline legacy y del scoring local |
| P-06 | `python -m pytest tests/test_openapi_contracts.py -o addopts="" -q` | 0 | `tests/test_openapi_contracts.py` | **14 passed** en 8.14 s | `51ec3c06` | Contratos OpenAPI versionados conformes |
| P-07 | `python -m pytest tests/test_f1_deployment_unit.py -o addopts="" -q` | 0 | `tests/test_f1_deployment_unit.py` | **3 passed** en 0.19 s | `51ec3c06` | Política de persistencia y gate `current` a nivel unitario/estático |
| P-08 | `python -m pytest tests/test_scoring_inputs.py -o addopts="" -q` | 0 | `tests/test_scoring_inputs.py` | **22 passed, 1 skipped** en 40.29 s | `51ec3c06` | Resolución de insumos, fingerprint, integridad de stores y modo reproducible |

**Total de la selección:** 34 + 18 + 12 + 23 + 8 + 14 + 3 + 22 = **134 PASS únicos** y **1 skip**. Incluye las 5 pruebas nuevas del arnés; sin ellas, la selección histórica es **129 PASS + 1 skip**. El run P-02a (13) es la línea base del mismo archivo; no se suma como prueba distinta. El skip de P-08 es una condición del entorno, no un fallo.

## 3. Pruebas Java dirigidas

Directorio de trabajo: `services/backend`.

```powershell
.\mvnw.cmd -B -o -DskipITs "-Dtest=RankingPersistenceServiceTests,FirmsOriginPolicyTests,FirmsOriginPolicyBindingTests,RankingResultValidatorTests" -DfailIfNoTests=false test
```

| ID | Exit | Resultado | Revisión | Conclusión verificable |
|---|---:|---|---|---|
| J-01 | 0 | **85 tests, 0 failures, 0 errors, 0 skipped**; `BUILD SUCCESS`; 18.98 s | `51ec3c06` | Persistencia de 50 filas, idempotencia, gate `current`, binding de política y validación de resultados |

Desglose de `services/backend/target/surefire-reports/`:

| Clase | Tests | Fallos | Errores | Skip |
|---|---:|---:|---:|---:|
| `FirmsOriginPolicyBindingTests` | 7 | 0 | 0 | 0 |
| `FirmsOriginPolicyTests` | 5 | 0 | 0 | 0 |
| `RankingPersistenceServiceTests` | 13 | 0 | 0 | 0 |
| `RankingResultValidatorTests` | 60 | 0 | 0 | 0 |
| **Total** | **85** | **0** | **0** | **0** |

`-o` fuerza Maven offline; `-DskipITs` evita failsafe/Testcontainers. Por tanto, esta corrida **no** sustituye `RankingHttpToPostgresIT`, `RankingPersistenceIT` ni `FirmsOriginLegacyRowIT`.

## 4. Comprobaciones estáticas y de evidencia

Todas las comprobaciones de esta sección se ejecutaron sobre `51ec3c06` (tree `68da56fc`), salvo las rutas externas W3/W4, que declaran el mismo SHA.

| ID | Comando | Exit | Archivo / salida | Resultado | Conclusión |
|---|---|---:|---|---|---|
| S-01 | `git status --porcelain --ignored` | 0 | worktree | Línea base: 0 cambios tracked; solo `__pycache__/` y `services/backend/target/` ignorados | Worktree limpio antes de los cambios |
| S-02 | `git rev-parse HEAD; git rev-parse 'HEAD^{tree}'` | 0 | Git | `51ec3c06…` / `68da56fc…` | Revisión atada al candidato |
| S-03 | `Get-ChildItem artifacts\hito2 -Recurse -Filter 'ca4_browser_*.png' \| ForEach-Object { Get-FileHash $_.FullName -Algorithm SHA256 }` | 0 | PNG CA4 | closeout update = cached = `49B4E796…`; d26 cold/update/cached = `A7E8B583…`; W3 cold/update/cached = `539A4BD5…` | Capturas idénticas por minuto; no se alteraron |
| S-04 | `Get-Content artifacts\hito2\closeout_e2e\timings_browser.csv; Get-Content artifacts\hito2\d26\timings_browser.csv` | 0 | CSV de timings | closeout: 897.39 / 1952.52 / 563.88 / 582.61 ms; d26: 3691.87 / 1526.44 / 604.65 / 563.68 ms | Tiempos documentados; RUN-02/03 comparten minuto |
| S-05 | `Test-Path tests\e2e\test_vertical_slice.py; Test-Path scripts\e2e_slice.py` | 0 | Artefactos E2E | `False` / `False` | CA1 y CA5 literales sin artefacto planificado |
| S-06 | `Select-String -Path docker-compose.yml -Pattern '^  [a-z0-9-]+:\|profiles:'` | 0 | `docker-compose.yml` | `web-v2` en línea 157; `profiles: ["presentation"]` en línea 161; `legacy`/`ops` separados | UI fuera de la ruta por defecto |
| S-07 | `Select-String -Path app\components\ranking_backend_view.py -Pattern '_human_hm\|Obtenido del backend'` | 0 | Vista de ranking | `_human_hm` en 137-138; header en 505; detalle con segundos en 849 | Header con precisión de minuto |
| S-08 | `Get-FileHash 'C:\SAPI-OCC-S2-A2-INTEG-20261022\EV-W3\validate_ca5.W3.diff' -Algorithm SHA256; Get-Content 'C:\SAPI-OCC-S2-A2-INTEG-20261022\EV-W3\validate_ca5.W3.diff'` | 0 | Validador W3 | SHA-256 `EFA6764D…`; exactamente 3 líneas sustituidas (`15c15`, `73c73`, `78c78`): ruta, puertos backend/ML, URL ranking | CA5 W3 no es literal |
| S-09 | `Get-FileHash 'C:\SAPI-OCC-S2-A2-INTEG-20261022\EV-W3\e2e\ca4_browser_cold.png','C:\SAPI-OCC-S2-A2-INTEG-20261022\EV-W3\e2e\ca4_browser_update.png','C:\SAPI-OCC-S2-A2-INTEG-20261022\EV-W3\e2e\ca4_browser_cached.png' -Algorithm SHA256` | 0 | PNG W3 | cold/update/cached = `539A4BD57BE75C37D3068FF4B26100287DA1BFF2889C4117F7A8275C5743AC11` | W3 también tiene capturas idénticas |
| S-10 | `git diff --stat` | 0 | Diff local | 2 archivos; +143 / −5 | Solo arnés y su test fueron modificados |

## 5. Integridad de la evidencia

- **No se editaron** los PNG CA4 ni los CSV históricos. Sus hashes se leyeron después de los cambios y coinciden con los de `01-DIAGNOSTICO-CA.md`.
- **No se regeneró** ningún E2E; los únicos artefactos nuevos son los cuatro Markdown de `recovery-evidence/`.
- **No se tocó** `C:\SAPI`, el candidato protegido, Jira, Git remoto ni imágenes Docker.
- **No se ejecutó** la batería completa ni el gate de cobertura. Los comandos dirigidos usan `-o addopts=""`; esto se declara para que no se confunda con una corrida de CI.
- **No se inventaron** PASS: los estados de `01` distinguen evidencia externa W3/W4, evidencia estática y brechas literales.

## 6. Qué no se ejecutó y por qué

| Actividad | Motivo | Consecuencia |
|---|---|---|
| `docker compose up` / E2E real | Docker prohibido y daemon no disponible en esta sesión | CA1/CA5 de SAPI-66 no se acreditan literalmente |
| `RankingHttpToPostgresIT` | Requiere Testcontainers/DB real | CA8 de SAPI-43 queda parcial |
| SAPI-71 Attempt 2 / corrida operacional SAPI-43 | Requiere autorización humana, credenciales y datos del equipo Windows | CA1 de SAPI-43 queda condicionado |
| Batería completa / gate de cobertura | Fuera de alcance y alto costo | Solo hay evidencia dirigida, no un nuevo veredicto de CI |
| D08 / G1 / L1 | Prohibidos en esta recuperación | Gate B no cambia |

## 7. Reproducción

```powershell
# Python dirigido (raíz del workspace)
python -m pytest tests/test_compose_v2.py -o addopts="" -q
python -m pytest tests/test_measure_browser_e2e_d21.py -o addopts="" -q
python -m pytest tests/test_db_migrations_v2.py -o addopts="" -q
python -m pytest tests/test_ml_api.py -o addopts="" -q
python -m pytest tests/test_architecture.py -o addopts="" -q
python -m pytest tests/test_openapi_contracts.py -o addopts="" -q
python -m pytest tests/test_f1_deployment_unit.py -o addopts="" -q
python -m pytest tests/test_scoring_inputs.py -o addopts="" -q

# Java dirigido (services/backend)
.\mvnw.cmd -B -o -DskipITs "-Dtest=RankingPersistenceServiceTests,FirmsOriginPolicyTests,FirmsOriginPolicyBindingTests,RankingResultValidatorTests" -DfailIfNoTests=false test
```

Los resultados pueden variar en tiempos; los conteos y el código de salida son los que se registran en este documento.
