# Procedencia de la evidencia — R1 y R2

**Paquete:** `artifacts/oc-e2e-20261024/`  
**Informe:** `reports/OC-E2E-20261024-CERTIFICACION.md`  
**Redacción:** `REDACTION-NOTICE.md`

Este documento separa, por corrida, **qué código de aplicación se probó**, **qué
versión del arnés produjo cada artefacto** y **en qué commit se publicó**. Su
objetivo es que ninguna medición se atribuya al commit equivocado.

---

## 1. Identidades fijas

| Rol | R1 | R2 |
|---|---|---|
| Rama | `test/oc-fullstack-e2e-20261024` | `test/oc-fullstack-e2e-r2-20261024` |
| Commit de aplicación evaluado | `2a71c7e1160ab87ef7c0ec5e2dfaf3b06c1b4876` | Mismos árboles que `2a71c7e` (base `eb1b370`) |
| Tree de aplicación | `655ad33db79b5ba98e06df770595ed916d660036` | `404518eb9c5982452ec74c93efffd17b52e4c462` (incluye arnés R2) |
| HEAD al capturar | `2a71c7e` (arnés sin commitear) | `eb1b37030d206462878a785a8f4a67edba7b2c98` (arnés sin commitear) |
| Commit que incorpora el arnés | `426605f86a98939cd5124ef0e9cea5aa0fc271d1` | `449ccfdfcd02a5955ea8242898351c6c2da8790c` (E1) |
| Commit de evidencia | `426605f` (PR #41) | `449ccfdfcd02a5955ea8242898351c6c2da8790c` (E1) |

### 1.1 Árboles de aplicación

Los cuatro árboles relevantes son **idénticos** en `2a71c7e` y en la base R2
`eb1b370`, por lo que ambas corridas probaron el mismo código de aplicación:

| Ruta | Tree SHA-1 (R1 y R2) |
|---|---|
| `services/` | `9cd77f12a2f9b9353923ed8567b7b7f7a539ca08` |
| `app/` | `82e9d30a23cda053c44599f6e579e4b1eaa67f93` |
| `contracts/` | `e4c6874cf86939384ad3cd76ce09d4aadd2c4abb` |
| `db/` | `6dff056d733f01594d0917cd7df9a11f1b8efae9` |

Verificación:

```powershell
git rev-parse 2a71c7e:services 2a71c7e:app 2a71c7e:contracts 2a71c7e:db
git rev-parse eb1b370:services eb1b370:app eb1b370:contracts eb1b370:db
git diff --stat 2a71c7e..eb1b370 -- services app contracts db
# sin salida: la aplicación no cambió
```

---

## 2. Versión exacta del arnés

| Arnés | R1 blob / SHA-256 | R2 blob / SHA-256 | Artefactos que produce |
|---|---|---|---|
| `tests/e2e/test_full_stack_timings.py` | `3b750d8bcc2f6bd68df4ff50627a6db84d2d9f45` / `26877fbf4251173742edef2c8a52896ca5f4e20d872aacc31736a7e32e8fcd42` | `22828600e01e27bade5b430fc2174eebeaa26b36` / `e7169f4e178dc9208c5c9d9bb83c884806f9f3065d106b7a6bea5abd8fd20015` | `timings/ca4-*`, `timings/ca4-raw-*` |
| `tests/e2e/test_full_stack_contracts.py` | No existía | `635212c73e01af86bcc657d2542f0ac6c485db45` / `f8796b6ad0e15add4962b16cf27103460d54d05e2b99aaa75f832184d360b613` | `e2e/contracts-r2.json` |
| `tests/e2e/test_full_stack_browser.py` | `a71286d7c3f849804f7b1bd88611006a11d1164e` / `0ce977aa8739b995ff2363786d48789f7406e4c920164502f57d85d1a874c311` | Igual (sin cambios) | `e2e/*.json`, `e2e/streamlit-ranking.png` |
| `tests/e2e/test_full_stack_negative.py` | `eefb2f5df0c01863523b235aa6dcf78378d8cc9c` / `8424c02c9dba35aa76a1346a9041929a7fb586a3f9449064032301e3b6b53903` | Igual (sin cambios) | `negative/*` |

**Diferencia clave R1/R2:** el arnés R1 de CA4 medía, pero no imponía caché fría
ni correlacionaba `request_id`; la caché se vaciaba reiniciando `web-v2` a mano
antes de la corrida. El arnés R2 reinicia `web-v2` dentro del test, falla si
`cold_ui` no produce una llamada real y archiva logs crudos correlacionados. Por
eso **las mediciones CA4 de R1 no son comparables ni reutilizables**.

### 2.1 Autoverificación R2

Cada JSON R2 registra el SHA-256 y el blob Git del arnés que lo produjo:

```powershell
python -c "import json; d=json.load(open('artifacts/oc-e2e-20261024/timings/ca4-timings.json')); print(d['provenance'])"
python -c "import json; d=json.load(open('artifacts/oc-e2e-20261024/e2e/contracts-r2.json')); print(d['provenance'])"
```

Los valores publicados coinciden con `git hash-object` del archivo en el commit
de evidencia. Para R1 esa autoverificación no existe; su vínculo es documental:
el log de la corrida y el commit `426605f`, cuyo blob de CA4 es `3b750d8b`.

---

## 3. Mapa artefacto → corrida → productor

| Grupo | Corrida | Productor |
|---|---|---|
| `e2e/browser-verification.json`, `e2e/health-hops.json`, `e2e/idempotency.json`, `e2e/ml-service-log*.json/txt`, `e2e/openapi-conformance.json`, `e2e/postgis-verification.json`, `e2e/ranking-http.json`, `e2e/streamlit-ranking.png` | R1 | Arnés browser R1 (blob `a71286d7`) |
| `e2e/contracts-r2.json` | R2 | Arnés contratos R2 (blob `635212c7`) |
| `negative/*` | R1 | Arnés negativo (blob `eefb2f5d`) |
| `timings/*` (incluye `ca4-raw-*.log` y `ca4-request-correlation.json`) | R2 | Arnés CA4 R2 (blob `22828600`) |
| `logs/04`–`09`, `12`–`14`, `22`, `24`, `26`, `28`, `31`, `33`, `35`, `36` | R1 | pytest / Maven R1 |
| `logs/41-r2-contracts.log`, `logs/42-r2-ca4.log` | R2 | pytest R2 |
| `logs/40-r2-compose-up.log`, `logs/43-r2-compose-config.log` | R2 | Docker Compose R2 |
| `logs/01`–`03`, `10`–`11`, `15`–`21`, `23`, `25`, `27`, `29`, `30`, `32`, `34`, `37`–`39` | R1 | Comandos manuales de ciclo de vida |
| `environment.txt`, `r2-final-state.json`, `r2-git-state.txt` | R2 | Captura de entorno/estado R2 |
| `r1-final-state.json`, `r1-git-state.txt` | R1 | Captura de estado R1 (renombrados para evitar ambigüedad) |
| `ranking-response-0*.json`, `postgis-snapshot.txt`, `restart-*.json`, `ui-backend-*.json`, `screenshots/*` | R1 | Comandos manuales R1 |

Los artefactos R1 conservan su contenido salvo la redacción de datos
identificatorios descrita en `REDACTION-NOTICE.md`; sus hashes vigentes están en
`SHA256SUMS.txt`.

---

## 4. Qué commit produjo qué evidencia

| Evidencia | Commit de aplicación | Arnés | Commit de publicación |
|---|---|---|---|
| R1 (e2e, negative, CA4, logs 01–39) | `2a71c7e` | Blobs R1 de §2 | `426605f` |
| R2 CA4 (`timings/*`, logs 42) | `2a71c7e` (árboles idénticos en `eb1b370`) | `22828600` | `449ccfdf` (E1) |
| R2 contratos (`e2e/contracts-r2.json`, logs 41) | `2a71c7e` (árboles idénticos en `eb1b370`) | `635212c7` | `449ccfdf` (E1) |
| R2 entorno/estado (logs 40, 43, `r2-*`, `environment.txt`) | `2a71c7e` (árboles idénticos en `eb1b370`) | N/A (comandos) | `449ccfdf` (E1) |

El commit de evidencia R2 se registra en §5 y en el cuerpo del PR de
sustitución. No se reescribió la historia de R1.

---

## 5. Publicación

- **R1:** rama `test/oc-fullstack-e2e-20261024`, commit `426605f`, PR #41
  (draft). Contiene los valores identificatorios originales en su historia; ver
  `REDACTION-NOTICE.md` §4.
- **R2:** rama `test/oc-fullstack-e2e-r2-20261024`, PR de sustitución (draft)
  contra `recovery/s2-academic-20261024` (`eb1b370`). El paquete se incorporó en
  el commit de evidencia `449ccfdfcd02a5955ea8242898351c6c2da8790c` (E1); un
  segundo commit de solo documentación registra ese SHA sin alterar el paquete.
- **Commit de evidencia R2 (E1):**
  `449ccfdfcd02a5955ea8242898351c6c2da8790c`.
- **Verificación reproducible:** los blobs publicados en E1 coinciden con los
  hashes registrados en la evidencia y el manifiesto verifica 91/91.

```powershell
# Blob del arnés CA4 en el commit de evidencia (debe ser 22828600...)
git rev-parse 449ccfdfcd02a5955ea8242898351c6c2da8790c:tests/e2e/test_full_stack_timings.py
# Blob del arnés de contratos (debe ser 635212c7...)
git rev-parse 449ccfdfcd02a5955ea8242898351c6c2da8790c:tests/e2e/test_full_stack_contracts.py
# Manifiesto contra los blobs commiteados: 91 entradas, 0 discrepancias
# (usar el bloque de verificación de README §8 o un script equivalente)
```

---

## 6. Limitaciones de esta procedencia

1. R1 no registró autohash del arnés; su vínculo es documental (log + commit).
2. Las mediciones CA4 R1 se conservan solo en la copia local de auditoría
   (`sapi-audit-baseline-426605f`), no en este paquete, para no presentarlas como
   vigentes.
3. `environment.txt` fue regenerado para R2; los valores R1 siguen en §3 del
   informe y las versiones de herramientas son las mismas.
4. Este documento no certifica CA5, Gate B ni SAPI-43; solo identifica
   procedencia.
