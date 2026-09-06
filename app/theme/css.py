"""Construye la hoja de estilo de la app desde `app.theme.tokens`.

Reemplaza el bloque literal que vivía dentro de `_inject_css()` en
`app/app.py`. Las reglas son las mismas; lo que cambia es que ningún color,
radio ni área de toque está escrito acá: todos se leen de los tokens, así que
un cambio de paleta es una edición en un archivo y no una búsqueda por tres.

Los tamaños en `rem` se dejaron como estaban a propósito. Esta fase es un
traslado más la corrección del ámbar; aplicar la escala tipográfica nueva
cambiaría el render, y eso corresponde a la fase de componentes. La escala se
publica acá como variables CSS para que esa fase la consuma sin volver a
tocar este archivo.
"""

from __future__ import annotations

from app.theme import tokens as t


def _type_scale_vars() -> str:
    """Escala tipográfica como custom properties, para la fase de componentes."""
    lines = []
    for name, style in t.TYPE_SCALE.items():
        lines.append(f"            --sapi-font-{name}-size: {style.size_px}px;")
        lines.append(f"            --sapi-font-{name}-line: {style.line_px}px;")
        lines.append(f"            --sapi-font-{name}-weight: {style.weight};")
    return "\n".join(lines)


def build_stylesheet() -> str:
    """Hoja de estilo completa, envuelta en `<style>`, lista para st.markdown."""
    return f"""
        <style>
        @import url('{t.FONT_IMPORT_URL}');

        :root {{
            --sapi-surface-page: {t.SURFACE_PAGE};
            --sapi-surface-card: {t.SURFACE_CARD};
            --sapi-border-card: {t.BORDER_CARD};
            --sapi-text-primary: {t.TEXT_PRIMARY};
            --sapi-accent: {t.ACCENT};
            --sapi-radius-control: {t.RADIUS_PX["control"]}px;
            --sapi-radius-card: {t.RADIUS_PX["card"]}px;
            --sapi-radius-banner: {t.RADIUS_PX["banner"]}px;
            --sapi-touch-target: {t.TOUCH_TARGET_PX}px;
{_type_scale_vars()}
        }}

        /* ── Contenedor principal ── */
        section.main .block-container {{
            max-width: 100%;
            padding: 1.5rem 0.75rem 0 0.75rem;
            overflow-x: hidden;
        }}

        html, body, [class*="css"] {{
            font-family: {t.FONT_STACK};
        }}
        h1, h2, h3, h4 {{ font-weight: 700 !important; letter-spacing: -0.01em; }}

        /* Mapa Folium: st_folium mide el ancho del iframe por JS al montar el
           componente. Si esa medición corre antes de que el navegador aplique
           este CSS, el ancho queda fijado en px y no acompaña el reflow. Es la
           única regla que sigue peleando contra un componente, y se queda
           porque el bug que evita es real y visible en móvil. */
        iframe[title="streamlit_folium.st_folium"] {{
            width: 100% !important;
            max-width: 100% !important;
        }}

        /* La selección propia de st.dataframe se anula: el resalte de fila lo
           pinta style_display_dataframe con el color de riesgo de la celda. */
        div[data-testid="stDataFrame"] div[role="gridcell"][aria-selected="true"],
        div[data-testid="stDataFrame"] [data-selected="true"] {{
            background-color: transparent !important;
            outline: none !important;
            box-shadow: none !important;
        }}

        /* ── Pestañas Mapa / Detalle ──
           Pasaron a ser navegación principal, así que se leen como tal: área
           de toque cómoda y estado activo explícito, no el subrayado tenue
           por defecto. */
        button[data-baseweb="tab"] {{
            height: var(--sapi-touch-target);
            padding: 0 1.1rem;
            font-weight: 600;
        }}
        div[data-baseweb="tab-highlight"] {{ background-color: {t.ACCENT}; }}

        /* ── Sidebar: navy institucional ──
           secondaryBackgroundColor del theme se dejó neutro porque afecta
           también widgets fuera del sidebar; el navy va acotado acá. */
        section[data-testid="stSidebar"] {{ background: {t.SURFACE_SIDEBAR}; }}
        section[data-testid="stSidebar"] * {{ color: {t.TEXT_ON_SIDEBAR}; }}
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        section[data-testid="stSidebar"] small,
        section[data-testid="stSidebar"] .stCaption {{
            color: {t.TEXT_ON_SIDEBAR_MUTED} !important;
        }}
        section[data-testid="stSidebar"] hr {{ border-color: {t.SIDEBAR_RULE}; }}
        section[data-testid="stSidebar"] div[data-testid="stMetricValue"] {{
            color: {t.TEXT_ON_SIDEBAR} !important;
        }}
        section[data-testid="stSidebar"] div[data-testid="stMetricLabel"] {{
            color: {t.TEXT_ON_SIDEBAR_LABEL} !important;
        }}
        section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
        section[data-testid="stSidebar"] input {{
            background: {t.SIDEBAR_INPUT_FILL} !important;
            border-color: {t.SIDEBAR_INPUT_BORDER} !important;
            color: {t.TEXT_ON_SIDEBAR} !important;
        }}
        /* Los <code> inline traen fondo claro propio; con el texto forzado a
           blanco arriba quedaban blanco sobre claro. */
        section[data-testid="stSidebar"] code {{
            background: {t.SIDEBAR_CODE_FILL} !important;
            color: {t.TEXT_ON_SIDEBAR} !important;
        }}

        /* En el sidebar angosto de un teléfono el dropdown de días cubre todo
           el rango demo por sí solo; el calendario secundario sobra. */
        @media (max-width: {t.BREAKPOINT_NARROW_PX}px) {{
            section[data-testid="stSidebar"] div[data-testid="stDateInput"] {{
                display: none;
            }}
        }}

        /* ── Tarjetas del panel principal ──
           Acotadas a section.main: sobre el navy del sidebar una tarjeta
           blanca dejaría texto blanco sobre blanco. */
        section.main div[data-testid="stMetric"] {{
            background: {t.SURFACE_CARD};
            border: 1px solid {t.BORDER_CARD};
            border-radius: var(--sapi-radius-card);
            padding: 0.9rem 1rem;
        }}
        div[data-testid="stAlert"] {{
            border-radius: var(--sapi-radius-card);
            border: 1px solid {t.BORDER_CARD};
        }}
        button, div[data-baseweb="select"] > div, div[data-testid="stDateInput"] input {{
            border-radius: var(--sapi-radius-control) !important;
        }}
        </style>
        """
