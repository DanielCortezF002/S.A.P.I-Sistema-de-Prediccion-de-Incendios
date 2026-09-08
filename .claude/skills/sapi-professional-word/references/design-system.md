# Design system — sapi-professional-word

Criterios editoriales **provisionales**, derivados del smoke test
técnico-editorial del 07/09/2026 (`artifacts/editorial-smoke/`,
3 iteraciones).

El smoke test validó el **proceso** de generación, maquetación,
renderizado e inspección visual (pipeline DOCX → PDF → PNG, estilos
Word, control de paginación, QA visual iterativo) -- **no constituye una
referencia estética externa ni una identidad visual definitiva para
S.A.P.I.** Nada de lo que sigue en este archivo es "branding oficial":
es un punto de partida razonable para cuando no existe nada mejor. Ver
la jerarquía de referencias a continuación.

## Jerarquía de referencias visuales (léela antes que el resto de este archivo)

Ante cualquier decisión de diseño para un documento real, consulta en
este orden -- una referencia de nivel superior **reemplaza** las
decisiones de nivel inferior, incluida cualquier decisión de este
archivo:

1. **Plantilla institucional oficial** (de la universidad, la
   asignatura, o la organización para la que se escribe el documento),
   si existe.
2. **Documento humano aprobado expresamente por el usuario** como
   referencia visual para este proyecto, si existe (ver
   `templates/README.md`).
3. **Convenciones académicas de la universidad/asignatura** (normas de
   formato que la institución exija, aunque no vengan en forma de
   plantilla descargable: tipografía exigida, márgenes, formato de
   citas, etc.).
4. **Este design system provisional** -- se usa únicamente cuando
   ninguna de las tres referencias anteriores existe o cubre la decisión
   en cuestión.

De una referencia de nivel 1-3, **nunca se copia el contenido** -- solo
se extrae guía de: tipografía, márgenes, jerarquía, portada, densidad,
tablas, captions, encabezados, pies, numeración, uso de color, espacio
en blanco.

## Dirección (aplicable en cualquier nivel de la jerarquía)

Académico, técnico, sobrio, contemporáneo, editorial, creíble.

## Evitar explícitamente

- Estética de chatbot / asistente de IA.
- Plantilla tipo Canva.
- Folleto comercial.
- Presentación (slides) convertida a Word.
- Dashboard convertido a documento.

## Prohibido por defecto (nivel 4 -- salvo que una referencia de nivel 1-3 indique otra cosa)

- Emojis.
- Gradientes.
- Cajas redondeadas.
- Tarjetas ("cards").
- Sombras.
- Iconografía decorativa (íconos cartoon, nubes, servidores 3D, etc.).
- Títulos gigantes (un `Title` grande está bien; un `Title` que domina
  media página, no).
- Fondos de sección (bloques de color detrás de un título o bloque de
  texto).
- Exceso de azul o morado (el "purple gradient" es la firma visual más
  reconocible de contenido generado por IA sin dirección de diseño;
  evitarlo activamente).
- Barras laterales decorativas.
- Callouts innecesarios (cajas "Nota:" o "Importante:" con fondo de
  color, salvo que el propio documento humano de referencia las use).
- Exceso de negrita (negrita para UN término clave por párrafo como
  mucho, nunca una oración completa en negrita salvo un dato crítico
  puntual).
- Exceso de bullets (una lista debe ser una lista real -- ítems breves,
  paralelos entre sí -- nunca la sustitución sistemática de párrafos
  narrativos por listas).

## Límites obligatorios (nivel 4)

- **Máximo 2 familias tipográficas** en todo el documento (una para
  encabezados, otra para cuerpo -- ver más abajo).
- **Como mucho 1 color de acento discreto**, y **ningún color es
  branding oficial de S.A.P.I.** El color de acento debe derivarse, en
  este orden: de una plantilla institucional (nivel 1), de una
  referencia humana aprobada (nivel 2), de una convención académica
  (nivel 3); solo si ninguna de esas existe, se usa una solución neutra
  y sobria como la de este archivo (nivel 4). Nunca inventar un color
  "de marca" para el proyecto. Todo lo que no sea el acento es tinta/
  gris: texto principal en un gris muy oscuro (no negro puro, que se ve
  más duro en pantalla e impresión), texto secundario/meta en un gris
  medio, líneas divisorias en un gris claro. El acento se reserva para
  un elemento de énfasis puntual (p. ej., el borde de un componente
  destacado en un diagrama), nunca para bloques grandes de superficie.

