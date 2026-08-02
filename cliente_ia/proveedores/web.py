"""
MV Cliente IA · proveedor web (lee el sitio real)
==================================================
Cubre sólo la fase 1: baja el HTML público del dominio que se le pasa y saca
de ahí el nombre, la propuesta de valor, el idioma y las señales del ICP. Las
fases 2 a 5 las delega (ver `ProveedorEncadenado`), porque adivinar empresas
y personas leyendo una home sería inventarlas.

Sin red, o con un sitio que no responde, levanta `ErrorWeb` y el encadenador
pasa al siguiente proveedor sin romper la corrida.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.request
from html import unescape

from .. import geo
from ..modelos import Empresa
from .base import Proveedor
from .demo import ProveedorDemo, _texto, semilla

TIMEOUT = 12
LARGO_MAX = 400_000          # 400 KB de HTML alcanzan de sobra para el <head> y el hero
UA = "Mozilla/5.0 (compatible; MVClienteIA/1.0; +https://github.com/vieraschiavi/MV-Cliente-IA)"


class ErrorWeb(RuntimeError):
    pass


def bajar(url: str, timeout: int = TIMEOUT) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    pedido = urllib.request.Request(url, headers={"User-Agent": UA,
                                                  "Accept-Language": "es,pt,en"})
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:   # noqa: S310
            crudo = r.read(LARGO_MAX)
            codificacion = r.headers.get_content_charset() or "utf-8"
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ErrorWeb(f"No se pudo leer {url}: {e}") from e
    return crudo.decode(codificacion, errors="replace")


def _etiqueta(html: str, patron: str) -> str:
    m = re.search(patron, html, re.I | re.S)
    return unescape(m.group(1)).strip() if m else ""


def _minuscula_inicial(texto: str) -> str:
    return texto[0].lower() + texto[1:] if texto else texto


def _sin_puntofinal(texto: str) -> str:
    return texto.rstrip().rstrip(".")


def _sin_html(texto: str) -> str:
    texto = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", texto, flags=re.I | re.S)
    texto = re.sub(r"<[^>]+>", " ", texto)
    return re.sub(r"\s+", " ", unescape(texto)).strip()


class ProveedorWeb(Proveedor):
    nombre = "web"

    def __init__(self, idioma_base: str = "es", timeout: int = TIMEOUT):
        self.idioma_base = idioma_base
        self.timeout = timeout
        self._demo = ProveedorDemo(idioma_base)

    def investigar(self, dominio: str) -> Empresa:
        html = bajar(dominio, self.timeout)

        titulo = (_etiqueta(html, r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)')
                  or _etiqueta(html, r"<title[^>]*>(.*?)</title>"))
        descripcion = (_etiqueta(html, r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)')
                       or _etiqueta(html, r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)'))
        h1 = _etiqueta(html, r"<h1[^>]*>(.*?)</h1>")
        lang = _etiqueta(html, r'<html[^>]+lang=["\']([a-zA-Z-]+)')

        cuerpo = _sin_html(html)[:6000]
        # La categoría sale del texto real del sitio, no sólo del dominio: es
        # la única diferencia de fondo con el proveedor demo en esta fase.
        categoria_clave = self._demo.detectar_categoria(f"{dominio} {titulo} {descripcion} {cuerpo}")
        icp = semilla()["icp_por_categoria"][categoria_clave]
        sectores = semilla()["sectores"]

        idioma = (lang or self.idioma_base).split("-")[0].lower()
        if idioma not in geo.IDIOMAS:
            idioma = self.idioma_base

        nombre = re.split(r"[·|\-–—]", titulo)[0].strip() if titulo else ""
        if not nombre:
            nombre = dominio.replace("www.", "").split(".")[0].title()

        propuesta = descripcion or _sin_html(h1) or cuerpo[:220]
        pais = geo.pais_de_dominio(dominio) or geo.PAIS_DEFAULT

        # Los textos de los tres idiomas salen del catálogo (la fase 6 los
        # necesita completos); la propuesta del idioma del sitio es la real,
        # leída del <meta description>, y pisa a la del catálogo.
        textos = self._demo._textos_multi(categoria_clave, icp, sectores)
        if propuesta.strip():
            textos.setdefault(idioma, {})["propuesta"] = _minuscula_inicial(
                _sin_puntofinal(propuesta.strip()))
        dolores = list(textos[idioma]["dolores"])

        # Idiomas que el propio sitio declara tener (Kobra publica /en/ y /pt/).
        idiomas = sorted({idioma} | {
            m.lower() for m in re.findall(r'hreflang=["\']([a-z]{2})', html, re.I)
        } & set(geo.IDIOMAS)) or [idioma]

        # El texto crudo del sitio viaja en la empresa: es lo que el proveedor
        # LLM usa para razonar sobre el producto REAL (competidores directos,
        # compradores del rubro correcto) en vez de la categoría del catálogo.
        resumen_sitio = "\n".join(p for p in (
            titulo, descripcion, _sin_html(h1 or ""), cuerpo[:1500]) if p).strip()[:2000]

        return Empresa(
            dominio=dominio,
            nombre=nombre,
            propuesta=f"{nombre} {textos[idioma]['propuesta']}.",
            resumen_sitio=resumen_sitio,
            categoria=_texto(icp["categoria"], idioma),
            pais=pais.codigo,
            idiomas=idiomas,
            sectores_objetivo=[_texto(sectores[s]["nombre"], idioma) for s in icp["sectores"]],
            dolores=dolores,
            diferenciales=list(textos[idioma]["diferenciales"]),
            tamano_objetivo=icp["tamano_objetivo"],
            fuente=self.nombre,
            textos=textos,
        )
