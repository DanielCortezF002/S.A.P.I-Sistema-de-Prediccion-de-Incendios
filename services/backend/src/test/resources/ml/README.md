# Fixture del servicio ML

`predict-reproducible-2026-09-01.json` es una respuesta **real** de `POST /predict`
del servicio ML (`services/ml_api`), no un ejemplo inventado:

| Campo | Valor |
|---|---|
| Código | `main` en `8a14054` |
| Modo de datos | `SAPI_REPRODUCIBILITY_MODE=1` (snapshots versionados) |
| Petición | `POST /predict` con cuerpo `{}` (último bucket con lectura meteorológica real) |
| Resultado | 200, `forecast_time` 2026-09-01T00:00:00Z, 50 celdas, empates de 41, 7 y 2 celdas |
| sha256 | `f55de2c47d55cc5ad34ed0dd504cdcf66592efed0ff4f365feac8331022d3a2f` |

Se usa como cuerpo del stub HTTP en los tests de SAPI-57. El score es un ranking
relativo entre las 50 celdas, no una probabilidad calibrada. No se edita a mano:
los tests que necesitan un cuerpo inválido lo derivan de este archivo en memoria.
