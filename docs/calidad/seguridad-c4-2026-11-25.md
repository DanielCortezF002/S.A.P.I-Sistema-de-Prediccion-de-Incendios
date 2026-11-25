# C4 · Seguridad · acceso denegado y escáneres · 25-11-2026

- Stack medido: proyecto Compose `sapi-h3-518c0b5`, construido desde `518c0b58e6b229317f51b1da56ac23346dc2ef74` (UI 518c0b5; backend con las mismas capas que el de `sapi`, ver `reports/orden-25-11-h3/INFORME.md`). Puertos en loopback: web 18501, backend 18080, ml-api 18000, db 15432.
- Rama de trabajo: `DanielCortezF002/plan-25-11-c4-c5`. Commits locales, sin push.
- Hardware: AMD Ryzen AI 7 350 (8 núcleos, 16 hilos), 31 GB de RAM, Windows 11 Home 10.0.26200. Ejecutado en el computador local, no en ambiente desplegado.

## 1. Escenario (declarado antes de correr las sondas)

| Parte | Valor |
|---|---|
| Fuente | Cliente anónimo en el mismo equipo, sin credenciales |
| Estímulo | Pide rutas no publicadas que podrían exponer los datos persistidos (`ejecuciones`, `predicciones_celda`, `celdas_geom`), la configuración (Actuator, `application.properties`, migraciones) o archivos del sistema (recorrido de rutas); usa métodos no permitidos sobre la ruta pública; envía entrada maliciosa a `forecast_time`; abre una conexión a PostgreSQL sin contraseña |
| Entorno | Stack local `sapi-h3-518c0b5` en operación normal (los 4 servicios arriba) |
| Respuesta | El sistema rechaza sin entregar datos ni detalles internos |
| Medida | **A:** 23 de 23 sondas responden 401, 403, 404 o 405. **C:** 3 de 3 responden 422 (error del contrato). **A + C:** 0 cuerpos contienen alguna cadena centinela (credenciales, nombres de tablas, `inputs_fingerprint`, trazas Java o Python, `/etc/passwd`). **D01:** PostgreSQL exige credencial (no responde AuthenticationOk sin contraseña). Cumple solo si se cumplen las cuatro |

Grupo **B** (`/docs`, `/openapi.json`, `/redoc` del ml-api; `/v3/api-docs`, `/swagger-ui.html` del backend): se registra lo que responde, **sin criterio de cumplimiento**. Documentan la forma de la API, no entregan datos persistidos.

Alcance y límites declarados antes de correr:

- No hay autenticación en SAPI: la única ruta de datos publicada es `GET /api/v1/ranking`, que es pública por diseño. Este escenario prueba que **no hay otra** ruta que entregue datos, no prueba un control de acceso con usuarios.
- No se prueban contraseñas ni se usa la contraseña real de la base. D01 solo lee el tipo de autenticación que pide el servidor y cierra la conexión.
- No se llama a `GET /api/v1/ranking` válido ni a `POST /predict` válido: no se dispara el scoring.
- Todos los puertos publicados están en `127.0.0.1`. Lo que pase desde otra máquina de la red no se evalúa aquí.

Sondas y centinelas: [evidencia/2026-11-25-seguridad/sondas_acceso.py](evidencia/2026-11-25-seguridad/sondas_acceso.py).

## 2. Resultado de las sondas (verificado hoy)

Escenario y script commiteados en `83007240fec72b453959a6881694a10b2e0eeb99` (2026-11-25T08:07:05-03:00). Corrida: 2026-11-25T11:07:17Z a 11:07:22Z, una sola vez, con el script de ese commit. Evidencia cruda: [resultado-sondas.json](evidencia/2026-11-25-seguridad/resultado-sondas.json) (SHA-256 `34c2dfa3b88d09663a092f6e11296588e49f1c663c50b82af0c7e4c3d359e48c`). Verificación posterior de A23: [verificacion-a23.json](evidencia/2026-11-25-seguridad/verificacion-a23.json).

