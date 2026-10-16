# ADV-05 — Validación real del fix aplicado (Directiva 37)

**Estado: RESUELTO Y VALIDADO.** El propietario del proyecto aplicó
manualmente el diff autorizado (Directiva 36) fuera del alcance de esta
sesión, dado que `src/refresh/` está protegido por un hook `PreToolUse` sin
mecanismo de excepción (`C:\SAPI\.claude\hooks\sapi_guard.py`).

## 1. Confirmación de que el diff aplicado coincide con lo autorizado

```
git diff -- src/refresh/firms_refresh.py src/refresh/dmc_refresh.py
```

Ambas funciones `_publish` ahora ejecutan `append_jsonl` antes de
`atomic_write_json`, exactamente como en la propuesta de
`docs/evidence/adv05-change-control-proposal-20261015/README.md` §3 — 2
líneas movidas por archivo, ningún otro cambio. `git diff --check`: limpio.
Ningún otro archivo rastreado modificado. Confirmado que no se tocó el
baseline científico, `artifacts/hito1`, el Modelo D, ni ningún otro
componente protegido ajeno a ADV-05.

## 2. GREEN contra el código real (ambos sentidos, FIRMS y DMC)

### Sentido 1 — falla el historial, puntero no debe avanzar

| Prueba | Resultado |
|---|---|
| `test_adv05_firms_history_failure_leaves_pointer_unchanged` | PASS — puntero byte-idéntico tras fallo de historial |
| `test_adv05_firms_retry_reconciles_history_after_failed_append` | PASS — el reintento publica de verdad (no `up_to_date` falso), versión final sí queda en el historial |
| `test_adv05_dmc_history_failure_prevents_first_publication` | PASS — `CURRENT.json` nunca se crea en la primera publicación si el historial falla |
| `test_adv05a_firms_history_append_failure_prevents_pointer_write` | PASS — lock liberado, `CURRENT.json` nunca escrito, historial vacío |
| `test_adv05b_dmc_history_append_failure_prevents_pointer_write` | PASS — homólogo DMC |

### Sentido 2 — falla el puntero DESPUÉS de que el historial ya se escribió

`test_adv05_firms_orphaned_history_record_when_pointer_write_fails` — PASS,
con un hallazgo real documentado en el propio test:

- El historial queda con **un registro huérfano** (describe una versión que
  el puntero nunca llegó a reflejar) — exactamente como anticipó la
  propuesta de change-control.
- El puntero **no avanza** mientras su propia escritura falle.
- Al reintentar (con la escritura del puntero restaurada), el sistema
  **reproduce el mismo contenido determinista** (misma ventana de datos ⇒
  mismo sha256) y publica correctamente. El historial queda con el mismo
  sha256 **dos veces**: una del intento huérfano, otra de la republicación
  real.
- **Esto no es una duplicación errónea ni una corrupción**: es un registro
  fiel de dos eventos distintos (uno que no llegó a tomar efecto, otro que
  sí) sobre el mismo contenido. El invariante real que importa —que el
  puntero final corresponda a un evento real y verificable del historial,
  sin inventar un tercer estado— se cumple. Se ajustó la aserción del test
  para exigir exactamente esto, en vez de una unicidad de sha256 que el
  propio diseño del fix nunca prometió (ver propuesta §3: "inconsistencia
  cosmética en el log de auditoría, no una corrupción de CURRENT").

**No se encontró ningún defecto adicional que exigiera modificar
`src/refresh/` más allá del diff ya aplicado.**

## 3. Pruebas de caracterización existentes — actualizadas, no descartadas

`tests/test_adv05_characterization.py` fue reescrito íntegramente: las 5
aserciones que antes confirmaban el comportamiento defectuoso como "esperado"
ahora exigen el comportamiento correcto. Todas pasan contra el código real
aplicado (ver tabla arriba — son los mismos 5 casos, ahora con nombres y
aserciones que reflejan la corrección). Ningún archivo protegido fue tocado
para lograr esto; solo `tests/`.

## 4. Regresión completa

```
pytest tests/test_adv05_proposed_fix_oracle.py tests/test_adv05_characterization.py
       tests/test_remediation_red_defects.py tests/test_refresh_adversarial.py
       tests/test_scoring_inputs.py tests/test_firms_refresh.py tests/test_dmc_refresh.py
       tests/test_refresh_primitives.py tests/test_dmc_store_contract.py
-> 186 passed, 2 skipped, 0 failed en 41.98s
```

**B1/B2/B3: no reabiertos.** Las 9 pruebas de `test_remediation_red_defects.py`
y el resto de la suite adversarial permanecen en PASS, sin ninguna
regresión introducida por el reordenamiento de `_publish`.

## 5. Estado de F4

Sin cambio de clasificación: `src/refresh/firms_refresh.py` y
`src/refresh/dmc_refresh.py` seguirán apareciendo como divergentes del
baseline `cd6b58e` en el check de freeze — correctamente, porque ahora
tienen **dos** cambios autorizados acumulados (TOCTOU + Bloque A B1/B2/B3, y
ahora ADV-05), todos con cadena de autorización documentada. No se declara
F4 PASS; no se modificó `scripts/freeze_check.py` ni su baseline.

## 6. Riesgos residuales

- El registro huérfano de historial (sentido 2) es cosmético, no
  corrupto, pero sigue siendo visible en el log append-only; un operador
  que audite el historial manualmente debe saber que un evento de historial
  no garantiza por sí solo que el puntero llegó a reflejarlo — debe
  cruzarse contra el puntero vigente, tal como ya advertía la propuesta.
- No se evaluaron escenarios de fallo concurrente (dos procesos
  escribiendo a la vez) — fuera del alcance de ADV-05 tal como se definió.
