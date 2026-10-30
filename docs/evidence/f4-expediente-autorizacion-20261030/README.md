# Expediente de autorización de excepciones F4 (resolución D3)

Generado por `scripts/build_f4_expediente.py` sobre el candidato `61b1afbeb85d2dafda63dd880b55948b136fa94e`. Un expediente por archivo congelado. **Ninguna excepción está autorizada hasta que el responsable del proyecto firme cada expediente.**

| Expediente | Archivo | Defecto(s) | Pins y evidencia |
|---|---|---|---|
| `01_scoring_inputs.md` | `src/inference/scoring_inputs.py` | B2 | PASS |
| `02_firms_source.md` | `src/procesamiento/firms_source.py` | B1 | PASS |
| `03_dmc_refresh.md` | `src/refresh/dmc_refresh.py` | ADV-05 | PASS |
| `04_firms_refresh.md` | `src/refresh/firms_refresh.py` | B1, B3, ADV-05 | PASS |

Contexto: las excepciones se añadieron a `scripts/freeze_check.py` en la misma PR (#39) que el control evalúa, citando una directiva del orquestador de agentes y no una firma del PO. Por eso GB-04 sigue abierto hasta esta firma.
## Resultados sobre el candidato (F2, 30-10-2026)

- Pruebas que ejercitan las 4 rutas más `tests/test_freeze_f4_exceptions.py`
  (11 archivos de prueba): **290 passed, 5 skipped, 0 failed** (Windows, Python 3.14.7).
- `scripts/freeze_check.py` en esta copia de trabajo de Windows: el ítem F4 congelados
  da **PASS** ("sin cambios salvo 4 excepciones F4 autorizadas"). Hubo un único FAIL, en
  F6/F9 `artifacts/hito1/reproducibility/manifest.json`, y es un artefacto de checkout:
  el blob versionado coincide con el pin (`a02500da7fb2…`) en el baseline, en main, en
  70c29f9 y en el candidato, pero `core.autocrlf=true` lo escribe con CRLF en disco.
  La verificación con fin de línea LF (equivalente a CI Linux) está en el informe F2.
- Ninguna excepción se considera autorizada por estos resultados: la decisión es la firma.
