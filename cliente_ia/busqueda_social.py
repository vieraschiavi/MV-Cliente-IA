"""
MV Cliente IA · búsqueda de clientes por redes sociales, con palabras clave
===========================================================================
A partir de la huella del producto (`cliente_ia.segmento`) arma las consultas
que encuentran MÁS empresas del mismo segmento en LinkedIn, Instagram, X,
TikTok y el buscador — cada una acotada al sector de la campaña y al país de
la ola.

Por qué son enlaces de búsqueda y no resultados
-----------------------------------------------
Esto podría devolver una lista de perfiles ya resuelta. No lo hace, y es a
propósito: LinkedIn e Instagram prohíben el scraping en sus términos y lo
bloquean técnicamente, así que una lista "automática" sería o inventada o
frágil — las dos cosas que este producto no hace (ver el encabezado de
`proveedores/contactos.py` y la regla 5 del proyecto). Lo que sí se puede
hacer bien es lo que hace un vendedor bueno: escribir la consulta correcta.
Eso es lo que se automatiza acá, y es donde estaba el trabajo real — nadie
sabe de memoria el operador de búsqueda de gente por empresa de LinkedIn.

Las consultas se arman con:
  · las palabras clave MEDIDAS del producto (bigramas primero: «software de
    cobranzas» encuentra el rubro, «software» encuentra internet entero),
  · el sector concreto de la campaña,
  · el país de la ola, para que el resultado sea alcanzable.
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass

from . import geo, segmento

# Cuántas palabras clave entran en una consulta. Más que tres y los buscadores
# empiezan a devolver cero: cada término extra es un AND.
CLAVES_POR_CONSULTA = 3

# Instagram y TikTok buscan por hashtag/palabra, no aceptan operadores.
# LinkedIn y el buscador sí. Cada plantilla refleja lo que ESA red entiende.
REDES = ("linkedin", "instagram", "x", "tiktok", "buscador")

NOMBRE_RED = {
    "linkedin": "LinkedIn",
    "instagram": "Instagram",
    "x": "X",
    "tiktok": "TikTok",
    "buscador": "Buscador",
}


@dataclass
class Busqueda:
    """Una consulta lista para abrir en el navegador."""
    red: str
    etiqueta: str
    consulta: str
    url: str

    def a_dict(self) -> dict:
        return {"red": self.red, "etiqueta": self.etiqueta,
                "consulta": self.consulta, "url": self.url}


def _hashtag(termino: str) -> str:
    """«Fintech de Préstamos» → «fintechprestamos».

    Sin espacios, sin acentos y en minúscula: es la única forma en que
    Instagram y TikTok indexan un hashtag. Con «Fintechdepréstamos» el enlace
    abría una etiqueta vacía.
    """
    palabras = segmento.normalizar(termino)
    return "".join(palabras) or "".join(
        c for c in termino.lower() if c.isalnum())


def _claves(huella: segmento.Huella, tope: int = CLAVES_POR_CONSULTA) -> list[str]:
    return segmento.palabras_de_busqueda(huella, tope)


def _sin_repetir(terminos: list[str]) -> list[str]:
    """Saca los términos que ya están dichos por otro.

    El sector de la campaña («Fintech de préstamos») y la palabra clave medida
    («fintech prestamos») suelen ser lo MISMO escrito distinto. Metidos los dos
    en una consulta con AND, el buscador devuelve cero. Se compara por palabras
    normalizadas, no por texto: es lo que hace equivalentes a los dos.
    """
    salida: list[str] = []
    cubierto: set[str] = set()
    for t in terminos:
        palabras = set(segmento.normalizar(t))
        if not palabras or palabras <= cubierto:
            continue
        salida.append(t)
        cubierto |= palabras
    return salida


def _frase(terminos: list[str]) -> str:
    """Los términos como UNA consulta, sin repetir ninguna palabra.

    El primero va entero —es el sector o el dolor, y mutilarlo lo arruinaría—;
    de los siguientes se sacan las palabras ya dichas. Sin esto la consulta de
    intención salía «gestion cobranzas software cobranzas»: «cobranzas» dos
    veces no agrega nada y en algunos buscadores directamente pesa en contra.
    """
    partes: list[str] = []
    dichas: set[str] = set()
    for i, t in enumerate(terminos):
        if i == 0:
            partes.append(t.strip())
            dichas |= set(segmento.normalizar(t))
            continue
        nuevas = [p for p in segmento.normalizar(t) if p not in dichas]
        if not nuevas:
            continue
        partes.append(" ".join(nuevas))
        dichas |= set(nuevas)
    return " ".join(p for p in partes if p)


# Cargos que firman la decisión, en los tres idiomas. Van en la búsqueda de
# gente de LinkedIn: sin esto devolvía pasantes y analistas del rubro.
CARGOS = {
    "es": "director OR gerente OR jefe OR responsable",
    "pt": "diretor OR gerente OR chefe OR responsavel",
    "en": "director OR head OR manager OR chief",
}


def para_segmento(huella: segmento.Huella, sector: str = "", pais: str = "",
                  idioma: str = "es", dolor: str = "",
                  cargos: list[str] | None = None) -> list[Busqueda]:
    """Las consultas que encuentran CLIENTES de un segmento (sector × país).

    Ojo con qué palabra va en qué consulta, porque es donde esto se hace bien
    o se hace al revés:

    · Para encontrar **empresas compradoras** la palabra es el SECTOR, no la
      del producto. Una empresa cuya web habla como nuestra web no es un
      cliente: es un competidor. (Este módulo llegó a estar escrito así y
      devolvía justo la lista equivocada.)
    · Para encontrar **intención de compra** la palabra es el DOLOR: quién se
      está quejando ahora mismo del problema que resolvemos. Ahí sí entran las
      palabras del producto, porque describen el problema.
    · La huella del producto se usa sólo para acotar el rubro en el buscador,
      donde un término de más no vacía el resultado.

    Sin sector y sin huella no hay nada útil que buscar: se devuelve vacío en
    vez de un enlace con la caja vacía, que es peor que nada.
    """
    claves = _claves(huella)
    sector = (sector or "").strip()
    dolor = (dolor or "").strip()
    if not claves and not sector:
        return []

    nombre_pais = geo.nombre_pais(pais, idioma) if pais else ""
    idi = idioma if idioma in CARGOS else "es"
    # El término que identifica al COMPRADOR. El sector manda; sin sector se
    # cae a la palabra del producto, que al menos acota el rubro.
    comprador = sector or claves[0]

    def q(valor: str) -> str:
        return urllib.parse.quote_plus(valor)

    salida: list[Busqueda] = []

    # LinkedIn · empresas del rubro comprador en el país. `companyHqGeo`
    # necesita el id numérico de la región (que no tenemos), así que el país va
    # como término: menos preciso que el filtro nativo, pero sin credenciales.
    li = f"{comprador} {nombre_pais}".strip()
    salida.append(Busqueda(
        red="linkedin", etiqueta="empresas del rubro", consulta=li,
        url=f"https://www.linkedin.com/search/results/companies/?keywords={q(li)}",
    ))
    # LinkedIn · la gente que firma dentro de ese rubro. Con los cargos que
    # la campaña dedujo del producto real, la consulta busca ESOS puestos
    # ("Gerente de Cobranzas" OR "Director de Riesgo"); sin ellos queda el
    # genérico por idioma de siempre (director OR gerente…), que matchea a
    # cualquier jefe de cualquier rubro — era la parte floja de la consulta.
    termino_cargos = (" OR ".join(f'"{c}"' for c in cargos[:3])
                      if cargos else CARGOS[idi])
    li_gente = f"{comprador} {termino_cargos} {nombre_pais}".strip()
    salida.append(Busqueda(
        red="linkedin", etiqueta="decisores", consulta=li_gente,
        url=f"https://www.linkedin.com/search/results/people/?keywords={q(li_gente)}",
    ))

    etiqueta_ig = _hashtag(comprador)
    if etiqueta_ig:
        salida.append(Busqueda(
            red="instagram", etiqueta="hashtag del rubro", consulta=f"#{etiqueta_ig}",
            url=f"https://www.instagram.com/explore/tags/{urllib.parse.quote(etiqueta_ig)}/",
        ))
        salida.append(Busqueda(
            red="tiktok", etiqueta="hashtag del rubro", consulta=f"#{etiqueta_ig}",
            url=f"https://www.tiktok.com/tag/{urllib.parse.quote(etiqueta_ig)}",
        ))

    # X · intención: quién habla AHORA del problema. Acá sí van las palabras
    # del dolor y del producto — son las que describen el problema, no la
    # solución. `f=live` ordena por reciente, que es lo único que importa
    # cuando se busca una queja fresca.
    intencion = _sin_repetir(([dolor] if dolor else []) + claves)[:2]
    x_q = _frase(intencion) or comprador
    salida.append(Busqueda(
        red="x", etiqueta="quién tiene el problema", consulta=x_q,
        url=f"https://x.com/search?q={q(x_q)}&f=live",
    ))

    # Buscador · el que más rinde: sitios del rubro comprador en el TLD del
    # país, sin los agregadores que ensucian toda búsqueda comercial.
    tld = _tld(pais)
    partes = [f'"{comprador}"' if " " in comprador else comprador]
    if tld:
        partes.append(f"site:{tld}")
    partes.append("-site:linkedin.com -site:facebook.com -site:instagram.com")
    web = " ".join(partes)
    salida.append(Busqueda(
        red="buscador", etiqueta="sitios del rubro", consulta=web,
        url=f"https://duckduckgo.com/?q={q(web)}",
    ))
    return salida


def _tld(pais: str) -> str:
    """El dominio de nivel país, para acotar la búsqueda web. Vacío para los
    países sin TLD útil o sin país elegido."""
    cod = (pais or "").strip().lower()
    if len(cod) != 2:
        return ""
    # US no se acota: casi nada del país vive bajo .us.
    return "" if cod == "us" else f".{cod}"


def por_campana(huella: segmento.Huella, campanas, idioma: str = "es",
                tope: int = 6) -> list[dict]:
    """Un bloque de búsquedas por campaña (sector × ola), en el orden del
    producto: el país del cliente primero. `tope` acota cuántas campañas se
    exponen — la interfaz no puede mostrar treinta bloques."""
    ordenadas = sorted(campanas, key=lambda c: (c.prioridad, c.sector))[:tope]
    salida = []
    for c in ordenadas:
        pais = c.paises[0] if c.paises else ""
        # El idioma y el dolor salen de la campaña: la ola brasileña busca en
        # portugués y con el dolor escrito en portugués, que es como lo va a
        # haber escrito quien se está quejando en X.
        busquedas = para_segmento(huella, c.sector, pais,
                                  c.idioma or idioma, c.dolor,
                                  cargos=getattr(c, "cargos", None))
        if not busquedas:
            continue
        salida.append({
            "campana_id": c.id,
            "sector": c.sector,
            "nivel": c.nivel,
            "pais": pais,
            "busquedas": [b.a_dict() for b in busquedas],
        })
    return salida
