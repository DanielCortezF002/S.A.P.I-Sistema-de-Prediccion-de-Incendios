# HU-88 -- Evidencia de ejecucion

- Fecha: 2026-11-22 (UTC-3).
- Rama: `feat/SAPI-88-explicacion-modelo-d` (desde `main` @ 9e70867).
- Entorno: venv local `.venv-hu88` (no versionado), Python 3.14.10, numpy 2.5.2, scipy 1.18.1,
  scikit-learn 1.9.0, joblib 1.5.3 (versiones de `artifacts/hito1/reproducibility/manifest.json`;
  el artefacto se entreno con Python 3.14.6).
- Datos reales leidos: ninguno. El dataset 14b36ad8 no se usa.

## Comandos

```sh
python scripts/explicar_modelo_d.py
# SHA-256 OK: ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f
# Estructura OK: 22 arboles, 25 variables  (exit 0)

python scripts/explicar_modelo_d.py --expected-sha256 0000...0000 --out-dir <tmp>
# ERROR: SHA-256 no coincide ... El artefacto NO se deserializo.  (exit 2)

python -m pytest tests/test_hu88_explicar_modelo_d.py -o addopts="" --noconftest -q
# 12 passed (8 originales + 4 de las observaciones B-1 y B-3 del Auditor)
```

`--noconftest` y `-o addopts=""`: el `tests/conftest.py` compartido importa `src.procesamiento.features`
(requiere todo `requirements.txt`) y `pytest.ini` exige cobertura >= 80 % de `app`/`src`; estas pruebas
no usan esos fixtures ni cubren esos paquetes.

## Archivos

- `modelo_d_explicacion.json` -- salida completa (hash, verificacion, importancias, detalle por arbol).
- `modelo_d_explicacion.md` -- misma informacion en tablas.
- `modelo_d_importancias.svg` -- figura de importancias (revisada visualmente en Edge headless).

`sha256sum models/prototype_model_d.pkl` antes y despues: `ac017bef...2173f` (sin cambios).

## Observaciones del Auditor (orden01-hu88-t1t2-20261122.md, SHA-256 50370c35...)

- B-1: el JSON (`explicacion.parada_temprana`) y el MD ("Por que hay este numero de arboles") registran los
  parametros leidos del pkl tras verificar su hash: early_stopping='auto', do_early_stopping_=True,
  n_iter_no_change=10, max_iter=100, validation_fraction=0.1, scoring='loss', n_iter_=22,
  validation_score_ con 23 valores, mejor iteracion de validacion 12 y 10 iteraciones sin mejora.
- B-2: `docs/modelo_d_una_pagina.md` cita para los empates HU-83 commit 2175742 (rama ml/sapi-83-preregistro)
  y el rango corregido 74,5-89,0 % (seccion 12 del preregistro, commit afb8725).
- B-3: `fuente_importancia` (JSON), el MD y el documento declaran que la importancia usa atributos privados
  de scikit-learn 1.9.0 (`_predictors`).
