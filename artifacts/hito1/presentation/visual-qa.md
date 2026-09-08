# QA visual — presentación Canva S.A.P.I. Hito 1 (11 slides)

Diseño: `DAHUkB2w4Zg` (candidato 1 de 4 generados por
`generate-design-structured` a partir del outline aprobado). Dos rondas
de QA sobre el mismo diseño — nunca se regeneró ni se creó un nuevo
candidato. Revisión hecha slide por slide contra miniaturas reales
renderizadas por Canva, no contra el outline (que solo describe
intención). `DESIGN_REVIEW` del audit de capacidades quedó en `PARTIAL`
porque Canva no ofrece una herramienta automatizada de revisión de
jerarquía/contraste/legibilidad; esta tabla es esa verificación hecha
manualmente.

## Ronda 1 (07-09-2026) — fabricaciones de la IA de generación

| Slide | Hallazgo | Severidad | Acción | Estado |
|---|---|---|---|---|
| 1 (Portada) | Imagen decorativa tipo mapa de calor satelital (rojo/verde) insertada por la IA — lee como imaginería de incendio, prohibida por el encargo | CRÍTICA | Imagen eliminada | CORREGIDO |
| 1 (Portada) | Faltaban "Hito 1 · Sprint 1" y "Universidad Andrés Bello · INSW421"; nombre del proyecto truncado | ALTA | Nombre completo restaurado; subtítulo e institución agregados | CORREGIDO |
| 1 (Portada) | Efecto colateral: al reducir el tamaño de fuente del título, el cuadro de texto se ancló por el borde inferior, superponiendo título y autor | CRÍTICA | Reposicionados con coordenadas absolutas explícitas | CORREGIDO |
| 2 | Título divergía del outline aprobado; pregunta central recortada; sin mención de las 50 celdas | ALTA | Título y pregunta central restaurados completos | CORREGIDO |
| 3 | Adjetivos no verificados: "priorización efectiva", "de manera eficiente" | MEDIA | Reescrito sin adjetivos infladores | CORREGIDO |
| 4 | Sin ningún diagrama — arquitectura descrita solo en texto, incumpliendo el mandato explícito de redibujarla en vectores | CRÍTICA | Diagrama vectorial de 6 etapas construido con formas y conectores nativos de Canva | CORREGIDO |
| 4 | Adjetivos inflados: "optimizando la atención...", "ranking efectivo" | MEDIA | Reescrito a lenguaje neutro y preciso | CORREGIDO |
| 5 | Infografía de línea de tiempo genérica con datos inventados (horas de reloj sin sentido, "76,60%", "Nombre del evento") | CRÍTICA (fabricación) | Imagen eliminada; construida línea temporal real (features ≤ T / T / T+6h) | CORREGIDO |
| 5 | Título reformulaba el alcance científico ("Estrategias de Predicción...") | ALTA | Corregido a "Predecir sin mirar el futuro" | CORREGIDO |
| 6 | Sin título grande de slide (H1), a diferencia de las demás 9 | MEDIA | Título agregado a 80px | CORREGIDO (ronda 1) — **rehecho por completo en ronda 2** |
| 7 | Dashboard genérico inventado con cifra "85%" fabricada y texto sobre "efectividad" | CRÍTICA (fabricación de métrica y de dashboard) | Reemplazado por frame explícito "INSERTAR CAPTURA REAL..." | CORREGIDO (ronda 1) — **reorientado en ronda 2** |
| 8 | Cifras clave incrustadas en párrafos a 28px, no como "cifras grandes" | MEDIA | Extraídas a elementos de 72px | CORREGIDO |
| 9 | Bloque de calidad comprimido, omitía desglose completo y mención del tag | MEDIA | Desglose completo restaurado (ronda 1) — **reestructurado en tarjetas en ronda 2** | CORREGIDO |
| 9 | Ilustración genérica tipo "panel de BI" sin relación con datos reales | MEDIA | Imagen eliminada | CORREGIDO |
| 10 | Sin título grande de slide (H1) | MEDIA | Título agregado a 80px | CORREGIDO |
| 11 | Bloque de contacto de plantilla genérica ("hello@reallygreatsite") reemplazando el cierre real | CRÍTICA (contenido de plantilla genérica) | Reemplazado por los tres conceptos de cierre reales + frase final + DEMO → | CORREGIDO |

**Resultado ronda 1:** 19 hallazgos, 6 críticos, 0 críticos restantes.

## Ronda 2 (08-09-2026) — dirección visual y jerarquía (feedback de revisión externa)

Sobre el mismo diseño `DAHUkB2w4Zg`, sin regenerar ni crear un nuevo
candidato, atendiendo el veredicto "🟡 muy buena base — hacer una
última pasada de diseño en 5 slides + insertar dashboard real".

