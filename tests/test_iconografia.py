"""La interfaz no lleva emojis, lleva iconos SVG.

Un emoji lo dibuja la fuente del sistema: el mismo botón sale de otro color y
de otra forma en Windows, en el WebView de Android y en el navegador. Estos
tests existen para que el próximo cambio no vuelva a meter uno «porque era más
rápido» — pasó una vez y la barra lateral tenía ocho colores ajenos a la
paleta.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "webapp" / "frontend" / "src"
TEMA = FUENTE / "theme.css"
ICONOS = FUENTE / "componentes" / "Iconos.jsx"
LANDING = RAIZ / "marketing" / "generar_landing.py"


def _es_emoji(ch: str) -> bool:
    """Pictogramas de color y dingbats — no la puntuación tipográfica.

    El `→` de «Ver todos →» y el `·` separador se quedan: son tipografía, los
    dibuja la misma fuente que el texto y no cambian de plataforma.
    """
    o = ord(ch)
    return (
        0x1F300 <= o <= 0x1FAFF          # pictogramas y símbolos
        or 0x1F000 <= o <= 0x1F0FF       # fichas y cartas
        or 0x2600 <= o <= 0x27BF         # misceláneos y dingbats (✉ ☎ ✔ ✘ ✓)
        or 0x2B00 <= o <= 0x2BFF         # flechas gordas (⬇ ⬆)
        or o == 0xFE0F                   # selector de presentación emoji
        or 0x1D538 <= o <= 0x1D56B       # doble trazo (el 𝕏 que se usaba de logo)
        or o in (0x25B8, 0x25B4, 0x25BE, 0x2304)  # ▸ ▴ ▾ ⌄
    )


def _archivos_de_interfaz() -> list[Path]:
    return sorted(
        p for p in FUENTE.rglob("*")
        if p.is_file() and p.suffix in {".jsx", ".js", ".json", ".css", ".html"}
    )


def test_ningun_archivo_de_la_interfaz_tiene_emojis():
    sucios = {}
    for p in _archivos_de_interfaz():
        texto = p.read_text(encoding="utf-8")
        hallados = sorted({c for c in texto if _es_emoji(c)})
        if hallados:
            sucios[str(p.relative_to(RAIZ))] = hallados
    assert not sucios, (
        "Volvieron los emojis a la interfaz. Usá <Icono nombre=\"…\"/> de "
        f"componentes/Iconos.jsx en su lugar: {sucios}")


def test_la_landing_generada_tampoco_tiene_emojis():
    """La landing se genera; no alcanza con mirar el .py, hay que mirar la salida."""
    paginas = [RAIZ / "landing" / "index.html",
               RAIZ / "landing" / "pt" / "index.html",
               RAIZ / "landing" / "en" / "index.html"]
    for p in paginas:
        if not p.exists():          # se genera con `python3 -m marketing.generar_landing`
            continue
        hallados = sorted({c for c in p.read_text(encoding="utf-8") if _es_emoji(c)})
        assert not hallados, f"{p.relative_to(RAIZ)} tiene emojis: {hallados}"


def test_el_generador_de_landing_dibuja_los_iconos_en_svg():
    fuente = LANDING.read_text(encoding="utf-8")
    assert "_TRAZOS" in fuente and "def _ico(" in fuente
    assert 'stroke="currentColor"' in fuente, (
        "Los iconos de la landing tienen que heredar el color del botón.")


def test_todos_los_iconos_usados_existen_en_el_set():
    """Un nombre mal escrito no rompe la pantalla (Icono devuelve null), así que
    sin este test el icono simplemente desaparecería sin que nadie se entere."""
    declarados = set(re.findall(r"^  (\w+):", ICONOS.read_text(encoding="utf-8"), re.M))
    assert declarados, "no se pudieron leer los nombres de Iconos.jsx"

    usados = set()
    for p in _archivos_de_interfaz():
        if p == ICONOS:
            continue
        texto = p.read_text(encoding="utf-8")
        usados |= set(re.findall(r'<Icono\s+nombre="(\w+)"', texto))
        # La barra lateral los arma desde una tabla: { ruta, ico, clave }. El
        # `[,{]` de adelante no es decorativo: sin él el patrón picaba dentro
        # de `geográfico: "todos"` y el test fallaba por un comentario.
        usados |= set(re.findall(r'[,{]\s*ico:\s*"(\w+)"', texto))

    faltan = usados - declarados
    assert not faltan, f"Iconos usados que no existen en Iconos.jsx: {sorted(faltan)}"


def test_los_iconos_no_tienen_color_ni_tamano_cableado():
    """Si un trazo trae su propio `stroke="#..."` deja de acompañar al texto."""
    fuente = ICONOS.read_text(encoding="utf-8")
    trazos = fuente.split("const TRAZOS", 1)[1].split("export const NOMBRES_ICONO", 1)[0]
    assert "#" not in trazos, "hay un color cableado dentro de un trazo"
    assert 'stroke="currentColor"' in fuente


def test_los_campos_de_correo_llevan_el_estilo_del_tema():
    """Regresión: la regla enumeraba text/password/number y NO email, así que
    los cuatro campos de correo salían con el blanco del navegador encima del
    tema oscuro."""
    css = TEMA.read_text(encoding="utf-8")
    # Una vez para escritorio y otra dentro del @media móvil.
    assert css.count('input[type="email"]') == 2, (
        "Falta `input[type=\"email\"]` en alguna de las dos reglas de controles.")

    # Y que ningún tipo de campo usado en la app se quede afuera de la regla.
    usados = set(re.findall(r'<input[^>]*type="(\w+)"', "\n".join(
        p.read_text(encoding="utf-8") for p in _archivos_de_interfaz()
        if p.suffix == ".jsx")))
    # Estos tres tienen su propio estilo (o ninguno, a propósito).
    usados -= {"checkbox", "radio", "file", "submit", "button", "hidden"}
    regla = css.split("/* ---- controles ---- */", 1)[1].split("{", 2)[1]
    faltan = {t for t in usados if f'input[type="{t}"]' not in regla}
    assert not faltan, f"Tipos de campo sin estilo del tema: {sorted(faltan)}"


def test_el_cuerpo_del_correo_puede_partir_una_url_larga():
    """Regresión: el enlace traqueado son 200+ caracteres sin espacios y con
    sólo `pre-wrap` estiraba la ficha a 483 px, metiendo scroll horizontal en
    toda la página en un teléfono de 390 px."""
    css = TEMA.read_text(encoding="utf-8")
    bloque = css.split(".mail pre {", 1)[1].split("}", 1)[0]
    assert "overflow-wrap: anywhere" in bloque


def test_el_chevron_puede_rotar():
    """`transform` no se aplica a un elemento inline: sin `inline-flex` la
    flecha de la fase abierta nunca giraba."""
    css = TEMA.read_text(encoding="utf-8")
    bloque = css.split(".chev {", 1)[1].split("}", 1)[0]
    assert "inline-flex" in bloque


def test_las_etiquetas_nuevas_estan_en_los_tres_idiomas():
    """Regla 2 del proyecto: todo texto de interfaz existe en es/pt/en."""
    for idioma in ("es", "en", "pt-BR"):
        d = json.loads((FUENTE / "i18n" / f"{idioma}.json").read_text(encoding="utf-8"))
        assert d["common"]["aviso"], idioma
        assert d["metricas"]["publicado"], idioma
        assert d["metricas"]["no_publicado"], idioma
        # Y que las cadenas de las que se sacó el emoji no hayan quedado vacías.
        for clave in ("exportar_csv", "exportar_xlsx"):
            assert d["common"][clave].strip(), f"{idioma}.common.{clave} quedó vacía"


def test_el_nombre_del_producto_cambia_solo_en_ingles():
    """Regla 2 del proyecto: MV Cliente IA en es/pt, MV SearchCostumer AI en
    inglés — en las CUATRO fuentes donde el nombre está escrito a mano. Sin
    este test, cablear "MV Cliente IA" en el JSON inglés o en el strings.xml
    de Android dejaba pasar la suite entera en verde (encontrado en la
    auditoría de reglas de negocio: ninguno de los tests existentes comparaba
    el valor de marca entre idiomas, sólo que la clave no estuviera vacía)."""
    from marketing.generar_landing import TEXTOS

    ES_PT, EN = "MV Cliente IA", "MV SearchCostumer AI"

    for idioma, esperado in (("es", ES_PT), ("pt-BR", ES_PT), ("en", EN)):
        d = json.loads((FUENTE / "i18n" / f"{idioma}.json").read_text(encoding="utf-8"))
        assert d["common"]["marca_texto"] == esperado, idioma
        assert d["common"]["titulo_pagina"].startswith(esperado), idioma

    for idioma, esperado in (("es", ES_PT), ("pt", ES_PT), ("en", EN)):
        assert TEXTOS[idioma]["marca"] == esperado, idioma
        assert TEXTOS[idioma]["titulo"].startswith(esperado), idioma

    ANDROID = RAIZ / "android" / "app" / "src" / "main" / "res"
    default = (ANDROID / "values" / "strings.xml").read_text(encoding="utf-8")
    en = (ANDROID / "values-en" / "strings.xml").read_text(encoding="utf-8")
    assert f'name="app_name">{ES_PT}<' in default
    assert f'name="app_name">{EN}<' in en
