# QA visual — smoke test editorial DOCX (ficticio)

**Documento:** `editorial-smoke.docx` / `.pdf` (6 páginas, A4)
**No forma parte del Hito ni de la documentación oficial de S.A.P.I.**

## Iteraciones

1. **v1 (build inicial):** 6 páginas. Encontrado: página de TOC casi vacía
   (el campo de Word no se puebla en conversión headless de LibreOffice +
   salto de página manual antes de Introducción) y Tabla 1 aislada en una
   página propia con exceso de blanco (salto manual antes de Metodología).
2. **v2 (quitar los 3 saltos manuales):** 4 páginas — por debajo del rango
   5–7 pedido. El contenido, sin los saltos, quedó demasiado denso
   (Resultados + Conclusiones + Referencias comprimidos en una sola página).
3. **v3 (final):** se agregó contenido genuino (un párrafo en Introducción,
   una subsección "4.1 Discusión de los resultados" con dos párrafos, un
   párrafo de cierre en Conclusiones) y se reintrodujo **un único** salto
   de página manual, antes de "Referencias" — convención editorial estándar
   (la bibliografía casi siempre abre en página propia), no relleno
   artificial. Resultado: 6 páginas, densidad pareja, sin tablas aisladas.

Se usaron las 3 iteraciones permitidas como máximo.

## Nota obligatoria sobre la Tabla de contenidos

La TOC se construyó con `TableOfContents` (campo real de Word,
`headingStyleRange: "1-2"`) y `features.updateFields = true` en la
configuración del documento, para que Word recalcule el campo al abrir.
**LibreOffice, al convertir a PDF en modo headless, no ejecuta esa
actualización de campos** — por eso en el render la sección "Tabla de
contenidos" aparece sin entradas. Esto es una limitación conocida del
mecanismo (campo de Word, no texto generado), documentada aquí tal como
exige el punto 12 del encargo. Al abrir `editorial-smoke.docx` en
Microsoft Word real, la tabla de contenidos se puebla automáticamente
(o con F9 si Word pregunta antes de actualizar).

## Revisión página por página (v3, final)

**Página 1 (portada) — PASS**
Título, subtítulo, línea divisoria fina, bloque de metadatos (institución/
asignatura/autor/fecha) y nota de descargo. Sin número de página visible.
Buen uso de espacio en blanco, sin caja de color. No parece plantilla de IA.

**Página 2 (TOC + Introducción + inicio de Arquitectura) — PASS**
Header y footer con número "1" visibles. TOC sin entradas (ver nota
arriba). Cuatro párrafos de Introducción con interlineado y justificación
consistentes. Arranca "2. Arquitectura" con su primer párrafo; queda
~25 % de blanco al final de la página, dentro de lo normal (no es un salto
forzado, es el punto natural donde termina el texto antes de la figura).

**Página 3 (figura + Tabla 1 + inicio de Metodología) — PASS**
Figura 1 y su caption permanecen juntas (keepNext respetado). Diagrama
legible, plano, monocromático con un único acento; sin íconos ni
degradados. Tabla 1 completa, sin fila cortada entre páginas, encabezado
distinguible (fondo gris claro, negrita). "3. Metodología" y "3.1" arrancan
al final de la página sin quedar huérfanos (el heading fue movido junto
con su primer párrafo).

**Página 4 (Metodología 3.2/3.2.1 + Resultados + Tabla 2 + Discusión) — PASS**
Tres niveles de encabezado (H1/H2/H3) claramente distinguibles entre sí sin
resultar exagerados. Tabla 2 completa, alineación numérica correcta,
encabezado distinguible. El párrafo posterior a la tabla no quedó pegado
a la última fila. "4.1 Discusión" arranca con espaciado consistente,
sin overflow ni recorte de texto.

**Página 5 (Conclusiones) — PASS**
Tres párrafos de cierre. Queda blanco considerable al final (~55 %), pero
es el cierre natural de la sección antes de que "Referencias" abra en
página propia (ver iteración 3) — no es un salto vacío accidental.

**Página 6 (Referencias) — PASS**
Tres entradas `[DEMO]` con sangría francesa correcta y estilo bibliográfico
consistente (autor, año en paréntesis, título en cursiva, editorial/fuente).
Ninguna referencia se presenta como real.

## Criterio de "profesional" (punto 20 del encargo)

¿Este documento parece algo que un estudiante universitario competente
podría haber maquetado cuidadosamente en Word? — **Sí.** Tipografía de dos
familias (Calibri Light para títulos, Constantia para cuerpo), portada
sobria sin cajas de color, jerarquía de encabezados clara sin ser
excesiva, tablas con bordes finos y encabezado distinguible, figura plana
sin decoración, referencias con sangría francesa real. No hay emojis,
degradados, tarjetas ni exceso de negrita.

## Elementos verificados explícitamente

- Estilos de párrafo reales (no formato manual repetido): Title, Subtitle,
  Heading 1/2/3, Body Text (Normal), Caption, Table Text, Reference.
- Dos secciones de Word: portada sin header/footer/numeración; cuerpo con
  header discreto ("Informe técnico experimental" + regla fina) y footer
  con número de página (`PageNumber.CURRENT`, numeración reiniciada en 1).
- Control de paginación: `keepNext` en todos los encabezados y en el
  párrafo de la figura; `keepLines` en captions; `cantSplit` en filas de
  tabla; `widowControl` activado a nivel de documento.
- Referencias cruzadas naturales en el cuerpo ("Como se observa en la
  Figura 1…", "La Tabla 2 resume…").