| Medida declarada | Observado | Cumple |
|---|---|---|
| A: 23 de 23 en 401/403/404/405 | **19 de 23:** 15 con 404 (A01–A11, A18–A21) y 4 con 405 (A14–A17). **A12, A13 y A22 → 400**; **A23 (`/.env` en web) → 200** | **No** |
| C: 3 de 3 con 422 | 3 de 3 con 422 `invalid_request` («La petición no cumple el contrato: forecast_time …») | Sí |
| A + C: 0 centinelas | **1:** A01 contiene `ejecuciones` | **No** |
| D01: PostgreSQL exige credencial | Responde `AuthenticationSASL` (código 10, `SCRAM-SHA-256`): pide contraseña antes de abrir sesión | Sí |

**Veredicto del escenario tal como se declaró: NO CUMPLE.** El criterio no se cambia después de medir. Lo que explica cada desvío, con su evidencia:

| ID | Desvío | Qué se ve en la evidencia | Severidad | Decisión |
|---|---|---|---|---|
| SEC-C4-01 | A12 y A13 (backend, `/..;/` y `%2e%2e`) y A22 (web, `%2e%2e` en `/app/static`) responden **400**, no un código del conjunto declarado | Backend: página HTML de Tomcat «HTTP Status 400 – Bad Request», 435 bytes, sin traza. Web: texto `Bad Request`, 11 bytes. Ningún cuerpo trae `root:x:0:0` ni otro centinela | Baja | **Justificado:** el servidor rechaza la ruta antes de resolverla y no entrega nada. Es un error de especificación del criterio (no incluí 400), no un defecto acreditado del producto. Queda registrado como lección para el próximo escenario |
| SEC-C4-02 | A23 `/.env` en web responde **200** (7.459 bytes) | El cuerpo es el `index.html` de Streamlit: su SHA-256 (`b7c55a74…`) es idéntico al de `/` y al de una ruta inventada (`/cualquier-ruta-inexistente`). Streamlit responde su página a cualquier ruta; no sirvió un archivo `.env` | Baja | **Justificado** con `verificacion-a23.json`. No hay `.env` en la imagen que se haya visto, pero esto no se verificó dentro del contenedor |
| SEC-C4-03 | Centinela `ejecuciones` en A01 | El 404 de Spring repite la ruta pedida: `"path":"/api/v1/ejecuciones"`. No entrega datos de la tabla | Ninguna | **Justificado:** falso positivo del centinela (eco de la ruta) |
| SEC-C4-04 | Grupo B (observación): el ml-api responde 200 en `/docs`, `/openapi.json` y `/redoc`. El backend no publica documentación (`/v3/api-docs` y `/swagger-ui.html` → 404) | `/openapi.json` describe `POST /predict` y el esquema `RankingResult`. El ml-api (puerto 18000) es alcanzable desde el equipo sin pasar por el backend | Baja (solo en `127.0.0.1`) | **Abierto como defecto** DEF-SEC-07: el compose comenta el ml-api como «interno», pero publica su puerto en el host. No se creó ticket en Jira (fuera del alcance de hoy) |

Lectura acotada: con esta evidencia, **ninguna** de las 26 sondas A y C entregó datos persistidos, configuración ni archivos del sistema. Esto **no** demuestra un control de acceso: SAPI no tiene usuarios ni autenticación, y la ruta de datos publicada (`/api/v1/ranking`) es pública por diseño.

## 3. Escáneres

### 3.1 Trivy y pip-audit (reutilizados, verificados el 25-11 a las 01:29–01:37 Santiago)

No se re-ejecutaron. Fuente: [resumen-escaneos.md](../../reports/orden-25-11-h3/escaneo/resumen-escaneos.md) y crudos en `reports/orden-25-11-h3/escaneo/crudos/`, commit `a98072a` (SAPI-89) con la corrección `74cfb1d`. Imágenes de `sapi-h3-518c0b5`, SHA de código `518c0b5`. Trivy `aquasec/trivy:0.58.1`; pip-audit 2.7.3; OSV-Scanner v1.9.2 sobre `services/backend/pom.xml`.

### 3.2 npm audit

**No aplica:** el repositorio no versiona `package.json`, `package-lock.json`, `yarn.lock` ni `pnpm-lock.yaml` (verificado hoy con `git ls-files`). Trivy encontró 0 hallazgos de Node.js dentro de las imágenes `web-v2` y `ml-api`.

