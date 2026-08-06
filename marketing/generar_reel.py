"""
MV Cliente IA · reels verticales para redes (Instagram / TikTok / Shorts)
=========================================================================
Produce `landing/reel/{es,pt,en}/reel.mp4`: el video corto VERTICAL (9:16,
720×1280) para publicar en redes. Es una pieza distinta del demo de la
landing (`generar_video`, 16:9): acá el lenguaje es el de un reel — fondo
estrellado con halo, rótulos estilo terminal, titulares grandes con la
palabra clave en verde, capturas de la app en modo móvil dentro de una
tarjeta, chips de canales, un contador que sube y subtítulos con las
palabras importantes en amarillo. El cierre es un llamado a la acción con
la web y las tres búsquedas gratis.

    python3 -m marketing.generar_reel

Mismas reglas que el demo: no se versiona un video editado a mano (se
regenera de acá), cada idioma lleva su locución neural y su marca
(MV Cliente IA en es/pt, MV SearchCostumer AI en inglés), y ni la voz ni
las placas mencionan el orden de países — eso es cocina del motor.

Necesita lo mismo que `generar_video`: `edge-tts`, `playwright` (con el
Chromium del sistema) e `imageio-ffmpeg`.
"""
from __future__ import annotations

import random
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .generar_banners import APAGADO, ICONO, NAVY, NAVY2, TINTA, VERDE, _fuente
from .generar_video import (
    _correr_corrida,
    _duracion,
    _esperar_api,
    _ffmpeg,
    _puerto_libre,
    _voz_recortada,
)

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "landing" / "reel"

ANCHO, ALTO = 720, 1280
FPS = 30
FUNDIDO = 0.3
# Aire después de la voz de cada escena. Más corto que en el demo 16:9 a
# propósito: un reel con pausas largas se siente con lag y se abandona.
RESPIRO = 0.45
AMARILLO = (255, 209, 60)

# La captura móvil se hace a 360×640 con factor 2: sale un PNG de 720×1280
# con la app en su layout de teléfono — el mismo que ve el APK.
VISOR_MOVIL = {"width": 360, "height": 640}

ESCENAS = ("hook", "panel", "canales", "contador", "prospectos", "analisis", "cta")

