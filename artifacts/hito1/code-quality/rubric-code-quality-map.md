# Mapa a rúbrica — Calidad de código (Hito 1, 8%)

Generado 07-09-2026. Niveles: `EXCELENTE_DEFENDIBLE` ·
`BUENO_DEFENDIBLE` · `SUFICIENTE_DEFENDIBLE` · `INSUFICIENTE_RISK`. No
se predice nota.

## Checklist

| Comprobación | Resultado |
|---|---|
| Código limpio/modular | Estructura de paquetes coherente; Data Contract verificado por AST y test dedicado (`FUERTE`) |
| Nomenclatura | Descriptiva y consistente, con mezcla razonable español/inglés (`ADECUADO`) |
| Responsabilidades separadas | 3 módulos con responsabilidad única observable citados; frontera app/inferencia verificada por test | 
| Manejo de errores | 29 try/except, 3 excepciones de dominio, 0 bare except, 12 `except Exception` amplios pero justificados (`ADECUADO`) |
| Buenas prácticas generales | Configuración centralizada (`src/config.py`), logging en el pipeline legacy, docstrings explicativos en el pipeline temporal |
| SOLID solo cuando demostrable | 2 principios evaluados con evidencia concreta (responsabilidad única, separación de capas); 3 marcados `NOT_EVALUATED` explícitamente, no asumidos |

- **Nivel defendible hoy:** `BUENO_DEFENDIBLE`. La separación de capas
  está excepcionalmente bien respaldada (verificada por AST + test de
  regresión, no solo por convención) y el manejo de errores es
  consistente y con excepciones de dominio reales. No es
  `EXCELENTE_DEFENDIBLE` porque: (a) sin lint/type-checking/complejidad
  configurado (brecha reconocida, no corregida en esta fase); (b) 10
  funciones superan 80 líneas, con 2 candidatas reales a refactor
  (`main()` de `app.py`, `render_ops_detail_panel()`); (c) 3 de los 5
  principios SOLID quedan `NOT_EVALUATED` por falta de evidencia
  suficiente, no se puede reclamar "cumple SOLID" globalmente.
- **Brecha:** las 3 anteriores.
- **Recuperable antes de presentación:** sí, con esfuerzo bajo/medio
  (configurar `ruff` con reglas básicas, dividir 2 funciones largas) —
  pero requiere tocar el repositorio, explícitamente fuera del alcance
  de esta fase de auditoría.
- **Fase que lo cerrará:** una fase de implementación posterior, si se
  decide priorizarla frente a las 3 fases restantes del Hito
  (Cierre metodológico, Documento final, Presentación+demo).

## Resumen sin puntaje inventado

| Aspecto | Estado |
|---|---|
| Modularidad | FUERTE |
| Nomenclatura | ADECUADO |
| Manejo de errores | ADECUADO |
| Aislamiento legacy | VERIFIED (test dedicado) |
| Linting | NOT_CONFIGURED |
| Type checking | NOT_CONFIGURED |
| Métricas de complejidad | NOT_MEASURED |
| Seguridad | NOT_PERFORMED (no es el alcance de esta fase) |
| SOLID (2/5 principios) | Evidencia concreta; 3/5 NOT_EVALUATED |
