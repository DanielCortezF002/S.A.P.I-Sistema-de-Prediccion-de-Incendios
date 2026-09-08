# Protocolo de aceptación del incremento — LISTO PARA EJECUTAR

**Este documento es un protocolo actual, no un acta histórica.** No
describe una sesión que ya ocurrió — describe los pasos que una persona
(idealmente distinta de quien desarrolló el pipeline) debe seguir para
aceptar o rechazar el incremento del prototipo, con fecha real de cuando
efectivamente se ejecute.

Existe evidencia real de una sesión de aceptación previa, pero de
alcance distinto (usabilidad móvil, auto-evaluación del desarrollador,
no de este incremento del pipeline temporal): ver
`docs/acta-pruebas-aceptacion-usuario.md`. Ese documento NO cubre el
pipeline temporal/prototipo de datos reales congelado en
`docs/arquitectura-hito1.md` — por eso se define este protocolo nuevo.

---

## Campos a completar en el momento real de la ejecución

| Campo | Valor |
|---|---|
| Fecha real de ejecución | _(completar el día que se ejecute — no usar una fecha anterior)_ |
| Versión / commit evaluado | `9f076172adca3dbce0285f5d942d2803ac6f68a4` (HEAD al cierre de esta fase, rama `main`) — actualizar al commit real si cambia antes de ejecutar |
| Sprint Goal | _(completar con el Sprint Goal real de Sprint 1, si existe documentado en Jira — no inventar uno aquí)_ |
| Evaluador (nombre/rol) | _(completar — debe ser una persona real que ejecute la sesión)_ |

## HU / incremento a revisar

El incremento a aceptar es el **prototipo local del pipeline temporal**
descrito en `docs/arquitectura-hito1.md`: modo "Prototipo (datos reales)"
del dashboard, `score_current_grid()` sobre las 50 celdas.

## Criterios verificables a demostrar en vivo

Usar los mismos AC-T01..AC-T10 de `acceptance-checks.txt` como guion de
demo — cada uno ya tiene respaldo técnico (test/código), pero esta
sesión verifica que el comportamiento sea el mismo **en vivo**, no solo
en la suite de tests:

| # | Paso de demo | Esperado | Observado | PASS/FAIL |
|---|---|---|---|---|
| 1 | Abrir `streamlit run app/app.py`, confirmar que el modo por defecto es "Prototipo (datos reales)" | Selector muestra Prototipo preseleccionado | _(completar)_ | _(completar)_ |
| 2 | Observar el banner de frescura de datos | Si la lectura DMC tiene >24h de antigüedad, aparece el banner de datos históricos/desactualizados | _(completar)_ | _(completar)_ |
| 3 | Contar las celdas mostradas en el mapa/tabla | 50 celdas, ninguna repetida | _(completar)_ | _(completar)_ |
| 4 | Revisar el ranking cuando existan celdas empatadas | El mismo número de posición se repite para el grupo empatado (no un orden artificialmente distinto) | _(completar)_ | _(completar)_ |
| 5 | Seleccionar una celda con DEM fuera de cobertura (si existe alguna) | Elevación/pendiente muestran "N/D", nunca "0" | _(completar)_ | _(completar)_ |
| 6 | Confirmar en el detalle de una celda que no aparece lenguaje de "probabilidad de incendio" ni "alerta oficial" | Solo lenguaje de score/ranking exploratorio | _(completar)_ | _(completar)_ |

## Aceptación / rechazo

| Campo | Valor |
|---|---|
| Observación general | _(completar)_ |
| Aceptación / rechazo | _(completar — NO rellenar sin que una persona real ejecute la sesión)_ |
| Nombre y rol del evaluador | _(completar)_ |

---

**Nota de honestidad temporal:** mientras estos campos digan
"(completar)", este protocolo NO constituye evidencia de aceptación
ejecutada — es la plantilla lista para usarse. Cualquier versión de este
archivo con los campos llenos debe llevar la fecha real de esa ejecución,
nunca una fecha retroactiva.
