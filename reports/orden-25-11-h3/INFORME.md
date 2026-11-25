# Orden 25-11 · stack `sapi-h3-518c0b5` · informe por punto

- Fecha: 2026-11-25, 01:06 a ~02:00 (America/Santiago); 04:06 a ~05:00 UTC.
- SHA del código: `518c0b58e6b229317f51b1da56ac23346dc2ef74` (verificado completo con `git rev-parse 518c0b5`). Rama local `DanielCortezF002/h3-518c0b5-verificacion`, creada desde ese SHA. Sin push.
- Hardware: AMD Ryzen AI 7 350 w/ Radeon 860M (8 núcleos, 16 hilos), 31 GB de RAM, Windows 11 Home 10.0.26200. Docker 29.9.2 con 16 CPU y 15,1 GiB asignados al motor.
- N de VUs (k6): 0. No se corrió k6.
- Ejecutado en el computador local, no en ambiente desplegado.
- pytest: no se ejecutó ninguna suite en esta orden. Si se corre, va con `--ignore=tests/test_f1_ca8_operational_overlay_dynamic.py`.
- Orden seguido: 1 → 2a → 4 → 3. k6 preparado y detenido a la espera de luz verde.

## Punto 1 · Stack paralelo `sapi-h3-518c0b5`

Comando: `docker compose -p sapi-h3-518c0b5 --profile presentation up -d --build db-v2 ml-api backend web-v2`, con `SAPI_DB_PORT=15432`, `SAPI_ML_PORT=18000`, `SAPI_BACKEND_PORT=18080`, `SAPI_WEB_PORT=18501` (los puertos por defecto los usa `sapi`). Volúmenes nuevos y propios: `sapi-h3-518c0b5_sapi_v2_pgdata`, `sapi-h3-518c0b5_sapi_v2_secrets`. Listo a las ~01:08 Santiago, antes del corte de las 11:00, así que 2a se hizo sobre h3 y no sobre `sapi`.

| Servicio | SHA de código | Image ID h3 | Digest (RepoDigest local) | Estado |
|---|---|---|---|---|
| web-v2 | 518c0b5 | `sha256:43e4b8116802bbeed355a7f356602a33a2c6de4f3c9551a582a06d823612eeda` | `sapi-h3-518c0b5-web-v2@sha256:43e4b811…` (igual al ID) | Up, sin healthcheck; `/_stcore/health` 200 `ok` |
| backend | 518c0b5 | `sha256:738e2f76e7eda6c4056d4070e967104ef9ffb7986b552653cd353570b80be369` | `sapi-h3-518c0b5-backend@sha256:738e2f76…` | healthy; `/health` 200 `UP` |
| ml-api | 518c0b5 | `sha256:54d48696931638db3de0180128487999ba2af9712336f6e77b8949bf2a8915dd` | `sapi-h3-518c0b5-ml-api@sha256:54d48696…` | healthy; `/health` 200 `ok`, `prototype_model_d_v1` |
| db-v2 | imagen pública | `sha256:3f4a5d48e0be9580ed70ed618cd039ce57bbb2dd113053d3836e28513f1f87cd` | `postgis/postgis@sha256:3f4a5d48…` | healthy |

Las imágenes son locales y no se publicaron en ningún registro: el «digest» es el RepoDigest local que asigna Docker, igual al Image ID. GET `/api/v1/ranking`: 200, 50 celdas, `score_semantics=relative_rank`, 15,4 s en frío.

### Comparación con el stack `sapi` (`docker image inspect`)

| Servicio | Image ID `sapi` | ¿Mismo ID? | Capas comunes (prefijo) | Lectura |
|---|---|---|---|---|
| web-v2 | `a21c5bbf…` | No | 8 de 9 | Misma base y dependencias; difiere la capa del código (`sapi` se construyó el 24-11 16:52 UTC) |
| backend | `4fa46325…` | No | **9 de 9** | Mismas capas, mismo `Created` (2026-11-23T13:10:47Z). El ID cambia solo por la etiqueta `com.docker.compose.project` (`sapi` vs `sapi-h3-518c0b5`). El JAR es el mismo. |
| ml-api | `ec6c0efc…` | No | 8 de 10 | Misma base `python:3.14-slim` y mismas dependencias; difieren las 2 capas finales de la aplicación |
| db-v2 | `3f4a5d48…` | **Sí** | 18 de 18 | Idéntica |

**Explícito:** backend y ml-api **sí** salen de la misma base que `sapi`. En backend coinciden todas las capas; en ml-api coinciden la base y las dependencias y solo cambia el código. Ninguno de los dos tiene IDs iguales a los de `sapi`.

Limitación: el checkout del stack `sapi` (`C:\Proyecto SAPI\SAPI`) está hoy en `fd371cc3d5e04c226331b449863504748c588868`, que no es ancestro de 518c0b5. Sus imágenes no tienen etiqueta de SHA, así que **no se puede afirmar con qué SHA se construyeron**. Evidencia: [identidad/stacks.txt](identidad/stacks.txt).

## Punto 2a · Escáneres

Herramientas en contenedor (no hay ninguna instalada en el equipo): Trivy `aquasec/trivy:0.58.1` sobre las 3 imágenes construidas; pip-audit 2.7.3 sobre los `site-packages` instalados dentro de cada imagen Python (contenedor desechable `--rm`, la imagen no cambia); OSV-Scanner `ghcr.io/google/osv-scanner:v1.9.2` sobre `services/backend/pom.xml`. OWASP dependency-check no se usó: el escaneo de Java lo cubren Trivy (sobre el JAR dentro de la imagen) y OSV (sobre el pom). Resumen completo: [escaneo/resumen-escaneos.md](escaneo/resumen-escaneos.md). Salidas crudas: [escaneo/crudos/](escaneo/crudos/).

