"""
MV Cliente IA · ubicación hasta el barrio
=========================================
«Por zona» quería decir más que el país: el dueño lo pidió explícito — hasta
el barrio. Las olas (local / regional / mundo, ver `geo.py`) dicen en qué
PAÍS está una empresa; esto agrega en qué CIUDAD y en qué BARRIO, para
competidores y prospectos reales.

De dónde sale, en dos pasos y sin inventar nada:

1. **La dirección que la propia empresa publica** en su sitio — el marcado
   schema.org (`PostalAddress` en JSON-LD o microdatos) que casi todo sitio
   con local físico trae para Google, y si no, la etiqueta `<address>`. Se
   lee del MISMO HTML que ya se bajó para medir la afinidad o los contactos:
   cero visitas nuevas a ese sitio.
2. **De la dirección al barrio**, con Nominatim (OpenStreetMap): gratis, sin
   clave, y con barrios para cualquier país — no hay una lista de barrios de
   un país cableada acá (regla 1 del proyecto). Su política de uso pide un
   User-Agent que identifique la app, como mucho un pedido por segundo y no
   repetir consultas: se cumple con un candado global, una espera mínima
   entre pedidos y una caché en memoria.

Lo que no está publicado queda vacío. Una empresa 100 % online no tiene
barrio, y ponerle uno sería inventarlo.

Se apaga entero con `MVCLIENTE_GEOCODIFICAR=0` (para quien no quiera que el
motor consulte OpenStreetMap); en ese caso se usa sólo la ciudad que el
sitio declare, si declara una.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.parse
from html import unescape

NOMINATIM = "https://nominatim.openstreetmap.org/search"
ESPERA_ENTRE_PEDIDOS = 1.1        # la política de Nominatim: ≤ 1 pedido/s
TIMEOUT = 6

_RE_JSONLD = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
_RE_ADDRESS = re.compile(r"<address[^>]*>(.*?)</address>", re.I | re.S)
_RE_TAG = re.compile(r"<[^>]+>")

# Lo que Nominatim llama barrio cambia según el país y el mapeo local: se
# toma el primero que exista, del más fino al más grueso.
_CLAVES_BARRIO = ("neighbourhood", "suburb", "quarter", "city_district", "borough")
_CLAVES_CIUDAD = ("city", "town", "village", "municipality")

_candado = threading.Lock()
_ultimo_pedido = 0.0
_cache: dict[str, dict] = {}


def _texto(html: str) -> str:
    return " ".join(unescape(_RE_TAG.sub(" ", html or "")).split())


def _de_jsonld(nodo) -> dict:
    """La primera PostalAddress que aparezca, en cualquier nivel."""
    if isinstance(nodo, list):
        for x in nodo:
            r = _de_jsonld(x)
            if r:
                return r
        return {}
    if not isinstance(nodo, dict):
        return {}
    if "streetAddress" in nodo or "addressLocality" in nodo:
        pais = nodo.get("addressCountry", "")
        if isinstance(pais, dict):
            pais = pais.get("name", "")
        return {k: str(v).strip() for k, v in (
            ("calle", nodo.get("streetAddress", "")),
            ("ciudad", nodo.get("addressLocality", "")),
            ("region", nodo.get("addressRegion", "")),
            ("pais", pais)) if str(v or "").strip()}
    for clave in ("address", "location", "@graph", "contactPoint"):
        if clave in nodo:
            r = _de_jsonld(nodo[clave])
            if r:
                return r
    return {}


def _microdato(html: str, prop: str) -> str:
    m = re.search(rf'itemprop=["\']{prop}["\'][^>]*>([^<]{{2,160}})<', html, re.I)
    return " ".join(unescape(m.group(1)).split()) if m else ""


def direccion_de_html(html: str) -> dict:
    """La dirección que el sitio publica: {calle, ciudad, region, pais},
    sólo con lo que encontró. Vacío si el sitio no publica ninguna."""
    html = html or ""
    for bloque in _RE_JSONLD.findall(html):
        try:
            r = _de_jsonld(json.loads(bloque.strip()))
        except ValueError:
            continue                      # JSON-LD roto: pasa en la vida real
        if r:
            return r
    micro = {k: _microdato(html, prop) for k, prop in (
        ("calle", "streetAddress"), ("ciudad", "addressLocality"),
        ("region", "addressRegion"), ("pais", "addressCountry"))}
    micro = {k: v for k, v in micro.items() if v}
    if micro:
        return micro
    m = _RE_ADDRESS.search(html)
    if m:
        texto = _texto(m.group(1))[:200]
        # Un <address> con sólo un correo o un teléfono no es una dirección.
        if len(texto) >= 8 and "@" not in texto:
            return {"calle": texto}
    return {}


def _activo() -> bool:
    return os.getenv("MVCLIENTE_GEOCODIFICAR", "1") != "0"


def geocodificar(direccion: dict, pais: str = "") -> dict:
    """{ciudad, barrio, pais} de una dirección, vía Nominatim. Nunca falla:
    sin red, sin resultado o apagado, devuelve {}."""
    if not _activo() or not direccion.get("calle"):
        return {}
    consulta = ", ".join(v for v in (direccion.get("calle"), direccion.get("ciudad"),
                                     direccion.get("region"), direccion.get("pais")) if v)
    cod = (pais or "").strip().lower()
    clave = f"{cod}|{consulta.lower()}"
    if clave in _cache:
        return _cache[clave]

    parametros = {"q": consulta, "format": "jsonv2", "addressdetails": "1", "limit": "1"}
    if len(cod) == 2:
        from . import geo
        parametros["countrycodes"] = cod
        # Los nombres en el idioma del país: sin esto «São Paulo» volvía
        # como «San Pablo» (el pedido salía con Accept-Language en
        # castellano), y nadie busca un barrio por su nombre traducido.
        parametros["accept-language"] = geo.idioma_de(cod.upper())
    url = f"{NOMINATIM}?{urllib.parse.urlencode(parametros)}"

    global _ultimo_pedido
    resultado: dict = {}
    with _candado:
        espera = ESPERA_ENTRE_PEDIDOS - (time.monotonic() - _ultimo_pedido)
        if espera > 0:
            time.sleep(espera)
        try:
            # Import local: `web` arrastra el proveedor demo, y este módulo
            # lo usan los proveedores.
            from .proveedores.web import bajar
            datos = json.loads(bajar(url, TIMEOUT))
        except Exception:                                 # noqa: BLE001
            datos = []
        finally:
            _ultimo_pedido = time.monotonic()
    if isinstance(datos, list) and datos and isinstance(datos[0], dict):
        a = datos[0].get("address") or {}
        barrio = next((a[k] for k in _CLAVES_BARRIO if a.get(k)), "")
        ciudad = next((a[k] for k in _CLAVES_CIUDAD if a.get(k)), "")
        resultado = {k: v for k, v in (
            ("barrio", barrio), ("ciudad", ciudad),
            ("pais", (a.get("country_code") or "").upper())) if v}
    _cache[clave] = resultado
    return resultado


def ubicar(html: str, pais: str = "", geocodificar_ok: bool = True) -> dict:
    """Todo junto: {direccion, ciudad, barrio, pais}, con lo que se pudo.

    La ciudad geocodificada gana sobre la declarada (OpenStreetMap la
    devuelve normalizada: «Montevideo», no «MVD» ni «Montevideo, Uruguay»);
    si no hubo geocodificación, queda la que declara el sitio."""
    d = direccion_de_html(html)
    if not d:
        return {}
    salida = {"direccion": ", ".join(v for v in (d.get("calle"), d.get("ciudad")) if v)}
    if d.get("ciudad"):
        salida["ciudad"] = d["ciudad"]
    if geocodificar_ok:
        salida.update(geocodificar(d, pais))
    return {k: v for k, v in salida.items() if v}
