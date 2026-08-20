"""El icono de la marca sale de UNA fuente y llega igual a las tres plataformas.

`packaging/generar_iconos.py` no renderiza SVG (el entorno no tiene cairosvg
ni rsvg, y traer una cadena de librerías nativas para dibujar dos polígonos
sin curvas no se justifica): copia las coordenadas y los colores del
`<path>` del SVG a constantes de Python. Eso funciona, pero abre una grieta —
alguien cambia el SVG y los PNG siguen mostrando el logo viejo, en silencio,
hasta que se ve en un teléfono.

Estos tests cierran esa grieta comparando las constantes contra el SVG REAL,
y verifican lo que ya salió mal una vez: que el `foreground` adaptativo entre
en la zona segura de Android.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "packaging"))

import generar_iconos as gi  # noqa: E402

SVG = (RAIZ / "assets/brand/mv_icon.svg").read_text(encoding="utf-8")


def test_las_constantes_coinciden_con_el_svg():
    """Si el SVG cambia y el generador no, los iconos quedan viejos sin que
    nada avise. Acá se comparan los dos, campo por campo."""
    paradas = re.findall(r'stop-color="(#[0-9a-fA-F]{6})"', SVG)
    assert tuple(paradas) == gi.DEGRADADO, (
        f"el degradado del SVG es {paradas} y el generador usa {gi.DEGRADADO}")

    rect = re.search(r'<rect[^>]*rx="(\d+)"', SVG)
    assert rect and int(rect.group(1)) == gi.RADIO, (
        "el radio de las esquinas no coincide con el rx del <rect>")

    # Los dos glifos: color, desplazamiento en X y el `d` entero.
    for etiqueta, color, dx, d in (
            ("M", gi.BLANCO, gi.M_X, gi.M_PATH),
            ("V", gi.VERDE, gi.V_X, gi.V_PATH)):
        assert color.lower() in SVG.lower(), f"el color de la {etiqueta} no está en el SVG"
        assert f"translate({dx},{gi.BASE_Y})" in SVG, (
            f"el translate de la {etiqueta} no coincide con el SVG")
        assert d in SVG, f"el trazado de la {etiqueta} no es el del SVG"

    assert f"scale({gi.ESCALA}," in SVG, "la escala no coincide con el SVG"


def test_el_icono_adaptativo_entra_en_la_zona_segura():
    """Android recorta el icono adaptativo con la máscara del lanzador
    (círculo, squircle, gota) y sólo garantiza los 72dp centrales de 108.

    La primera versión de este generador dibujaba el `foreground` a todo lo
    ancho, igual que el icono cuadrado: en un lanzador circular las letras
    quedaban cortadas por los costados. Se verifica sobre el PNG generado —
    que el dibujo entre, no que la intención estuviera.
    """
    for dens in gi.DENSIDADES:
        png = RAIZ / f"android/app/src/main/res/mipmap-{dens}/ic_launcher_foreground.png"
        im = Image.open(png).convert("RGBA")
        # Con umbral, no `getbbox()` pelado: reducir de 1024 a 48 px deja un
        # fleco de antialias de alpha 1-20/255 alrededor del dibujo. Ese fleco
        # es invisible, pero `getbbox()` lo cuenta y hacía "fallar" al icono
        # por 4 px de nada. Se mide dónde el icono SE VE.
        caja = im.getchannel("A").point(lambda a: 255 if a > 40 else 0).getbbox()
        assert caja, f"{png.name} salió vacío"

        lado = im.width
        radio_seguro = lado * gi.SEGURO / 2
        cx = cy = lado / 2
        # La esquina más lejana del contenido tiene que caer dentro del
        # círculo seguro: es la máscara que más recorta.
        for x, y in ((caja[0], caja[1]), (caja[2], caja[1]),
                     (caja[0], caja[3]), (caja[2], caja[3])):
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            assert dist <= radio_seguro + 1, (
                f"{png.name}: el contenido llega a {dist:.0f}px del centro y "
                f"la zona segura termina en {radio_seguro:.0f}px — un lanzador "
                "circular lo recorta")


def test_todas_las_plataformas_tienen_su_icono():
    """Web, PC y Android. Antes cada uno tenía su PNG suelto hecho a mano y
    no había forma de saber si seguían siendo el mismo dibujo."""
    for ruta, lado in gi.DESTINOS_PNG:
        f = RAIZ / ruta
        assert f.exists(), f"falta {ruta} (corré packaging/generar_iconos.py)"
        assert Image.open(f).size == (lado, lado), f"{ruta} no mide {lado}px"

    for ico in ("assets/brand/mv.ico", "electron/build/icon.ico"):
        f = RAIZ / ico
        assert f.exists(), f"falta {ico}"
        # Multi-tamaño: con uno solo adentro, Windows reescala y el de 16px
        # de la barra de tareas se ve sucio.
        tamanos = Image.open(f).info.get("sizes", set())
        assert (16, 16) in tamanos and (256, 256) in tamanos, (
            f"{ico} tendría que traer de 16 a 256; trae {sorted(tamanos)}")

    for dens, lado in gi.DENSIDADES.items():
        carpeta = RAIZ / "android/app/src/main/res" / f"mipmap-{dens}"
        for nombre in ("ic_launcher", "ic_launcher_round", "ic_launcher_foreground"):
            f = carpeta / f"{nombre}.png"
            assert f.exists(), f"falta {f.relative_to(RAIZ)}"
            assert Image.open(f).size == (lado, lado), (
                f"{f.relative_to(RAIZ)} no mide {lado}px")


def test_el_fondo_adaptativo_sale_del_degradado():
    """El XML del color de fondo lo escribe el generador. Estaba a mano en
    #0A1020 — más oscuro que el logo — y quedó así cuando la marca cambió el
    degradado, porque nada lo ataba al SVG."""
    xml = (RAIZ / "android/app/src/main/res/values/ic_launcher_background.xml"
           ).read_text(encoding="utf-8")
    color = re.search(r'name="ic_launcher_background">(#[0-9A-Fa-f]{6})<', xml)
    assert color, "no se encontró el color de fondo del icono adaptativo"

    def _rgb(css):
        return tuple(int(css[i:i + 2], 16) for i in (1, 3, 5))

    arriba, abajo = _rgb(gi.DEGRADADO[0]), _rgb(gi.DEGRADADO[1])
    esperado = tuple((a + b) // 2 for a, b in zip(arriba, abajo, strict=True))
    assert _rgb(color.group(1)) == esperado, (
        f"el fondo adaptativo es {color.group(1)} y el medio del degradado "
        f"es #{esperado[0]:02X}{esperado[1]:02X}{esperado[2]:02X} — "
        "corré packaging/generar_iconos.py")