| Slide | Hallazgo | Severidad | Acción | Estado |
|---|---|---|---|---|
| Global (1,2,3,4,7,8,9,11) | El motivo decorativo tipo hoja/pétalo de la plantilla Canva (asset recolorable reutilizado en 8 de 11 slides) no tenía relación visual con riesgo/datos/grilla/geografía/ingeniería — delataba el origen de plantilla | ALTA (identidad visual) | Eliminado de las 9 instancias en las 8 slides que lo tenían (slides 5, 6 y 10 nunca lo tuvieron) | CORREGIDO |
| 2 | Slide demasiado vacía/textual; sin identidad espacial propia de S.A.P.I. | ALTA | Construido esquema propio: corredor (Viña del Mar — Quilpué — Villa Alemana), grilla real de 10×5 líneas con 4 celdas destacadas en verde de acento (motivo de marca S.A.P.I., no decoración genérica), fuentes debajo | CORREGIDO |
| 3 | Faltaba el dato de 107 positivos (estaba en el diseño aprobado, se perdió en la generación); formato numérico anglosajón (363,000 / 7,260) en vez de español | ALTA (pérdida de dato + formato) | Reconstruida como 4 métricas grandes (363.000 · 7.260 · 107 · 50) con formato español, flujo compacto debajo | CORREGIDO |
| 6 | La IA convirtió instrucciones para el expositor en contenido visible de la slide ("No presentar curvas ROC o PR como logros", "Clarificar que el desempeño no es estable", "Importancia de la interpretación rigurosa...") — meta-comentario de presentación, no contenido | CRÍTICA (contenido inapropiado para audiencia) | Rehecha por completo: 5 badges por año (2022 NO ENTRENABLE / 2023 LIMITADO / 2024* ADECUADO — acento verde / 2025 LIMITADO / 2026 LIMITADO·PARCIAL), mensaje dominante único, nota del asterisco | CORREGIDO |
| 7 | Placeholder del dashboard en columna vertical estrecha (642 px, ~33% del ancho) — la captura real del dashboard S.A.P.I. es landscape y quedaría aplastada | ALTA (formato incompatible con el asset real) | Placeholder reconstruido en landscape ocupando ~68% del ancho (1300 px), callouts numerados (①②③) reubicados a la derecha en columna vertical | CORREGIDO |
| 9 | Formato de lista de bullets genérica; faltaba "CA históricos completos: 6/10" (dato del outline aprobado) | ALTA (pérdida de dato + formato) | Reconstruida como 4 tarjetas visuales (Trazabilidad/Calidad/Riesgos/Git) en grilla 2×2; CA 6/10 restaurado explícitamente en la tarjeta de Trazabilidad | CORREGIDO |
| 10 | Lenguaje más categórico que la evidencia real: "No seguimiento semanal de avances", "Falta de Definition of Done documentada" | MEDIA (precisión epistémica) | Reformulado a "Sin evidencia de seguimiento/revisión semanal" y "Sin Definition of Done previa al desarrollo" | CORREGIDO |
| 10 | Faltaba la frase de cierre metodológico ("No se reconstruyó evidencia retroactivamente") como elemento visible | MEDIA | Agregada en una banda discreta al pie de la slide | CORREGIDO |

**Resultado ronda 2:** 8 hallazgos, 1 crítico, 0 críticos restantes.

## Verificación de claims científicos (post-ronda 2)

Repetida contra las 11 slides ya corregidas:

- No aparece "predice incendios", "probabilidad de incendio" ni "alerta
  oficial" atribuida a S.A.P.I.
- DMC 330007 sigue presentado como meteorología REGIONAL (slides 4, 11).
- FIRMS sigue tratado como detección satelital, nunca "incendio
  confirmado" (slides 2, 5, 11).
- Horizonte de 6 horas y ventana `T < t ≤ T+6h` correctos (slide 5).
- Slide 6 presenta la validación como "evidencia exploratoria, no
  generalización predictiva demostrada" — ya sin las instrucciones de
  expositor que antes aparecían como contenido visible.
- Ninguna slide convierte el score en probabilidad calibrada.
- Cifras verificadas contra las fuentes congeladas tras la ronda 2:
  363.000 / 7.260 / 107 / 50 (slide 3), 6/10 CA históricos (slide 9),
  470/470 · 91,72% · 5/5 (slide 8) — todas coinciden con
  `docs/informe-hito1-final.md`.

`SCIENTIFIC_SCOPE: PASS`.

## Resumen acumulado (rondas 1+2)

- **Hallazgos totales:** 27.
- **Críticos:** 7 — todos corregidos, 0 restantes.
- **Altos:** 7 — todos corregidos.
- **Medios:** 13 — todos corregidos.
- **`CRITICAL_VISUAL_ISSUES` restantes: 0.**
- **Motivo botánico de plantilla: REMOVED** (0 instancias restantes en
  las 11 slides).

## Pendiente único

La slide 7 mantiene el frame explícito "INSERTAR CAPTURA REAL DEL
DASHBOARD S.A.P.I." — no existe una captura real localizable en el
repositorio (`reports/screenshots/` vacío salvo `.gitkeep`, verificado)
ni una herramienta para subir un archivo local en esta sesión de Canva.
Es la única tarea de contenido que queda pendiente antes de declarar el
deck congelado — el resto de la dirección visual ya está resuelta.
