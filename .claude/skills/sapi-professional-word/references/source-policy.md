# Source policy — sapi-professional-word

Reglas absolutas para cualquier cita, referencia bibliográfica o cifra
atribuida a una fuente externa en un documento producido con este skill.

## Reglas absolutas (no negociables)

- **NO inventar fuentes.** Si no se puede verificar que una fuente existe
  y dice lo que se le atribuye, no se cita.
- **NO inventar DOI.** Un DOI que no se pudo confirmar contra la fuente
  real no se incluye -- se omite el DOI o se omite la referencia entera.
- **NO inventar autores.** Nunca atribuir una obra a un autor sin
  confirmarlo contra la fuente.
- **NO inventar años.** Un año de publicación incierto no se redondea ni
  se adivina.
- **NO incluir una referencia que no haya sido verificada.** "Suena
  plausible" no es verificación. Verificación significa haber accedido a
  la fuente (o a un registro confiable de ella) y confirmado que dice lo
  que el documento le atribuye.
- **NO usar blogs SEO como fundamento científico o técnico.** Contenido
  optimizado para posicionamiento en buscadores, sin autoría verificable
  ni revisión editorial/por pares, no sostiene una afirmación técnica.

Si una afirmación necesita una fuente y no se puede verificar una fuente
real que la sostenga, la opción correcta es **debilitar la afirmación o
marcarla explícitamente como no verificada** -- nunca fabricar la fuente
para sostener la afirmación como estaba.

## Jerarquía de fuentes (de mayor a menor peso)

1. **Fuente oficial/primaria** (el dato de origen: una API institucional,
   un dataset publicado por quien lo produjo, un repositorio de código
   fuente citado directamente).
2. **Artículo revisado por pares** (journal o conferencia con proceso de
   revisión verificable).
3. **Documentación técnica oficial** (manual o documentación publicada
   por el fabricante/mantenedor de una herramienta, librería o servicio).
4. **Fuente secundaria de calidad** (un reporte técnico, una tesis, un
   medio especializado con autoría y edición identificables) -- se usa
   cuando no existe una fuente de mayor jerarquía disponible, y se
   señala como secundaria.

## Registro obligatorio por fuente

Para cada fuente usada en un documento, registrar (en el propio
documento como referencia bibliográfica, y en las notas de trabajo del
skill si el proceso de verificación no es evidente por sí mismo):

- Autor o institución.
- Título.
- Año.
- URL o DOI (el que exista realmente; nunca inventar el que falte).
- La afirmación específica del documento que esa fuente respalda (para
  poder auditar después "¿esta fuente realmente dice esto?").
- Fecha de consulta, cuando la fuente es un recurso web que puede
  cambiar (una página institucional, un dataset con actualizaciones).

## Fuentes prioritarias para S.A.P.I.

Cuando un documento de S.A.P.I. necesita citar la procedencia de un dato
o método, estas fuentes tienen prioridad por ser las que el proyecto
usa realmente (ver también `sapi-scientific-claims.md`):

- **NASA FIRMS** (detecciones satelitales de fuego) -- fuente primaria
  oficial.
- **Dirección Meteorológica de Chile (DMC)** -- fuente primaria oficial
  para telemetría meteorológica (estación 330007, Rodelillo).
- **Copernicus DEM** (modelo de elevación digital, GLO-30) -- fuente
  primaria oficial.
- **Documentación oficial del software usado** (scikit-learn, pandas,
  LibreOffice, etc.) -- para afirmaciones sobre cómo se comporta una
  herramienta.
- **Literatura científica primaria** -- cuando el documento necesita
  fundamentar un método o concepto general (p. ej. qué es un gradient
  boosting, cómo se define missingness explícito) con una fuente
  académica, no con una explicación de blog.

## Verificación práctica

Antes de escribir una cita en un documento real:

1. Localizar la fuente (acceder a la URL/DOI, o al archivo/dataset del
   repositorio).
2. Confirmar que efectivamente dice lo que se le va a atribuir -- no
   asumir por el título.
3. Registrar los campos de la sección "Registro obligatorio" de arriba.
4. Solo entonces escribir la cita en el documento.

Si en cualquier paso de este proceso no se puede completar la
verificación, la cita no se escribe.
