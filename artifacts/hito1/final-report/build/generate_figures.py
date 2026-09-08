"""Genera las dos figuras reales del informe (Figura 1: arquitectura
general; Figura 2: flujo causal en T) a partir del contenido YA
documentado en docs/arquitectura-hito1.md (secciones 2 y 7) -- no
inventa componentes ni resultados, solo visualiza en PNG lo que esos
diagramas ASCII ya describen, con estilo plano/técnico (sin
iconografía decorativa, sin degradados, sin emojis), consistente con
references/design-system.md del skill sapi-professional-word.
"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__)) + "/figures"
os.makedirs(OUT_DIR, exist_ok=True)

INK = (43, 43, 43)          # #2B2B2B
INK_SOFT = (89, 89, 89)     # #595959
LINE = (140, 140, 140)      # #8C8C8C
LINE_LIGHT = (191, 191, 191)  # #BFBFBF
ACCENT = (62, 92, 88)       # #3E5C58 -- acento discreto, no institucional
WHITE = (255, 255, 255)

def font(size, bold=False):
    names = ["arialbd.ttf", "arial.ttf"] if bold else ["arial.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            continue
    return ImageFont.load_default()

F_TITLE = font(15, bold=True)
F_BOX = font(13, bold=True)
F_SMALL = font(11)
F_TINY = font(10)


def box(draw, xy, text, sub=None, fill=WHITE, outline=INK, accent=False):
    x0, y0, x1, y1 = xy
    draw.rectangle(xy, outline=(ACCENT if accent else outline), width=2, fill=fill)
    lines = text.split("\n")
    total_h = len(lines) * 18 + (14 if sub else 0)
    ty = y0 + ((y1 - y0) - total_h) / 2
    for ln in lines:
        w = draw.textlength(ln, font=F_BOX)
        draw.text((x0 + (x1 - x0 - w) / 2, ty), ln, font=F_BOX, fill=INK)
        ty += 18
    if sub:
        w = draw.textlength(sub, font=F_TINY)
        draw.text((x0 + (x1 - x0 - w) / 2, ty + 2), sub, font=F_TINY, fill=INK_SOFT)


def arrow_down(draw, x, y0, y1):
    draw.line([(x, y0), (x, y1)], fill=LINE, width=2)
    draw.polygon([(x - 6, y1 - 10), (x + 6, y1 - 10), (x, y1)], fill=LINE)


# ---------------------------------------------------------------
# Figura 1 -- Arquitectura general
# ---------------------------------------------------------------
W, H = 1200, 1500
img = Image.new("RGB", (W, H), WHITE)
d = ImageDraw.Draw(img)
cx = W // 2
bw = 760
x0, x1 = cx - bw // 2, cx + bw // 2

y = 30
box(d, (x0, y, x1, y + 90),
    "FUENTES", "NASA FIRMS  ·  DMC 330007 Rodelillo (regional)  ·  Copernicus DEM")
y2 = y + 90
arrow_down(d, cx, y2, y2 + 40)

y = y2 + 40
box(d, (x0, y, x1, y + 90),
    "PROCESAMIENTO CAUSAL / ESPACIAL",
    "regional_meteo · episodes (2 km / 6 h) · dem_features · temporal_features (<= T)")
y2 = y + 90
arrow_down(d, cx, y2, y2 + 40)

y = y2 + 40
box(d, (x0, y, x1, y + 90),
    "DATASET TEMPORAL Y ESPACIAL",
    "(cell_id, forecast_time) -> target en (T, T+6h] | 362.883 filas elegibles")
y2 = y + 90
arrow_down(d, cx, y2, y2 + 40)

y = y2 + 40
box(d, (x0, y, x1, y + 90),
    "MODELO D", "HistGradientBoostingClassifier -- historial + meteo regional + lags + topografía",
    accent=True)
y2 = y + 90
arrow_down(d, cx, y2, y2 + 40)

y = y2 + 40
box(d, (x0, y, x1, y + 90),
    "SCORE RELATIVO POR 50 CELDAS", "score_current_grid(T)")
y2 = y + 90
arrow_down(d, cx, y2, y2 + 40)

y = y2 + 40
box(d, (x0, y, x1, y + 90),
    "RANKING / GRUPOS DE EMPATE", "rank único · display_rank + tie_group_size (method=\"min\")")
y2 = y + 90
arrow_down(d, cx, y2, y2 + 40)

y = y2 + 40
box(d, (x0, y, x1, y + 90),
    "DASHBOARD STREAMLIT", "app/components/prototype_view -- mapa + panel de detalle")

img.crop((0, 0, W, y + 90 + 30)).save(f"{OUT_DIR}/figura-1-arquitectura.png", dpi=(200, 200))

# ---------------------------------------------------------------
# Figura 2 -- Flujo causal de una predicción en T
# ---------------------------------------------------------------
W2, H2 = 1200, 1350
img2 = Image.new("RGB", (W2, H2), WHITE)
d2 = ImageDraw.Draw(img2)
x0, x1 = cx - bw // 2, cx + bw // 2

steps = [
    ("forecast_time T", None),
    ("INFORMACIÓN DISPONIBLE <= T", "regional_meteo hasta T · historial FIRMS hasta T · topografía estática"),
    ("CONSTRUCCIÓN DE FEATURES (50 CELDAS)", "misma meteo regional para las 50 celdas; historial y topografía sí varían"),
    ("MODELO D", "HistGradientBoostingClassifier · predict_proba"),
    ("SCORES RELATIVOS POR CELDA", "sin calibración de probabilidad"),
    ("RANKING + GRUPOS DE EMPATE", "rank único / display_rank (method=\"min\") / tie_group_size"),
    ("MAPA (DASHBOARD STREAMLIT)", None),
]
y = 30
bh = 130
gap = 40
for i, (title, sub) in enumerate(steps):
    accent = (i == 3)
    box(d2, (x0, y, x1, y + bh), title, sub, accent=accent)
    if i < len(steps) - 1:
        arrow_down(d2, cx, y + bh, y + bh + gap)
    y += bh + gap

img2.crop((0, 0, W2, y)).save(f"{OUT_DIR}/figura-2-flujo-causal.png", dpi=(200, 200))

print("Figuras generadas:")
print(f"{OUT_DIR}/figura-1-arquitectura.png")
print(f"{OUT_DIR}/figura-2-flujo-causal.png")
