# Despliegue local de S.A.P.I. para la defensa del Hito 3 (HU-90)

Subtarea HU-90.T1 (SAPI-136). Versión 0.1, 22-11-2026.

Es el procedimiento para levantar el panel en la demostración y dejar evidencia de cada criterio de SAPI-90. Complementa la sección «Instalación» del `README.md` y no la reemplaza.

**Decisión pendiente:** el profesor Matías todavía no confirma por escrito que este entorno local cuente como «ambiente desplegado» (HU-90.T3, SAPI-138). Mientras no lo confirme, este documento es el plan principal y no un cierre.

## 1. Requisitos del equipo

| Requisito | Valor | Motivo |
|---|---|---|
| Docker Desktop (o Docker Engine) con Compose v2 | `docker compose version` responde | Es la única dependencia de la opción A |
| CPU asignada a Docker | 2 vCPU o más | `ml-api` corre con 2 workers (A4); con 1 vCPU, `/predict` hace cola |
| Puertos libres en 127.0.0.1 | 5432, 8000, 8080, 8501 | Se cambian con `SAPI_DB_PORT`, `SAPI_ML_PORT`, `SAPI_BACKEND_PORT` y `SAPI_WEB_PORT` en un `.env` |
| Red | Solo para el primer `--build` | Descarga imágenes base y dependencias. Después no consulta servicios externos (modo reproducible, ADR-009) |
| Python 3 en el equipo | Solo para la verificación automática (§3) | El script usa solo la librería estándar |

No hace falta `.env` ni escribir contraseñas: la de la base se genera en el volumen `sapi_v2_secrets` en el primer arranque (SAPI-66.CA5).

## 2. Arranque para la demostración

Desde un clon limpio, en PowerShell:

```powershell
git clone https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios.git sapi-demo
cd sapi-demo
git rev-parse HEAD                          # anotar el SHA (debe ser el del tag hito3)
Measure-Command { docker compose --profile presentation up --build -d --wait } | Select-Object TotalSeconds
docker compose --profile presentation ps    # los cuatro servicios en «healthy»
```

`--profile presentation` agrega el panel Streamlit (`web-v2`). Sin ese profile solo levantan `db-v2`, `ml-api` y `backend`. `--wait` termina cuando los cuatro servicios pasan su health check. Desde SAPI-90, `web-v2` tiene el suyo (`/_stcore/health`).

Luego se abre `http://127.0.0.1:8501`.

Para la defensa conviene construir antes (`--build` el día previo) y el día de la presentación usar `docker compose --profile presentation up -d --wait`, que no descarga nada.

**Qué se muestra:** el ranking reproducible del 2026-09-01T00:00Z. Es igual en cualquier equipo y no es una corrida diaria: el score es un orden relativo entre 50 celdas, no una probabilidad de incendio.

## 3. Verificación automática (evidencia de CA1, CA2 y CA3)

`scripts/compose_v2_preflight.py` levanta el stack en un proyecto Compose aislado (`sapi60-preflight`), verifica cada punto y escribe la evidencia redactada (sin rutas, usuario, equipo ni secretos). Al final ejecuta `down -v` **solo** sobre ese proyecto: no toca los volúmenes del proyecto de la demo.

```powershell
$env:COMPOSE_PROFILES = "presentation"
python scripts/compose_v2_preflight.py --out-dir ..\sapi90-evidence-YYYYMMDD
Remove-Item Env:COMPOSE_PROFILES
```

Código de salida 0 = todo PASS.

| Criterio de SAPI-90 | Qué verifica el script | Dónde queda |
|---|---|---|
| CA1: un comando desde clon limpio, health checks en 200 y tiempo registrado | `docker compose build`, `up -d --wait`, estado `healthy` y puerto en loopback de los cuatro servicios. `GET /health` del backend y del ML; `GET /_stcore/health` del panel; `pg_isready` de la base. Duración de cada comando | Evidencia en `--out-dir` |
| CA2: la base conserva los datos al reiniciar | `down` sin `-v`, `up -d --wait` y conteo de ejecuciones y predicciones antes y después | Ídem, checks `ca4.*` (numeración de SAPI-60) |
| CA3: secretos fuera del repositorio | El arranque funciona sin `.env`. El escaneo de secretos de HU-89 (`scripts/secret_scan.py`) revisa lo versionado | Evidencia del preflight + job `secrets` del PR #49 |

Además verifica la cadena completa: Flyway V001–V004 aplicadas, 50 celdas en `celdas_geom`, `GET /api/v1/ranking` con 50 celdas y `scientific_model_validation=false`, persistencia sin duplicados y la consulta `db/queries/latest_ranking.sql`.

## 4. Criterios que este documento no cierra

| Criterio | Estado | Qué falta y quién |
|---|---|---|
| CA4: prueba de carga repetida (p95 con n declarado, mismo método del Hito 2: 1.330 ms en frío y 1.919 ms en refresco) | Sin ejecutar | Daniel fija la meta de KPI-03 en `docs/objetivos.md`. Después se repite con el mismo método y se reporta con fecha, SHA y comparación con la línea base (HU-90.T2) |
| CA5: ADR-011 firmado por otra persona | Sin firma | Respuesta de Matías (HU-90.T3) |
| HU-90.V | Pendiente | Mauricio Herrera y Angelo Sepúlveda levantan SAPI siguiendo este documento, y el acta registra dónde se trabaron |

## 5. Problemas conocidos y qué hacer

| Síntoma | Causa | Acción |
|---|---|---|
| `db-v2` termina con «la base persistente ya existe y el volumen sapi_v2_secrets no tiene su contraseña» | Se borró uno de los dos volúmenes v2 y no el otro | Restaurar el volumen, o borrar ambos (`docker compose down` y `docker volume rm <proyecto>_sapi_v2_pgdata <proyecto>_sapi_v2_secrets`). Se pierde la persistencia local |
| `bind: address already in use` | Otro proceso usa 5432, 8000, 8080 u 8501 (por ejemplo la base legacy del Hito 1) | Detenerlo o mover el puerto en `.env` |
| El panel muestra un error 504 o 503 controlado | El ML aún carga o está detenido (D-04: con el contenedor ML detenido la respuesta es 504) | Esperar a que `ml-api` esté `healthy` y recargar. Es el comportamiento probado de la matriz de fallas (`docs/pruebas/matriz-fallas.md`) |
| `up --wait` no termina | Docker sin CPU o memoria suficiente | Subir los recursos en Docker Desktop (2 vCPU o más) |
| `docker compose down -v` | Borra **todos** los volúmenes del archivo, también la base del Hito 1 | No usarlo en la demo. Usar `down` |

## 6. Plan B el día de la defensa

Si el equipo de la sala falla:
1. Mostrar el stack ya levantado en el notebook propio (construido el día anterior).
2. Mostrar la evidencia de §3 (fecha y SHA) y las capturas de HU-86 y HU-80.

No se cambia a un servicio cloud improvisado: la restricción de $0 (SAPI-67) sigue vigente.
