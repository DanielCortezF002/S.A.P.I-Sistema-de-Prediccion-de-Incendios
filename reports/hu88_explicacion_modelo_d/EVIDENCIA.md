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
# 8 passed
```

`--noconftest` y `-o addopts=""`: el `tests/conftest.py` compartido importa `src.procesamiento.features`
(requiere todo `requirements.txt`) y `pytest.ini` exige cobertura >= 80 % de `app`/`src`; estas pruebas
no usan esos fixtures ni cubren esos paquetes.

## Archivos

- `modelo_d_explicacion.json` -- salida completa (hash, verificacion, importancias, detalle por arbol).
- `modelo_d_explicacion.md` -- misma informacion en tablas.
- `modelo_d_importancias.svg` -- figura de importancias (revisada visualmente en Edge headless).

`sha256sum models/prototype_model_d.pkl` antes y despues: `ac017bef...2173f` (sin cambios).
