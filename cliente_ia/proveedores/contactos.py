"""
MV Cliente IA · contactos públicos de cada empresa real
=======================================================
Visita el sitio de cada prospecto REAL (la portada más sus páginas de
contacto) y extrae los datos que la propia empresa publica para que la
contacten: el correo comercial (info@/ventas@/contacto@), el teléfono y sus
perfiles de LinkedIn e Instagram.

Dos límites deliberados:

1. **Sólo lo publicado.** Se lee el sitio de la empresa, que es donde ella
   misma pide que le escriban. No se adivinan casillas, no se scrapea
   Google ni LinkedIn (los dos lo bloquean y lo prohíben) y no se buscan
   personas: para la persona está el cargo + la búsqueda de LinkedIn armada.
2. **Lo que no está, no está.** Una empresa sin correo publicado queda sin
   correo; inventarlo es exactamente el bug que acabamos de sacar.
"""
from __future__ import annotations

import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from .web import ErrorWeb, bajar

TIMEOUT = 5
MAX_EMPRESAS = 30            # tope de sitios a visitar por corrida
MAX_PAGINAS_EXTRA = 2        # además de la portada: contacto / nosotros
HILOS = 8

# El TLD tiene que ser alfabético: si no, "bootstrap@4.0.0" (una versión de
# librería en el JS del sitio) pasa por correo.
RE_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}\b")
RE_TEL = re.compile(r'href=["\']tel:([+0-9() .\-]{7,20})', re.I)
RE_LINKEDIN = re.compile(
    r"https?://(?:[a-z.]+\.)?linkedin\.com/(?:company|school)/[A-Za-z0-9._%\-]+", re.I)
RE_INSTAGRAM = re.compile(r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9._]+)/?", re.I)
RE_ENLACE = re.compile(r'href=["\']([^"\']+)["\']', re.I)
RE_PAGINA_CONTACTO = re.compile(r"contact|contacto|contato|nosotros|quienes|about|sobre", re.I)

# Un @ dentro de un nombre de archivo o un hash de librería no es un correo.
_EXT_BASURA = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js", ".woff")
_DOMINIOS_BASURA = ("example.", "sentry", "wixpress", "sentry-next", "schema.org")
_PREFIJOS_COMERCIALES = ("info", "contacto", "contact", "ventas", "sales", "hola",
                         "hello", "comercial", "hi", "atencion", "consultas")
_NO_PERFIL_IG = {"p", "reel", "reels", "explore", "accounts", "stories", "tv"}


def _base(dominio: str) -> str:
    return dominio.lower().removeprefix("https://").removeprefix("http://") \
                  .removeprefix("www.").split("/")[0]


def _filtrar_emails(crudos: list[str], dominio: str) -> list[str]:
    base = _base(dominio)
    vistos: list[str] = []
    for e in crudos:
        el = e.lower().strip(".")
        if el in vistos or el.endswith(_EXT_BASURA):
            continue
        if any(b in el for b in _DOMINIOS_BASURA):
            continue
        vistos.append(el)

    def rango(e: str) -> tuple[int, int]:
        # Primero las casillas del propio dominio; entre ellas, las
        # comerciales (info@, ventas@) antes que cualquier otra.
        mismo = 0 if e.endswith("@" + base) or e.endswith("." + base) else 1
        comercial = 0 if e.split("@")[0] in _PREFIJOS_COMERCIALES else 1
        return (mismo, comercial)

    return sorted(vistos, key=rango)[:3]


def _instagram(html: str) -> str:
    for m in RE_INSTAGRAM.finditer(html):
        usuario = m.group(1)
        if usuario.lower() not in _NO_PERFIL_IG:
            return f"https://www.instagram.com/{usuario}"
    return ""


