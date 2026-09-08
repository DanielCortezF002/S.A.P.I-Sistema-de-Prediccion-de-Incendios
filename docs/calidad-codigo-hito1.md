# Calidad de código — Sprint 1 / Hito 1

**Estado:** documento de trabajo, auditoría de lectura de `src/` y
`app/` — no se modificó ningún archivo de código. Fecha de esta fase:
**07-09-2026**.

## 1. Propósito

Evaluar el criterio "Calidad de código / buenas prácticas" (8%) de la
rúbrica de Hito 1 con evidencia real leída del código — nunca
declarando "cumple SOLID" de forma global, ni traduciendo cobertura de
tests en una afirmación de código limpio.

## 2. Método

Se auditaron `src/` (5.353 líneas, 21 módulos) y `app/` (4.717 líneas,
23 módulos) mediante lectura directa e inspección estructural (AST para
longitud de funciones; `grep` para patrones de manejo de errores,
imports y excepciones). No se instaló ninguna herramienta de lint/type-
checking/complejidad — su ausencia ya es, en sí misma, un hallazgo (ver
sección 8).

## 3. Matriz principal

| Aspecto | Criterio observable | Evidencia | Resultado | Estado | Brecha |
|---|---|---|---|---|---|
| Modularidad | Separación por capa: ingesta / procesamiento / inferencia / modelo / UI | 21 módulos en `src/` organizados en 5 paquetes (`ingesta`, `procesamiento`, `inferencia`, `modelo`, `geo`, `query`, `pipeline`); `app/` separado en `components/`, `utils/`, `theme/`, `data/` | Estructura de paquetes coherente con la arquitectura documentada en `docs/arquitectura-hito1.md` | FUERTE | Ninguna en la estructura de paquetes |
| Frontera UI↔inferencia↔procesamiento | `app/` no debe importar `src.ingesta`/`procesamiento`/`modelo`/`pipeline` directamente | `tests/test_architecture.py` (AST estático, PASS); `src/inference/prototype_service.py` como única interfaz pública | Contrato verificado automáticamente, no solo documentado | FUERTE | Ninguna |
| Aislamiento legacy | El prototipo no debe importar `matriz_features`/`xgboost_optimized.pkl`/`demo_seed`/NDVI sintético | `tests/test_prototype_service.py::test_no_legacy_imports_in_prototype_modules` PASS; docstring explícito de `prototype_service.py` | Verificado por test, no solo por convención | FUERTE | Ninguna |
| Nomenclatura | Nombres de función/variable descriptivos, sin abreviaturas crípticas | Muestreo: `score_current_grid()`, `load_regional_meteo_series()`, `validate_temporal_causality()`, `build_feature_matrix()`, `classify_freshness()` | Nombres consistentemente descriptivos del comportamiento, en español para dominio/inglés para mecánica genérica | ADECUADO | Mezcla de idioma español/inglés en nombres (no es un error, pero no es 100% uniforme) |
| Duplicación evidente | Repetición de la misma lógica en más de un lugar | La grilla espacial fue duplicada históricamente (data_processor/spatial_joiner/generate_seed) — corregido: todos importan de `src/geo/grid.py`, verificado por `tests/test_grid_consistency.py` | Duplicación histórica real, corregida y con test de regresión | ADECUADO | La corrección es reciente (05-09-2026) — no se puede afirmar que nunca reaparecerá sin el test que ya existe |
| Funciones excesivamente largas | Funciones con lógica de negocio no deberían superar ~50-80 líneas | 303 funciones auditadas (AST): 23 (7,6%) superan 50 líneas, 10 (3,3%) superan 80 líneas. La más larga con lógica real es `score_current_grid()` (93 líneas); `build_stylesheet()` (830 líneas) es una plantilla CSS, no lógica de negocio | Proporción baja de funciones largas; las más largas son UI/CSS o el corazón del pipeline de inferencia | ADECUADO | `main()` de `app/app.py` (142 líneas) y `render_ops_detail_panel()` (132 líneas) son candidatas reales a dividir |
| Manejo de errores | try/except tipado, excepciones de dominio, sin `except:` desnudo | 29 bloques try/except en `src`+`app`; 3 excepciones de dominio (`PrototypeUnavailableError`, `TemporalLeakageError`, `RowNotFoundError`); 0 `except:` desnudos; 12 `except Exception` (típicamente en degradación de red, ver R-03 en `docs/matriz-riesgo.md`) | Manejo de errores tipado y con mensajes explicables (`PrototypeUnavailableError` explica qué falta y qué comando correr) | ADECUADO | 12 `except Exception` son amplios — aceptable para degradación de fuentes externas, no ideal si ocultara errores de programación |
| Logging | Uso de `logging`/observabilidad en vez de `print()` silencioso | `src/db.py`, `parallel_ingester.py`, `baseline.py`, `optimizer.py`, `serializer.py`, `run_daily.py`, `data_processor.py`, `features.py`, `prediction_query.py` importan/usan logging | Adopción real en el pipeline legacy y en `src/db.py` | ADECUADO | El pipeline temporal nuevo (`regional_meteo.py`, `episodes.py`, `target_builder.py`) no usa logging — se apoya en tests y excepciones explícitas en su lugar |
| Manejo de NaN | Ausencia de dato nunca se convierte en 0 | `dem_features.py` (`NaN` explícito si no hay cobertura raster); `HistGradientBoostingClassifier` (soporte nativo); `_fmt_nd()` en UI | Verificado por test en la capa de datos (ver `docs/atributos-calidad-hito1.md`, QA-04) | FUERTE (datos) / PARCIAL (UI) | UI sin test dedicado (mismo hallazgo ya documentado, no se repite la corrección aquí) |
| Configuración | Configuración centralizada, no dispersa | `src/config.py` (32 líneas, 100% cobertura) concentra `SAPI_DATA_MODE`, credenciales vía `os.getenv`, bboxes | Un único punto de configuración | FUERTE | Ninguna |
| Documentación técnica | Docstrings explicando el "por qué", no solo el "qué" | Módulos del pipeline temporal (`regional_meteo.py`, `target_builder.py`, `prototype_service.py`) tienen docstrings extensos citando la auditoría que originó cada decisión | Documentación técnica real y trazable a decisiones concretas | FUERTE | Módulos legacy (`data_processor.py`, `spatial_joiner.py`) tienen menos densidad de docstrings explicativos |
| Lint / type-checking | `ruff`/`flake8`/`mypy` configurados | Búsqueda explícita: `ruff.toml`, `.flake8`, `mypy.ini`, secciones en `pyproject.toml`/`setup.cfg` — ninguno existe | Sin configuración | NO_VERIFICADO | Brecha real, ya documentada en Atributos de Calidad — no se instala nada en esta fase |
| Complejidad ciclomática | Medición de complejidad por función | Ninguna herramienta instalada ni ejecutada | Sin medición | NO_VERIFICADO | Igual que arriba |

