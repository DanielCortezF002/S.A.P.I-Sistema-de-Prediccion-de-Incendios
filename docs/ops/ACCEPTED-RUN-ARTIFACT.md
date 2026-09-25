# Artefacto de corrida aceptada, replay y readiness del Output Plane

Un resultado aceptado de `GET /score` (contrato `sapi-output-v1`) se puede **capturar**
como evidencia inmutable, **reproducir** sin ningún servicio y **verificar** de forma
independiente. Código en `src/output/` (no en `src/ops/`, que es del Operations Plane).

## Comandos

```bash
# Capturar (solo GET; valida ANTES de escribir)
python -m src.output.accepted_run capture --url http://127.0.0.1:8600/score \
    [--out ../SAPI-71-evidence/accepted-runs] [--synthetic]
# Verificar sin red (con el ancla de la captura, recomendado)
python -m src.output.accepted_run verify <accepted-run.json> [--expect-fingerprint <fp>]
# Reproducir en el Control Center (sin bridge, n8n, NASA, DMC ni red)
python -m app.control_center --replay <accepted-run.json> [--expect-fingerprint <fp>]
# Paquete de evidencia compacto (summary.json, summary.md, artifact_fingerprint.txt)
python -m src.output.accepted_run evidence <accepted-run.json> [--out DIR]
# ¿Output Plane listo para RC1? Emite el OUTPUT_PLANE_MANIFEST
python -m src.output.readiness [--out OUTPUT_PLANE_MANIFEST.json]
```

**Exit de `accepted_run`:** 0 = capturado o válido; 2 = uso o destino rechazado;
3 = no aceptado o inválido; 4 = sin red.
**Exit de `readiness`:** 0 READY, 1 NOT_READY, 2 INCOMPLETE.

## Captura segura

- **Solo `GET`**, sin redirecciones. Nada de POST, refresh, CURRENT, n8n ni Telegram.
- **Se valida antes de escribir.** Pasa por el mismo portón que el Control Center en
  vivo: 50 celdas de la grilla oficial, rank 1..50 único, scores finitos,
  `inputs_fingerprint`, geometría oficial, `alert_identity` recalculada y metadatos
  de identidad seguros. Además se exige `sapi-output-v1` y que las limitaciones sean las
  canónicas. `data_unavailable`, `prototype_unavailable`, `internal_error`, respuestas
  inválidas o sin red no producen artefacto.
- **Destino.** Rechaza, antes de cualquier consulta, `data/raw`, `data/processed`,
  `models`, cualquier carpeta `versions` y cualquier carpeta con `CURRENT.json` (propia
  o de un ancestro). Por defecto escribe en `../SAPI-71-evidence/accepted-runs/`.
- **Capturar el mismo resultado dos veces** conserva la primera captura
  (`already_captured`). Si ya existe otro contenido con el mismo nombre, se rechaza.
- **Metadatos de captura:** hora, estado HTTP, content-type y URL saneada (sin usuario,
  clave, query ni fragmento).

## Contenido e identidades

```
{artifact_schema_version: "sapi-accepted-run-v1",
 artifact_fingerprint,                       # sha256 del bloque `stable`
 identities: {inputs_fingerprint, notification_identity, artifact_fingerprint},
 stable: {artifact_schema_version, canonical_output_schema_version, data_origin, output},
 capture: {captured_at, source_mode: LIVE_CAPTURE, http_status, content_type, source_url}}
```

`output` es una copia por **lista blanca** de la salida canónica: metadatos de evaluación,
FIRMS, DMC y modelo, `meteo_actual`, las 50 celdas (`cell_id`, `score`, `rank`,
`display_rank`, `tie_group_size`, `geometry`), `input_identity`, `alert_identity` y
`limitations`. Nunca incluye `disclaimer` libre, claves, headers, entorno ni trazas.
`data_origin` es `OPERATIONAL` o `SYNTHETIC`, forma parte del contenido estable, así que
cambiarlo es manipulación.

