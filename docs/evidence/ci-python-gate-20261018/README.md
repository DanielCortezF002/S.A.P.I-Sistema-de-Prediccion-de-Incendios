# CI-P1 — Reconciliación del Quality Gate Python (2026-10-18)

## Origen y alcance

- Run inicial: [CI #1](https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios/actions/runs/39142646544).
- SHA inspeccionado: `2ba8cebe895b3791241546e7303a8f771a93683b` (`main`).
- Fuentes: artefactos `gate-python-2ba8cebe895b3791241546e7303a8f771a93683b.zip` y `gate-freeze-2ba8cebe895b3791241546e7303a8f771a93683b.zip` del run inicial.
- Alcance: lint, formateo y recolección de pruebas Python; sin modificar rutas congeladas F4, `main`, el PR #31 o entregables académicos.

## Diagnóstico del run inicial

1. Black rechazó `app/components/ranking_backend_view.py` y `tests/test_ranking_backend_view.py`.
2. Flake8 reportó 11 líneas largas (E501) y 5 líneas en blanco con espacios (W293) en `ranking_backend_view.py`.
3. Pytest abortó en la recolección: `ModuleNotFoundError: No module named 'selenium'` en `tests/test_measure_browser_e2e_d21.py`.
4. El freeze falló en `F4 congelados (commits)`. `F2 fingerprint Modelo D` y `F5 verify_reproducibility` pasaron. `F7 contratos v0` fue INFO y `F4b contratos aditivos` PASS.

## Corrección

- `requirements-dev.txt`: se declara `selenium==4.51.0`, compatible con Python 3.14.
- `app/components/ranking_backend_view.py`: formato Black, espacios y líneas CSS/strings, sin cambios en declaraciones CSS.
- `tests/test_ranking_backend_view.py`: formato Black.
- `tests/test_risk_colors.py`: se distingue el estilo visual legítimo de `stDataFrame` de un hack de selección por checkbox; siguen prohibidos `MutationObserver` y los selectores de checkbox.

## Verificación en copia aislada

- Python `3.14.8`, `black==26.5.1`, `flake8==7.3.0` y dependencias de `requirements-dev.txt`.
- Black (`--workers 1 --check`) sobre las rutas bloqueantes del gate: **17 archivos sin cambios pendientes; PASS, exit 0**.
- Flake8 (`--jobs=1 --max-line-length=100 --extend-ignore=E203,W503`) sobre las mismas rutas: **PASS, exit 0**.
- Pytest enfocado (`-q -o addopts='' tests/test_risk_colors.py tests/test_measure_browser_e2e_d21.py`): **23 passed, exit 0**.
- Pytest completo (`-q`, incluyendo el umbral de cobertura de `pytest.ini`): **2132 passed, 138 skipped, 6270 warnings, cobertura 85.26 %, exit 0**.
- CSS de `_inject_css` comparado con el commit base tras normalizar exclusivamente blancos: **sin cambio de declaraciones**.
- `git diff --check`: **PASS, exit 0**.

Black y Flake8 se ejecutaron en un solo worker por restricciones de creación de procesos del entorno de prueba, sin alterar sus reglas. No se ejecutó navegador E2E real. Las omisiones y warnings no constituyen validación científica.

## Pendientes y límites

- **F4 histórico continúa FAIL**: `src/inference/scoring_inputs.py`, `src/procesamiento/firms_source.py`, `src/refresh/dmc_refresh.py`, `src/refresh/firms_refresh.py` cambiaron desde el baseline y requieren control de cambios; no se aplica waiver.
- El CI remoto de GitHub Actions para el nuevo SHA deberá verificarse separadamente; este documento acredita únicamente la prueba aislada ejecutada.
- El Modelo D sigue siendo un **ranking relativo**, sin probabilidades calibradas, validación científica ni alertas oficiales.