# En los subtítulos, *palabra* se pinta de amarillo (el resto en tinta).
GUION: dict[str, dict] = {
    "es": {
        "marca": ("MV CLIENTE", "IA"),
        "voz_neural": "es-UY-MateoNeural",
        "kicker": {
            "hook": "LLEGÓ A TU MERCADO",
            "panel": "EL PANEL, ANDANDO",
            "canales": "SE ENCHUFA A LO QUE YA USÁS",
            "contador": "UNA SOLA CORRIDA",
            "prospectos": "LA LISTA, ORDENADA",
            "analisis": "TU NEGOCIO, PROYECTADO",
            "cta": "EL FUTURO YA LLEGÓ",
        },
        "hook_titulo": ("Clientes que", "llegan solos"),
        "chips": ("CORREO", "LINKEDIN", "X (TWITTER)", "EXCEL / CSV"),
        "chips_sub": "En el idioma de quien lo recibe: ES · PT · EN",
        "contador_n": 1000,
        "contador_sub": "empresas por corrida · decisores · correos",
        "cta_caja": "PROBALO GRATIS",
        "cta_sub": "mvclienteia.com · 3 búsquedas de regalo",
        "sub": {
            "hook": "Pegás tu enlace y *aparecen* tus clientes.",
            "panel": "Seis fases *automáticas*, de tu web a los correos.",
            "canales": "Correo, LinkedIn y X, en *su* idioma.",
            "contador": "Hasta *mil* empresas por corrida.",
            "prospectos": "Ordenada por *probabilidad* de cierre.",
            "analisis": "Ventas, gastos y *neto* a 24 meses.",
            "cta": "Entrá y probalo *gratis*.",
        },
        "voz": {
            "hook": "¿Y si tus próximos clientes aparecieran solos? Pegás el "
                    "enlace de tu producto, y un agente sale a buscarlos.",
            "panel": "Este es el panel, andando: seis fases automáticas, de tu "
                     "web a los correos listos.",
            "canales": "Escribe el correo, el mensaje de LinkedIn y el posteo "
                       "para equis, en el idioma de quien lo recibe: español, "
                       "portugués o inglés.",
            "contador": "Elegís cuántas: cincuenta, cien, quinientas, hasta mil "
                        "empresas por corrida, con sus decisores y los correos "
                        "listos para salir.",
            "prospectos": "La lista llega ordenada por probabilidad de cierre, "
                          "con las señales de por qué contactar a cada empresa.",
            "analisis": "Y el análisis proyecta tu negocio con tus números: "
                        "ventas, gastos y resultado neto hasta veinticuatro meses.",
            "cta": "Probalo gratis en mv cliente ia punto com. Tenés tres "
                   "búsquedas de regalo.",
        },
    },
    "pt": {
        "marca": ("MV CLIENTE", "IA"),
        "voz_neural": "pt-BR-AntonioNeural",
        "kicker": {
            "hook": "CHEGOU AO SEU MERCADO",
            "panel": "O PAINEL, FUNCIONANDO",
            "canales": "SE CONECTA AO QUE VOCÊ JÁ USA",
            "contador": "UMA ÚNICA RODADA",
            "prospectos": "A LISTA, ORDENADA",
            "analisis": "SEU NEGÓCIO, PROJETADO",
            "cta": "O FUTURO JÁ CHEGOU",
        },
        "hook_titulo": ("Clientes que", "chegam sozinhos"),
        "chips": ("E-MAIL", "LINKEDIN", "X (TWITTER)", "EXCEL / CSV"),
        "chips_sub": "No idioma de quem recebe: ES · PT · EN",
        "contador_n": 1000,
        "contador_sub": "empresas por rodada · decisores · e-mails",
        "cta_caja": "TESTE GRÁTIS",
        "cta_sub": "mvclienteia.com · 3 buscas de presente",
        "sub": {
            "hook": "Cole o seu link e seus clientes *aparecem*.",
            "panel": "Seis fases *automáticas*, do seu site aos e-mails.",
            "canales": "E-mail, LinkedIn e X, no idioma *deles*.",
            "contador": "Até *mil* empresas por rodada.",
            "prospectos": "Ordenada por *probabilidade* de fechamento.",
            "analisis": "Vendas, custos e *líquido* em 24 meses.",
            "cta": "Entre e teste *grátis*.",
        },
        "voz": {
            "hook": "E se os seus próximos clientes aparecessem sozinhos? Você "
                    "cola o link do seu produto, e um agente sai para buscá-los.",
            "panel": "Este é o painel, funcionando: seis fases automáticas, do "
                     "seu site aos e-mails prontos.",
            "canales": "Escreve o e-mail, a mensagem do LinkedIn e o post para "
                       "o xis, no idioma de quem recebe: espanhol, português "
                       "ou inglês.",
            "contador": "Você escolhe quantas: cinquenta, cem, quinhentas, até mil "
                        "empresas por rodada, com os decisores e os e-mails "
                        "prontos para sair.",
            "prospectos": "A lista chega ordenada por probabilidade de "
                          "fechamento, com os sinais de por que contatar cada empresa.",
            "analisis": "E a análise projeta o seu negócio com os seus números: "
                        "vendas, custos e resultado líquido até vinte e quatro meses.",
            "cta": "Teste grátis em mv cliente ia ponto com. Você tem três "
                   "buscas de presente.",
        },
    },
    "en": {
        "marca": ("MV SearchCostumer", "AI"),
        "voz_neural": "en-US-GuyNeural",
        "kicker": {
            "hook": "IT REACHED YOUR MARKET",
            "panel": "THE PANEL, RUNNING",
            "canales": "PLUGS INTO WHAT YOU USE",
            "contador": "ONE SINGLE RUN",
            "prospectos": "THE LIST, RANKED",
            "analisis": "YOUR BUSINESS, PROJECTED",
            "cta": "THE FUTURE IS HERE",
        },
        "hook_titulo": ("Customers that", "show up alone"),
        "chips": ("EMAIL", "LINKEDIN", "X (TWITTER)", "EXCEL / CSV"),
        "chips_sub": "In the recipient's language: ES · PT · EN",
        "contador_n": 1000,
        "contador_sub": "companies per run · decision makers · emails",
        "cta_caja": "TRY IT FREE",
        "cta_sub": "mvclienteia.com · 3 searches on us",
        "sub": {
            "hook": "Paste your link and your customers *appear*.",
            "panel": "Six *automatic* phases, from your site to the emails.",
            "canales": "Email, LinkedIn and X, in *their* language.",
            "contador": "Up to *1,000* companies per run.",
            "prospectos": "Ranked by *likelihood* to close.",
            "analisis": "Sales, costs and *net* over 24 months.",
            "cta": "Come try it for *free*.",
        },
        "voz": {
            "hook": "What if your next customers showed up on their own? You "
                    "paste your product's link, and an agent goes out to find them.",
            "panel": "This is the panel, running: six automatic phases, from "
                     "your site to ready-to-send emails.",
            "canales": "It writes the email, the LinkedIn message and the X "
                       "post, in the recipient's language: Spanish, Portuguese "
                       "or English.",
            "contador": "You choose how many: fifty, one hundred, five hundred, up "
                        "to one thousand companies per run, with their decision "
                        "makers and ready-to-send emails.",
            "prospectos": "The list arrives ranked by likelihood to close, with "
                          "the signals for why to contact each company.",
            "analisis": "And the analysis projects your business with your "
                        "numbers: sales, costs and net result up to twenty-four months.",
            "cta": "Try it free at mvclienteia dot com. You get three searches "
                   "on us.",
        },
    },
}


