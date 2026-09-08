# Mapa a rúbrica — Atributos de calidad (Hito 1, 10%)

Generado 07-09-2026. Niveles: `EXCELENTE_DEFENDIBLE` ·
`BUENO_DEFENDIBLE` · `SUFICIENTE_DEFENDIBLE` · `INSUFICIENTE_RISK`. No se
predice nota del profesor.

## Hito 1 — Atributos de calidad (10%)

**Checklist de nivel máximo (exigencia de la rúbrica):**

| Comprobación | Resultado |
|---|---|
| Atributos claramente identificados | 10 candidatos evaluados; 10 documentados en la matriz principal (7 con estado verificado/parcial + 3 explícitamente no verificados/no aplicable, nunca omitidos en silencio) |
| Vinculados por requerimiento | 9 de 16 requerimientos de `docs/trazabilidad-hito1.md` tienen un atributo de calidad medible asociado (sección 15 de `docs/atributos-calidad-hito1.md`); los 7 restantes marcados explícitamente `SIN CRITERIO DE CALIDAD VERIFICABLE`, no forzados |
| Criterios medibles | Cada fila QA-01..QA-10 tiene un criterio verificable (cifra, test nombrado, o archivo concreto) — ninguna fila usa un adjetivo sin evidencia |
| Criterios verificados | QA-01 (Fiabilidad), QA-02 (Integridad de datos) y QA-05 (Reproducibilidad): `VERIFICADO` con evidencia completa. QA-03, QA-04, QA-06, QA-07: `PARCIALMENTE_VERIFICADO` con brecha específica documentada. QA-08 (Rendimiento) y QA-09 (Seguridad): `NO_VERIFICADO` explícito, sin disfrazarse |
| Evidencia disponible | Toda evidencia citada apunta a artefactos ya congelados y verificados en esta misma fase (`pytest-full.txt`, `pytest-junit.xml`, `coverage-summary.txt`, `streamlit-smoke.txt`, `acceptance-checks.txt`, `models/prototype_model_d_metadata.json`) — cero cifras asumidas sin confirmar |

- **Nivel defendible hoy:** `BUENO_DEFENDIBLE`. No es
  `EXCELENTE_DEFENDIBLE` porque 4 de 7 atributos con requerimiento
  asociado quedan `PARCIALMENTE_VERIFICADO` (mantenibilidad sin
  lint/complejidad, robustez de UI sin test dedicado, auditabilidad con
  el GAP heredado de Trazabilidad, usabilidad sin validación de usuario
  externa independiente) — son brechas reales y documentadas, no
  cosméticas ni ocultas.
- **Brecha:** las 4 anteriores, más rendimiento y seguridad sin ninguna
  verificación, más disponibilidad sin requerimiento asociado.
- **Recuperable antes de presentación:** parcialmente. Mantenibilidad
  (agregar configuración mínima de `ruff`) y robustez de UI (un test de
  `_fmt_nd()`) son recuperables con esfuerzo bajo, pero requieren tocar
  el repositorio — fuera del alcance de esta fase, que es solo
  documentación sobre evidencia ya congelada. Usabilidad con usuario
  externo real y el vínculo HU del pipeline temporal requieren una
  sesión/gestión real, no solo documentación.
- **Fase que lo cerrará:** esta fase deja la matriz lista para revisión;
  cerrar las brechas requiere una fase de implementación/gestión
  posterior, explícitamente fuera del alcance de "solo documentar
  atributos de calidad".

## Resumen sin puntaje inventado

| Atributo | Estado | Nivel de defensa |
|---|---|---|
| Fiabilidad | VERIFICADO | Fuerte — 470/0, smoke 5/5, tests de contrato dedicados |
| Integridad de datos | VERIFICADO | Fuerte — 4 invariantes con test dedicado cada una |
| Reproducibilidad | VERIFICADO | Fuerte — hash, commit, semilla, metadata todos presentes |
| Mantenibilidad | PARCIALMENTE_VERIFICADO | Estructural fuerte (AST, cobertura), sin métricas estáticas |
| Robustez a datos faltantes | PARCIALMENTE_VERIFICADO | Capa de datos fuerte, capa de UI manual |
| Auditabilidad/trazabilidad | PARCIALMENTE_VERIFICADO | GAP heredado de Trazabilidad, documentado, no oculto |
| Usabilidad | PARCIALMENTE_VERIFICADO | Smoke técnico fuerte, sin usuario externo independiente |
| Rendimiento | NO_VERIFICADO | Sin medición (`NOT_MEASURED`) |
| Seguridad | NO_VERIFICADO | Sin verificación (`NOT_PERFORMED`) |
| Disponibilidad | NO_APLICA | Sin requisito de disponibilidad ni despliegue/SLA en este incremento local (`AVAILABILITY: NOT_VERIFIED (NO_APLICA_AL_INCREMENTO)`) — no es un atributo fallido |