| Imagen / manifiesto | Herramienta | CRITICAL | HIGH | Con corrección publicada |
|---|---|---|---|---|
| web-v2 (Debian 13.8) paquetes SO | Trivy | 2 | 162 | 0 de los CRITICAL (libxml2, sin versión corregida en Debian) |
| web-v2 Python | Trivy | 5 | 29 | pillow 12.3.0 → 13.0.0, urllib3 2.7.0 → 2.8.0, msgpack 1.1.2 → 1.2.3, setuptools 70.3.0 → 78.1.1 |
| ml-api (Debian 13.8) paquetes SO | Trivy | 2 | 162 | Igual que web (misma base) |
| ml-api Python | Trivy | 5 | 30 | Las de web, más black 26.5.1 → 26.10.1 (dependencia de desarrollo que entra por `requirements-dev.txt`) |
| backend (Ubuntu 26.04) paquetes SO | Trivy | 0 | 0 | — |
| backend Java (JAR) | Trivy | 4 | 5 | tomcat-embed-core 11.0.24 → 11.0.25; jackson-core / jackson-databind 3.1.5 → 3.1.7 o 3.2.2 |
| web-v2 site-packages | pip-audit | — | — | pillow 12.3.0: 42 avisos, corregida en 13.0.0 |
| ml-api site-packages | pip-audit | — | — | pillow 12.3.0 (42) y black 26.5.1 (1) |
| `pom.xml` | OSV-Scanner | — | — | tomcat-embed-core 11.0.24 (4 avisos), jackson-core 3.1.5 (2), jackson-databind 3.1.5 (5) |

Notas:

- Trivy y pip-audit no coinciden en urllib3, msgpack y setuptools: pip-audit no los marca. Usan bases distintas (Trivy: GHSA/NVD; pip-audit: PyPI/OSV). No se resolvió cuál tiene razón; queda pendiente.
- Que haya CVE no significa que sean explotables en SAPI: no se analizó alcanzabilidad. Las cifras son de hoy y cambian con las bases de datos.
- El primer intento de Trivy (leyendo un `.tar` montado desde Windows) agotó el tiempo; el resultado válido es el segundo, leyendo las imágenes por el socket de Docker. El `.tar` temporal quedó en el scratchpad, fuera del repo.
- No se escanearon las imágenes de `sapi`: el plan B solo aplicaba si h3 no estaba listo a las 11:00.

## Punto 4 · Procedimiento 6B para h3

[PROCEDIMIENTO-6B-RESILIENCIA-ML-API-H3.md](PROCEDIMIENTO-6B-RESILIENCIA-ML-API-H3.md): 9 pasos PowerShell de copiar y pegar, cada uno con resultado esperado y cómo volver al estado inicial, y un cotejo con el procedimiento del 24-11. Hallazgo principal del cotejo: el procedimiento anterior apuntaba a 8501/8000/8080, que hoy son del stack `sapi`; ejecutado tal cual sobre h3 habría probado el stack equivocado. **No se ejecutó.**

## Punto 3 · Recorrido Edge

[recorrido-edge/MATRIZ.md](recorrido-edge/MATRIZ.md), con 6 capturas PNG y su texto. Una sola corrida, 04:28:39 a 04:29:33 UTC. Pasos 1, 2, 3, 4 y 6a: PASS. Paso 5: PARCIAL (el log del backend acredita la nueva consulta, 200 a las 04:29:38.9 UTC, pero la captura salió durante la recarga). 6b en UI y resiliencia: NO_EVALUABLE. Siguen vigentes dos defectos ya registrados en el ítem 40: «Spring Boot (cache 5 min)» y las tarjetas meteorológicas truncadas. El recorrido coincidió con el escaneo Trivy, así que sus tiempos no sirven como medición.

## k6 · preparado, no ejecutado

[k6/LEEME.md](k6/LEEME.md), [k6/sapi_h3_carga.js](k6/sapi_h3_carga.js), [k6/Invoke-K6Corrida.ps1](k6/Invoke-K6Corrida.ps1). Escenarios `humo` (1 VU), `l1` (2), `l2` (5) y `rampa` (0→10). Solo se validaron con `k6 inspect`, que no envía peticiones. El guion aborta si apunta al stack `sapi`. Los umbrales son propuestos y deben fijarse antes de leer PASS/FAIL. **Espera luz verde explícita antes de cada corrida.**

## Estado en que queda el equipo

- `sapi-h3-518c0b5` sigue arriba (4 servicios; puertos 15432/18000/18080/18501) para el 6B y k6. No se borró nada.
- Stack `sapi`: no se tocó. Sigue con los mismos 4 contenedores y las mismas imágenes.
- Imágenes de herramientas que se descargaron: `aquasec/trivy:0.58.1`, `ghcr.io/google/osv-scanner:v1.9.2` y `grafana/k6:0.54.0`. No se creó ningún volumen aparte de los dos de h3.

## Clasificación de afirmaciones

- **Verificado hoy:** todo lo de los puntos 1, 2a, 3 y la preparación de 4 y k6, con evidencia en esta carpeta.
- **Histórico:** identidades de `sapi-kpi03-a3d08ee`, el procedimiento 6B del 24-11 y los defectos del ítem 40.
- **Pendiente:** ejecutar el 6B en h3 (Daniel), las corridas k6 (cada una con luz verde), fijar los umbrales k6, conciliar Trivy con pip-audit, el análisis de alcanzabilidad de los CVE y determinar con qué SHA se construyeron las imágenes de `sapi`.