# ---------------------------------------------------------------------------
# Dibujo
# ---------------------------------------------------------------------------
def _fuente_mono(tam: int):
    """Mono bold para los rótulos estilo terminal y el contador."""
    ruta = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
    try:
        from PIL import ImageFont
        return ImageFont.truetype(ruta, tam)
    except OSError:
        return _fuente(tam)


def _fondo_estrellas(semilla: int = 7) -> Image.Image:
    """Cielo navy con estrellas y un halo verde: el escenario de todo el reel.
    La semilla es fija para que dos corridas den el mismo video byte a byte
    (misma razón que el modo demo del motor)."""
    img = Image.new("RGB", (ANCHO, ALTO), NAVY)
    px = img.load()
    for y in range(ALTO):
        t = y / ALTO * 0.5
        c = tuple(int(NAVY[i] + (NAVY2[i] - NAVY[i]) * t) for i in range(3))
        for x in range(ANCHO):
            px[x, y] = c

    rnd = random.Random(semilla)
    d = ImageDraw.Draw(img)
    for _ in range(170):
        x, y = rnd.randrange(ANCHO), rnd.randrange(ALTO)
        brillo = rnd.randint(70, 220)
        r = rnd.choice((1, 1, 1, 2))
        d.ellipse([x, y, x + r, y + r], fill=(brillo, brillo, min(255, brillo + 20)))

    # El halo va en una capa aparte desenfocada: dibujarlo con círculos
    # concéntricos directo sobre el fondo dejaba anillos visibles.
    halo = Image.new("RGB", (ANCHO, ALTO), (0, 0, 0))
    dh = ImageDraw.Draw(halo)
    cx, cy, radio = ANCHO // 2, 560, 200
    for r in range(radio, 0, -6):
        v = int(46 * (1 - r / radio))
        dh.ellipse([cx - r, cy - r, cx + r, cy + r],
                   fill=(0, v, int(v * 0.78)))
    halo = halo.filter(ImageFilter.GaussianBlur(28))
    # Suma aditiva: el halo se comporta como una luz, no como una pintura.
    from PIL import ImageChops
    return ImageChops.add(img, halo)


def _cabecera(d: ImageDraw.ImageDraw, idioma: str) -> None:
    """La línea de marca de arriba: «● MV Cliente IA  AUTO-GTM»."""
    marca, marca2 = GUION[idioma]["marca"]
    f = _fuente(22)
    fm = _fuente_mono(17)
    texto = f"{marca} {marca2}"
    etiqueta = "AUTO-GTM"
    w = 16 + 10 + d.textlength(texto, font=f) + 14 + _ancho_espaciado(d, etiqueta, fm, 3)
    x = (ANCHO - w) // 2
    y = 86
    d.ellipse([x, y + 8, x + 10, y + 18], fill=VERDE)
    d.text((x + 20, y), texto, font=f, fill=TINTA)
    _texto_espaciado(d, (x + 20 + d.textlength(texto, font=f) + 14, y + 4),
                     etiqueta, fm, APAGADO, 3)