## 4. Principios de diseño — solo cuando hay evidencia concreta

No se afirma "cumple SOLID" como declaración global. Evaluación puntual:

| Principio | Evidencia concreta | Resultado |
|---|---|---|
| Responsabilidad única (observable) | `src/inference/prototype_service.py` tiene una sola responsabilidad pública (`score_current_grid()`); `target_builder.py` solo construye targets; `causality_validator.py` solo valida causalidad | Observable en 3 módulos citados |
| Separación de capas | Data Contract verificado por AST (`test_architecture.py`): `app/` no accede a `src.ingesta`/`procesamiento`/`modelo`/`pipeline` directamente | Observable, con test de regresión |
| Fronteras/interfaces explícitas | `prototype_service.py` es la única interfaz pública del prototipo hacia `app/`; `regional_meteo.py` expone `load_regional_meteo_series()` como único punto de entrada | Observable en el pipeline temporal |
| Inversión de dependencias | Sin evidencia de un mecanismo explícito de inyección de dependencias o interfaces abstractas (ABC/Protocol) en el código auditado | `NOT_EVALUATED` — no se encontró evidencia suficiente para afirmar ni negar |
| Abierto/cerrado, sustitución de Liskov, segregación de interfaces | Sin evidencia específica auditada en esta fase | `NOT_EVALUATED` |

## 5. Arquitectura documentada vs. código real

`docs/arquitectura-hito1.md` describe el Data Contract y el aislamiento
legacy — se contrastó contra el código real, no se asumió por
documentación:

- `app/components/prototype_view.py`: confirmado que solo importa
  `src.inference.prototype_service` (línea 24-28) — no importa
  `src.procesamiento` ni `src.ingesta` directamente, consistente con el
  Data Contract.
- `src/inference/prototype_service.py`: confirmado que importa
  `src.geo.grid`, `src.procesamiento.dem_features`,
  `src.procesamiento.episodes`, `src.procesamiento.regional_meteo`,
  `src.procesamiento.temporal_features` — es decir, SÍ accede a
  `procesamiento` (correcto, porque `src/inference` no está en la lista
  de módulos prohibidos para `app/`; el prohibido es que **`app/`** lo
  haga directamente, no que `src/inference` lo haga).
- Pipeline temporal: confirmado que `regional_meteo.py`, `episodes.py`,
  `target_builder.py`, `causality_validator.py` no importan nada de
  `app/` ni de los módulos legacy (`data_processor.py`,
  `spatial_joiner.py`, `src/modelo/*`).

