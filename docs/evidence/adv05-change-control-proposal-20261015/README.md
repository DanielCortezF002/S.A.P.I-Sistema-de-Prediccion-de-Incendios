# ADV-05 — Propuesta de change-control (Directiva 35 / Etapa 1)

**Estado: propuesta NO aplicada.** `src/refresh/firms_refresh.py` y
`src/refresh/dmc_refresh.py` están en `FROZEN_PATHS` de `scripts/freeze_check.py`
(F4). Conforme a la Directiva 35 §1.5, no se modifican sin autorización
específica de change-control. Este documento entrega el diagnóstico exacto,
el diff propuesto y la evidencia RED/GREEN simulada, para que un humano
autorice (o no) su aplicación.

## 1. Comportamiento incorrecto exacto

`_publish()` en ambos módulos escribe el puntero `CURRENT.json`
**antes** de registrar el evento en el historial de auditoría
(`pointer_history.jsonl`):

```python
# src/refresh/firms_refresh.py:272-277 (actual, sin cambios)
def _publish(paths: FirmsPaths, pointer: dict, event: str) -> None:
    atomic_write_json(paths.pointer, pointer)      # <- 1) CURRENT avanza
    append_jsonl(                                   # <- 2) si esto falla...
        paths.history,
        {"event": event, "at": _utcnow().isoformat(), **pointer},
    )

# src/refresh/dmc_refresh.py:586-589 (actual, sin cambios)
def _publish(paths: DmcPaths, pointer: dict, event: str, **extra: Any) -> None:
    atomic_write_json(paths.pointer, pointer)        # <- 1) CURRENT avanza
    record = {"event": event, "at": _utcnow().isoformat(), **extra, **pointer}
    append_jsonl(paths.history, record)              # <- 2) si esto falla...
```

Si `append_jsonl` falla (disco lleno, error de I/O), el puntero **ya quedó
publicado** con la nueva versión. Consecuencias demostradas por
`tests/test_adv05_characterization.py` (pasan hoy, confirmando que el
defecto está presente, no que está resuelto):

1. `CURRENT.json` avanza a una versión cuya publicación nunca se registra en
   el historial — auditoría rota, de forma silenciosa.
2. Un reintento posterior ve el puntero ya actualizado y reporta
   `up_to_date`, perdiendo **permanentemente** la oportunidad de reconciliar
   el historial — no hay mecanismo de recuperación.
3. El mismo patrón existe en DMC (`test_characterize_adv05_dmc_history_failure_breaks_pointer_atomicity`).

## 2. Prueba discriminante nueva (no protegida, ya creada y commiteada)

`tests/test_adv05_proposed_fix_oracle.py` — RED confirmado hoy contra el
código actual:

```
pytest tests/test_adv05_proposed_fix_oracle.py -v --no-cov
-> FAILED (assert pointer unchanged after failed history append)
   AssertionError: ADV-05 confirmado: CURRENT.json avanzo pese a que el
   historial de auditoria fallo...
```

## 3. Diff propuesto (mínimo, NO aplicado)

Reordenar: registrar el historial **antes** de publicar el puntero. Si el
historial falla, el puntero nunca avanza (nada cambia, reintento seguro); si
el puntero fallara después de un historial exitoso (mucho menos probable,
`atomic_write_json` es atómico vía temp+replace), queda una línea de
historial "huérfana" para una versión que nunca llegó a ser CURRENT —
inconsistencia cosmética en el log de auditoría, no una corrupción de
CURRENT, y detectable comparando el último evento de historial contra el sha
del puntero vigente.

```diff
--- a/src/refresh/firms_refresh.py
+++ b/src/refresh/firms_refresh.py
@@ -272,9 +272,9 @@
 def _publish(paths: FirmsPaths, pointer: dict, event: str) -> None:
-    atomic_write_json(paths.pointer, pointer)
     append_jsonl(
         paths.history,
         {"event": event, "at": _utcnow().isoformat(), **pointer},
     )
+    atomic_write_json(paths.pointer, pointer)
```