def _ancho_espaciado(d, texto: str, fuente, extra: int) -> float:
    return sum(d.textlength(c, font=fuente) + extra for c in texto) - extra


def _texto_espaciado(d, xy, texto: str, fuente, color, extra: int) -> None:
    """Letras separadas a mano: el look de terminal del rótulo."""
    x, y = xy
    for c in texto:
        d.text((x, y), c, font=fuente, fill=color)
        x += d.textlength(c, font=fuente) + extra


def _fuente_que_entra(d, texto: str, tam: int, max_w: int):
    """Achica la fuente hasta que el texto entre: «MV SearchCostumer AI» a 58
    puntos se salía del cuadro y nadie lo vio hasta mirar el PNG."""
    while tam > 20:
        f = _fuente(tam)
        if d.textlength(texto, font=f) <= max_w:
            return f
        tam -= 2
    return _fuente(tam)


def _kicker(d: ImageDraw.ImageDraw, idioma: str, escena: str, y: int = 150) -> None:
    texto = GUION[idioma]["kicker"][escena]
    f = _fuente_mono(24)
    w = _ancho_espaciado(d, texto, f, 6)
    _texto_espaciado(d, ((ANCHO - w) // 2, y), texto, f, APAGADO, 6)


def _subtitulo(img: Image.Image, idioma: str, escena: str, y: int = 1130) -> None:
    """La línea de abajo, con las palabras entre *asteriscos* en amarillo —
    el resalte de los reels. Fondo oscuro semitransparente para que se lea
    sobre cualquier escena."""
    d = ImageDraw.Draw(img, "RGBA")
    partes = GUION[idioma]["sub"][escena].split("*")
    f = _fuente_que_entra(d, "".join(partes), 30, ANCHO - 76)
    total = sum(d.textlength(p, font=f) for p in partes)
    x = (ANCHO - total) // 2
    d.rounded_rectangle([x - 18, y - 10, x + total + 18, y + 46],
                        radius=10, fill=(5, 8, 16, 190))
    for i, parte in enumerate(partes):
        color = AMARILLO if i % 2 else TINTA
        d.text((x, y), parte, font=f, fill=color)
        x += d.textlength(parte, font=f)


def _tarjeta_captura(fondo: Image.Image, captura: Path,
                     con_cara: bool = False) -> None:
    """La captura móvil dentro de una tarjeta redondeada con borde, centrada
    entre el rótulo y el subtítulo.

    Con presentador la tarjeta se achica: si no, el recuadro de la cara le
    caía encima. El teléfono se ve igual de bien más corto; dos cosas pisadas,
    no.
    """
    shot = Image.open(captura).convert("RGB")
    alto_obj = 620 if con_cara else 850
    ancho_obj = int(shot.width * alto_obj / shot.height)
    shot = shot.resize((ancho_obj, alto_obj), Image.LANCZOS)

    mask = Image.new("L", shot.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *shot.size], radius=26, fill=255)
    x, y = (ANCHO - ancho_obj) // 2, 225
    fondo.paste(shot, (x, y), mask)
    ImageDraw.Draw(fondo).rounded_rectangle(
        [x - 2, y - 2, x + ancho_obj + 2, y + alto_obj + 2],
        radius=27, outline=(0, 200, 150), width=3)


# ---------------------------------------------------------------------------
# Escenas
# ---------------------------------------------------------------------------
def _escena_hook(idioma: str, destino: Path) -> Path:
    img = _fondo_estrellas()
    d = ImageDraw.Draw(img)
    _cabecera(d, idioma)
    _kicker(d, idioma, "hook", 210)
    linea1, linea2 = GUION[idioma]["hook_titulo"]
    mas_larga = max((linea1, linea2), key=len)
    f = _fuente_que_entra(d, mas_larga, 76, ANCHO - 60)
    d.text(((ANCHO - d.textlength(linea1, font=f)) // 2, 290), linea1,
           font=f, fill=TINTA)
    d.text(((ANCHO - d.textlength(linea2, font=f)) // 2, 385), linea2,
           font=f, fill=VERDE)
    _subtitulo(img, idioma, "hook")
    img.save(destino)
    return destino


def _escena_captura(idioma: str, escena: str, captura: Path, destino: Path,
                    con_cara: bool = False) -> Path:
    img = _fondo_estrellas()
    d = ImageDraw.Draw(img)
    _cabecera(d, idioma)
    _kicker(d, idioma, escena)
    _tarjeta_captura(img, captura, con_cara)
    _subtitulo(img, idioma, escena)
    img.save(destino)
    return destino


def _escena_canales(idioma: str, destino: Path) -> Path:
    img = _fondo_estrellas()
    d = ImageDraw.Draw(img)
    _cabecera(d, idioma)
    _kicker(d, idioma, "canales", 300)
    f = _fuente_mono(30)
    y = 420
    chips = GUION[idioma]["chips"]
    for fila in (chips[:2], chips[2:]):
        anchos = [_ancho_espaciado(d, c, f, 3) + 56 for c in fila]
        x = (ANCHO - sum(anchos) - 24 * (len(fila) - 1)) // 2
        for chip, w in zip(fila, anchos, strict=True):
            d.rounded_rectangle([x, y, x + w, y + 74], radius=12,
                                fill=(16, 26, 44), outline=TINTA, width=2)
            _texto_espaciado(d, (x + 28, y + 20), chip, f, TINTA, 3)
            x += w + 24
        y += 104
    fs = _fuente(27)
    sub = GUION[idioma]["chips_sub"]
    d.text(((ANCHO - d.textlength(sub, font=fs)) // 2, y + 26), sub,
           font=fs, fill=APAGADO)
    _subtitulo(img, idioma, "canales")
    img.save(destino)
    return destino


def _escena_contador(idioma: str, carpeta: Path, valor: int | None = None) -> list[Path]:
    """El contador que sube (el «$ 74.827» de los reels, versión honesta:
    cuenta empresas de la corrida demo, no plata). Devuelve un cuadro por
    número; el armado los pasa a 30 fps y clava el último hasta que la voz
    termina."""
    t = GUION[idioma]
    final = valor if valor is not None else t["contador_n"]
    cuadros: list[Path] = []
    # ~1.2 s de conteo: 36 cuadros del 0 al final, con el arranque rápido y
    # el final frenando (cuadrática), que es como cuentan los reels.
    pasos = 36
    for i in range(pasos + 1):
        n = round(final * (1 - (1 - i / pasos) ** 2))
        img = _fondo_estrellas()
        d = ImageDraw.Draw(img)
        _cabecera(d, idioma)
        _kicker(d, idioma, "contador", 330)
        fn = _fuente_mono(150)
        texto = str(n)
        caja_w = _ancho_espaciado(d, str(final), fn, 8) + 120
        x0 = (ANCHO - caja_w) // 2
        d.rounded_rectangle([x0, 450, x0 + caja_w, 680], radius=18,
                            fill=(12, 20, 36), outline=AMARILLO, width=3)
        w = _ancho_espaciado(d, texto, fn, 8)
        _texto_espaciado(d, ((ANCHO - w) // 2, 478), texto, fn, AMARILLO, 8)
        fs = _fuente(29)
        sub = t["contador_sub"]
        d.text(((ANCHO - d.textlength(sub, font=fs)) // 2, 716), sub,
               font=fs, fill=APAGADO)
        _subtitulo(img, idioma, "contador")
        ruta = carpeta / f"{idioma}_contador_{i:03d}.png"
        img.save(ruta)
        cuadros.append(ruta)
    return cuadros


def _escena_cta(idioma: str, destino: Path) -> Path:
    t = GUION[idioma]
    img = _fondo_estrellas()
    d = ImageDraw.Draw(img)
    _cabecera(d, idioma)

    if ICONO.exists():
        ico = Image.open(ICONO).convert("RGBA").resize((110, 110), Image.LANCZOS)
        img.paste(ico, (ANCHO // 2 - 55, 250), ico)

    marca, marca2 = t["marca"]
    f = _fuente_que_entra(d, f"{marca} {marca2}", 58, ANCHO - 80)
    w = d.textlength(marca, font=f) + 16 + d.textlength(marca2, font=f)
    x = (ANCHO - w) // 2
    d.text((x, 395), marca, font=f, fill=TINTA)
    d.text((x + d.textlength(marca, font=f) + 16, 395), marca2, font=f, fill=VERDE)
    _kicker(d, idioma, "cta", 490)

    caja = t["cta_caja"]
    fc = _fuente_mono(44)
    wc = _ancho_espaciado(d, caja, fc, 8) + 120
    x0 = (ANCHO - wc) // 2
    d.rounded_rectangle([x0, 590, x0 + wc, 700], radius=16,
                        fill=(10, 30, 26), outline=VERDE, width=3)
    _texto_espaciado(d, (x0 + 60, 616), caja, fc, VERDE, 8)

    fs = _fuente(30)
    sub = t["cta_sub"]
    d.text(((ANCHO - d.textlength(sub, font=fs)) // 2, 750), sub,
           font=fs, fill=TINTA)
    _subtitulo(img, idioma, "cta")
    img.save(destino)
    return destino


# ---------------------------------------------------------------------------
# Presentador (el recuadro con la cara, como en los reels de referencia)
# ---------------------------------------------------------------------------
# Los reels que funcionan tienen una persona hablando en un recuadro: es lo que
# los hace mirar. Eso no se genera con código — hace falta una cara. Así que el
# generador acepta un clip del dueño y lo compone encima de todas las escenas.
# Se graba UNA vez con el teléfono y todos los reels futuros lo llevan.
#
#   marketing/presentador/es.mp4   (y pt.mp4 / en.mp4)
#
# Sin clip, el reel sale como hasta ahora. No se inventa una cara.
PRESENTADOR = RAIZ / "marketing" / "presentador"
# Tamaño y posición del recuadro, en píxeles del lienzo 720×1280. Va abajo de
# todo y ARRIBA del subtítulo, como en las referencias. Con un clip 4:3 el
# recuadro mide ~201 px de alto y termina en 1081, con aire hasta el subtítulo.
PIP_ANCHO = 260
PIP_Y = 880


def clip_presentador(idioma: str) -> Path | None:
    """El clip del idioma, o el de español como respaldo, o nada."""
    for candidato in (PRESENTADOR / f"{idioma}.mp4", PRESENTADOR / "es.mp4"):
        if candidato.exists() and candidato.stat().st_size > 10_000:
            return candidato
    return None


def _con_presentador(ff: str, escena_mp4: Path, clip: Path, desde: float,
                     destino: Path) -> tuple[Path, float]:
    """Pega el recuadro del presentador sobre una escena ya armada.

    `desde` es el segundo del clip por donde va esta escena: así el
    presentador avanza a lo largo del reel en vez de reiniciarse en cada
    corte, que se nota y queda a robot. Devuelve dónde quedó el clip.
    """
    dur = _duracion(ff, escena_mp4)
    largo_clip = _duracion(ff, clip)
    if largo_clip <= 0.5:
        return escena_mp4, desde
    # Si el clip se termina, se vuelve al principio: es preferible repetir a
    # dejar el recuadro congelado en el último cuadro.
    if desde + dur > largo_clip:
        desde = 0.0
    filtro = (
        f"[1:v]trim=start={desde:.2f}:duration={dur:.2f},setpts=PTS-STARTPTS,"
        f"scale={PIP_ANCHO}:-2,"
        # Esquinas redondeadas + borde verde, con la misma geometría que la
        # tarjeta de las capturas para que se lea como el mismo diseño.
        f"pad=iw+6:ih+6:3:3:color=0x00C896[pip];"
        f"[0:v][pip]overlay=x=(W-w)/2:y={PIP_Y}:shortest=0[v]"
    )
    subprocess.run(
        [ff, "-y", "-loglevel", "error",
         "-i", str(escena_mp4), "-i", str(clip),
         "-filter_complex", filtro,
         "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-r", str(FPS),
         "-c:a", "copy", "-t", f"{dur:.2f}", str(destino)],
        check=True)
    return destino, desde + dur


# ---------------------------------------------------------------------------
# Capturas móviles
# ---------------------------------------------------------------------------
def _capturas_movil(idioma: str, base: str, corrida_id: str,
                    carpeta: Path) -> dict[str, Path]:
    from playwright.sync_api import sync_playwright

    ejecutables = sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome"))
    lanzar = {"executable_path": str(ejecutables[-1])} if ejecutables else {}

    salida: dict[str, Path] = {}
    with sync_playwright() as p:
        navegador = p.chromium.launch(**lanzar)
        # device_scale_factor=2: la captura sale a 720×1280 nítidos con el
        # layout móvil de theme.css (max-width 860px) — la misma app del APK.
        ctx = navegador.new_context(viewport=VISOR_MOVIL, device_scale_factor=2,
                                    is_mobile=True)
        ctx.add_init_script(
            f"localStorage.setItem('mvcliente_idioma', '{idioma}');"
            f"localStorage.setItem('mvcliente_corrida', '{corrida_id}');")
        pagina = ctx.new_page()

        def foto(nombre: str) -> None:
            ruta = carpeta / f"{idioma}_m_{nombre}.png"
            pagina.screenshot(path=str(ruta))
            salida[nombre] = ruta

        pagina.goto(f"{base}/#/")
        pagina.wait_for_selector(".fase.listo >> nth=5", timeout=20000)
        foto("panel")

        pagina.goto(f"{base}/#/prospectos")
        pagina.wait_for_selector("table, .pers, .fila", timeout=20000)
        foto("prospectos")

        pagina.goto(f"{base}/#/analisis")
        pagina.wait_for_selector("#an-precio", timeout=20000)
        for campo, valor in (("precio", "99"), ("nuevos_por_mes", "3"),
                             ("churn_pct", "5"), ("gasto_fijo", "500"),
                             ("costo_por_cliente", "10"), ("gasto_ads", "300"),
                             ("cac", "150")):
            pagina.fill(f"#an-{campo}", valor)
        pagina.click('button[type="submit"]')
        pagina.wait_for_selector(".tablewrap table", timeout=30000)
        pagina.locator(".tablewrap table").scroll_into_view_if_needed()
        pagina.wait_for_timeout(400)
        foto("analisis")

        navegador.close()
    return salida


# ---------------------------------------------------------------------------
# Audio y armado
# ---------------------------------------------------------------------------
def _locucion(idioma: str, escena: str, destino: Path) -> Path:
    """Igual que en generar_video, con el guion de los reels. El retry está
    porque el servicio corta síntesis sin motivo (NoAudioReceived)."""
    import asyncio
    import time as _t

    import edge_tts

    t = GUION[idioma]

    async def _generar():
        await edge_tts.Communicate(t["voz"][escena], t["voz_neural"]).save(str(destino))

    for intento in range(3):
        try:
            asyncio.run(_generar())
            if destino.exists() and destino.stat().st_size >= 1000:
                return destino
        except Exception:                                # noqa: BLE001
            if intento == 2:
                raise
        _t.sleep(2 * (intento + 1))
    raise RuntimeError(f"La locución de {idioma}/{escena} salió vacía")


def _escena_mp4(ff: str, imagen: Path, voz: Path, destino: Path) -> Path:
    dur = round(_duracion(ff, voz) + RESPIRO, 2)
    filtros = (
        f"scale={ANCHO}:{ALTO}:force_original_aspect_ratio=decrease,"
        f"pad={ANCHO}:{ALTO}:(ow-iw)/2:(oh-ih)/2:color=#0a1020,"
        f"fade=t=in:st=0:d={FUNDIDO},fade=t=out:st={dur - FUNDIDO}:d={FUNDIDO},"
        "format=yuv420p"
    )
    subprocess.run(
        [ff, "-y", "-loglevel", "error",
         "-loop", "1", "-framerate", str(FPS), "-i", str(imagen),
         "-i", str(voz), "-t", str(dur),
         "-vf", filtros, "-af", "apad",
         "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
         "-shortest", str(destino)],
        check=True)
    return destino


def _escena_animada_mp4(ff: str, patron: str, cuadros: int, voz: Path,
                        destino: Path) -> Path:
    """Secuencia de cuadros (el contador) + voz. Los cuadros corren a 30 fps
    y el último se clava (tpad clone) hasta que la locución termina."""
    dur = round(_duracion(ff, voz) + RESPIRO, 2)
    cola = max(0.0, round(dur - cuadros / FPS, 2))
    filtros = (
        f"tpad=stop_mode=clone:stop_duration={cola},"
        f"fade=t=in:st=0:d={FUNDIDO},fade=t=out:st={dur - FUNDIDO}:d={FUNDIDO},"
        "format=yuv420p"
    )
    subprocess.run(
        [ff, "-y", "-loglevel", "error",
         "-framerate", str(FPS), "-i", patron,
         "-i", str(voz), "-t", str(dur),
         "-vf", filtros, "-af", "apad",
         "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
         "-shortest", str(destino)],
        check=True)
    return destino


def _concatenar(ff: str, escenas: list[Path], destino: Path) -> Path:
    lista = escenas[0].parent / f"{destino.parent.name}_reel_lista.txt"
    lista.write_text("".join(f"file '{p}'\n" for p in escenas), encoding="utf-8")
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(lista), "-c", "copy", "-movflags", "+faststart", str(destino)],
        check=True)
    return destino


def generar() -> list[Path]:
    ff = _ffmpeg()
    salidas: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="mv-reel-") as tmp:
        carpeta = Path(tmp)
        puerto = _puerto_libre()
        base = f"http://127.0.0.1:{puerto}"
        servidor = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "webapp.backend.api:app",
             "--port", str(puerto), "--log-level", "warning"],
            cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            _esperar_api(base)
            corrida_id = _correr_corrida(base)
            for idioma in GUION:
                fotos = _capturas_movil(idioma, base, corrida_id, carpeta)
                cara = clip_presentador(idioma)
                reloj_cara = 0.0
                partes: list[Path] = []
                for escena in ESCENAS:
                    voz = _voz_recortada(
                        ff,
                        _locucion(idioma, escena, carpeta / f"{idioma}_r_{escena}.mp3"),
                        carpeta / f"{idioma}_r_{escena}.wav")
                    mp4 = carpeta / f"{idioma}_r_{escena}.mp4"
                    if escena == "hook":
                        img = _escena_hook(idioma, carpeta / f"{idioma}_hook.png")
                        partes.append(_escena_mp4(ff, img, voz, mp4))
                    elif escena == "canales":
                        img = _escena_canales(idioma, carpeta / f"{idioma}_canales.png")
                        partes.append(_escena_mp4(ff, img, voz, mp4))
                    elif escena == "contador":
                        cuadros = _escena_contador(idioma, carpeta)
                        patron = str(carpeta / f"{idioma}_contador_%03d.png")
                        partes.append(_escena_animada_mp4(ff, patron, len(cuadros),
                                                          voz, mp4))
                    elif escena == "cta":
                        img = _escena_cta(idioma, carpeta / f"{idioma}_cta.png")
                        partes.append(_escena_mp4(ff, img, voz, mp4))
                    else:                                # panel · prospectos · analisis
                        img = _escena_captura(idioma, escena, fotos[escena],
                                              carpeta / f"{idioma}_{escena}.png",
                                              con_cara=bool(cara))
                        partes.append(_escena_mp4(ff, img, voz, mp4))
                    if cara:
                        # El recuadro se pega sobre la escena ya armada, y el
                        # clip sigue avanzando de una escena a la otra.
                        con_cara, reloj_cara = _con_presentador(
                            ff, partes[-1], cara, reloj_cara,
                            carpeta / f"{idioma}_pip_{escena}.mp4")
                        partes[-1] = con_cara
                destino = DESTINO / idioma / "reel.mp4"
                salidas.append(_concatenar(ff, partes, destino))
                print(f"  ✓ {destino.relative_to(RAIZ)}  "
                      f"({destino.stat().st_size // 1024} KB · "
                      f"{_duracion(ff, destino):.0f} s"
                      f"{' · con presentador' if cara else ''})")
        finally:
            servidor.terminate()
            servidor.wait(timeout=10)
    return salidas


if __name__ == "__main__":
    generar()
