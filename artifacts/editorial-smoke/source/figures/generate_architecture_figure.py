"""Genera la Figura 1 (arquitectura conceptual, ficticia) del smoke test
editorial, usando únicamente Pillow (ya presente en el entorno -- no se
instaló ningún paquete nuevo). Diagrama plano, técnico, monocromático con
un único acento discreto -- sin íconos, sin degradados, sin 3D.

Infraestructura de prueba únicamente (artifacts/editorial-smoke/), no
forma parte del código de la aplicación S.A.P.I.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

INK = (43, 43, 43)
ACCENT = (62, 92, 88)  # verde-azulado apagado, único acento -- no azul/morado
WHITE = (255, 255, 255)

SCALE = 3  # supersample para buena resolución, luego se reduce
W, H = 1500 * SCALE, 700 * SCALE

BOX_W, BOX_H = 300 * SCALE, 170 * SCALE
BOX_Y = 220 * SCALE
GAP = 60 * SCALE

BOXES = [
    ("Adquisición de\ndatos experimentales", False),
    ("Procesamiento y\nnormalización", False),
    ("Modelo de\ninferencia (demo)", True),
    ("Panel de\nvisualización", False),
]

FONT_PATH = r"C:\Windows\Fonts\calibri.ttf"


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size)


def _text_multiline(draw: ImageDraw.ImageDraw, xy, text: str, font, fill) -> None:
    lines = text.split("\n")
    line_h = font.size * 1.35
    total_h = line_h * len(lines)
    x, y = xy
    y0 = y - total_h / 2 + line_h / 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        draw.text((x - w / 2, y0 + i * line_h - font.size / 2), line, font=font, fill=fill)


def _arrow(draw: ImageDraw.ImageDraw, x0, y0, x1, y1, width: int) -> None:
    draw.line([(x0, y0), (x1, y1)], fill=INK, width=width)
    head = 16 * SCALE
    draw.polygon(
        [
            (x1, y1),
            (x1 - head, y1 - head / 2),
            (x1 - head, y1 + head / 2),
        ],
        fill=INK,
    )


def main() -> None:
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    label_font = _font(21 * SCALE)
    small_font = _font(17 * SCALE)

    n = len(BOXES)
    total_w = n * BOX_W + (n - 1) * GAP
    start_x = (W - total_w) // 2

    centers = []
    for i, (label, highlight) in enumerate(BOXES):
        x0 = start_x + i * (BOX_W + GAP)
        y0 = BOX_Y
        x1, y1 = x0 + BOX_W, y0 + BOX_H
        edge = ACCENT if highlight else INK
        line_w = 5 * SCALE if highlight else 3 * SCALE
        draw.rectangle([x0, y0, x1, y1], outline=edge, width=line_w, fill=WHITE)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        centers.append((cx, cy, x0, x1, y0, y1))
        _text_multiline(draw, (cx, cy), label, label_font, INK)

    # Flechas de flujo entre etapas consecutivas.
    for i in range(n - 1):
        _, _, _, x1_prev, _, _ = centers[i]
        _, _, x0_next, _, _, _ = centers[i + 1]
        y = BOX_Y + BOX_H // 2
        _arrow(draw, x1_prev + 6 * SCALE, y, x0_next - 6 * SCALE, y, 3 * SCALE)

    # Fuente de datos (ficticia) alimentando la primera etapa -- caja punteada.
    src_w, src_h = BOX_W, 120 * SCALE
    src_x0 = start_x
    src_y0 = BOX_Y + BOX_H + 130 * SCALE
    src_x1, src_y1 = src_x0 + src_w, src_y0 + src_h

    dash = 14 * SCALE
    gap_d = 8 * SCALE
    # Rectángulo punteado dibujado manualmente (Pillow no tiene dash nativo).
    x = src_x0
    while x < src_x1:
        draw.line([(x, src_y0), (min(x + dash, src_x1), src_y0)], fill=INK, width=3 * SCALE)
        draw.line([(x, src_y1), (min(x + dash, src_x1), src_y1)], fill=INK, width=3 * SCALE)
        x += dash + gap_d
    y = src_y0
    while y < src_y1:
        draw.line([(src_x0, y), (src_x0, min(y + dash, src_y1))], fill=INK, width=3 * SCALE)
        draw.line([(src_x1, y), (src_x1, min(y + dash, src_y1))], fill=INK, width=3 * SCALE)
        y += dash + gap_d

    _text_multiline(
        draw,
        ((src_x0 + src_x1) // 2, (src_y0 + src_y1) // 2),
        "Fuentes de datos\n(demo, ficticias)",
        small_font,
        INK,
    )
    _arrow(
        draw,
        (src_x0 + src_x1) // 2,
        src_y0 - 6 * SCALE,
        (src_x0 + src_x1) // 2,
        BOX_Y + BOX_H + 6 * SCALE,
        3 * SCALE,
    )

    img = img.resize((W // SCALE, H // SCALE), Image.LANCZOS)

    out_path = Path("artifacts/editorial-smoke/source/figures/architecture-figure.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, dpi=(300, 300))
    print(f"Escrito {out_path} ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
