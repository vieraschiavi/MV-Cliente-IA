"""
MV Cliente IA · genera TODOS los iconos desde una sola fuente
==============================================================
    python3 packaging/generar_iconos.py

El isotipo MV (cuadrado azul con degradado, M blanca y V verde) vive en
`assets/brand/mv_icon.svg`, que es el logo real de la marca. De ahí salen,
por cálculo y no a mano:

  assets/brand/   mv_icon.png (1024) · _256 · _128 · _64 · _32 · mv.ico
  electron/build/ icon.png (256) · icon.ico      -> instalador y ventana de PC
  android/…/res/  mipmap-*/ic_launcher{,_round,_foreground}.png
  landing/ y public/  mv_icon.png                -> favicon de la web

Por qué está escrito así
------------------------
1. **Un solo origen.** Antes cada plataforma tenía su PNG suelto, hechos a
   mano en algún momento y sin forma de saber si seguían siendo el mismo
   dibujo. Cuando la marca cambió el logo (degradado + M y V entrelazadas)
   no había un comando que lo propagara: había que acordarse de doce
   archivos. Ahora se corre esto y listo.

2. **Sin dependencias de render de SVG.** El entorno no tiene cairosvg ni
   rsvg, y agregar uno para dibujar dos polígonos sería traer una cadena de
   librerías nativas a un proyecto que hoy sólo necesita Pillow. Los dos
   glifos del logo son polígonos SIN CURVAS —vienen de convertir la
   tipografía a trazado— así que se dibujan exactos con `ImageDraw.polygon`.
   Las coordenadas de abajo son las del `<path>` del SVG, verbatim.

3. **Si el SVG cambia, esto tiene que cambiar.** Es la contra de no
   renderizar SVG de verdad. `tests/test_iconos.py` compara los números de
   acá contra el SVG y falla si alguien toca uno sin el otro.
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
MARCA = RAIZ / "assets" / "brand"
SVG = MARCA / "mv_icon.svg"

LADO = 1024                      # el viewBox del SVG
MARGEN = 6                       # <rect x="6" y="6" …>
RADIO = 230                      # rx del <rect>
DEGRADADO = ("#1c3f63", "#0d2440")   # arriba -> abajo
BLANCO = "#ffffff"
VERDE = "#5cb531"

# Los dos glifos, tal cual el `d` del SVG. El sistema de la tipografía tiene
# la Y para arriba, por eso el `scale(s, -s)` del SVG: acá se aplica igual.
ESCALA = 0.21484375
BASE_Y = 650
M_X, V_X = 205, 540
M_PATH = ("M188 1493H678L1018 694L1360 1493H1849V0H1485V1092L1141 287H897"
          "L553 1092V0H188Z")
V_PATH = "M10 1493H397L793 391L1188 1493H1575L1022 0H563Z"


def _puntos(d: str, dx: float) -> list[tuple[float, float]]:
    """El `d` de un path recto (M/L/H/V/Z) a coordenadas del lienzo.

    Sólo esos cuatro comandos: los glifos ya vienen aplanados a polígono, y
    un parser de curvas acá sería código muerto que igual habría que probar.
    """
    pts: list[tuple[float, float]] = []
    x = y = 0.0
    for cmd, args in re.findall(r"([MLHVZ])([-\d\s.]*)", d, flags=re.I):
        nums = [float(n) for n in re.findall(r"-?[\d.]+", args)]
        c = cmd.upper()
        if c == "M" or c == "L":
            for i in range(0, len(nums), 2):
                x, y = nums[i], nums[i + 1]
                pts.append((x, y))
        elif c == "H":
            for n in nums:
                x = n
                pts.append((x, y))
        elif c == "V":
            for n in nums:
                y = n
                pts.append((x, y))
    # El transform del SVG: translate(dx, BASE_Y) scale(ESCALA, -ESCALA).
    return [(dx + px * ESCALA, BASE_Y - py * ESCALA) for px, py in pts]


def _rgb(css: str) -> tuple[int, int, int]:
    return tuple(int(css[i:i + 2], 16) for i in (1, 3, 5))


# Cuánto del icono adaptativo de Android es zona SEGURA. El lienzo es de
# 108dp pero el lanzador recorta a una máscara (círculo, squircle, gota…) y
# sólo los 72dp centrales están garantizados. Un `foreground` dibujado a todo
# lo ancho se ve con las letras cortadas en cuanto el lanzador usa círculo.
SEGURO = 72 / 108


def dibujar(lado: int = LADO, *, fondo: bool = True) -> Image.Image:
    """El isotipo a `lado`×`lado`. Sin `fondo`, sólo las letras sobre
    transparente, encogidas y centradas dentro de la zona segura — es lo que
    Android quiere de `ic_launcher_foreground`."""
    # Se dibuja SIEMPRE a 1024 y se reduce al final: rasterizar un polígono
    # chico directamente deja los bordes dentados, y estos iconos se ven a
    # 48 px en la lista de apps.
    im = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))

    if fondo:
        arriba, abajo = _rgb(DEGRADADO[0]), _rgb(DEGRADADO[1])
        tira = Image.new("RGB", (1, LADO))
        for y in range(LADO):
            t = y / (LADO - 1)
            tira.putpixel((0, y), tuple(
                round(a + (b - a) * t) for a, b in zip(arriba, abajo, strict=True)))
        placa = tira.resize((LADO, LADO), Image.BILINEAR).convert("RGBA")
        mascara = Image.new("L", (LADO, LADO), 0)
        ImageDraw.Draw(mascara).rounded_rectangle(
            [MARGEN, MARGEN, LADO - 1 - MARGEN, LADO - 1 - MARGEN],
            RADIO, fill=255)
        placa.putalpha(mascara)
        im.alpha_composite(placa)

    letras = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
    d = ImageDraw.Draw(letras)
    # La M primero y la V encima: es el orden del SVG y es lo que las
    # entrelaza — el brazo verde cruza por delante del asta derecha blanca.
    d.polygon(_puntos(M_PATH, M_X), fill=_rgb(BLANCO))
    d.polygon(_puntos(V_PATH, V_X), fill=_rgb(VERDE))

    if fondo:
        im.alpha_composite(letras)
    else:
        # Adaptativo: las letras se encogen a la zona segura y se centran de
        # verdad (su caja real, no el lienzo — el logo no está centrado en el
        # viewBox: la M arranca en 205 y la V termina en ~880).
        caja = letras.getbbox()
        recorte = letras.crop(caja)
        # Se ajusta por la DIAGONAL, no por el ancho. La máscara que más
        # recorta es un círculo de diámetro `SEGURO`, y las esquinas de una
        # caja de ese ancho quedan afuera: con un logo apaisado como «MV»
        # —donde las esquinas del recuadro SON letra, no aire— eso cortaba
        # el asta izquierda de la M y el brazo derecho de la V.
        radio = LADO * SEGURO / 2
        media_diagonal = (recorte.width ** 2 + recorte.height ** 2) ** 0.5 / 2
        escala = radio / media_diagonal
        chico = recorte.resize(
            (max(1, round(recorte.width * escala)),
             max(1, round(recorte.height * escala))), Image.LANCZOS)
        im.alpha_composite(chico, ((LADO - chico.width) // 2,
                                   (LADO - chico.height) // 2))

    return im if lado == LADO else im.resize((lado, lado), Image.LANCZOS)


# Dónde va cada cosa. (ruta, lado) — relativo a la raíz del repo.
DESTINOS_PNG = [
    ("assets/brand/mv_icon.png", 1024),
    ("assets/brand/mv_icon_256.png", 256),
    ("assets/brand/mv_icon_128.png", 128),
    ("assets/brand/mv_icon_64.png", 64),
    ("assets/brand/mv_icon_32.png", 32),
    ("electron/build/icon.png", 256),
    ("landing/mv_icon.png", 1024),
    # La copia propia de la app React: Vite la lleva a dist/ y de ahí
    # `marketing.armar_sitio` la publica en public/app/. Sin esto, el
    # favicon del panel se quedaba con el logo viejo.
    ("webapp/frontend/public/mv_icon.png", 1024),
]
TAMANOS_ICO = [16, 32, 48, 64, 128, 256]
DENSIDADES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def main() -> int:
    if not SVG.exists():
        print(f"Falta {SVG}")
        return 1

    hechos = 0
    for ruta, lado in DESTINOS_PNG:
        destino = RAIZ / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        dibujar(lado).save(destino)
        hechos += 1

    # .ico multi-tamaño: Windows elige el que necesita (16 en la barra de
    # tareas, 256 en el instalador). Con un solo tamaño adentro, Windows
    # reescala y se ve mal justo en el chico.
    grande = dibujar(256)
    for ico in ("assets/brand/mv.ico", "electron/build/icon.ico"):
        (RAIZ / ico).parent.mkdir(parents=True, exist_ok=True)
        grande.save(RAIZ / ico, sizes=[(n, n) for n in TAMANOS_ICO])
        hechos += 1

    # El color plano que Android pone DETRÁS del `foreground` adaptativo.
    # Sale del punto medio del degradado en vez de estar escrito a mano en el
    # XML: así el icono adaptativo no se queda con el azul viejo el día que la
    # marca cambie el degradado — que es exactamente lo que había pasado
    # (el XML decía #0A1020, más oscuro que el logo nuevo).
    arriba, abajo = _rgb(DEGRADADO[0]), _rgb(DEGRADADO[1])
    medio = "#{:02X}{:02X}{:02X}".format(
        *((a + b) // 2 for a, b in zip(arriba, abajo, strict=True)))
    xml = RAIZ / "android/app/src/main/res/values/ic_launcher_background.xml"
    xml.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<!-- Generado por packaging/generar_iconos.py: es el medio del\n"
        "     degradado de assets/brand/mv_icon.svg. No editar a mano. -->\n"
        "<resources>\n"
        f'    <color name="ic_launcher_background">{medio}</color>\n'
        "</resources>\n", encoding="utf-8")
    hechos += 1

    for dens, lado in DENSIDADES.items():
        carpeta = RAIZ / "android/app/src/main/res" / f"mipmap-{dens}"
        carpeta.mkdir(parents=True, exist_ok=True)
        cuadrado = dibujar(lado)
        cuadrado.save(carpeta / "ic_launcher.png")
        cuadrado.save(carpeta / "ic_launcher_round.png")
        # El `foreground` del icono adaptativo va SIN fondo: Android le pone
        # el suyo y lo recorta a la forma que use el lanzador (círculo,
        # squircle…). Con el cuadrado adentro se vería un cuadrado dentro de
        # un círculo.
        dibujar(lado, fondo=False).save(carpeta / "ic_launcher_foreground.png")
        hechos += 3

    print(f"  OK: {hechos} archivos generados desde {SVG.relative_to(RAIZ)}")
    print("    (public/ se regenera con `python3 -m marketing.armar_sitio`)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
