"""Construye la hoja de estilo de la app desde `app.theme.tokens`.

Reemplaza el bloque literal que vivía dentro de `_inject_css()` en
`app/app.py`. Colores de página, radios, áreas de toque y tipografía se leen
de los tokens; el modo `claro`/`oscuro` elige qué Appearance aplicar.
"""

from __future__ import annotations

from app.theme import tokens as t


def _type_scale_vars() -> str:
    """Escala tipográfica como custom properties."""
    lines = []
    for name, style in t.TYPE_SCALE.items():
        lines.append(f"            --sapi-font-{name}-size: {style.size_px}px;")
        lines.append(f"            --sapi-font-{name}-line: {style.line_px}px;")
        lines.append(f"            --sapi-font-{name}-weight: {style.weight};")
    return "\n".join(lines)


def build_stylesheet(mode: str = t.APPEARANCE_CLARO) -> str:
    """Hoja de estilo completa, envuelta en `<style>`, lista para st.markdown."""
    a = t.appearance_tokens(mode)
    return f"""
        <style>
        @import url('{t.FONT_IMPORT_URL}');

        :root {{
            --sapi-surface-page: {a.surface_page};
            --sapi-surface-muted: {a.surface_muted};
            --sapi-surface-card: {a.surface_card};
            --sapi-border-card: {a.border_card};
            --sapi-border-subtle: {a.border_subtle};
            --sapi-text-primary: {a.text_primary};
            --sapi-accent: {a.accent};
            --sapi-radius-control: {t.RADIUS_PX["control"]}px;
            --sapi-radius-card: {t.RADIUS_PX["card"]}px;
            --sapi-radius-banner: {t.RADIUS_PX["banner"]}px;
            --sapi-touch-target: {t.TOUCH_TARGET_PX}px;
{_type_scale_vars()}
        }}

        /* Fondo de página: Streamlit fija el del config.toml al arrancar;
           acá se sobrescribe para que el toggle claro/oscuro tenga efecto. */
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        section.main,
        .main,
        .block-container {{
            background-color: var(--sapi-surface-page) !important;
            color: var(--sapi-text-primary);
        }}
        [data-testid="stHeader"] {{
            background: var(--sapi-surface-page) !important;
        }}
        /* Widgets del panel principal que Streamlit pinta con el theme light */
        section.main [data-testid="stMarkdownContainer"],
        section.main [data-testid="stText"],
        section.main [data-testid="stWidgetLabel"],
        section.main .stTabs [data-baseweb="tab"],
        section.main .stRadio label {{
            color: var(--sapi-text-primary) !important;
        }}
        section.main div[data-testid="stAlert"] {{
            background: var(--sapi-surface-card) !important;
            color: var(--sapi-text-primary) !important;
        }}
        section.main div[data-baseweb="tab-list"] {{
            background: var(--sapi-surface-muted);
            border-radius: var(--sapi-radius-control);
        }}

        /* ── Contenedor principal ──
           padding-top >= la altura del header fijo de Streamlit (~2.9rem):
           con menos, el título y los chips del header propio quedaban
           renderizados debajo de la barra "Deploy" y se veían cortados. */
        section.main .block-container {{
            max-width: 100%;
            padding: 3.25rem 0.75rem 0 0.75rem;
            overflow-x: hidden;
        }}

        html, body, [class*="css"] {{
            font-family: {t.FONT_STACK};
            font-size: var(--sapi-font-body-size);
            line-height: var(--sapi-font-body-line);
            font-weight: var(--sapi-font-body-weight);
        }}
        section.main h1,
        section.main h2,
        section.main h3,
        section.main h4,
        section.main p,
        section.main label,
        section.main span {{
            color: var(--sapi-text-primary);
        }}
        h1 {{
            font-size: var(--sapi-font-display-size) !important;
            line-height: var(--sapi-font-display-line) !important;
            font-weight: var(--sapi-font-display-weight) !important;
            letter-spacing: -0.01em;
        }}
        h2, h3 {{
            font-size: var(--sapi-font-h1-size) !important;
            line-height: var(--sapi-font-h1-line) !important;
            font-weight: var(--sapi-font-h1-weight) !important;
            letter-spacing: -0.01em;
        }}
        h4 {{
            font-size: var(--sapi-font-h2-size) !important;
            line-height: var(--sapi-font-h2-line) !important;
            font-weight: var(--sapi-font-h2-weight) !important;
            letter-spacing: -0.01em;
        }}
        section.main [data-testid="stCaptionContainer"],
        section.main small,
        section.main .stCaption {{
            font-size: var(--sapi-font-small-size);
            line-height: var(--sapi-font-small-line);
            color: var(--sapi-text-primary);
            opacity: 0.78;
        }}

        /* Mapa Folium: st_folium mide el ancho del iframe por JS al montar el
           componente. Si esa medición corre antes de que el navegador aplique
           este CSS, el ancho queda fijado en px y no acompaña el reflow. Es la
           única regla que sigue peleando contra un componente, y se queda
           porque el bug que evita es real y visible en móvil. */
        iframe[title="streamlit_folium.st_folium"] {{
            width: 100% !important;
            max-width: 100% !important;
        }}

        /* ── Botones ── Área de toque ≥44px (WCAG 2.5.5) desde --sapi-touch-target.
           El texto heredaba --sapi-text-primary por la regla `section.main
           p/span` de arriba, mientras el FONDO del botón quedaba con el gris
           tenue nativo de Streamlit (pensado para su propio tema claro, no
           para las superficies oscuras de esta app): en oscuro, texto claro
           sobre un botón casi blanco era invisible; en claro, el texto
           "secondary" nativo de Streamlit es un gris apagado que igual
           costaba leer. Se fija el mismo par fondo/texto que ya usa cada
           tarjeta de la app — contraste verificado, consistente con el
           resto — en vez de heredar el tema propio del botón. */
        section.main div[data-testid="stButton"] > button,
        section.main div[data-testid="stDownloadButton"] > button {{
            min-height: var(--sapi-touch-target);
            padding: 0 1.1rem;
            font-weight: 600;
            background: var(--sapi-surface-card);
            border: 1px solid var(--sapi-border-card);
            color: var(--sapi-text-primary) !important;
        }}
        section.main div[data-testid="stButton"] > button p,
        section.main div[data-testid="stButton"] > button span,
        section.main div[data-testid="stButton"] > button div,
        section.main div[data-testid="stDownloadButton"] > button p,
        section.main div[data-testid="stDownloadButton"] > button span,
        section.main div[data-testid="stDownloadButton"] > button div {{
            color: var(--sapi-text-primary) !important;
        }}
        section.main div[data-testid="stButton"] > button:hover,
        section.main div[data-testid="stDownloadButton"] > button:hover {{
            border-color: var(--sapi-accent);
            color: var(--sapi-accent) !important;
        }}
        section.main div[data-testid="stButton"] > button:hover p,
        section.main div[data-testid="stButton"] > button:hover span,
        section.main div[data-testid="stDownloadButton"] > button:hover p,
        section.main div[data-testid="stDownloadButton"] > button:hover span {{
            color: var(--sapi-accent) !important;
        }}
        /* Botón "primary" (el modo ☀️/🌙 activo del interruptor de apariencia):
           fondo de acento sólido, texto blanco — Streamlit ya hace exactamente
           esto nativamente, pero el bloque de arriba lo pisaba con el fondo
           de tarjeta. Se reafirma acá, después, para que gane. */
        section.main div[data-testid="stButton"] > button[kind="primary"] {{
            background: var(--sapi-accent);
            border-color: var(--sapi-accent);
            color: {t.TEXT_ON_SIDEBAR} !important;
        }}
        section.main div[data-testid="stButton"] > button[kind="primary"] p,
        section.main div[data-testid="stButton"] > button[kind="primary"] span,
        section.main div[data-testid="stButton"] > button[kind="primary"] div {{
            color: {t.TEXT_ON_SIDEBAR} !important;
        }}

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
            background: var(--sapi-surface-card);
            border: 1px solid var(--sapi-border-card);
            border-radius: var(--sapi-radius-card);
            padding: 0.9rem 1rem;
            color: var(--sapi-text-primary);
        }}
        section.main div[data-testid="stMetric"] label,
        section.main div[data-testid="stMetric"] [data-testid="stMetricLabel"],
        section.main div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
            color: var(--sapi-text-primary) !important;
        }}
        div[data-testid="stAlert"] {{
            border-radius: var(--sapi-radius-card);
            border: 1px solid var(--sapi-border-card);
        }}
        section.main div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--sapi-surface-card);
            border-color: var(--sapi-border-card) !important;
        }}
        button, div[data-baseweb="select"] > div, div[data-testid="stDateInput"] input {{
            border-radius: var(--sapi-radius-control) !important;
        }}

        /* ── Ops-center: hero, chips, var-cards, detalle ── */
        .sapi-risk-hero {{
            display: grid;
            grid-template-columns: auto 1fr auto;
            gap: {t.SPACE_PX["md"]}px {t.SPACE_PX["lg"]}px;
            align-items: center;
            border-radius: var(--sapi-radius-banner);
            padding: {t.SPACE_PX["lg"]}px {t.SPACE_PX["xl"]}px;
            margin: 0 0 {t.SPACE_PX["md"]}px 0;
            font-family: {t.FONT_STACK};
        }}
        .sapi-risk-hero__icon {{
            width: 48px; height: 48px;
            display: grid; place-items: center;
            border-radius: var(--sapi-radius-card);
            background: rgba(0,0,0,0.18);
        }}
        .sapi-risk-hero__icon svg {{ width: 28px; height: 28px; }}
        .sapi-risk-hero__kicker {{
            font-size: var(--sapi-font-micro-size);
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            opacity: 0.9;
        }}
        .sapi-risk-hero__title {{
            font-size: var(--sapi-font-h1-size);
            line-height: var(--sapi-font-h1-line);
            font-weight: 800;
            letter-spacing: -0.02em;
            margin-top: 2px;
        }}
        .sapi-risk-hero__meta {{
            font-size: var(--sapi-font-small-size);
            font-weight: 500;
            margin-top: 4px;
            opacity: 0.92;
        }}
        .sapi-risk-hero__badge {{
            border: 1px solid rgba(255,255,255,0.35);
            border-radius: var(--sapi-radius-control);
            padding: {t.SPACE_PX["sm"]}px {t.SPACE_PX["md"]}px;
            font-size: var(--sapi-font-micro-size);
            font-weight: 700;
            text-align: center;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}
        .sapi-risk-hero__badge small {{
            display: block;
            font-weight: 500;
            opacity: 0.85;
            font-size: 10px;
            margin-top: 2px;
        }}
        @media (max-width: {t.BREAKPOINT_NARROW_PX}px) {{
            .sapi-risk-hero {{ grid-template-columns: auto 1fr; }}
            .sapi-risk-hero__badge {{ grid-column: 1 / -1; }}
        }}

        .sapi-risk-chip {{
            display: flex;
            align-items: flex-start;
            gap: {t.SPACE_PX["sm"]}px;
            background: var(--sapi-surface-card);
            border: 1px solid var(--sapi-border-card);
            border-radius: var(--sapi-radius-card);
            padding: {t.SPACE_PX["md"]}px;
            min-height: var(--sapi-touch-target);
        }}
        .sapi-risk-chip.is-active {{
            box-shadow: inset 0 0 0 2px var(--chip-stroke, var(--sapi-accent));
        }}
        .sapi-risk-chip__mark {{
            width: 36px; height: 36px; flex: none;
            border-radius: var(--sapi-radius-control);
            background: var(--chip-surface, #95a5a6);
            display: grid; place-items: center;
        }}
        .sapi-risk-chip__mark svg {{ width: 20px; height: 20px; }}
        .sapi-risk-chip__label {{
            font-size: var(--sapi-font-small-size);
            font-weight: 700;
            color: var(--sapi-text-primary);
        }}
        .sapi-risk-chip__desc {{
            font-size: var(--sapi-font-micro-size);
            color: var(--sapi-text-primary);
            opacity: 0.72;
            margin-top: 2px;
        }}

        .sapi-var-card {{
            background: var(--sapi-surface-card);
            border: 1px solid var(--sapi-border-card);
            border-radius: var(--sapi-radius-card);
            padding: {t.SPACE_PX["md"]}px {t.SPACE_PX["lg"]}px;
            min-height: 96px;
            display: flex;
            flex-direction: column;
            gap: {t.SPACE_PX["xs"]}px;
            font-family: {t.FONT_STACK};
        }}
        .sapi-var-card__top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .sapi-var-card__name {{
            font-size: var(--sapi-font-micro-size);
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: var(--sapi-text-primary);
            opacity: 0.75;
        }}
        .sapi-var-card__icon {{
            width: 28px; height: 28px;
            color: var(--sapi-text-primary);
            opacity: 0.55;
            display: grid; place-items: center;
        }}
        .sapi-var-card__icon svg {{ width: 16px; height: 16px; }}
        .sapi-var-card__value {{
            font-size: 28px;
            line-height: 1.1;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: var(--sapi-text-primary);
        }}
        .sapi-var-card__unit {{
            font-size: var(--sapi-font-small-size);
            font-weight: 600;
            margin-left: 4px;
            opacity: 0.7;
            color: var(--sapi-text-primary);
        }}
        .sapi-var-card__state {{
            display: inline-block;
            margin-top: auto;
            font-size: var(--sapi-font-micro-size);
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 999px;
            width: fit-content;
        }}
        .sapi-var-card__state.state-alto {{
            background: {t.RISK["alto"].surface}22;
            color: {t.RISK["alto"].text};
        }}
        .sapi-var-card__state.state-normal {{
            background: var(--sapi-surface-muted);
            color: var(--sapi-text-primary);
            opacity: 0.9;
        }}

        .sapi-detail {{
            background: var(--sapi-surface-card);
            border: 1px solid var(--sapi-border-card);
            border-radius: var(--sapi-radius-card);
            overflow: hidden;
            margin-bottom: {t.SPACE_PX["md"]}px;
            font-family: {t.FONT_STACK};
        }}
        .sapi-detail__head {{
            display: flex;
            align-items: center;
            gap: {t.SPACE_PX["md"]}px;
            padding: {t.SPACE_PX["lg"]}px;
            border-bottom: 1px solid var(--sapi-border-card);
        }}
        .sapi-detail__id {{
            font-size: var(--sapi-font-h2-size);
            font-weight: 800;
            letter-spacing: -0.02em;
            color: var(--sapi-text-primary);
        }}
        .sapi-detail__zone {{
            font-size: var(--sapi-font-small-size);
            color: var(--sapi-text-primary);
            opacity: 0.72;
        }}
        .sapi-detail__prob {{
            margin-left: auto;
            text-align: right;
            font-size: 22px;
            font-weight: 800;
            color: var(--sapi-text-primary);
        }}
        .sapi-detail__prob small {{
            display: block;
            font-size: var(--sapi-font-micro-size);
            font-weight: 600;
            opacity: 0.65;
        }}
        .sapi-detail__block {{
            padding: {t.SPACE_PX["lg"]}px;
            border-bottom: 1px solid var(--sapi-border-card);
        }}
        .sapi-detail__block:last-child {{ border-bottom: none; }}
        .sapi-detail__block-title {{
            font-size: var(--sapi-font-micro-size);
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: {t.SPACE_PX["sm"]}px;
            color: var(--sapi-text-primary);
            opacity: 0.7;
        }}
        .sapi-rule-row {{
            display: flex;
            gap: {t.SPACE_PX["md"]}px;
            align-items: flex-start;
            padding: {t.SPACE_PX["md"]}px;
            border-radius: var(--sapi-radius-control);
            border: 1px solid {t.RISK["alto"].stroke};
            background: {t.RISK["alto"].surface}18;
        }}
        .sapi-rule-row.is-off {{
            background: var(--sapi-surface-muted);
            border-color: var(--sapi-border-card);
        }}
        .sapi-rule-dot {{
            width: 10px; height: 10px; border-radius: 50%;
            margin-top: 5px; flex: none;
            background: {t.RISK["alto"].surface};
        }}
        .sapi-rule-row.is-off .sapi-rule-dot {{ background: {t.RISK_UNKNOWN.surface}; }}
        .sapi-rule-title {{
            font-weight: 700;
            font-size: var(--sapi-font-small-size);
            color: var(--sapi-text-primary);
        }}
        .sapi-rule-sub {{
            font-size: var(--sapi-font-micro-size);
            opacity: 0.75;
            color: var(--sapi-text-primary);
            margin-top: 2px;
        }}
        .sapi-meta-grid {{
            display: grid;
            grid-template-columns: auto 1fr;
            gap: {t.SPACE_PX["xs"]}px {t.SPACE_PX["lg"]}px;
            font-size: var(--sapi-font-small-size);
            color: var(--sapi-text-primary);
            margin: 0;
        }}
        .sapi-meta-grid dt {{ opacity: 0.65; font-weight: 600; }}
        .sapi-meta-grid dd {{ margin: 0; }}

        .sapi-alert-row {{
            display: flex;
            align-items: center;
            gap: {t.SPACE_PX["md"]}px;
            padding: {t.SPACE_PX["md"]}px;
            background: var(--sapi-surface-card);
            border: 1px solid var(--sapi-border-card);
            border-radius: var(--sapi-radius-card);
            margin-bottom: {t.SPACE_PX["sm"]}px;
        }}
        .sapi-section {{
            margin: {t.SPACE_PX["xl"]}px 0 {t.SPACE_PX["md"]}px 0;
        }}
        .sapi-title-compact h1 {{
            font-size: var(--sapi-font-h1-size) !important;
            line-height: var(--sapi-font-h1-line) !important;
            margin-bottom: 0.15rem !important;
        }}

        /* ── Claude Design ops layout ── */
        .sapi-ops-header {{
            display: flex; flex-wrap: wrap; justify-content: space-between;
            gap: {t.SPACE_PX["md"]}px; align-items: flex-start;
            margin: 0 0 {t.SPACE_PX["md"]}px 0; font-family: {t.FONT_STACK};
        }}
        .sapi-ops-brand {{ display: flex; gap: {t.SPACE_PX["md"]}px; align-items: center; }}
        .sapi-ops-mark {{
            width: 44px; height: 44px; border-radius: var(--sapi-radius-card);
            background: var(--sapi-accent); color: #fff; font-weight: 800;
            display: grid; place-items: center; font-size: 20px;
        }}
        .sapi-ops-title {{
            font-size: var(--sapi-font-h1-size); font-weight: 800;
            letter-spacing: -0.02em; color: var(--sapi-text-primary);
        }}
        .sapi-ops-sub {{
            font-size: var(--sapi-font-small-size); color: var(--sapi-text-primary);
            opacity: 0.75; margin-top: 2px;
        }}
        .sapi-ops-chips {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }}
        .sapi-chip {{
            display: inline-flex; align-items: center; gap: 6px;
            padding: 6px 10px; border-radius: 999px; font-size: 11px; font-weight: 700;
            letter-spacing: 0.04em; text-transform: uppercase;
            background: var(--sapi-surface-card); border: 1px solid var(--sapi-border-card);
            color: var(--sapi-text-primary);
        }}
        .sapi-chip--live {{ border-color: {t.RISK["bajo"].stroke}; color: {t.RISK["bajo"].text}; }}
        .sapi-chip--muted {{ opacity: 0.7; }}
        .sapi-chip--time {{ font-variant-numeric: tabular-nums; }}

        section.main div[data-testid="stAlert"] {{
            background: var(--sapi-surface-muted) !important;
            border-left: 4px solid var(--sapi-accent) !important;
            color: var(--sapi-text-primary) !important;
        }}
        .sapi-corridor-verified {{
            text-align: right; font-size: 11px; font-weight: 600; letter-spacing: 0.04em;
            text-transform: uppercase; color: var(--sapi-text-primary); opacity: 0.65;
            margin: -0.35rem 0 {t.SPACE_PX["md"]}px 0;
        }}

        .sapi-mayor {{
            display: grid; grid-template-columns: 1.25fr 1fr; gap: {t.SPACE_PX["lg"]}px;
            background: var(--mayor-bg); color: var(--mayor-fg);
            border-radius: var(--sapi-radius-banner);
            border: 1px solid var(--mayor-stroke);
            padding: {t.SPACE_PX["xl"]}px; margin: 0 0 {t.SPACE_PX["lg"]}px 0;
            font-family: {t.FONT_STACK};
        }}
        .sapi-mayor__kicker {{
            font-size: 11px; font-weight: 800; letter-spacing: 0.12em;
            text-transform: uppercase; opacity: 0.9; margin-bottom: 2px;
        }}
        .sapi-mayor__level {{
            display: flex; align-items: center; gap: {t.SPACE_PX["md"]}px;
            margin: 4px 0 8px 0;
        }}
        .sapi-mayor__shape {{
            width: 52px; height: 52px; display: grid; place-items: center;
            background: rgba(0,0,0,0.18); border-radius: var(--sapi-radius-card);
            flex: none;
        }}
        .sapi-mayor__shape svg {{ width: 32px; height: 32px; }}
        .sapi-mayor__word {{
            font-size: 52px; line-height: 1; font-weight: 800; letter-spacing: -0.02em;
        }}
        .sapi-mayor__sub {{
            margin-top: 4px; font-size: 13px; font-weight: 700;
            letter-spacing: 0.04em; text-transform: uppercase; opacity: 0.92;
        }}
        .sapi-mayor__id {{
            margin-top: 4px; font-size: 16px; font-weight: 800;
        }}
        .sapi-mayor__desc {{
            margin-top: 6px; font-size: 13px; line-height: 1.4; opacity: 0.9; max-width: 38rem;
        }}
        .sapi-mayor__meta {{
            display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 12px;
        }}
        .sapi-mini-chip {{
            display: inline-block; padding: 4px 10px; border-radius: 999px;
            background: rgba(0,0,0,0.18); border: 1px solid rgba(255,255,255,0.3);
            font-size: 11px; font-weight: 700; letter-spacing: 0.02em;
        }}
        .sapi-mayor__right {{
            background: rgba(0,0,0,0.18); border-radius: var(--sapi-radius-card);
            border: 1px solid rgba(255,255,255,0.15);
            padding: {t.SPACE_PX["lg"]}px;
            display: flex; flex-direction: column; justify-content: space-between;
        }}
        .sapi-mayor__right-head {{
            display: flex; justify-content: space-between; align-items: baseline;
            margin-bottom: 10px; padding-bottom: 6px;
            border-bottom: 1px solid rgba(255,255,255,0.15);
        }}
        .sapi-mayor__right-title {{
            font-size: 12px; font-weight: 800; letter-spacing: 0.08em;
            text-transform: uppercase;
        }}
        .sapi-mayor__right-sub {{
            font-size: 11px; font-weight: 600; opacity: 0.8;
        }}
        .sapi-mayor__rule-table {{
            display: flex; flex-direction: column; gap: 8px;
        }}
        .sapi-mayor__rule-row {{
            display: grid; grid-template-columns: auto 1fr auto; align-items: center;
            gap: 10px; padding: 8px 10px; border-radius: 4px;
            background: rgba(0,0,0,0.14); font-size: 13px;
        }}
        .sapi-mayor__rule-row.is-on {{
            background: rgba(255,255,255,0.15);
        }}
        .sapi-mayor__rule-check {{
            width: 20px; height: 20px; border-radius: 4px;
            display: grid; place-items: center; font-size: 12px; font-weight: 800;
            background: rgba(255,255,255,0.22); flex: none;
        }}
        .sapi-mayor__rule-info {{
            display: flex; flex-direction: column; gap: 1px;
        }}
        .sapi-mayor__rule-name {{
            font-weight: 700; font-size: 13px; line-height: 1.2;
        }}
        .sapi-mayor__rule-thresh {{
            font-size: 11px; opacity: 0.8; line-height: 1.2;
        }}
        .sapi-mayor__rule-val {{
            font-weight: 800; font-size: 14px; font-variant-numeric: tabular-nums;
        }}
        .sapi-mayor__rule-footnote {{
            font-size: 11px; line-height: 1.35; opacity: 0.82;
            margin-top: 10px; padding-top: 8px;
            border-top: 1px solid rgba(255,255,255,0.12);
        }}
        @media (max-width: 900px) {{
            .sapi-mayor {{ grid-template-columns: 1fr; }}
            .sapi-mayor__word {{ font-size: 38px; }}
        }}

        .sapi-vstrip {{
            display: grid; grid-template-columns: repeat(4, 1fr);
            gap: {t.SPACE_PX["md"]}px; margin: 0 0 {t.SPACE_PX["lg"]}px 0;
        }}
        .sapi-vcard {{
            background: var(--sapi-surface-card); border: 1px solid var(--sapi-border-card);
            border-radius: var(--sapi-radius-card); padding: {t.SPACE_PX["sm"]}px {t.SPACE_PX["md"]}px;
            font-family: {t.FONT_STACK}; color: var(--sapi-text-primary);
        }}
        .sapi-vcard__sig {{
            font-size: 11px; font-weight: 800; letter-spacing: 0.08em; opacity: 0.55;
        }}
        .sapi-vcard__name {{
            font-size: 12px; font-weight: 600; margin-top: 1px; opacity: 0.8;
        }}
        .sapi-vcard__value {{
            font-size: 26px; font-weight: 800; letter-spacing: -0.02em; margin-top: 4px;
            line-height: 1;
        }}
        .sapi-vcard__unit {{ font-size: 12px; font-weight: 600; opacity: 0.65; margin-top: 2px; }}
        .sapi-vcard__meta {{
            display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 6px;
        }}
        .sapi-vcard__badge {{
            display: inline-block; padding: 2px 8px; border-radius: 999px;
            font-size: 11px; font-weight: 700;
        }}
        .sapi-vcard__badge.is-alto, .sapi-vcard__badge.is-critico {{
            background: {t.RISK["alto"].surface}22; color: {t.RISK["alto"].text};
        }}
        .sapi-vcard__badge.is-normal {{
            background: var(--sapi-surface-muted); color: var(--sapi-text-primary);
        }}
        .sapi-vcard__badge.is-na {{
            background: {t.RISK_UNKNOWN.surface}33; color: var(--sapi-text-primary);
        }}
        .sapi-var-trend {{ font-size: 12px; font-weight: 700; }}
        .sapi-var-trend.is-na {{ font-weight: 500; opacity: 0.65; }}
        .sapi-vcard__since {{
            font-size: 11px; font-weight: 500; opacity: 0.65; margin-top: 3px;
        }}
        @media (max-width: 900px) {{
            .sapi-vstrip {{ grid-template-columns: 1fr 1fr; }}
        }}
        @media (max-width: {t.BREAKPOINT_NARROW_PX}px) {{
            .sapi-vstrip {{ grid-template-columns: 1fr; }}
        }}

        .sapi-map-frame {{
            background: var(--sapi-surface-card); border: 1px solid var(--sapi-border-card);
            border-radius: var(--sapi-radius-card); padding: {t.SPACE_PX["md"]}px;
            margin-bottom: {t.SPACE_PX["md"]}px;
        }}
        .sapi-map-header {{
            display: flex; justify-content: space-between; align-items: baseline;
            margin-bottom: 8px; font-family: {t.FONT_STACK};
        }}
        .sapi-map-title {{
            font-size: 13px; font-weight: 700; color: var(--sapi-text-primary);
        }}
        .sapi-map-crs {{
            font-size: 11px; font-weight: 600; opacity: 0.65; color: var(--sapi-text-primary);
        }}
        .sapi-sum-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }}
        .sapi-sum-chip {{
            display: inline-flex; align-items: center; gap: 6px;
            padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 700;
            background: var(--sapi-surface-card); border: 1px solid var(--c);
            color: var(--sapi-text-primary);
        }}

        .sapi-panel {{
            background: var(--sapi-surface-card); border: 1px solid var(--sapi-border-card);
            border-radius: var(--sapi-radius-card); overflow: hidden;
            font-family: {t.FONT_STACK}; color: var(--sapi-text-primary);
        }}
        .sapi-panel__head {{
            display: flex; justify-content: space-between; align-items: center;
            gap: 12px; padding: 14px 16px; border-bottom: 3px solid;
        }}
        .sapi-panel__id {{ font-size: 20px; font-weight: 800; }}
        .sapi-panel__zone {{ font-size: 12px; opacity: 0.7; }}
        .sapi-panel__coords {{ font-size: 11px; opacity: 0.6; font-variant-numeric: tabular-nums; margin-top: 2px; }}
        .sapi-panel__badge {{
            padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 800;
            text-transform: uppercase;
        }}
        .sapi-panel__block {{
            padding: 14px 16px; border-bottom: 1px solid var(--sapi-border-card);
        }}
        .sapi-panel__block:last-child {{ border-bottom: none; }}
        .sapi-panel__h {{
            font-size: 11px; font-weight: 800; letter-spacing: 0.08em;
            text-transform: uppercase; opacity: 0.65; margin-bottom: 8px;
        }}
        .sapi-kv {{ list-style: none; padding: 0; margin: 0; }}
        .sapi-kv li {{
            display: flex; justify-content: space-between; gap: 12px;
            padding: 4px 0; font-size: 13px;
        }}
        .sapi-kv span {{ opacity: 0.7; }}
        .sapi-empty {{ font-size: 13px; opacity: 0.75; margin: 0; }}

        .sapi-detail-rule-line {{
            display: flex; align-items: center; justify-content: space-between;
            gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--sapi-border-card);
            font-size: 13px;
        }}
        .sapi-detail-rule-mark {{
            width: 18px; height: 18px; border-radius: 3px;
            display: grid; place-items: center; font-size: 11px; font-weight: bold;
            background: var(--sapi-surface-muted); color: var(--sapi-text-primary);
        }}
        .sapi-detail-rule-line.is-on .sapi-detail-rule-mark {{
            background: {t.RISK["alto"].surface}33; color: {t.RISK["alto"].text};
        }}
        .sapi-detail-rule-cond {{ flex: 1; margin-left: 6px; font-size: 12px; }}
        .sapi-detail-rule-val {{ font-size: 13px; font-variant-numeric: tabular-nums; }}

        .sapi-rule-score-box {{
            display: grid; grid-template-columns: auto 1fr; gap: 12px;
            align-items: center; margin-top: 10px; padding: 10px 12px;
            border-radius: var(--sapi-radius-control);
            background: var(--sapi-surface-muted); border: 1px solid var(--sapi-border-card);
        }}
        .sapi-rule-score-badge {{
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            min-width: 44px; padding: 4px 6px; border-radius: 4px;
            background: {t.RISK["alto"].surface}; color: white;
            line-height: 1; font-weight: 800;
        }}
        .sapi-rule-score-num {{ font-size: 18px; }}
        .sapi-rule-score-de {{ font-size: 9px; text-transform: uppercase; opacity: 0.85; margin: 1px 0; }}
        .sapi-rule-score-total {{ font-size: 12px; }}
        .sapi-rule-score-desc {{ font-size: 12px; line-height: 1.35; color: var(--sapi-text-primary); }}

        /* ── 4 Estados al pie ── */
        .sapi-four-states {{
            display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
            margin: 16px 0 20px 0; font-family: {t.FONT_STACK};
        }}
        .sapi-state-card {{
            background: var(--sapi-surface-card); border: 1px solid var(--sapi-border-card);
            border-radius: var(--sapi-radius-card); padding: 12px 14px;
        }}
        .sapi-state-card__head {{
            display: flex; align-items: center; gap: 8px; margin-bottom: 6px;
        }}
        .sapi-state-card__mark {{
            width: 24px; height: 24px; border-radius: 4px;
            display: grid; place-items: center; flex: none;
        }}
        .sapi-state-card__title {{
            font-size: 12px; font-weight: 800; letter-spacing: 0.05em;
            color: var(--sapi-text-primary);
        }}
        .sapi-state-card__desc {{
            font-size: 12px; line-height: 1.35; color: var(--sapi-text-primary);
            opacity: 0.8; margin: 0;
        }}
        @media (max-width: 900px) {{
            .sapi-four-states {{ grid-template-columns: 1fr 1fr; }}
        }}
        @media (max-width: {t.BREAKPOINT_NARROW_PX}px) {{
            .sapi-four-states {{ grid-template-columns: 1fr; }}
        }}

        /* ── Auditoría y transparencia operativa ── */
        .sapi-audit-box {{
            display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;
            padding: 16px; background: var(--sapi-surface-muted);
            border: 1px solid var(--sapi-border-card);
            border-radius: var(--sapi-radius-card); margin: 16px 0;
            font-family: {t.FONT_STACK};
        }}
        .sapi-audit-col {{
            font-size: 12px; line-height: 1.4; color: var(--sapi-text-primary);
        }}
        .sapi-audit-col p {{ margin: 4px 0 0 0; opacity: 0.82; }}
        .sapi-audit-title {{
            font-size: 11px; font-weight: 800; letter-spacing: 0.06em;
            text-transform: uppercase; color: var(--sapi-accent);
        }}
        .sapi-audit-col--alert .sapi-audit-title {{
            color: {t.RISK["alto"].text};
        }}
        @media (max-width: 900px) {{
            .sapi-audit-box {{ grid-template-columns: 1fr; }}
        }}
        </style>
        """
