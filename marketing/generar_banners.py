"""
MV Cliente IA · banners de los correos
=======================================
Genera el banner que encabeza el correo HTML, uno por idioma, en
`landing/banners/banner_<idioma>.png` (600 px de ancho: el estándar de los
clientes de correo, se ve nítido en pantallas 2× sin pasarse en peso).

    python3 -m marketing.generar_banners

Por qué una imagen y no HTML: Gmail, Outlook y Apple Mail recortan CSS de
formas distintas, y un gradiente hecho con divs se ve roto en al menos uno de
los tres. Una PNG se ve igual en todos. El correo igual lleva texto alternativo
y el mismo mensaje en el cuerpo, así que un cliente con las imágenes
bloqueadas —que es la mitad— no pierde nada.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "landing" / "banners"
ICONO = RAIZ / "assets" / "brand" / "mv_icon.png"

ANCHO, ALTO = 600, 220

# Tokens de la marca (los mismos de webapp/frontend/src/theme.css).
NAVY = (10, 16, 32)
NAVY2 = (20, 32, 54)
VERDE = (0, 200, 150)
TINTA = (234, 241, 251)
APAGADO = (147, 165, 192)

TEXTOS = {
    "es": {
        "marca": "MV CLIENTE", "marca2": "IA",
        "titulo": "Tus próximos clientes,\nencontrados por vos.",
        "pie": "Ver el video  ▸",
    },
    "pt": {
        "marca": "MV CLIENTE", "marca2": "IA",
        "titulo": "Seus próximos clientes,\nencontrados para você.",
        "pie": "Ver o vídeo  ▸",
    },
    "en": {
        "marca": "MV SearchCostumer", "marca2": "AI",
        "titulo": "Your next customers,\nfound for you.",
        "pie": "Watch the video  ▸",
    },
}

# Rutas de fuentes del sistema, en orden de preferencia. Si no hay ninguna se
# usa la bitmap de PIL: fea pero el banner sale igual, no revienta el build.
FUENTES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/segoeuib.ttf",
]


def _fuente(tam: int):
    for ruta in FUENTES:
        if Path(ruta).exists():
            try:
                return ImageFont.truetype(ruta, tam)
            except OSError:
                continue
    return ImageFont.load_default()


def _fondo() -> Image.Image:
    """Degradado diagonal navy con un halo verde arriba a la derecha."""
    img = Image.new("RGB", (ANCHO, ALTO), NAVY)
    px = img.load()
    for y in range(ALTO):
        for x in range(0, ANCHO, 2):        # de a dos: mitad de trabajo, se ve igual
            t = (x / ANCHO) * 0.55 + (1 - y / ALTO) * 0.45
            c = tuple(int(NAVY[i] + (NAVY2[i] - NAVY[i]) * t) for i in range(3))
            px[x, y] = c
            if x + 1 < ANCHO:
                px[x + 1, y] = c

    halo = Image.new("RGB", (ANCHO, ALTO), NAVY)
    hpx = halo.load()
    cx, cy, r = ANCHO * 0.86, ALTO * 0.12, ALTO * 1.15
    for y in range(ALTO):
        for x in range(0, ANCHO, 2):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            k = max(0.0, 1 - d / r) ** 2 * 0.30
            base = px[x, y]
            c = tuple(int(base[i] + (VERDE[i] - base[i]) * k) for i in range(3))
            hpx[x, y] = c
            if x + 1 < ANCHO:
                hpx[x + 1, y] = c
    return halo


def generar_uno(idioma: str) -> Path:
    t = TEXTOS[idioma]
    img = _fondo()
    d = ImageDraw.Draw(img)

    # Isotipo + nombre de la marca.
    if ICONO.exists():
        ico = Image.open(ICONO).convert("RGBA").resize((34, 34), Image.LANCZOS)
        img.paste(ico, (34, 30), ico)
    f_marca = _fuente(15)
    x = 80
    d.text((x, 38), t["marca"], font=f_marca, fill=TINTA)
    x += int(d.textlength(t["marca"], font=f_marca)) + 6
    d.text((x, 38), t["marca2"], font=f_marca, fill=VERDE)

    # Titular a dos líneas.
    f_tit = _fuente(30)
    y = 92
    for linea in t["titulo"].split("\n"):
        d.text((34, y), linea, font=f_tit, fill=TINTA)
        y += 38

    # Franja inferior: la llamada al video.
    d.rectangle([0, ALTO - 42, ANCHO, ALTO], fill=(8, 13, 26))
    d.rectangle([0, ALTO - 43, ANCHO, ALTO - 42], fill=(36, 52, 79))
    f_pie = _fuente(14)
    d.text((34, ALTO - 30), t["pie"], font=f_pie, fill=VERDE)

    # Triangulito de "reproducir" a la derecha.
    cx, cy = ANCHO - 46, ALTO - 21
    d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], outline=VERDE, width=2)
    d.polygon([(cx - 4, cy - 6), (cx - 4, cy + 6), (cx + 6, cy)], fill=VERDE)

    DESTINO.mkdir(parents=True, exist_ok=True)
    destino = DESTINO / f"banner_{idioma}.png"
    img.save(destino, optimize=True)
    return destino


def generar() -> list[Path]:
    return [generar_uno(i) for i in TEXTOS]


if __name__ == "__main__":
    for p in generar():
        print(f"  ✓ {p.relative_to(RAIZ)}  ({p.stat().st_size // 1024} KB)")
