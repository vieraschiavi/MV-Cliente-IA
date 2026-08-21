"""La landing, mirada por un navegador de verdad.

Estos tres bugs pasaron la revisión de código y el resto de la suite, y los
encontró recién un Chromium abriendo la página:

1. **El botón «copiar clave» seguía visible después de un pago rechazado.**
   El navegador aplica el atributo `hidden` con `display:none`, pero cualquier
   regla de autor con `display` le gana — y `.btn` pone `inline-flex`. Leyendo
   el HTML el botón estaba oculto; en pantalla no.
2. **La barra de navegación se partió en dos líneas.** Al agregar el enlace
   «Demo» los seis enlaces dejaron de entrar en los 1080px de `.wrap`: «Cómo
   funciona» se cortó al medio y el botón verde se salió de la pantalla. El
   `.py` que la genera se seguía leyendo perfecto.
3. **La barra arrastraba scroll horizontal a TODA la página en el celular.**
   Medía 519px en una pantalla de 320. El arreglo del punto 2 —evitar que el
   texto se parta— fue justo lo que lo causó, así que los dos casos tienen que
   medirse juntos o uno vuelve mientras se arregla el otro.

Los tres son de disposición: no hay forma de detectarlos sin renderizar. Si en
la máquina no hay Playwright o no está el Chromium, el test se saltea (el CI de
Windows y el resto de la suite no dependen de esto).
"""
from __future__ import annotations

import http.server
import os
import socketserver
import threading
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
LANDING = RAIZ / "landing"

# El ancho a partir del cual los enlaces del menú se muestran: por debajo se
# esconden enteros (ver el @media de generar_landing.py).
CON_MENU = 1080


def _chromium() -> str | None:
    """El binario que trae el entorno; Playwright solo no lo encuentra si no
    se corrió `playwright install` (y acá no se puede: no hay red)."""
    for base in (os.getenv("PLAYWRIGHT_BROWSERS_PATH"), "/opt/pw-browsers"):
        if not base:
            continue
        candidatos = sorted(Path(base).glob("chromium*/chrome-linux/chrome"))
        if candidatos:
            return str(candidatos[-1])
    return None


@pytest.fixture(scope="module")
def sitio():
    if not (LANDING / "index.html").exists():
        pytest.skip("la landing no está generada (python3 -m marketing.generar_landing)")

    raiz = str(LANDING)

    class Manejador(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=raiz, **kw)

        def log_message(self, *a):        # sin ruido en la salida de pytest
            pass

    with socketserver.TCPServer(("127.0.0.1", 0), Manejador) as srv:
        hilo = threading.Thread(target=srv.serve_forever, daemon=True)
        hilo.start()
        try:
            yield f"http://127.0.0.1:{srv.server_address[1]}"
        finally:
            srv.shutdown()


@pytest.fixture(scope="module")
def navegador():
    pw_api = pytest.importorskip("playwright.sync_api")
    binario = _chromium()
    if not binario:
        pytest.skip("no hay un Chromium de Playwright en esta máquina")
    with pw_api.sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=binario, args=["--no-sandbox"])
        try:
            yield nav
        finally:
            nav.close()


# Lo que se mide de la barra, de una sola pasada: hacer varias llamadas
# separadas dejaba que el layout cambiara entre medición y medición.
_MEDIR = """() => {
  const barra = document.querySelector('nav .wrap');
  const cta = document.querySelector('nav .right .btn');
  const enlaces = [...document.querySelectorAll('.nlinks a')];
  const alto = e => e.getBoundingClientRect().height;
  return {
    scroll: document.documentElement.scrollWidth,
    ancho: document.documentElement.clientWidth,
    ctaAlto: alto(cta),
    ctaDerecha: cta.getBoundingClientRect().right,
    partidos: enlaces.filter(e => e.offsetParent && alto(e) > 40).map(e => e.textContent),
    visibles: enlaces.filter(e => e.offsetParent).length,
    desborda: barra.scrollWidth > barra.clientWidth + 1,
  };
}"""


@pytest.mark.parametrize("ancho", [1440, 1280, 1080, 1024, 900, 768, 480, 390, 320])
@pytest.mark.parametrize("idioma,ruta", [("es", "/"), ("pt", "/pt/"), ("en", "/en/")])
def test_la_barra_no_se_parte_ni_desborda(navegador, sitio, idioma, ruta, ancho):
    pag = navegador.new_page(viewport={"width": ancho, "height": 800})
    try:
        pag.goto(sitio + ruta, wait_until="domcontentloaded")
        m = pag.evaluate(_MEDIR)
    finally:
        pag.close()

    donde = f"[{idioma} @ {ancho}px]"
    assert m["scroll"] <= m["ancho"] + 1, (
        f"{donde} la página arrastra scroll horizontal "
        f"({m['scroll']}px de contenido en {m['ancho']}px de pantalla)")
    assert not m["partidos"], f"{donde} enlaces partidos en dos líneas: {m['partidos']}"
    assert m["ctaAlto"] <= 46, f"{donde} el botón del menú se partió (alto {m['ctaAlto']:.0f}px)"
    assert m["ctaDerecha"] <= m["ancho"] + 1, f"{donde} el botón del menú se sale de la pantalla"
    assert not m["desborda"], f"{donde} la barra desborda su propio ancho"
    # Y que la decisión sea la que se quiso: con lugar están los seis; sin
    # lugar no está ninguno a medias.
    assert m["visibles"] in (0, 6), f"{donde} quedaron {m['visibles']} enlaces visibles"
    if ancho > CON_MENU:
        assert m["visibles"] == 6, f"{donde} hay lugar de sobra y el menú no se muestra"


@pytest.mark.parametrize("idioma,ruta", [("es", "/"), ("pt", "/pt/"), ("en", "/en/")])
def test_el_formulario_de_demo_se_ve_y_valida(navegador, sitio, idioma, ruta):
    """Sin backend no se puede probar el envío, pero sí lo que decide el
    navegador solo: que el aviso arranque oculto (el bug del `[hidden]`) y que
    no deje mandar el formulario vacío ni con un correo inventado."""
    pag = navegador.new_page(viewport={"width": 1280, "height": 900})
    errores: list[str] = []
    pag.on("pageerror", lambda e: errores.append(str(e)))
    try:
        pag.goto(sitio + ruta, wait_until="domcontentloaded")
        estado = pag.locator("#demo-estado")
        assert not estado.is_visible(), f"[{idioma}] el aviso del formulario arranca visible"

        pag.locator("#demo-form button[type=submit]").click()
        pag.wait_for_timeout(200)
        assert not estado.is_visible(), f"[{idioma}] el formulario vacío se envió igual"

        pag.fill("#demo-nombre", "Ana Pérez")
        pag.fill("#demo-empresa", "Acme")
        pag.fill("#demo-pais", "Uruguay")
        pag.fill("#demo-email", "no-es-un-correo")
        pag.locator("#demo-form button[type=submit]").click()
        pag.wait_for_timeout(200)
        assert not estado.is_visible(), f"[{idioma}] pasó un correo que no es un correo"

        assert not errores, f"[{idioma}] errores de JavaScript en la página: {errores}"
    finally:
        pag.close()
