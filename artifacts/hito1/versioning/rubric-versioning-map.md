# Mapa a rúbrica — Versionamiento (Hito 1, 8%)

Generado 07-09-2026. Niveles: `EXCELENTE_DEFENDIBLE` ·
`BUENO_DEFENDIBLE` · `SUFICIENTE_DEFENDIBLE` · `INSUFICIENTE_RISK`. No
se predice nota.

## Checklist

| Comprobación | Resultado |
|---|---|
| Commits frecuentes | 68 commits en `main`, pero con una brecha real de 53 días sin actividad (06-07 a 28-08-2026) — frecuencia real desigual, no constante |
| Mensajes descriptivos | 66/68 (97%) con prefijo tipo+scope identificable; clasificación `FUERTE` con ejemplos citados |
| Branching consistente | Nomenclatura consistente (`feature/`, `experiment/`, `design/`), pero sin evidencia de un flujo de integración (PR/merge) documentado y una rama `develop` remota sin uso real — `PARTIAL` |
| Cierre/versionado del Sprint | Tag ANOTADO real `v1.0.0-sprint1-verified` — tagger date propio 31-08-2026 (no inferido del commit), target commit del mismo día, mensaje con evidencia técnica citada, y referencia independiente previa en `docs/acta-pruebas-aceptacion-usuario.md` — `VERIFIED` |
| Tag de cierre | `VERIFIED` (ver arriba; verificación forense en `docs/versionamiento-hito1.md`, sección 6.1) |
| Trazabilidad Git↔Jira | 7/68 commits (10.3%) con referencia `SAPI-xx` explícita, cálculo reproducible — presente pero baja |

- **Nivel defendible hoy:** `BUENO_DEFENDIBLE`. El hallazgo de
  `v1.0.0-sprint1-verified` es fuerte y real — sube el nivel respecto a
  lo que se hubiera podido defender sin ese tag. No es
  `EXCELENTE_DEFENDIBLE` por la brecha de 53 días sin commits, la
  estrategia de ramas parcial (sin flujo de integración documentado) y
  la baja tasa de trazabilidad Git↔Jira (10.3%).
- **Brecha:** las 3 anteriores, más `CHANGELOG: NOT_FOUND`.
- **Recuperable antes de presentación:** la trazabilidad Git↔Jira y el
  branching son recuperables hacia adelante (Sprint 2), no
  retroactivamente para los commits ya hechos. Un tag adicional
  `hito1-evidence-2026-09-07` (si se decide crear, en una acción
  separada y explícitamente descrito como tag de cierre documental
  actual, no histórico) mejoraría el registro del estado actual sin
  cambiar el historial de Sprint 1.
- **Fase que lo cerrará:** el hallazgo del tag ya cierra gran parte de
  este criterio; el resto depende de disciplina futura, no de esta fase.

## Resumen sin puntaje inventado

| Aspecto | Estado |
|---|---|
| Volumen de commits | 68 en `main`, distribución desigual |
| Calidad de mensajes | FUERTE |
| Branching | PARTIAL |
| Tag de cierre de Sprint | VERIFIED — anotado, tagger date 31-08-2026 (`v1.0.0-sprint1-verified`) |
| Changelog | NOT_FOUND |
| Trazabilidad Git↔Jira | 10.3% (7/68), PARTIAL |
