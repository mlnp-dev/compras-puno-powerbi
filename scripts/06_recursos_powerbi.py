"""Dibuja las imágenes del diseño del reporte de Power BI (carpeta powerbi/recursos).

Estilo tomado de dos plantillas de referencia: menú lateral azul marino, área de trabajo clara,
tarjetas de cifras con ondas azules o verde azulado y una banda oscura arriba.

- fondo.png        : fondo de página (menú lateral marino + área gris azulada muy clara).
- banda.png        : banda oscura del encabezado de cada página (degradado marino con arcos tenues).
- ola_<color>.png  : fondo de las tarjetas de cifras (degradado con ondas suaves).
- logo_puno.png    : silueta de la región Puno (límites INEI simplificados) en verde azulado.
- fondo_tooltip.png: fondo blanco de la ventana emergente.

Uso:  python scripts/06_recursos_powerbi.py
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "powerbi", "recursos")
os.makedirs(OUT, exist_ok=True)
ESC = 2  # se dibuja al doble para que se vea nítido
MARINO, MARINO2 = "#14213D", "#1C2E52"
CLARO = "#EEF2F8"
MENU = 200  # ancho del menú lateral (px del lienzo de 1280)


def rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


def degradado(w, h, c1, c2, diagonal=True):
    yy, xx = np.mgrid[0:h, 0:w]
    t = (xx / w * 0.6 + yy / h * 0.4) if diagonal else yy / h
    t = t[..., None]
    return rgb(c1) * (1 - t) + rgb(c2) * t


def a_imagen(arr):
    return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))


# ---------------------------------------------------------------- fondo de página
# Arriba va la franja blanca del membrete institucional (MEMB px); debajo, el diseño de siempre.
MEMB = 64
W, H = 1280 * ESC, (720 + MEMB) * ESC
M = MEMB * ESC
fondo = Image.new("RGB", (W, H), CLARO)
fondo.paste(Image.new("RGB", (W, M), "#FFFFFF"), (0, 0))
menu = a_imagen(degradado(MENU * ESC, H - M, "#13203B", "#0E1830", diagonal=False))
fondo.paste(menu, (0, M))
linea = a_imagen(degradado(W, 3 * ESC, "#2BB39B", "#2F6FED"))  # filete teal → azul bajo el membrete
fondo.paste(linea, (0, M - 3 * ESC))
d = ImageDraw.Draw(fondo, "RGBA")
d.line([(MENU * ESC - 1, M), (MENU * ESC - 1, H)], fill=(255, 255, 255, 18), width=2)
fondo.save(os.path.join(OUT, "fondo.png"), optimize=True)

# ---------------------------------------------------------------- banda del encabezado
BW, BH = 1048 * ESC, 116 * ESC
banda = a_imagen(degradado(BW, BH, "#14213D", "#1E3A66")).convert("RGBA")
capa = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
dc = ImageDraw.Draw(capa)
for i, r in enumerate(range(60, 520, 46)):  # arcos concéntricos tenues a la derecha
    r *= ESC
    cx, cy = int(BW * 0.80), int(BH * 1.25)
    dc.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(80, 200, 190, max(8, 40 - i * 3)), width=2 * ESC)
for x in range(0, BW, 22 * ESC):  # puntos tenues
    for y in range(10 * ESC, BH, 22 * ESC):
        dc.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255, 14))
banda = Image.alpha_composite(banda, capa.filter(ImageFilter.GaussianBlur(0.6)))
mask = Image.new("L", (BW, BH), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, BW - 1, BH - 1], radius=16 * ESC, fill=255)
banda.putalpha(mask)
banda.save(os.path.join(OUT, "banda.png"), optimize=True)


# ---------------------------------------------------------------- tarjetas con ondas
def ola(nombre, c1, c2, c_ola):
    tw, th = 300 * ESC, 112 * ESC
    img = a_imagen(degradado(tw, th, c1, c2)).convert("RGBA")
    capa = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    dl = ImageDraw.Draw(capa)
    col = tuple(int(v) for v in rgb(c_ola))
    for k, (amp, fase, base, alfa) in enumerate([(14, 0.0, 0.62, 70), (18, 1.3, 0.72, 55), (12, 2.4, 0.84, 45)]):
        pts = [(x, th * base + amp * ESC * math.sin(x / tw * 2 * math.pi * 1.3 + fase)) for x in range(0, tw + 1, 4)]
        dl.polygon(pts + [(tw, th), (0, th)], fill=col + (alfa,))
        dl.line(pts, fill=(255, 255, 255, 40 - k * 10), width=ESC)
    brillo = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).ellipse([int(tw * 0.55), -int(th * 0.6), int(tw * 1.25), int(th * 0.7)],
                                   fill=(255, 255, 255, 28))
    img = Image.alpha_composite(img, capa)
    img = Image.alpha_composite(img, brillo.filter(ImageFilter.GaussianBlur(18 * ESC)))
    # esquinas redondeadas (transparentes) para que la tarjeta se vea como en la plantilla
    mask = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, tw - 1, th - 1], radius=14 * ESC, fill=255)
    img.putalpha(mask)
    img.save(os.path.join(OUT, f"ola_{nombre}.png"))


ola("azul", "#1E4FD8", "#3B82F6", "#93C5FD")
ola("teal", "#0F766E", "#22B5A0", "#7FE0CF")
ola("marino", "#14213D", "#2A4777", "#5B7DB8")
ola("indigo", "#3730A3", "#6366F1", "#A5B4FC")

# ---------------------------------------------------------------- ventana emergente
Image.new("RGB", (320 * ESC, 240 * ESC), "#FFFFFF").save(os.path.join(OUT, "fondo_tooltip.png"))

# ---------------------------------------------------------------- logo: silueta de Puno
from shapely.geometry import shape  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

g = json.load(open(os.path.join(BASE, "data", "ref", "geo", "puno_distritos.geojson"), encoding="utf-8"))
union = unary_union([shape(f["geometry"]).buffer(0) for f in g["features"] if f.get("geometry")]).simplify(0.01)
poli = max(getattr(union, "geoms", [union]), key=lambda p: p.area)
ruta = list(poli.exterior.coords)
L = 256 * ESC
xs, ys = [p[0] for p in ruta], [p[1] for p in ruta]
esc = 0.80 * L / max(max(xs) - min(xs), max(ys) - min(ys))
ox = (L - (max(xs) - min(xs)) * esc) / 2
oy = (L - (max(ys) - min(ys)) * esc) / 2
pts = [(ox + (x - min(xs)) * esc, oy + (max(ys) - y) * esc) for x, y in ruta]
logo = Image.new("RGBA", (L, L), (0, 0, 0, 0))
dl = ImageDraw.Draw(logo)
dl.polygon(pts, fill=(43, 179, 155, 255))
dl.line(pts + [pts[0]], fill=(190, 245, 235, 255), width=4 * ESC, joint="curve")
logo.save(os.path.join(OUT, "logo_puno.png"))
print("recursos en", OUT)