## Paleta neutra de nivel 4 (usada en el smoke test, no oficial)

Esta tabla registra los valores concretos usados en el smoke test
editorial como demostración de que "1 acento discreto, sin azul/morado
genérico" es alcanzable -- **no** es la paleta de S.A.P.I. Úsala solo
cuando no exista ninguna referencia de nivel 1-3.

| Uso | Valor | Nota |
|---|---|---|
| Texto principal | `#2B2B2B` | Nunca negro puro (`#000000`) |
| Texto secundario / meta | `#595959` | Subtítulos, captions, metadatos de portada |
| Líneas divisorias | `#BFBFBF` | Reglas finas bajo títulos, separadores de portada |
| Acento usado en el smoke test editorial | `#3E5C58` (verde-azulado apagado) | **No es un color institucional ni obligatorio de S.A.P.I.** -- es el valor concreto que se usó en `artifacts/editorial-smoke/` para demostrar el criterio "un solo acento discreto, nunca azul/morado saturado tipo IA". Cualquier tono igual de discreto y neutro sirve igual (terracota apagado, grafito con un matiz); si existe una referencia de nivel 1-3 con su propio color, esa referencia manda |
| Bordes de tabla | `#8C8C8C` (exterior), `#D9D9D9` (interior) | Finos, nunca gruesos ni de color |
| Sombreado de encabezado de tabla | `#EDEDED` | Gris muy claro, nunca un color saturado |

Si un documento real de S.A.P.I. tiene una identidad institucional
distinta (plantilla humana de la universidad, ver `templates/README.md`,
o cualquier otra referencia de nivel 1-3), esa identidad tiene prioridad
absoluta sobre esta tabla.

## Tipografía

Verificado disponible en esta máquina Windows (no asumir, confirmar con
`Get-ChildItem` sobre `C:\Windows\Fonts` o el registro de fuentes antes
de elegir, ya que la disponibilidad puede variar entre máquinas):
Calibri (+ Calibri Light), Cambria, Constantia, Garamond, Georgia,
Palatino Linotype, Times New Roman, Arial, Segoe UI.

Combinación usada en el smoke test (nivel 4, no obligatoria -- una
plantilla institucional o referencia humana de nivel 1-3 la reemplaza
directamente):
- **Títulos/encabezados:** Calibri Light (Title/Subtitle) y Calibri en
  negrita (Heading 1/2/3) -- sans serif limpia, contemporánea.
- **Cuerpo:** Constantia -- serif editorial diseñada para lectura en
  pantalla e impresión, más distintiva que "otro documento en Times New
  Roman" o "otro documento en Calibri de cuerpo a título".

No es la única combinación válida, y no es la tipografía "de S.A.P.I.":
es el ejemplo concreto que demostró, en el smoke test, que "máximo 2
familias, una sans para jerarquía, una serif o sans editorial muy
legible para cuerpo, ambas confirmadas como instaladas" es un criterio
alcanzable.

## Portada

Sobria. Título, subtítulo, institución, asignatura/contexto, autor,
fecha -- con espacio en blanco intencional, nunca una caja de color de
fondo. Una sola línea divisoria fina es aceptable como separador entre
el bloque de título y el bloque de metadatos. Sin número de página
visible en la portada.

## Jerarquía tipográfica de encabezados

`Heading 1` debe distinguirse con claridad (tamaño y peso mayores, una
regla inferior fina opcional) pero sin ser exagerado -- no debe verse
como un cartel. `Heading 2` es una jerarquía secundaria limpia,
claramente subordinada a `Heading 1`. `Heading 3` se distingue de
`Heading 2` (p. ej. cursiva + tamaño ligeramente menor) sin resultar
visualmente excesivo para un subapartado de detalle.

## Página

Tamaño carta o A4 (consistente en todo el documento), márgenes
consistentes (~2.5 cm es un punto de partida razonable de nivel 4),
header discreto (un texto corto, alineado, con una regla fina inferior
-- nunca el título completo del documento repetido en cada página),
footer con número de página y nada más salvo que el documento lo
requiera explícitamente. Evitar páginas casi vacías causadas por saltos
innecesarios (ver SKILL.md, sección "Lecciones obligatorias").

## Párrafos

Interlineado profesional (~1.15), espacio posterior moderado (no cero,
no excesivo), alineación justificada consistente en el cuerpo, ancho de
línea cómodo (ni columnas angostas de revista ni líneas que cruzan toda
la página). Párrafos de longitud natural -- ni bloques gigantes de una
sola idea, ni párrafos de una sola oración usados como sustituto de
prosa real.
