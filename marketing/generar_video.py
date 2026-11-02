"""
MV Cliente IA · generador del video demo en tres idiomas
=========================================================
Produce `landing/video/{es,pt,en}/demo.mp4`: el video que muestra la landing
y que enlazan los correos. Cada idioma lleva SU video: capturas de la
aplicación real corriendo en ese idioma, placas con la marca que corresponde
(MV Cliente IA en es/pt, MV SearchCostumer AI en inglés) y locución generada
en el idioma del receptor.

    python3 -m marketing.generar_video

No se versiona un video "a mano": igual que la landing y los banners, si hay
que cambiar algo se cambia acá y se regenera, porque tres videos editados por
separado se desincronizan a la primera corrección.

Además de requirements-dev necesita: `edge-tts` (locución neural; usa la red),
`playwright` (capturas; usa el Chromium del sistema, no descarga nada) e
`imageio-ffmpeg` (un ffmpeg completo con H.264/AAC — el de Playwright sólo
sabe VP8). Ninguna se importa arriba del todo: son opcionales y el resto de
`marketing` tiene que funcionar sin ellas.
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

from . import musica
from .generar_banners import APAGADO, ICONO, NAVY, NAVY2, TINTA, VERDE, _fuente

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "landing" / "video"

ANCHO, ALTO = 1280, 720
FPS = 30
FUNDIDO = 0.3          # segundos de fade a la entrada y a la salida de cada escena
RESPIRO = 0.8          # aire después de que termina la voz de cada escena
DOMINIO_DEMO = "mvkobranzaia.com"

# El orden de las escenas es el del pipeline; "portada" y "cierre" son placas
# generadas con PIL, el resto capturas de la aplicación. Va TODO el producto:
# faltaban competencia y análisis y el video vendía la mitad de la app.
ESCENAS = ("portada", "explorar", "modelos", "competencia", "prospectos", "decisores",
           "correo_texto", "correo_html", "linkedin", "analisis", "marketing", "cierre")

# Hacia dónde se acerca la cámara en cada captura: (x, y) como fracción del
# ancho y el alto, y el zoom final. Un acercamiento lento a la parte que
# nombra la voz: con las capturas quietas el video se sentía una
# presentación de diapositivas.
FOCO = {
    "portada": (0.5, 0.5, 1.04), "cierre": (0.5, 0.5, 1.04),
    "explorar": (0.55, 0.30, 1.10), "modelos": (0.45, 0.22, 1.22),
    "competencia": (0.55, 0.40, 1.12), "prospectos": (0.55, 0.25, 1.14),
    "decisores": (0.5, 0.35, 1.10), "correo_texto": (0.5, 0.45, 1.10),
    "correo_html": (0.5, 0.55, 1.10), "linkedin": (0.5, 0.55, 1.12),
    "analisis": (0.55, 0.55, 1.10), "marketing": (0.5, 0.20, 1.12),
}
ESCALA_CAPTURA = 2     # capturas al doble: el zoom no se ve pixelado

GUION: dict[str, dict] = {
    "es": {
        "marca": ("MV CLIENTE", "IA"),
        # Voz neural de Microsoft (edge-tts): es-UY = rioplatense, la misma
        # familia de voz que usa MV Kobra AI. gTTS quedó atrás: sonaba a
        # traductor, no a persona.
        "voz_neural": "es-UY-MateoNeural",
        "portada_sub": "Pegá el enlace de tu producto.\nEl agente sale a buscar tus clientes.",
        "cierre_sub": "Buscá · Contactá · Cerrá",
        "voz": {
            "portada": "MV Cliente IA. Pegá el enlace de tu producto, "
                       "y el agente sale a buscar tus clientes.",
            "explorar": "Seis fases automáticas: investiga tu producto, mapea la "
                        "competencia, arma las campañas, encuentra empresas, ubica "
                        "a los decisores y escribe los correos.",
            "competencia": "Tu competencia directa, agrupada por zona hasta el barrio, "
                           "con sus redes y los seguidores públicos de cada una.",
            "analisis": "Y la pestaña de análisis proyecta tu negocio con tus "
                        "números: clientes, ventas, gastos y resultado neto hasta "
                        "veinticuatro meses, en tres escenarios.",
            "prospectos": "La lista llega ordenada por probabilidad de cierre, "
                          "con ciudad y barrio, y se filtra por zona.",
            "decisores": "De cada empresa, los cargos que deciden, cada uno con su idioma.",
            "correo_texto": "Los correos salen personalizados y en el idioma del país "
                            "de quien los recibe: español, portugués o inglés.",
            "correo_html": "Con versión HTML lista para enviar, con banner y enlace a tu web.",
            "linkedin": "Y el mensaje de LinkedIn con su nota de invitación, ya "
                        "recortada a los trescientos caracteres.",
            "modelos": "Elegís el modelo de inteligencia artificial que quieras, del más "
                       "capaz al más económico, sin tocar nada técnico.",
            "marketing": "Y la pestaña de marketing digital audita tu sitio y tus redes de "
                         "verdad, te compara con tu competencia y te dice qué hacer primero.",
            "cierre": "MV Cliente IA. Vos aparecés y cerrás.",
        },
        "titulos": {
            "explorar": "Seis fases automáticas", "modelos": "Elegí tu modelo de IA",
            "competencia": "Competencia por zona, hasta el barrio",
            "prospectos": "Clientes por probabilidad de cierre",
            "decisores": "Los cargos que deciden",
            "correo_texto": "Correos en el idioma de cada país",
            "correo_html": "HTML listo para enviar",
            "linkedin": "Mensaje e invitación de LinkedIn",
            "analisis": "Tu negocio proyectado a 24 meses",
            "marketing": "Marketing digital, medido de verdad",
        },
    },
    "pt": {
        "marca": ("MV CLIENTE", "IA"),
        "voz_neural": "pt-BR-AntonioNeural",
        "portada_sub": "Cole o link do seu produto.\nO agente sai para buscar seus clientes.",
        "cierre_sub": "Busque · Contate · Feche",
        "voz": {
            "portada": "MV Cliente IA. Cole o link do seu produto, "
                       "e o agente sai para buscar os seus clientes.",
            "explorar": "Seis fases automáticas: pesquisa o seu produto, mapeia a "
                        "concorrência, monta as campanhas, encontra empresas, localiza "
                        "os decisores e escreve os e-mails.",
            "competencia": "A sua concorrência direta, agrupada por região até o bairro, "
                           "com as redes e os seguidores públicos de cada uma.",
            "analisis": "E a aba de análise projeta o seu negócio com os seus "
                        "números: clientes, vendas, custos e resultado líquido até "
                        "vinte e quatro meses, em três cenários.",
            "prospectos": "A lista chega ordenada por probabilidade de fechamento, "
                          "com cidade e bairro, e se filtra por região.",
            "decisores": "De cada empresa, os cargos que decidem, cada um com o seu idioma.",
            "correo_texto": "Os e-mails saem personalizados e no idioma do país de "
                            "quem recebe: espanhol, português ou inglês.",
            "correo_html": "Com versão HTML pronta para enviar, com banner e link "
                           "para o seu site.",
            "linkedin": "E a mensagem do LinkedIn com a nota de convite, já dentro "
                        "dos trezentos caracteres.",
            "modelos": "Você escolhe o modelo de inteligência artificial que quiser, do "
                       "mais capaz ao mais econômico, sem mexer em nada técnico.",
            "marketing": "E a aba de marketing digital audita o seu site e as suas redes de "
                         "verdade, compara você com a concorrência e diz o que fazer primeiro.",
            "cierre": "MV Cliente IA. Você aparece e fecha.",
        },
        "titulos": {
            "explorar": "Seis fases automáticas", "modelos": "Escolha o seu modelo de IA",
            "competencia": "Concorrência por região, até o bairro",
            "prospectos": "Clientes por probabilidade de fechamento",
            "decisores": "Os cargos que decidem",
            "correo_texto": "E-mails no idioma de cada país",
            "correo_html": "HTML pronto para enviar",
            "linkedin": "Mensagem e convite do LinkedIn",
            "analisis": "O seu negócio projetado em 24 meses",
            "marketing": "Marketing digital, medido de verdade",
        },
    },
    "en": {
        "marca": ("MV SearchCostumer", "AI"),
        "voz_neural": "en-US-GuyNeural",
        "portada_sub": "Paste your product's link.\nThe agent goes out to find your customers.",
        "cierre_sub": "Find · Reach · Close",
        "voz": {
            "portada": "MV SearchCostumer AI. Paste your product's link, "
                       "and the agent goes out to find your customers.",
            "explorar": "Six automatic phases: it researches your product, maps the "
                        "competition, builds the campaigns, finds companies, locates "
                        "the decision makers and writes the emails.",
            "competencia": "Your direct competitors, grouped by area down to the "
                           "neighborhood, with their social profiles and public follower counts.",
            "analisis": "And the analysis tab projects your business with your "
                        "numbers: customers, sales, costs and net result up to "
                        "twenty-four months, across three scenarios.",
            "prospectos": "The list arrives ranked by likelihood to close, with "
                          "city and neighborhood, and you can filter it by area.",
            "decisores": "For each company, the roles that decide, each with their language.",
            "correo_texto": "Emails go out personalized, in the language of the "
                            "recipient's country: Spanish, Portuguese or English.",
            "correo_html": "With an HTML version ready to send, with a banner and a "
                           "link to your site.",
            "linkedin": "Plus the LinkedIn message and its invitation note, already "
                        "under three hundred characters.",
            "modelos": "You pick the artificial intelligence model you want, from the most "
                       "capable to the most economical, without touching anything technical.",
            "marketing": "And the digital marketing tab audits your real website and social "
                         "profiles, compares you with your competitors and tells you what to fix first.",
            "cierre": "MV SearchCostumer AI. You show up and close.",
        },
        "titulos": {
            "explorar": "Six automatic phases", "modelos": "Pick your AI model",
            "competencia": "Competitors by area, down to the neighborhood",
            "prospectos": "Customers ranked by likelihood to close",
            "decisores": "The roles that decide",
            "correo_texto": "Emails in each country's language",
            "correo_html": "HTML ready to send",
            "linkedin": "LinkedIn message and invitation",
            "analisis": "Your business projected over 24 months",
            "marketing": "Digital marketing, actually measured",
        },
    },
}


# ---------------------------------------------------------------------------
# Placas (portada y cierre)
# ---------------------------------------------------------------------------
def _placa_fondo() -> Image.Image:
    """Degradado vertical navy — la versión 1280×720 del fondo de los banners."""
    img = Image.new("RGB", (ANCHO, ALTO), NAVY)
    px = img.load()
    for y in range(ALTO):
        t = y / ALTO * 0.7
        c = tuple(int(NAVY[i] + (NAVY2[i] - NAVY[i]) * t) for i in range(3))
        for x in range(ANCHO):
            px[x, y] = c
    return img


def _placa(idioma: str, escena: str, destino: Path) -> Path:
    t = GUION[idioma]
    img = _placa_fondo()
    d = ImageDraw.Draw(img)

    if ICONO.exists():
        ico = Image.open(ICONO).convert("RGBA").resize((96, 96), Image.LANCZOS)
        img.paste(ico, (ANCHO // 2 - 48, 170), ico)

    marca, marca2 = t["marca"]
    f_marca = _fuente(64)
    w = d.textlength(marca, font=f_marca) + 18 + d.textlength(marca2, font=f_marca)
    x = (ANCHO - w) // 2
    d.text((x, 300), marca, font=f_marca, fill=TINTA)
    d.text((x + d.textlength(marca, font=f_marca) + 18, 300), marca2,
           font=f_marca, fill=VERDE)

    sub = t["portada_sub"] if escena == "portada" else t["cierre_sub"]
    f_sub = _fuente(28)
    y = 410
    for linea in sub.split("\n"):
        d.text(((ANCHO - d.textlength(linea, font=f_sub)) // 2, y),
               linea, font=f_sub, fill=APAGADO)
        y += 42

    d.rectangle([ANCHO // 2 - 40, 530, ANCHO // 2 + 40, 534], fill=VERDE)
    img.save(destino)
    return destino


def _rotulo(idioma: str, escena: str, n: int, total: int, destino: Path) -> Path:
    """Capa transparente sobre la captura: el titular de la escena abajo a la
    izquierda (lo que la voz está diciendo, para quien mira sin sonido —
    la mayoría en la web arranca el video silenciado) y el avance arriba."""
    img = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    titulo = GUION[idioma]["titulos"][escena]
    f_tit, f_paso = _fuente(30), _fuente(17)
    ancho = int(d.textlength(titulo, font=f_tit)) + 64
    x0, y0 = 40, ALTO - 118
    d.rounded_rectangle([x0, y0, x0 + ancho, y0 + 70], radius=16, fill=(10, 16, 32, 232),
                        outline=(36, 52, 79, 255), width=2)
    d.rounded_rectangle([x0 + 18, y0 + 18, x0 + 24, y0 + 52], radius=3, fill=VERDE + (255,))
    d.text((x0 + 40, y0 + 16), titulo, font=f_tit, fill=TINTA + (255,))
    paso = f"{n:02d} / {total:02d}"
    w = int(d.textlength(paso, font=f_paso)) + 28
    d.rounded_rectangle([ANCHO - 40 - w, 28, ANCHO - 40, 62], radius=17, fill=(10, 16, 32, 215),
                        outline=(36, 52, 79, 255), width=2)
    d.text((ANCHO - 40 - w + 14, 35), paso, font=f_paso, fill=VERDE + (255,))
    # Barra de avance fina bajo el número: de un vistazo, cuánto falta.
    largo = int((w - 20) * n / total)
    d.rounded_rectangle([ANCHO - 30 - w, 68, ANCHO - 30 - w + largo, 71], radius=2, fill=VERDE + (255,))
    img.save(destino)
    return destino


# ---------------------------------------------------------------------------
# Capturas de la aplicación
# ---------------------------------------------------------------------------
def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _esperar_api(base: str, segundos: int = 30) -> None:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(f"{base}/api/salud", timeout=2):
                return
        except OSError:
            time.sleep(0.3)
    raise RuntimeError("El backend no levantó a tiempo")


def _correr_corrida(base: str, idioma: str = "es") -> str:
    # Una corrida por idioma: los rótulos que arma el servidor (olas,
    # regiones, detalle de cada fase) salen en el idioma de la corrida, y el
    # video en inglés mostraba «América Latina» y «mundo».
    cuerpo = json.dumps({"dominio": DOMINIO_DEMO, "modo": "demo",
                         "prospectos": 60, "idioma": idioma}).encode()
    req = urllib.request.Request(f"{base}/api/corridas", data=cuerpo,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        corrida_id = json.load(r)["id"]
    limite = time.monotonic() + 60
    while time.monotonic() < limite:
        with urllib.request.urlopen(f"{base}/api/corridas/{corrida_id}", timeout=5) as r:
            if json.load(r)["estado"] == "listo":
                return corrida_id
        time.sleep(0.4)
    raise RuntimeError("La corrida demo no terminó a tiempo")


def _competidores_reales(base: str, corrida_id: str, medidos: dict | None = None) -> dict:
    """La corrida demo con los datos PÚBLICOS y reales de sus competidores.

    Los competidores de la demo son empresas reales, así que el video no les
    puede inventar barrio ni seguidores. Se hace lo mismo que el modo real:
    se lee su sitio (redes que enlaza, dirección que publica) y se miden las
    cifras públicas de esas redes (cliente_ia/redes_publicas.py), con la
    fecha de hoy. Lo que la red o el sitio no muestren queda vacío o
    «no disponible», igual que en la app."""
    import os

    from cliente_ia import redes_publicas, ubicacion
    from cliente_ia.modelos import Competidor
    from cliente_ia.proveedores import contactos
    from cliente_ia.proveedores.web import bajar

    with urllib.request.urlopen(f"{base}/api/corridas/{corrida_id}", timeout=10) as r:
        corrida = json.load(r)
    campos = Competidor.__dataclass_fields__
    comps = [Competidor(**{k: v for k, v in d.items() if k in campos})
             for d in corrida.get("competidores", [])]
    if medidos:
        # Ya medidos en la corrida de otro idioma: los mismos datos, sin
        # volver a pedirle nada a los sitios ni a las redes.
        corrida["competidores"] = [{**c.a_dict(), **medidos.get(c.dominio, {})}
                                   for c in comps]
        return corrida
    for c in comps:
        try:
            html = bajar(c.dominio, 8)
        except Exception:                                  # noqa: BLE001
            continue
        c.redes = contactos.redes_de_html(html, c.dominio)
        u = ubicacion.ubicar(html, c.pais)
        c.direccion, c.ciudad, c.barrio = (u.get("direccion", ""), u.get("ciudad", ""),
                                           u.get("barrio", ""))
        if u.get("pais"):
            c.pais = u["pais"]
    os.environ["MVCLIENTE_METRICAS_REDES"] = "1"
    redes_publicas.medir(comps)
    corrida["competidores"] = [c.a_dict() for c in comps]
    return corrida


def _capturas(idioma: str, base: str, corrida_id: str, carpeta: Path,
              corrida: dict | None = None) -> dict[str, Path]:
    from playwright.sync_api import sync_playwright

    # El Chromium preinstalado del sistema: Playwright no descarga nada.
    # `chrome-linux*`: las versiones nuevas lo instalan en chrome-linux64.
    ejecutables = sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome"))
    lanzar = {"executable_path": str(ejecutables[-1])} if ejecutables else {}

    salida: dict[str, Path] = {}
    with sync_playwright() as p:
        navegador = p.chromium.launch(**lanzar)
        ctx = navegador.new_context(viewport={"width": ANCHO, "height": ALTO},
                                    device_scale_factor=ESCALA_CAPTURA)
        # El idioma y la corrida se fijan ANTES de que cargue la app, como si
        # el usuario ya los tuviera guardados de una sesión anterior.
        ctx.add_init_script(
            f"localStorage.setItem('mvcliente_idioma', '{idioma}');"
            f"localStorage.setItem('mvcliente_corrida', '{corrida_id}');")
        # Los supuestos de Análisis, para los KPI de Marketing digital.
        ctx.add_init_script(
            "localStorage.setItem('mvcliente_analisis_form', JSON.stringify({precio: '99', "
            "nuevos_por_mes: '3', churn_pct: '5', gasto_fijo: '500', costo_por_cliente: '10', "
            "gasto_ads: '300', cac: '150'}));")
        if corrida:
            # La app prefiere la corrida guardada en el navegador (modo sin
            # estado, ver estado.js): así ve los competidores medidos.
            ctx.add_init_script(
                f"localStorage.setItem('mvcliente_corrida_datos', {json.dumps(json.dumps(corrida))});")
        pagina = ctx.new_page()

        def foto(nombre: str) -> None:
            destino = carpeta / f"{idioma}_{nombre}.png"
            pagina.screenshot(path=str(destino))
            salida[nombre] = destino

        pagina.goto(f"{base}/#/")
        pagina.wait_for_selector(".fase.listo >> nth=5", timeout=20000)
        foto("explorar")

        # El selector de modelo, donde se busca: origen «Investigación con IA».
        # Sólo aparece con una clave cargada: una de mentira, puesta SÓLO
        # para esta escena (no lanza ninguna búsqueda) y sacada al terminar.
        # Antes vivía en todo el recorrido y Análisis intentaba usarla: el
        # video mostraba el cartel rojo de «clave rechazada».
        pagina.evaluate(
            "localStorage.setItem('mvcliente_clave_ia', 'sk-ant-api03-' + 'x'.repeat(95));"
            "localStorage.setItem('mvcliente_proveedor_ia', 'claude');"
            "localStorage.setItem('mvcliente_modelos_ia', "
            "JSON.stringify({claude: {modelo: 'claude-opus-5-5'}}));")
        pagina.reload()
        pagina.wait_for_selector(".fase.listo >> nth=5", timeout=20000)
        pagina.locator("#modo").select_option("llm")
        pagina.wait_for_selector("#modelo-explorar", timeout=10000)
        pagina.evaluate("window.scrollTo(0, 0)")
        pagina.wait_for_timeout(300)
        foto("modelos")
        pagina.locator("#modo").select_option("demo")
        pagina.evaluate("localStorage.removeItem('mvcliente_clave_ia');"
                        "localStorage.removeItem('mvcliente_modelos_ia');")

        # Fase 2 abierta: los competidores por ola y ciudad, con barrio y
        # cifras públicas de sus redes. Se sube la cabecera de la fase al
        # borde: con scroll_into_view de la primera tarjeta, las de abajo
        # (justo las que tenían seguidores) quedaban cortadas.
        pagina.locator(".fase").nth(1).locator("button").first.click()
        pagina.wait_for_selector(".comp", timeout=20000)
        pagina.locator(".fase").nth(1).evaluate("e => e.scrollIntoView({block: 'start'})")
        pagina.wait_for_timeout(400)
        foto("competencia")

        pagina.goto(f"{base}/#/prospectos")
        pagina.wait_for_selector("table, .pers, .fila", timeout=20000)
        # Con un barrio elegido en el filtro de zona: lo nuevo se ve.
        zona = pagina.locator("select[aria-label]")
        if zona.count():
            barrio = next((o for o in zona.locator("option").all_inner_texts() if " · " in o), None)
            if barrio:
                zona.select_option(label=barrio)
                pagina.wait_for_timeout(300)
        foto("prospectos")

        pagina.goto(f"{base}/#/decisores")
        pagina.wait_for_selector("table, .pers, .fila", timeout=20000)
        foto("decisores")

        pagina.goto(f"{base}/#/correos")
        pagina.wait_for_selector(".mail", timeout=20000)
        foto("correo_texto")

        primer_mail = pagina.locator(".mail").first
        primer_mail.locator(".pest").nth(1).click()      # pestaña HTML
        primer_mail.locator("iframe.vista-html").wait_for(timeout=10000)
        pagina.wait_for_timeout(700)                     # el iframe pinta el correo
        foto("correo_html")

        primer_mail.locator(".pest").nth(2).click()      # pestaña LinkedIn
        primer_mail.locator("pre").first.wait_for(timeout=10000)
        foto("linkedin")

        # Análisis: se cargan números de ejemplo y se muestra la proyección
        # (la parte financiera es matemática pura, corre sin clave de IA).
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

        # Marketing digital: la auditoría REAL del sitio de la demo (lee
        # mvkobranzaia.com y su competencia en el momento; nada inventado).
        pagina.goto(f"{base}/#/marketing")
        pagina.locator("button.primary").first.click()
        pagina.wait_for_selector(".mk-checks", timeout=120000)
        pagina.evaluate("window.scrollTo(0, 0)")
        pagina.wait_for_timeout(400)
        foto("marketing")

        navegador.close()
    return salida


# ---------------------------------------------------------------------------
# Audio y armado
# ---------------------------------------------------------------------------
def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def _locucion(idioma: str, escena: str, destino: Path) -> Path:
    """Voz neural por edge-tts (es-UY para el rioplatense, pt-BR y en-US
    nativas). El mp3 sale con la duración exacta de la locución: la escena
    dura eso más el respiro, así el audio nunca corre detrás de la imagen."""
    import asyncio

    import edge_tts

    t = GUION[idioma]

    async def _generar():
        await edge_tts.Communicate(t["voz"][escena], t["voz_neural"]).save(str(destino))

    # El servicio a veces corta una síntesis sin motivo (NoAudioReceived):
    # perder los 30 screenshots por una locución caída no tiene sentido.
    # Cinco intentos con espera creciente: con tres, una frase en inglés que
    # al minuto siguiente salía bien tiró abajo la generación entera.
    for intento in range(5):
        try:
            asyncio.run(_generar())
            if destino.exists() and destino.stat().st_size >= 1000:
                return destino
        except Exception:                                # noqa: BLE001
            if intento == 4:
                raise
        import time as _t
        _t.sleep(3 * (intento + 1))
    raise RuntimeError(f"La locución de {idioma}/{escena} salió vacía")


def _voz_recortada(ff: str, mp3: Path, destino: Path) -> Path:
    """Recorta el silencio que edge-tts deja en los bordes de cada síntesis
    (~0,7 s al final, ~0,1 al principio). Sin esto, entre escena y escena se
    acumulaban casi dos segundos de silencio y el video se sentía con lag —
    la voz estaba bien; lo lento eran los bordes."""
    subprocess.run(
        [ff, "-y", "-loglevel", "error", "-i", str(mp3),
         "-af",
         "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
         "areverse,"
         "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.12,"
         "areverse",
         str(destino)],
        check=True)
    return destino


def _duracion(ff: str, medio: Path) -> float:
    r = subprocess.run([ff, "-i", str(medio)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        raise RuntimeError(f"No se pudo medir {medio.name}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def _escena_mp4(ff: str, imagen: Path, voz: Path, destino: Path,
                foco: tuple[float, float, float] = (0.5, 0.5, 1.0),
                rotulo: Path | None = None) -> Path:
    dur = round(_duracion(ff, voz) + RESPIRO, 2)
    cuadros = int(dur * FPS)
    fx, fy, zoom = foco
    # zoompan sobre una imagen grande (4×) para que el paneo no tiemble: a
    # la resolución de salida, el redondeo a píxel enteros se nota.
    grande_w, grande_h = ANCHO * 4, ALTO * 4
    mov = (f"scale={grande_w}:{grande_h}:force_original_aspect_ratio=decrease,"
           f"pad={grande_w}:{grande_h}:(ow-iw)/2:(oh-ih)/2:color=#0a1020,"
           f"zoompan=z='1+({zoom}-1)*on/{cuadros}':"
           f"x='(iw-iw/zoom)*{fx}':y='(ih-ih/zoom)*{fy}':d={cuadros}:s={ANCHO}x{ALTO}:fps={FPS}")
    entradas = ["-loop", "1", "-framerate", str(FPS), "-i", str(imagen), "-i", str(voz)]
    if rotulo:
        entradas += ["-loop", "1", "-framerate", str(FPS), "-i", str(rotulo)]
        grafo = (f"[0:v]{mov}[m];[2:v]format=rgba,fade=t=in:st=0.35:d=0.45:alpha=1[r];"
                 f"[m][r]overlay=0:0,")
    else:
        grafo = f"[0:v]{mov},"
    grafo += (f"fade=t=in:st=0:d={FUNDIDO},fade=t=out:st={dur - FUNDIDO}:d={FUNDIDO},"
              "format=yuv420p[v]")
    subprocess.run(
        [ff, "-y", "-loglevel", "error", *entradas, "-t", str(dur),
         "-filter_complex", grafo, "-map", "[v]", "-map", "1:a", "-af", "apad",
         # CRF 26 + slow: con el zoom en movimiento, el 22 de antes daba
         # 12 MB por minuto — mucho para la web y para un enlace en un correo.
         "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
         "-shortest", str(destino)],
        check=True)
    return destino


def _tiempo_vtt(seg: float) -> str:
    m, s = divmod(max(0.0, seg), 60)
    return f"00:{int(m):02d}:{s:06.3f}"


def _extras_web(ff: str, idioma: str, partes: list[Path], carpeta_destino: Path,
                captura: Path) -> None:
    """Lo que acompaña al mp4 en la web: capítulos clicables, subtítulos con
    la locución (la mayoría arranca el video SIN sonido) y una portada propia
    con el botón de reproducir — antes la portada era el banner del correo."""
    t, inicio, capitulos, vtt = GUION[idioma], 0.0, [], ["WEBVTT", ""]
    for escena, parte in zip(ESCENAS, partes, strict=True):
        dur = _duracion(ff, parte)
        if escena in t["titulos"]:
            capitulos.append({"t": round(inicio, 1), "titulo": t["titulos"][escena]})
        vtt += [f"{_tiempo_vtt(inicio + 0.1)} --> {_tiempo_vtt(inicio + dur - FUNDIDO)}",
                t["voz"][escena], ""]
        inicio += dur
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    (carpeta_destino / "capitulos.json").write_text(
        json.dumps({"duracion": round(inicio, 1), "capitulos": capitulos},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (carpeta_destino / "demo.vtt").write_text("\n".join(vtt), encoding="utf-8")
    _portada(idioma, captura, inicio, carpeta_destino / "poster.jpg")


def _portada(idioma: str, captura: Path, segundos: float, destino: Path) -> Path:
    from PIL import ImageFilter
    fondo = Image.open(captura).convert("RGB").resize((ANCHO, ALTO), Image.LANCZOS)
    fondo = fondo.filter(ImageFilter.GaussianBlur(3))
    velo = Image.new("RGB", (ANCHO, ALTO), NAVY)
    img = Image.blend(fondo, velo, 0.62)
    d = ImageDraw.Draw(img)
    marca, marca2 = GUION[idioma]["marca"]
    f_marca, f_sub = _fuente(58), _fuente(26)
    w = d.textlength(marca, font=f_marca) + 16 + d.textlength(marca2, font=f_marca)
    x = (ANCHO - w) // 2
    d.text((x, 168), marca, font=f_marca, fill=TINTA)
    d.text((x + d.textlength(marca, font=f_marca) + 16, 168), marca2, font=f_marca, fill=VERDE)
    sub = GUION[idioma]["portada_sub"].split("\n")[0]
    d.text(((ANCHO - d.textlength(sub, font=f_sub)) // 2, 250), sub, font=f_sub, fill=APAGADO)
    cx, cy, r = ANCHO // 2, 430, 64
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=VERDE)
    d.polygon([(cx - 20, cy - 32), (cx - 20, cy + 32), (cx + 34, cy)], fill=NAVY)
    m, s = divmod(int(round(segundos)), 60)
    etiqueta = f"{m}:{s:02d}"
    f_dur = _fuente(22)
    wd = d.textlength(etiqueta, font=f_dur) + 30
    d.rounded_rectangle([cx - wd / 2, cy + r + 26, cx + wd / 2, cy + r + 62], radius=18,
                        fill=NAVY2, outline=(36, 52, 79))
    d.text((cx - wd / 2 + 15, cy + r + 31), etiqueta, font=f_dur, fill=TINTA)
    img.save(destino, quality=88)
    return destino


def _concatenar(ff: str, escenas: list[Path], destino: Path) -> Path:
    # La lista de concat es un archivo de trabajo: vive con las escenas en el
    # directorio temporal, no al lado del mp4 final (terminaba commiteada).
    lista = escenas[0].parent / f"{destino.parent.name}_lista.txt"
    lista.write_text("".join(f"file '{p}'\n" for p in escenas), encoding="utf-8")
    destino.parent.mkdir(parents=True, exist_ok=True)
    # Mismo códec y parámetros en todas las escenas: se concatena sin recodificar.
    subprocess.run(
        [ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(lista), "-c", "copy", "-movflags", "+faststart", str(destino)],
        check=True)
    return destino


def generar() -> list[Path]:
    ff = _ffmpeg()
    salidas: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="mv-video-") as tmp:
        carpeta = Path(tmp)

        puerto = _puerto_libre()
        base = f"http://127.0.0.1:{puerto}"
        servidor = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "webapp.backend.api:app",
             "--port", str(puerto), "--log-level", "warning"],
            cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            _esperar_api(base)
            medidos: dict = {}
            for idioma in GUION:
                corrida_id = _correr_corrida(base, idioma)
                corrida = _competidores_reales(base, corrida_id, medidos)
                medidos = medidos or {
                    c["dominio"]: {k: c[k] for k in ("redes", "metricas", "ciudad",
                                                     "barrio", "direccion", "pais")}
                    for c in corrida["competidores"]}
                imagenes = _capturas(idioma, base, corrida_id, carpeta, corrida)
                imagenes["portada"] = _placa(idioma, "portada",
                                             carpeta / f"{idioma}_portada.png")
                imagenes["cierre"] = _placa(idioma, "cierre",
                                            carpeta / f"{idioma}_cierre.png")

                partes = []
                con_rotulo = [e for e in ESCENAS if e in GUION[idioma]["titulos"]]
                for escena in ESCENAS:
                    voz = _voz_recortada(
                        ff,
                        _locucion(idioma, escena, carpeta / f"{idioma}_{escena}.mp3"),
                        carpeta / f"{idioma}_{escena}.wav")
                    rotulo = (_rotulo(idioma, escena, con_rotulo.index(escena) + 1,
                                      len(con_rotulo), carpeta / f"{idioma}_{escena}_r.png")
                              if escena in con_rotulo else None)
                    partes.append(_escena_mp4(ff, imagenes[escena], voz,
                                              carpeta / f"{idioma}_{escena}.mp4",
                                              FOCO.get(escena, (0.5, 0.5, 1.0)), rotulo))
                destino = DESTINO / idioma / "demo.mp4"
                sin_musica = _concatenar(ff, partes, carpeta / idioma / "demo_voz.mp4")
                cama = musica.pista(ff, _duracion(ff, sin_musica), carpeta / f"{idioma}_cama.wav")
                destino.parent.mkdir(parents=True, exist_ok=True)
                salidas.append(musica.mezclar(ff, sin_musica, cama, destino))
                _extras_web(ff, idioma, partes, destino.parent, imagenes["competencia"])
                print(f"  ✓ {destino.relative_to(RAIZ)}  "
                      f"({destino.stat().st_size // 1024} KB · "
                      f"{_duracion(ff, destino):.0f} s)")
        finally:
            servidor.terminate()
            servidor.wait(timeout=10)
    return salidas


if __name__ == "__main__":
    generar()
