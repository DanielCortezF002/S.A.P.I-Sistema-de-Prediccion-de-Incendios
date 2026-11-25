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

## 2. Resultado de las sondas

Pendiente: se completa en el commit siguiente, después de la corrida.

## 3. Escáneres

Pendiente: se completa en el commit siguiente.
