# SAPI-66 — corrección independiente ejecutada

Base preservada: e8e87d910675c7c96dccc417b542efa6964ba161.
Rama sucesora: feat/SAPI-66-e2e-hardening. Sin cambios en SAPI-71 ni código científico.

## Resultado comprobado

`astra-run-06/e2e_report.json`: 33/33 comprobaciones, ejecución completa, PASS.
Docker Compose construyó Dockerfile.ml-api, services/backend/Dockerfile y Dockerfile.web.
Proyecto nuevo, base inicialmente vacía y cuatro servicios esperados.
La primera visita real de Edge a web-v2 produjo 1 ejecución + 50 predicciones ANTES
 de consultar directamente el ranking desde el runner. Se comparan fingerprint y
50 IDs del navegador con REST, y todos los campos persistidos (scores, ranks,
empates, identidad y metadata) de REST con SQL. Replay conserva 1/50.
Se validaron geometrías, contratos 200/422, caída real del ML (504/upstream_timeout),
backend detenido con UI de error y recuperación. La caché se invalida reiniciando
solo web-v2 del proyecto de prueba, no mediante eventos DOM forzados.

Tiempo de navegación hasta ranking y trazabilidad visibles: 7.3634004 s.
Las otras muestras son peticiones completas, incluido el cuerpo, con servicios
ya activos. No se denominan arranques en frío ni se inventa un umbral.

## Correcciones de la auditoría

- El informe deriva su veredicto de checks ejecutados y finalización; conserva excepciones.
- Proyecto exclusivo, rechazo de recursos preexistentes, entorno Compose consistente,
  .env local excluido, contraseña efímera y limpieza limitada al proyecto propio.
- Build oficial obligatorio; eliminado el camino skip-up como evidencia de aceptación.
- Navegador real sustituye AppTest como prueba de cadena completa.
- SQL sin ID=1; comparación completa y conteos exactos, no solo ausencia de crecimiento.
- Salud exige healthy en los tres servicios con healthcheck; backend además debe responder UP.
- Tiempo incluye lectura del cuerpo; browser-render se mide por separado.
- Las cinco pruebas AppTest originales se conservan, se aíslan sus variables de entorno
  y requieren SAPI66_RUN_COMPONENT_TESTS=1. Sus skips no cuentan como aceptación E2E.

## Reproducción

Python con PyYAML, jsonschema y pytest; Node con playwright y Microsoft Edge instalado.
Alternativa: SAPI_E2E_BROWSER_CHANNEL=chromium con el navegador Playwright instalado.
NODE_PATH debe resolver el paquete playwright si no está en node_modules local.

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
python -m pytest tests/e2e/test_evidence_integrity.py tests/e2e/test_vertical_slice.py -q --override-ini addopts=''
python scripts/e2e_slice.py --out-dir artifacts/hito2/e2e/NEW-RUN --node node
```

Runtime ejecutado: Python 3.14.7 desde C:/SAPI-rc1-release-tooling/.venv/Scripts/python.exe;
Node y playwright del runtime de Codex. El JSON registra hashes del código realmente
probado y de los Dockerfiles: HEAD era la base más cambios locales, no una afirmación
falsa de haber probado un commit limpio posterior.

## Límites y trazabilidad

Snapshot reproducible congelado, no CURRENT operacional ni validación científica.
Las capturas prueban ranking y errores. Se bloquean CDNs/tiles externos en el navegador:
no se certifica cartografía externa ni apariencia integral del mapa en esta prueba.
No se ejecutó Release Gate ni se declara F1–F9 PASS.
Los intentos 01–05 conservan fallos del propio verificador (virtualización de opciones,
lectura UTF-8 Windows, clasificación 504 permitida, sidebar colapsado); no se cuentan
como PASS. No se modifica SAPI-61 para resolver limitaciones del test.
Estado: IMPLEMENTED_PENDING_REVIEW.

Los logs versionados conservan los mensajes completos, con rutas personales redactadas
y espacios finales normalizados. No son copias byte a byte de stdout.