**Conclusión:** la arquitectura documentada coincide con los imports
reales verificados — no se trata como prueba suficiente por sí sola,
se contrastó explícitamente.

## 6. Cobertura como evidencia secundaria (no como prueba de calidad)

Cobertura de código: **91.72%** sobre `app`+`src`, gate `pytest.ini`
≥80% (`artifacts/hito1/testing/coverage-summary.txt`); 470/470 tests
PASS. Esto se usa **únicamente como soporte**, no como prueba de código
limpio: la cobertura mide qué líneas se ejecutan durante la suite, no si
el diseño es legible, mantenible o está bien modularizado. Un módulo
puede tener 100% de cobertura y seguir siendo difícil de mantener (no es
el caso observado aquí, pero la afirmación "91.72% = código de alta
calidad" no se hace en este documento).

## 7. Manejo de errores — detalle

**Clasificación: ADECUADO**, con ejemplos reales:

- `src/inference/prototype_service.py::PrototypeUnavailableError`: se
  lanza con un mensaje que incluye la ruta del artefacto faltante y el
  comando exacto para generarlo ("Corre `python
  scripts/build_prototype_model.py` primero").
- `src/procesamiento/causality_validator.py::TemporalLeakageError`:
  excepción de dominio específica para violaciones de causalidad, en
  vez de un `ValueError` genérico.
- `src/ingesta/parallel_ingester.py`: usa `except Exception` amplio
  deliberadamente para degradación (R-03, `docs/matriz-riesgo.md`) —
  documentado como decisión de diseño, no como descuido.
- 0 bloques `except:` desnudos en todo `src`+`app`.

## 8. Legacy — aislamiento confirmado

El prototipo temporal permanece aislado de `demo_seed` y del pipeline
legacy, verificado (no solo declarado) por:
`tests/test_prototype_service.py::test_no_legacy_imports_in_prototype_modules`
y `tests/test_architecture.py::test_frontend_data_contract_compliance`
(ambos PASS, parte de los 470/470 congelados). Esto es evidencia
relevante y verificada para modularidad, mantenibilidad y separación de
responsabilidades — no una afirmación sin respaldo.

## 9. Lint / type-checking / complejidad — brecha reconfirmada

Búsqueda explícita en esta fase (sin instalar nada): `ruff.toml`,
`.flake8`, `mypy.ini`, secciones `[tool.ruff]`/`[tool.mypy]` en
`pyproject.toml`/`setup.cfg` — **cero resultados**, igual que en la
auditoría de Atributos de Calidad. No se ejecutó ninguna métrica nueva
para mejorar la rúbrica.

- `LINTING: NOT_CONFIGURED`
- `TYPE_CHECKING: NOT_CONFIGURED`
- `COMPLEXITY_METRICS: NOT_MEASURED`

## 10. Secretos / configuración — higiene básica (no auditoría de seguridad)

`.gitignore` excluye `.env`, `data/raw/*`, `data/processed/*`,
`models/*.pkl`, `.pytest_cache/`, `.coverage` — higiene razonable.
`git ls-files` no devuelve ningún `.env` real, credencial, `.pem` o
`.key` trackeado (solo `.env.example` con placeholders genéricos, ya
verificado en la fase de Testing). Esto es higiene de repositorio, no
una auditoría de seguridad:

**SECURITY_TESTING: NOT_PERFORMED.**

## 11. Brechas

1. Sin lint/type-checking/complejidad configurado (sección 9).
2. `main()` de `app/app.py` (142 líneas) y `render_ops_detail_panel()`
   (132 líneas) son candidatas reales a refactor por longitud — no se
   modificaron en esta fase.
3. El pipeline temporal nuevo no usa `logging` (se apoya en tests y
   excepciones) — inconsistente con el resto del proyecto que sí lo usa.
4. Inversión de dependencias y los otros 3 principios SOLID no
   evaluados por falta de evidencia suficiente (`NOT_EVALUATED`), no
   declarados como cumplidos ni incumplidos.
5. Documentación técnica desigual entre el pipeline temporal (fuerte) y
   el pipeline legacy (más ligera).

## 12. Evidencia reproducible

Conteos de líneas: `find src -name "*.py" | xargs wc -l`; longitud de
funciones: script Python con `ast` sobre `src/**/*.py` y `app/**/*.py`;
patrones de manejo de errores: `grep` sobre `try:`, `except`, `class
.*Error`; imports verificados por lectura directa de
`app/components/prototype_view.py` y
`src/inference/prototype_service.py`. Todo ejecutado contra el commit
`9f076172adca3dbce0285f5d942d2803ac6f68a4` sin modificar ningún archivo.