def contactos_de(dominio: str, timeout: int = TIMEOUT,
                 devolver_html: bool = False):
    """Contactos públicos de UN dominio. Devuelve {} si el sitio no responde.

    Con `devolver_html=True` devuelve `(contactos, html)`: el mismo texto que
    ya se bajó, para medir la afinidad de segmento sin un segundo pedido al
    sitio (cliente_ia/segmento.py). Verificar el rubro salía gratis y estaba
    a la vista — sólo había que no tirar el HTML."""
    base = _base(dominio)
    host = base
    try:
        paginas = [bajar(host, timeout)]
    except ErrorWeb:
        # Sitios que sólo responden con www (el apex da 5xx o ni resuelve).
        host = "www." + base
        try:
            paginas = [bajar(host, timeout)]
        except ErrorWeb:
            return ({}, "") if devolver_html else {}

    # De la portada salen los enlaces a "contacto"/"nosotros" del MISMO sitio.
    extra = 0
    for enlace in RE_ENLACE.findall(paginas[0]):
        if extra >= MAX_PAGINAS_EXTRA:
            break
        if enlace.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        if not RE_PAGINA_CONTACTO.search(enlace):
            continue
        url = urllib.parse.urljoin(f"https://{host}/", enlace)
        if _base(url) != base:
            continue
        try:
            paginas.append(bajar(url, timeout))
            extra += 1
        except ErrorWeb:
            continue

    junto = "\n".join(paginas)
    emails = _filtrar_emails(RE_EMAIL.findall(junto), dominio)
    # Muchos sitios no enlazan su página de contacto desde el HTML crudo
    # (menú por JavaScript): si la portada no dio correo, se prueban las
    # rutas típicas directo, hasta encontrar uno.
    if not emails:
        for ruta in ("contacto", "contact", "contato", "contact-us", "contactenos"):
            try:
                paginas.append(bajar(f"{host}/{ruta}", timeout))
            except ErrorWeb:
                continue
            junto = "\n".join(paginas)
            emails = _filtrar_emails(RE_EMAIL.findall(junto), dominio)
            if emails:
                break
    tel = RE_TEL.search(junto)
    linkedin = RE_LINKEDIN.search(junto)
    salida = {
        "email": emails[0] if emails else "",
        "emails": emails,
        "telefono": tel.group(1).strip() if tel else "",
        "linkedin": linkedin.group(0) if linkedin else "",
        "instagram": _instagram(junto),
        "web": f"https://{base}",
    }
    if devolver_html:
        # El HTML sale por separado, no dentro de `contactos`: ahí adentro
        # viajaría a la interfaz, al CSV y al JSON de la corrida guardada.
        return salida, junto
    return salida if any(salida[k] for k in ("email", "telefono", "linkedin", "instagram")) \
        else {"web": salida["web"]}


def enriquecer(prospectos, max_empresas: int = MAX_EMPRESAS,
               timeout: int = TIMEOUT, huella=None) -> tuple[int, int]:
    """Visita en paralelo los sitios de los prospectos REALES y les carga
    `contactos`. Devuelve (con_datos, visitados). Los sintéticos no se tocan:
    sus dominios no existen y visitarlos sería ruido.

    Con `huella` (de cliente_ia.segmento) aprovecha el MISMO HTML para medir
    cuánto habla ese sitio del segmento del producto y lo deja en
    `prospecto.afinidad`. Cero pedidos extra: el sitio ya estaba bajado."""
    reales = [p for p in prospectos if not p.sintetico and p.dominio][:max_empresas]
    if not reales:
        return (0, 0)
    from .. import segmento

    with ThreadPoolExecutor(max_workers=HILOS) as pool:
        futuros = {pool.submit(contactos_de, p.dominio, timeout, True): p
                   for p in reales}
        for futuro, p in futuros.items():
            try:
                contactos, html = futuro.result()
            except Exception:                            # noqa: BLE001
                contactos, html = {}, ""
            util = any(contactos.get(k) for k in
                       ("email", "telefono", "linkedin", "instagram"))
            p.contactos = contactos if util else (
                {"web": contactos["web"]} if contactos.get("web") else {})
            if huella and html:
                p.afinidad = segmento.afinidad_de_html(huella, html)
    con_datos = sum(1 for p in reales
                    if any(p.contactos.get(k) for k in
                           ("email", "telefono", "linkedin", "instagram")))
    return (con_datos, len(reales))