| Identidad | Responde | Cubre |
|---|---|---|
| `inputs_fingerprint` | ¿qué entradas se puntuaron? | `ScoringInputs.manifest()` (modelo, FIRMS, DMC, topografía) |
| `notification_identity` (= `alert_fingerprint`) | ¿qué alerta se derivaría? | hora, entradas, modelo, FIRMS y Top 5 (receta `sapi-alert-v1`, la misma que n8n) |
| `artifact_fingerprint` | ¿es este el resultado aceptado completo? | las 50 celdas, `input_identity`, versiones de contrato y `data_origin` |

Una alerta se deriva de unas entradas, y un artefacto contiene ambas. Dos artefactos
pueden compartir `notification_identity` y tener distinto `artifact_fingerprint`, por
ejemplo si cambia un score fuera del Top 5. `captured_at` y la URL **no** entran en el
`artifact_fingerprint`: el mismo resultado capturado dos veces tiene la misma identidad.

## Manipulación (verify y replay)

Se rechaza:
- un fingerprint que no corresponde al contenido o que está mal formado;
- identidades resumidas que no coinciden;
- contenido que no pasaría la captura: 49 celdas, cell_id o rank duplicado, rank con
  hueco, NaN o Infinity, sin `inputs_fingerprint`, `alert_identity` que no corresponde,
  geometría distinta de la oficial, identidad con forma de secreto, marca DEMO
  (`_synthetic`) u origen desconocido;
- campos desconocidos;
- una URL con credenciales;
- una versión de esquema distinta.

Replay y verify no escriben nada y no usan red.

**Límite honesto:** el fingerprint es auto-referente. Quien edite el contenido de forma
coherente (por ejemplo, un score fuera del Top 5) **y** recalcule el fingerprint obtiene
un artefacto válido en sí mismo pero con **otra** identidad. Para descartarlo hay que
anclar el fingerprint registrado en la captura (lo imprime `capture` y queda en
`artifact_fingerprint.txt`) con `--expect-fingerprint`. No hay firma criptográfica.

## Qué prueba y qué no prueba el replay

- **Prueba:** que el Control Center presenta exactamente lo capturado (celdas, ranks,
  scores, Top 5, FIRMS, identidades, vista previa de alerta y aviso científico), con la
  misma presentación que en vivo y sin servicios. Lo verifican los tests de equivalencia
  en vivo ↔ replay y el E2E sintético.
- **No prueba:** que el resultado siga vigente, que los datos de entrada fueran
  correctos, que el modelo sea válido ni que haya habido o no incendios. Tampoco que el
  artefacto provenga del bridge real, salvo que se ancle el fingerprint de la captura.
  REPLAY nunca es EN VIVO ni DEMO, y nunca notifica.

## Readiness y OUTPUT_PLANE_MANIFEST

`python -m src.output.readiness` ejecuta, con un resultado **sintético**
(`src/output/synthetic.py`) y solo en proceso o loopback, estos chequeos:
- serializador canónico del bridge y su cierre ante resultados inválidos;
- adaptador del Control Center y modos demo, en vivo (incluido sin servicio) y replay;
- renderer de alerta;
- identidad Python ↔ JavaScript y verificación en la política n8n (requieren `node`;
  sin él el estado es INCOMPLETE);
- recursos de la aplicación;
- ausencia de rutas o envíos de escritura y workflow n8n inactivo.

El manifest (`sapi-output-plane-manifest-v1`) registra:
- el `git_head` y el hash de contenido de las fuentes del Output Plane (normalizado de
  CRLF a LF);
- la identidad del Control Center y las versiones de contrato, alerta, receta de
  identidad, política de supresión y artefacto;
- el resultado de cada chequeo;
- un `manifest_fingerprint` determinista.

**El manifest es evidencia, no autorización.**

## Política de supresión en n8n (hook, sin activar)

La identidad no cambia. `deduplicate(current, previous, policy)` en `ops/n8n/policy.js`
recibe una política explícita `sapi-suppression-v1`. Por defecto:
- no se repite la misma identidad y categoría;
- no hay ventana de tiempo;
- `withheld` y `blocked` nunca se notifican.

Opciones futuras, por decisión humana:
- `window_minutes`: suprime una evaluación nueva de la misma categoría dentro de la
  ventana;
- agregar `error` a `never_notify_categories`.

Una política inválida nunca notifica, y ninguna política puede permitir reintentos
idénticos ni volver notificable `blocked`. El workflow sigue inactivo y no hay Telegram.