```diff
--- a/src/refresh/dmc_refresh.py
+++ b/src/refresh/dmc_refresh.py
@@ -586,9 +586,9 @@
 def _publish(paths: DmcPaths, pointer: dict, event: str, **extra: Any) -> None:
-    atomic_write_json(paths.pointer, pointer)
     record = {"event": event, "at": _utcnow().isoformat(), **extra, **pointer}
     append_jsonl(paths.history, record)
+    atomic_write_json(paths.pointer, pointer)
```

## 4. Verificación de que el diff propuesto funciona (simulado, sin tocar el archivo protegido)

Se verificó el efecto del diff mediante `monkeypatch.setattr(fr, "_publish", <versión propuesta>)`
en un test temporal (ejecutado y luego eliminado, no commiteado, consistente
con no dejar código de verificación desechable en el repositorio):

```
GREEN check (pointer unchanged after failed history append): True
CONFIRMED: reordering history-append before pointer-write resolves ADV-05.
```

Esto prueba que el diff propuesto es correcto **sin modificar el archivo
protegido** — la verificación se hizo sustituyendo la función en memoria
durante una ejecución de prueba aislada.

## 5. Bloqueo técnico encontrado al intentar aplicar (Directiva 36, 15-10-2026)

El Product Owner autorizó explícitamente (Directiva 36) aplicar el diff de
la sección 3. Al intentarlo con la herramienta `Edit` sobre
`src/refresh/firms_refresh.py`, el propio harness de Claude Code lo denegó:

```
SAPI freeze: protected file; needs explicit change control
```

Causa raíz: `C:\SAPI\.claude\hooks\sapi_guard.py` es un hook `PreToolUse`
configurado por el dueño de la cuenta (no por este candidato ni por ninguna
directiva de esta sesión) que **deniega incondicionalmente**, sin mecanismo
de excepción, cualquier `Write`/`Edit`/`MultiEdit` cuya ruta coincida con
`src[/\\](?:refresh|inference|modelo|output)` (entre otras). No evalúa
autorizaciones en el texto de la conversación — es un control técnico fuera
del alcance de esta sesión, y correctamente así: una instrucción de chat
nunca debería poder levantar por sí sola un guard de este tipo.

**No se intentó eludir este control** (p. ej. vía escritura por shell): el
mismo hook también deniega mutaciones de shell sobre rutas protegidas
(`WRITE_SHELL` + `PROTECTED`), y hacerlo de todas formas violaría tanto la
intención del guard como las instrucciones de seguridad de esta sesión.

**Para que esta corrección se aplique, el dueño de la cuenta debe, fuera de
esta sesión:** ajustar temporalmente `sapi_guard.py` (añadir una excepción
puntual, o deshabilitarlo transitoriamente), aplicar el diff de la sección 3
él mismo, o indicar un mecanismo distinto ya previsto que yo no conozca. Una
vez aplicado por ese medio, esta sesión puede continuar con la regresión
GREEN, los escenarios adversariales adicionales y el commit, tal como pide
la Directiva 36.

## 6. Qué falta para cerrar ADV-05 formalmente

1. **Autorización humana de change-control** para aplicar el diff de la
   sección 3 a `src/refresh/firms_refresh.py` y `src/refresh/dmc_refresh.py`.
2. Tras aplicar, ejecutar `tests/test_adv05_proposed_fix_oracle.py` (debe
   pasar a GREEN) y la regresión completa (`test_remediation_red_defects.py`,
   `test_refresh_adversarial.py`, `test_adv05_characterization.py` —
   estos últimos deberán **reescribirse** porque hoy afirman el
   comportamiento roto como "characterization", no como regresión aceptable).
3. Registrar el commit de remediación con referencia a esta propuesta,
   análogo a como `4012fbf` referenció `docs/evidence/sapi71-f4-prep/`.

## 7. Estado explícito

- **ADV-05: RESUELTO Y VALIDADO (Directiva 37).** El dueño de la cuenta
  aplicó el diff manualmente fuera de esta sesión. Validación completa con
  186 pruebas reales (0 fallos) en
  `docs/evidence/adv05-fix-validated-20261015/README.md`.
- **F4 histórico: FAIL, sin cambio** — ninguna de las acciones de esta
  sección tocó `src/refresh/*.py`; el diff vive únicamente en este documento.
- **B1/B2/B3: siguen cerrados**, sin reabrir (ver
  `docs/evidence/b1-b2-b3-estado-real-20261015/`), confirmado por regresión
  intacta.