### 3.3 Hallazgos medios o mayores y su decisión

Conteos de CVE únicos por paquete y severidad, contados hoy desde los JSON crudos de Trivy.

| ID | Imagen | Paquete | CRITICAL / HIGH / MEDIUM | ¿Corrección publicada? | Decisión |
|---|---|---|---|---|---|
| DEF-SEC-01 | backend | `tomcat-embed-core` 11.0.24 | 4 / 0 / 0 | Sí, 11.0.25 | **Abierto.** Sin análisis de alcanzabilidad |
| DEF-SEC-02 | backend | `jackson-core` y `jackson-databind` 3.1.5 | 0 / 5 / 2 | Sí, 3.1.7 o 3.2.2 | **Abierto** |
| SEC-H-01 | web-v2, ml-api | `pillow` 12.3.0 | 5 / 24 / 14 (43 únicos) | Sí, 13.0.0 | **Justificado (histórico + verificación parcial hoy):** `cf5f4cc` (rama `feat/SAPI-89-escaneo-seguridad`, 22-11) lo aceptó porque streamlit 1.63.0 exige `pillow<13`. Verificado hoy: `requirements.txt` fija `streamlit==1.63.0`, y en `app/`, `src/` y `services/` no hay `file_uploader` ni `import PIL`. No se verificó hoy la restricción `<13` de streamlit. Riesgo que queda: el paquete está instalado en las dos imágenes |
| DEF-SEC-03 | ml-api | `black` 26.5.1 | 0 / 1 / 0 | Sí, 26.10.1 | **Abierto en el stack medido.** Corregido en `cf5f4cc`, que no está en 518c0b5. Entra por `requirements-dev.txt` (herramienta de desarrollo dentro de la imagen de ejecución) |
| DEF-SEC-04 | web-v2, ml-api | `urllib3` 2.7.0, `msgpack` 1.1.2, `setuptools` 70.3.0 | 0 / 5 / 2 | Sí | **Abierto.** pip-audit no los marca; la discrepancia entre herramientas sigue sin resolver |
| DEF-SEC-05 | web-v2, ml-api | `libxml2` / `libxml2-dev` (Debian 13.8), CVE-2026-6653 | 1 / 0 / 0 por paquete | **No** en Debian | **Abierto, sin corrección disponible.** No se analizó si alguna ruta de SAPI procesa XML |
| DEF-SEC-06 | web-v2, ml-api, backend | Paquetes del sistema operativo | web/ml-api: 2 CRITICAL (DEF-SEC-05), 162 HIGH, 656 MEDIUM en 119 paquetes, 0 con corrección publicada. backend (Ubuntu 26.04): 0 / 0 / 58, 1 con corrección | Casi ninguno | **Abierto en bloque.** No se justifican uno por uno: no hay evidencia para hacerlo. Plan sugerido, no ejecutado: imagen base más delgada y reconstrucción periódica |
| DEF-SEC-07 | ml-api | Puerto 8000 publicado en el host con `/docs` y `/openapi.json` | — | — | **Abierto** (ver SEC-C4-04) |
| DEF-SEC-08 | backend | `stdlib` v1.27.3 dentro de `/usr/bin/pebble` | 0 / 0 / 1 | Sí | **Abierto** |

Ninguno de los defectos tiene ticket en Jira: crearlos no estaba autorizado hoy. Quedan registrados aquí con ID propio para trazarlos.

## 4. Clasificación

- **Verificado hoy:** sección 2 completa; conteos de la tabla 3.3 desde los JSON crudos; ausencia de lockfiles npm; `streamlit==1.63.0` en `requirements.txt` y ausencia de `file_uploader`/PIL en el código.
- **Histórico:** la aceptación de pillow y la corrección de black en `cf5f4cc` (22-11); los escaneos de Trivy, pip-audit y OSV (25-11, 01:29–01:37 Santiago).
- **Pendiente:** alcanzabilidad de cada CVE; conciliar Trivy con pip-audit (pillow 43 vs 42; urllib3, msgpack, setuptools); tickets Jira de DEF-SEC-01 a 08; un escenario con autenticación real, que hoy no existe en SAPI.
