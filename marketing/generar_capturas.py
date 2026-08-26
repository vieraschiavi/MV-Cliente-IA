"""
MV Cliente IA · captura del producto para los correos
======================================================
Genera `landing/banners/captura_<idioma>.png`: la **segunda imagen** que lleva
cada correo en frío, debajo del video.

    python3 -m marketing.generar_capturas

Por qué existe, si ya está el banner: el banner es una placa de marca dibujada
con PIL — dice de qué se trata, pero es un cartel. La captura es la pantalla
REAL del producto con la lista de clientes potenciales ya priorizada, que es
lo que la persona se lleva de la demo. En un correo en frío, ver el resultado
pesa más que leer la promesa.

Se saca del producto de verdad —se levanta el backend, se corre una corrida
demo y se fotografía la pantalla de Prospectos con Chromium—, no de un mockup:
un mockup se desactualiza en silencio y termina mostrando una interfaz que ya
no existe.

Las imágenes se guardan al lado de los banners porque `cliente_ia/enlaces.py`
las sirve de la misma carpeta (`RUTA_CAPTURA`), y `marketing/armar_sitio.py`
copia esa carpeta entera a `public/`.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

from .generar_video import (
    DOMINIO_DEMO,
    _correr_corrida,
    _esperar_api,
    _puerto_libre,
)

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "landing" / "banners"
IDIOMAS = ("es", "pt", "en")

# El bloque del correo la muestra a 540 px de ancho (`_BLOQUE_CAPTURA` en
# redaccion.py). Se captura al doble y se baja a 1080: en una pantalla retina
# una imagen de 540 px reales se ve borrosa, y 1080 px de PNG pesan ~150 KB,
# que en un correo es aceptable.
ANCHO_CAPTURA, ALTO_CAPTURA = 1280, 760
ANCHO_FINAL = 1080


def _chromium() -> dict:
    """El Chromium que ya trae el entorno; Playwright no baja nada."""
    encontrados = sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome"))
    return {"executable_path": str(encontrados[-1])} if encontrados else {}


# Tope del ensanche de emergencia (ver `_foto`): la tabla de Prospectos tiene
# nueve columnas y a 1280 px de ancho real ya no entran todas — sale
# recortada a la mitad de la última. No hay forma de saber de antemano cuánto
# hace falta (cambia con el largo de los datos de la corrida demo), así que
# se mide y se ensancha; este tope es sólo para no generar un PNG gigante si
# algo saliera mal.
ANCHO_CAPTURA_TOPE = 2400


def _foto(idioma: str, base: str, corrida_id: str, destino: Path) -> Path:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        navegador = p.chromium.launch(**_chromium())
        try:
            ctx = navegador.new_context(
                viewport={"width": ANCHO_CAPTURA, "height": ALTO_CAPTURA},
                device_scale_factor=1)
            # Idioma y corrida fijados ANTES de que cargue la app, como si el
            # usuario ya los tuviera guardados de una sesión anterior.
            ctx.add_init_script(
                f"localStorage.setItem('mvcliente_idioma', '{idioma}');"
                f"localStorage.setItem('mvcliente_corrida', '{corrida_id}');")
            pagina = ctx.new_page()
            pagina.goto(f"{base}/#/prospectos")
            pagina.wait_for_selector("table, .pers, .fila", timeout=20000)
            # Sin este respiro la tabla sale a medio pintar y la captura
            # muestra filas vacías: es el producto, pero parece roto.
            pagina.wait_for_timeout(600)

            # La tabla real tiene más columnas de las que entran en el ancho
            # fijo de captura: en la app eso está bien (`.tablewrap` scrollea
            # con `overflow-x:auto`, a propósito), pero en una foto estática
            # deja la última columna cortada a la mitad — parece el producto
            # roto, no una tabla larga. Se saca el freno del scroll y se mide
            # cuánto necesita la página entera para entrar sin cortar nada;
            # si hace falta, se agranda el viewport ANTES de fotografiar.
            ancho_necesario = pagina.evaluate("""
                () => {
                    const wrap = document.querySelector('.tablewrap');
                    if (wrap) wrap.style.overflow = 'visible';
                    return document.documentElement.scrollWidth;
                }
            """)
            ancho_final = min(ANCHO_CAPTURA_TOPE,
                               max(ANCHO_CAPTURA, ancho_necesario + 16))
            if ancho_final > ANCHO_CAPTURA:
                pagina.set_viewport_size({"width": ancho_final, "height": ALTO_CAPTURA})
                pagina.wait_for_timeout(150)  # reflow tras el resize
            pagina.screenshot(path=str(destino))
        finally:
            navegador.close()
    return destino


def _achicar(origen: Path, destino: Path) -> Path:
    with Image.open(origen) as img:
        alto = round(img.height * ANCHO_FINAL / img.width)
        img.convert("RGB").resize((ANCHO_FINAL, alto), Image.LANCZOS).save(
            destino, "PNG", optimize=True)
    return destino


def generar() -> list[Path]:
    salidas: list[Path] = []
    DESTINO.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mv-capturas-") as tmp:
        carpeta = Path(tmp)
        puerto = _puerto_libre()
        base = f"http://127.0.0.1:{puerto}"
        servidor = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "webapp.backend.api:app",
             "--port", str(puerto), "--log-level", "warning"],
            cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            _esperar_api(base)
            # Una sola corrida para los tres idiomas: los datos son los mismos,
            # lo que cambia es la interfaz.
            corrida_id = _correr_corrida(base)
            for idioma in IDIOMAS:
                cruda = _foto(idioma, base, corrida_id, carpeta / f"{idioma}.png")
                salidas.append(_achicar(cruda, DESTINO / f"captura_{idioma}.png"))
        finally:
            servidor.terminate()
            servidor.wait(timeout=10)
    return salidas


if __name__ == "__main__":
    print(f"Capturando {DOMINIO_DEMO} en {', '.join(IDIOMAS)}…")
    for p in generar():
        print(f"  ✓ {p.relative_to(RAIZ)}  ({p.stat().st_size // 1024} KB)")
