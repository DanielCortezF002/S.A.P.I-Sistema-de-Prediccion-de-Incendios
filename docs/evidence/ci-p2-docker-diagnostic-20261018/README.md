# CI-P2 — Diagnóstico de la prueba de integración Docker (2026-10-18, Chile)

## Incidente verificable

- Fuente: [CI #3, PR #32](https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios/actions/runs/39184234562).
- SHA del merge de prueba: `f53cdde62f6d1f1e927809a036c288ad447a82f5`.
- Job `python`: Black y Flake8 con salida 0; Pytest con salida 1.
- Resultado remoto: **2155 passed, 114 skipped, 1 failed**, cobertura **85.26 %**.
- Fallo único: `tests/test_f1_ca8_operational_overlay_dynamic.py::test_f1_operational_overlay_real_stack_enforces_current_only_gate`.
- Fase: `firms_origin=current`, respuesta HTTP **503** frente a **200** esperado.
- El reporte original no expone el `error_type` ni confirma si esa petición alcanzó el stub.
- La prueba local anterior omitió el escenario Docker por ausencia del ejecutable/daemon.

## Instrumentación propuesta en el test

1. Contabilizar solicitudes `POST` efectivamente recibidas por el stub HTTP del test.
2. Exigir que el backend haya consultado el stub en los escenarios rechazados y CURRENT; así, un HTTP 500 externo no cuenta como validación de la política.
3. Cuando el estado difiera de lo esperado, exponer únicamente `error_type` contractual y cantidad de POST en el fallo de Pytest, sin volcar cabeceras, variables de entorno ni credenciales.
4. Conservar `results.json` parcial incluso en caso de fallo y mantener la limpieza de contenedores en un bloque `finally` protegido.

No se agregan reintentos ni se cambian los códigos esperados, la política `current-only`, las rutas congeladas ni los componentes productivos.

## Verificaciones y límites

- Inspección de `RankingService` y `MlServiceClient`: HTTP 503 puede corresponder a error 503 del upstream o a una excepción de transporte; **todavía no se puede distinguir con la evidencia original**.
- Sintaxis Python (`ast.parse`): **PASS**.
- `git diff --check`: **PASS**, salida 0.
- Ejecución de Pytest en este contenedor: **no disponible**, `python -m pytest` respondió `No module named pytest`.
- Reproducción con Docker: **PENDIENTE**, Docker no está instalado en este entorno aislado.
- Nueva ejecución de GitHub Actions con la instrumentación: **PENDIENTE**.
- F4 de archivos congelados permanece **FAIL** y requiere procedimiento independiente.

**Estado:** instrumentación diagnóstica; no constituye resolución verificada del fallo CI-P2.
