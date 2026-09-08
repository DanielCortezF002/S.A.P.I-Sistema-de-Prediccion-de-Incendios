# Plantillas humanas — sapi-professional-word

Esta carpeta está reservada para una plantilla Word real, hecha por una
persona, si en algún momento existe una para un documento de S.A.P.I.
(p. ej. una plantilla institucional de la universidad para el informe
del Hito, o una plantilla previa que el equipo ya haya usado).

Hoy no existe ninguna plantilla en este repositorio -- esta carpeta
documenta la política a seguir el día que exista una.

## Jerarquía de referencias visuales

Esta es la misma jerarquía que define `references/design-system.md` --
se repite aquí porque esta carpeta es donde vive el nivel 1 y el nivel 2
en la práctica:

1. **Plantilla institucional oficial** (de la universidad, la
   asignatura, o la organización para la que se escribe el documento).
2. **Documento humano aprobado expresamente por el usuario** como
   referencia visual para este proyecto.
3. **Convenciones académicas de la universidad/asignatura**, aunque no
   vengan como plantilla descargable.
4. **El design system provisional** de `references/design-system.md` --
   solo si nada de lo anterior existe o cubre la decisión en cuestión.

Una referencia de nivel 1 o 2 se guarda en esta carpeta (ver "Cómo
agregar una plantilla" abajo) y **reemplaza** cualquier decisión visual
del design system provisional -- tipografía, color de acento, márgenes,
todo. El design system provisional nunca tiene prioridad sobre una
plantilla o documento humano real.

## Regla

Si existe una plantilla Word humana disponible (convencionalmente
nombrada `reference.docx` dentro de esta carpeta, siguiendo la misma
convención que usa el skill oficial `docx` para plantillas de
referencia), **úsala preferentemente** en vez de partir de cero con el
`design-system.md` de este skill.

De esa plantilla se extrae:

- Estilos (Title, Heading 1/2/3, Normal, Caption, etc. -- sus fuentes,
  tamaños, colores y espaciados reales).
- Márgenes y tamaño de página.
- Tipografía (las familias que la plantilla ya usa).
- Diseño de headers/pies de página.
- Formato de captions.
- Diseño de tablas (bordes, sombreado de encabezado, tipografía interna).
- Jerarquía visual general.

## Lo que NO se hace

**No copiar el contenido** de la plantilla -- solo su sistema de diseño
(estilos, estructura de secciones, convenciones tipográficas). El
contenido de cada documento real es propio de ese documento.

## Por qué esta regla existe

El objetivo es evitar recrear desde cero, documento tras documento, un
estilo genérico que termine pareciendo "hecho por IA" simplemente porque
cada vez se inventa una dirección de diseño distinta. Si una persona ya
resolvió ese problema con una plantilla real -- probablemente alineada
con lo que espera quien evalúa el documento (un profesor, una
institución) --, partir de esa plantilla es más defendible que partir
de `design-system.md`, que es un punto de partida razonable pero
genérico, no una identidad institucional específica.

## Cómo agregar una plantilla

1. Colocar el archivo como `templates/reference.docx` (o un nombre
   descriptivo si hay más de una, p. ej.
   `templates/reference-universidad-x.docx`).
2. Documentar en este README, en una tabla o lista breve, qué plantilla
   corresponde a qué contexto (p. ej. "reference.docx -- plantilla
   institucional para informes de seminario de licenciatura").
3. Antes de generar un documento real, leer la plantilla con
   `pandoc -t markdown reference.docx` (mecanismo del skill oficial,
   ver `SKILL.md`) para inventariar sus estilos, o inspeccionar
   `word/styles.xml` directamente tras descomprimirla, antes de decidir
   los estilos del nuevo documento.
