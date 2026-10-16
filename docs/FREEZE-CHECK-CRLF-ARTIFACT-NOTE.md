# Nota: FAIL de `freeze_check.py` en F6/F9 es un artefacto de checkout CRLF

**14/10/2026 (corregida 14/10/2026, dictamen Astra independiente, hallazgo "P2: explicación del
freeze"). No se modificó `scripts/freeze_check.py` (el verificador no se relaja).** Esta nota
documenta, con evidencia reproducible, por qué `freeze_check.py` reporta FAIL en F6/F9 (cinco
archivos de texto) aunque ninguno de ellos fue tocado por F1, y por qué eso es correcto
reportarlo así, no ocultarlo.

**Corrección respecto de la versión anterior de esta nota:** la versión committeada en `1bdd827`
incluía `contracts/openapi/ml-service.v0.yaml` en la tabla de "artefacto CRLF" y afirmaba que su
hash de blob LF coincidía con el "esperado" de `freeze_check.py`. **Eso era falso.** F6/F9
(`FILE_PINS`) y F7 (`CONTRACT_PINS`) son mecanismos distintos del mismo script, y no todo lo que
aparece "cambiado" en disco es un artefacto de codificación. La tabla de abajo cubre solo F6/F9
(cinco archivos de texto, confirmados CRLF-only). F7/F4b se explican aparte, en su propia sección,
porque uno de los dos contratos **sí cambió de contenido real**, no solo de fin de línea.

## Causa (F6/F9 — cinco archivos de texto)

Este clon se creó con `core.autocrlf=true`. Git normaliza los archivos de texto a `LF` en el
objeto commiteado (el *blob*), pero los materializa en el *working tree* con `CRLF` al hacer
checkout en Windows. `freeze_check.py` calcula el SHA-256 del archivo **en el working tree**
(CRLF) y lo compara contra un hash "esperado" (`FILE_PINS`) que fue fijado originalmente sobre
el contenido **LF** del blob. El contenido es idéntico; la codificación de fin de línea en disco
no.

## Evidencia (reproducible con los comandos exactos)

Para cada archivo: `git diff --stat -- <archivo>` (debe ser vacío, confirma que git considera
el archivo sin cambios) junto con `git show HEAD:<archivo> | sha256sum` (hash del *blob* LF,
coincide con el "esperado" de `freeze_check.py`) contra `sha256sum <archivo>` (hash del
*working tree* CRLF, coincide con el "observado"):

| Archivo | `git diff` | Blob LF (`git show HEAD:...`) | Working tree CRLF (`sha256sum`) |
|---|---|---|---|
| `db/migration/V001__enable_postgis.sql` | vacío | `5f3606cb3b51ffbcbb509213493b36f6ff2e5c298b2dedd1b39ed16aa99db0df` | `13c089d8a48449f5447b4ffff4feb2cdfce2a7cce5304612d532a8521d90d013` |
| `db/migration/V002__create_sapi_v2_schema.sql` | vacío | `22df9f6843a21e4d00609b882e6afa9f337d6a6dbdda82626f19549241584206` | `ba89d672a683450e95f0d46d4627cfc0e10ae14cf9cc90321355841a48a54470` |
| `db/migration/V003__seed_celdas_geom.sql` | vacío | `02690a1684aa19bb40c7bb856a892096211ed352221d715e99d3f93cbf5bf009` | `97c0eecd1f22fa436e7681a994430f35f1eee6c0bc474119ea026ab074e84ca9` |
| `models/prototype_model_d_metadata.json` | vacío | `fc2c62341d821ddf2c4483050c917a2b2f0ab96607d134bb9ba05b7f82a07bd9` | `3a03fe962bd75c86e4d706638ffd8a1607385892033fc3230f41164ad37a32f2` |
| `artifacts/hito1/reproducibility/manifest.json` | vacío | `a02500da7fb2e055766c76b154fbcf8e11b957a3f413d3e3c8c59d0ef2afa439` | `c8853f416d6f3d367990ee9c9af8810816e025cbb65586059e267b6698e966a3` |

Las columnas "Blob LF" coinciden exactamente con los valores "esperado=" que imprime
`freeze_check.py` para estas cinco filas `F6/F9`. `models/prototype_model_d.pkl` (PASS) es
binario y no sufre esta conversión -- confirma que el mecanismo es específicamente CRLF de
archivos de texto, no una discrepancia de contenido. Ninguno de estos cinco archivos está en
`CONTRACT_PINS`; ver la sección siguiente para los dos que sí.

## F7 (`CONTRACT_PINS`) — mecanismo distinto; NO generalizar el CRLF aquí

`check_contracts()` compara `sha256_file(rel)` (disco, sensible a CRLF igual que F6/F9) contra
`CONTRACT_PINS`, pero a diferencia de F6/F9 su fila nunca es `FAIL`: si algún contrato cambió,
la fila es **`F7 contratos v0 = INFO`**, y la pregunta de si ese cambio está autorizado la
resuelve una fila aparte, **`F4b contratos aditivos`**, que compara los dos YAML parseados (no
bytes de disco, así que no le afecta CRLF) y exige "sin claves eliminadas ni valores cambiados".
`Report.failed` solo mira filas `FAIL`; una fila `INFO` nunca bloquea el veredicto global, con o
sin `F4b` en `PASS`.

Los dos contratos en `CONTRACT_PINS` **no comparten la misma causa**:

| Archivo | Blob LF (`git show HEAD:...`) | Pin `CONTRACT_PINS` | Blob LF en baseline `cd6b58e` | Causa |
|---|---|---|---|---|
| `contracts/openapi/backend.v0.yaml` | `f3ea2916d589731852502917baa30b104d61380fccd083187b1498a2dc93531b` | `f3ea2916d589731852502917baa30b104d61380fccd083187b1498a2dc93531b` | igual al blob LF actual | **Coincide.** Es CRLF-only, igual que F6/F9 (disco=`feec5340c2…`); el blob no cambió desde el baseline. |
| `contracts/openapi/ml-service.v0.yaml` | `a553b7ae138f8566e9fd6dc707e57fdcebd2cb9a2a817780886b4ce9828916ff` | `4ca85a8719b2ea7c3516cd9ca710cb514010c10df422049da8383bbd50af49c7` | `4ca85a8719b2ea7c3516cd9ca710cb514010c10df422049da8383bbd50af49c7` | **No coincide, ni en LF.** El contenido cambió de verdad respecto del baseline: `git diff cd6b58e HEAD -- contracts/openapi/ml-service.v0.yaml` muestra campos opcionales nuevos en `RankingResultSynthetic` (`weather_timestamp`, `age_hours`, `freshness`, `station_id`, `station_name`, `firms_origin`, `firms_coverage_end`, `firms_lag_days`, `firms_status`), sin eliminar ni modificar ninguno existente. |

Para `ml-service.v0.yaml` el pin quedó desactualizado por un cambio de contrato real y
deliberado (incluye el propio campo `firms_origin` que sustenta todo F1) — no por CRLF. Que
aparezca como "cambiado" en `F7` es correcto; que sea `INFO` y no `FAIL` también lo es, porque
`F4b` ya confirmó que el cambio es solo-adición. No hay nada que "corregir" aquí salvo esta
descripción: el pin de `CONTRACT_PINS` no se actualiza en esta ronda (fuera del alcance F1;
mantenerlo desactualizado es intencional para que `F7`/`F4b` sigan ejercitándose en cada corrida).

## Por qué no se "relaja" el verificador

Las dos opciones correctas serían: (a) que `freeze_check.py` compare contra `git show
HEAD:<path>` en lugar de leer el archivo del disco, o (b) que el checkout de referencia fije
`core.autocrlf=false`/`.gitattributes` con `text eol=lf` para estas rutas. Ninguna de las dos
se implementó en esta ronda: la primera cambiaría el comportamiento del verificador (fuera del
alcance autorizado, que es remediación de F1, no refactor de `freeze_check.py`); la segunda
tocaría archivos fuera del alcance de F1. Se documenta la causa con evidencia verificable en
vez de ocultar el FAIL o alterar el verificador para que deje de reportarlo.

## F8 (worktree) -- causa distinta, sí corregida

Antes de esta nota, `F8 ignorados inesperados` fallaba porque dos archivos de evidencia
(`mvn_verify.log`, `pytest_full.log`, ambos cubiertos por `*.log` en `.gitignore`) quedaban
sueltos en el árbol de trabajo. Se eliminaron del disco (su contenido ya está en el ZIP de
auditoría con su propio SHA-256); esto sí corrige F8 legítimamente, sin tocar el verificador
ni la evidencia histórica comiteada.
