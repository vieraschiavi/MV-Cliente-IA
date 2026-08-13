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

import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from html import unescape

from .. import geo
from ..modelos import Empresa
from .base import Proveedor
from .demo import ProveedorDemo, _texto, semilla

TIMEOUT = 12
LARGO_MAX = 400_000          # 400 KB de HTML alcanzan de sobra para el <head> y el hero
UA = "Mozilla/5.0 (compatible; MVClienteIA/1.0; +https://github.com/vieraschiavi/MV-Cliente-IA)"
# Un sitio público vive en 80 o 443. Cualquier otro puerto que alguien pida
# es, en la práctica, un escaneo de la red donde corre el motor.
PUERTOS_PERMITIDOS = {80, 443}


class ErrorWeb(RuntimeError):
    pass


def _revisar_destino(url: str) -> None:
    """Deja pasar sólo http/https hacia una IP pública.

    El dominio lo elige quien usa el programa, y el motor lo va a buscar
    desde el servidor: sin este filtro, pedir `http://127.0.0.1:8000/` o
    `http://169.254.169.254/latest/meta-data/` hacía que el servidor leyera
    su propia red interna —o la metadata de la nube, con sus credenciales— y
    devolviera el contenido dentro de `empresa.resumen_sitio`. Es decir: no
    era un SSRF ciego, el texto volvía a la pantalla.

    Se resuelven TODAS las direcciones del host y basta una interna para
    rechazar: un dominio puede apuntar a varias, y alcanzaría con que una
    sola sea 127.0.0.1.
    """
    partes = urllib.parse.urlsplit(url)
    if partes.scheme not in ("http", "https"):
        raise ErrorWeb(f"Sólo se leen sitios http/https, no {partes.scheme!r}")
    host = partes.hostname
    if not host:
        raise ErrorWeb(f"No se entiende la dirección: {url!r}")
    puerto = partes.port or (443 if partes.scheme == "https" else 80)
    if puerto not in PUERTOS_PERMITIDOS:
        raise ErrorWeb(f"Puerto no permitido para leer un sitio: {puerto}")
    try:
        infos = socket.getaddrinfo(host, puerto, proto=socket.IPPROTO_TCP)
    except OSError as e:
        raise ErrorWeb(f"No se pudo resolver {host}: {e}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise ErrorWeb(
                f"{host} apunta a una dirección interna ({ip}); el motor "
                "sólo lee sitios públicos")


class _RedireccionesVigiladas(urllib.request.HTTPRedirectHandler):
    """`urllib` sigue los redirects solo, así que filtrar únicamente la URL
    inicial no alcanza: un sitio público puede contestar 302 hacia
    `http://169.254.169.254/`. Cada salto se revisa con la misma vara."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _revisar_destino(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_abridor = urllib.request.build_opener(_RedireccionesVigiladas)


def bajar(url: str, timeout: int = TIMEOUT) -> str:
    # Un solo esquema: `http://http://127.0.0.1/` se colaba porque ya
    # empezaba con "http://" y salteaba el forzado a https, quedando texto
    # plano contra un servicio interno.
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    resto = url.split("://", 1)[1]
    if resto.startswith(("http://", "https://")):
        raise ErrorWeb(f"Dirección con dos esquemas: {url!r}")
    _revisar_destino(url)
    pedido = urllib.request.Request(url, headers={"User-Agent": UA,
                                                  "Accept-Language": "es,pt,en"})
    try:
        with _abridor.open(pedido, timeout=timeout) as r:            # noqa: S310
            crudo = r.read(LARGO_MAX)
            codificacion = r.headers.get_content_charset() or "utf-8"
    except ErrorWeb:
        raise                                    # el motivo real ya está claro
    except (urllib.error.URLError, OSError, ValueError) as e:
        # Un redirect bloqueado sale envuelto en URLError: se desenvuelve para
        # no perder el motivo ("apunta a una dirección interna").
        if isinstance(getattr(e, "reason", None), ErrorWeb):
            raise e.reason from e
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
        # Se mira la IDENTIDAD de la página (dominio, título, descripción, h1)
        # y sólo el arranque del cuerpo: en 6000 caracteres de una app cargada
        # por JavaScript entra el manifiesto de rutas entero, y ahí cualquier
        # palabra suelta clasifica mal al producto.
        prosa = f"{titulo} {descripcion} {_sin_html(h1)} {cuerpo[:600]}"
        categoria_clave = self._demo.detectar_categoria(prosa, marca=dominio)
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
        #
        # Sin título, sin descripción y sin h1 la página NO describe ningún
        # producto: es un panel de administración o una app que se dibuja
        # entera por JavaScript (pasó con una URL de vercel.com/…, que dejó
        # 1500 caracteres de menú y el modelo perfiló sobre eso). En ese caso
        # se devuelve vacío a propósito: es la señal de "acá no hay producto
        # que leer", y vale más que un resumen de navegación.
        if not (titulo or descripcion or h1):
            resumen_sitio = ""
        else:
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
