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

from .generar_banners import APAGADO, ICONO, NAVY, NAVY2, TINTA, VERDE, _fuente

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "landing" / "video"

ANCHO, ALTO = 1280, 720
FPS = 30
FUNDIDO = 0.4          # segundos de fade a la entrada y a la salida de cada escena
RESPIRO = 0.8          # aire después de que termina la voz de cada escena
DOMINIO_DEMO = "mvkobranzaia.com"

# El orden de las escenas es el del pipeline; "portada" y "cierre" son placas
# generadas con PIL, el resto capturas de la aplicación. Va TODO el producto:
# faltaban competencia y análisis y el video vendía la mitad de la app.
ESCENAS = ("portada", "explorar", "competencia", "prospectos", "decisores",
           "correo_texto", "correo_html", "linkedin", "analisis", "cierre")

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
            "competencia": "Tu competencia directa, con el país y el solapamiento "
                           "de cada competidor a la vista.",
            "analisis": "Y la pestaña de análisis proyecta tu negocio con tus "
                        "números: clientes, ventas, gastos y resultado neto hasta "
                        "veinticuatro meses, en tres escenarios.",
            "prospectos": "La lista llega ordenada por probabilidad de cierre, "
                          "con las señales de por qué contactar a cada empresa.",
            "decisores": "De cada empresa, los cargos que deciden, cada uno con su idioma.",
            "correo_texto": "Los correos salen personalizados y en el idioma del país "
                            "de quien los recibe: español, portugués o inglés.",
            "correo_html": "Con versión HTML lista para enviar, con banner y enlace a tu web.",
            "linkedin": "Y el mensaje de LinkedIn con su nota de invitación, ya "
                        "recortada a los trescientos caracteres.",
            "cierre": "MV Cliente IA. Vos aparecés y cerrás.",
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
            "competencia": "A sua concorrência direta, com o país e a sobreposição "
                           "de cada concorrente à vista.",
            "analisis": "E a aba de análise projeta o seu negócio com os seus "
                        "números: clientes, vendas, custos e resultado líquido até "
                        "vinte e quatro meses, em três cenários.",
            "prospectos": "A lista chega ordenada por probabilidade de fechamento, "
                          "com os sinais de por que contatar cada empresa.",
            "decisores": "De cada empresa, os cargos que decidem, cada um com o seu idioma.",
            "correo_texto": "Os e-mails saem personalizados e no idioma do país de "
                            "quem recebe: espanhol, português ou inglês.",
            "correo_html": "Com versão HTML pronta para enviar, com banner e link "
                           "para o seu site.",
            "linkedin": "E a mensagem do LinkedIn com a nota de convite, já dentro "
                        "dos trezentos caracteres.",
            "cierre": "MV Cliente IA. Você aparece e fecha.",
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
            "competencia": "Your direct competitors, with each one's country and "
                           "overlap in plain sight.",
            "analisis": "And the analysis tab projects your business with your "
                        "numbers: customers, sales, costs and net result up to "
                        "twenty-four months, across three scenarios.",
            "prospectos": "The list arrives ranked by likelihood to close, with "
                          "the signals for why to contact each company.",
            "decisores": "For each company, the roles that decide, each with their language.",
            "correo_texto": "Emails go out personalized, in the language of the "
                            "recipient's country: Spanish, Portuguese or English.",
            "correo_html": "With an HTML version ready to send, with a banner and a "
                           "link to your site.",
            "linkedin": "Plus the LinkedIn message and its invitation note, already "
                        "under three hundred characters.",
            "cierre": "MV SearchCostumer AI. You show up and close.",
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


def _correr_corrida(base: str) -> str:
    cuerpo = json.dumps({"dominio": DOMINIO_DEMO, "modo": "demo",
                         "prospectos": 60}).encode()
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


def _capturas(idioma: str, base: str, corrida_id: str, carpeta: Path) -> dict[str, Path]:
    from playwright.sync_api import sync_playwright

    # El Chromium preinstalado del sistema: Playwright no descarga nada.
    ejecutables = sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome"))
    lanzar = {"executable_path": str(ejecutables[-1])} if ejecutables else {}

    salida: dict[str, Path] = {}
    with sync_playwright() as p:
        navegador = p.chromium.launch(**lanzar)
        ctx = navegador.new_context(viewport={"width": ANCHO, "height": ALTO})
        # El idioma y la corrida se fijan ANTES de que cargue la app, como si
        # el usuario ya los tuviera guardados de una sesión anterior.
        ctx.add_init_script(
            f"localStorage.setItem('mvcliente_idioma', '{idioma}');"
            f"localStorage.setItem('mvcliente_corrida', '{corrida_id}');")
        pagina = ctx.new_page()

        def foto(nombre: str) -> None:
            destino = carpeta / f"{idioma}_{nombre}.png"
            pagina.screenshot(path=str(destino))
            salida[nombre] = destino

        pagina.goto(f"{base}/#/")
        pagina.wait_for_selector(".fase.listo >> nth=5", timeout=20000)
        foto("explorar")

        # Fase 2 abierta: la grilla de competidores con país y solapamiento.
        pagina.locator(".fase").nth(1).locator("button").first.click()
        pagina.wait_for_selector(".comp", timeout=20000)
        pagina.locator(".comp").first.scroll_into_view_if_needed()
        pagina.wait_for_timeout(400)
        foto("competencia")

        pagina.goto(f"{base}/#/prospectos")
        pagina.wait_for_selector("table, .pers, .fila", timeout=20000)
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
    for intento in range(3):
        try:
            asyncio.run(_generar())
            if destino.exists() and destino.stat().st_size >= 1000:
                return destino
        except Exception:                                # noqa: BLE001
            if intento == 2:
                raise
        import time as _t
        _t.sleep(2 * (intento + 1))
    raise RuntimeError(f"La locución de {idioma}/{escena} salió vacía")


def _duracion(ff: str, medio: Path) -> float:
    r = subprocess.run([ff, "-i", str(medio)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        raise RuntimeError(f"No se pudo medir {medio.name}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


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
            corrida_id = _correr_corrida(base)
            for idioma in GUION:
                imagenes = _capturas(idioma, base, corrida_id, carpeta)
                imagenes["portada"] = _placa(idioma, "portada",
                                             carpeta / f"{idioma}_portada.png")
                imagenes["cierre"] = _placa(idioma, "cierre",
                                            carpeta / f"{idioma}_cierre.png")

                partes = []
                for escena in ESCENAS:
                    voz = _locucion(idioma, escena, carpeta / f"{idioma}_{escena}.mp3")
                    partes.append(_escena_mp4(ff, imagenes[escena], voz,
                                              carpeta / f"{idioma}_{escena}.mp4"))
                destino = DESTINO / idioma / "demo.mp4"
                salidas.append(_concatenar(ff, partes, destino))
                print(f"  ✓ {destino.relative_to(RAIZ)}  "
                      f"({destino.stat().st_size // 1024} KB · "
                      f"{_duracion(ff, destino):.0f} s)")
        finally:
            servidor.terminate()
            servidor.wait(timeout=10)
    return salidas


if __name__ == "__main__":
    generar()
