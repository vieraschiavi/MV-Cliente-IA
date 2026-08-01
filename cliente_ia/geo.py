"""
MV Cliente IA · geografía y prioridad de mercado
================================================
Regla del producto: **Uruguay primero, después LATAM, después el resto del
mundo**. Acá vive esa regla, en un solo lugar, para que la usen por igual el
scoring de prospectos (`cliente_ia.scoring`), el orden de las campañas
(`fases.f3_campanas`) y la interfaz.

Además de la prioridad, el catálogo define el **idioma de salida** de cada
país: es el idioma en que se redacta el correo del decisor
(`fases.f6_emails`). Los tres idiomas del producto son los mismos que los de
MV Kobra AI: español, portugués (Brasil) e inglés.
"""
from __future__ import annotations

from dataclasses import dataclass

# Los tres idiomas del producto — mismos que Kobra (landing es/pt/en).
IDIOMAS = ("es", "pt", "en")
IDIOMA_DEFAULT = "es"

# Prioridad de mercado. Número más bajo = se trabaja antes.
PRIORIDAD_LOCAL = 1     # Uruguay
PRIORIDAD_LATAM = 2     # el resto de América Latina
PRIORIDAD_MUNDO = 3     # todo lo demás

PESO_PRIORIDAD = {
    PRIORIDAD_LOCAL: 1.00,
    PRIORIDAD_LATAM: 0.72,
    PRIORIDAD_MUNDO: 0.45,
}

ETIQUETA_NIVEL = {
    PRIORIDAD_LOCAL: "local",
    PRIORIDAD_LATAM: "latam",
    PRIORIDAD_MUNDO: "mundo",
}


@dataclass(frozen=True)
class Pais:
    codigo: str          # ISO 3166-1 alfa-2
    nombre: str
    prioridad: int
    idioma: str          # idioma en que se le escribe a un decisor de este país
    moneda: str
    locale: str          # BCP 47, para formateo en la interfaz
    zona: str            # "UY" | "LATAM" | "MUNDO"

    @property
    def nivel(self) -> str:
        return ETIQUETA_NIVEL[self.prioridad]

    @property
    def peso(self) -> float:
        return PESO_PRIORIDAD[self.prioridad]


def _uy() -> Pais:
    return Pais("UY", "Uruguay", PRIORIDAD_LOCAL, "es", "UYU", "es-UY", "UY")


def _latam(codigo: str, nombre: str, moneda: str, locale: str, idioma: str = "es") -> Pais:
    return Pais(codigo, nombre, PRIORIDAD_LATAM, idioma, moneda, locale, "LATAM")


def _mundo(codigo: str, nombre: str, moneda: str, locale: str, idioma: str = "en") -> Pais:
    return Pais(codigo, nombre, PRIORIDAD_MUNDO, idioma, moneda, locale, "MUNDO")


CATALOGO: dict[str, Pais] = {
    # --- Nivel 1: mercado local -------------------------------------------
    "UY": _uy(),
    # --- Nivel 2: LATAM ----------------------------------------------------
    "AR": _latam("AR", "Argentina", "ARS", "es-AR"),
    "BR": _latam("BR", "Brasil", "BRL", "pt-BR", idioma="pt"),
    "CL": _latam("CL", "Chile", "CLP", "es-CL"),
    "PY": _latam("PY", "Paraguay", "PYG", "es-PY"),
    "BO": _latam("BO", "Bolivia", "BOB", "es-BO"),
    "PE": _latam("PE", "Perú", "PEN", "es-PE"),
    "CO": _latam("CO", "Colombia", "COP", "es-CO"),
    "EC": _latam("EC", "Ecuador", "USD", "es-EC"),
    "MX": _latam("MX", "México", "MXN", "es-MX"),
    "CR": _latam("CR", "Costa Rica", "CRC", "es-CR"),
    "PA": _latam("PA", "Panamá", "PAB", "es-PA"),
    "GT": _latam("GT", "Guatemala", "GTQ", "es-GT"),
    "DO": _latam("DO", "República Dominicana", "DOP", "es-DO"),
    # --- Nivel 3: resto del mundo -----------------------------------------
    "ES": _mundo("ES", "España", "EUR", "es-ES", idioma="es"),
    "PT": _mundo("PT", "Portugal", "EUR", "pt-PT", idioma="pt"),
    "US": _mundo("US", "Estados Unidos", "USD", "en-US"),
    "CA": _mundo("CA", "Canadá", "CAD", "en-CA"),
    "GB": _mundo("GB", "Reino Unido", "GBP", "en-GB"),
    "IE": _mundo("IE", "Irlanda", "EUR", "en-IE"),
    "DE": _mundo("DE", "Alemania", "EUR", "de-DE"),
    "FR": _mundo("FR", "Francia", "EUR", "fr-FR"),
    "IT": _mundo("IT", "Italia", "EUR", "it-IT"),
    "NL": _mundo("NL", "Países Bajos", "EUR", "nl-NL"),
    "AU": _mundo("AU", "Australia", "AUD", "en-AU"),
    "NZ": _mundo("NZ", "Nueva Zelanda", "NZD", "en-NZ"),
    "ZA": _mundo("ZA", "Sudáfrica", "ZAR", "en-ZA"),
    "IN": _mundo("IN", "India", "INR", "en-IN"),
    "SG": _mundo("SG", "Singapur", "SGD", "en-SG"),
    "AE": _mundo("AE", "Emiratos Árabes Unidos", "AED", "en-AE"),
}

PAIS_DEFAULT = CATALOGO["UY"]

# TLD nacional → país. Sirve para deducir el mercado de un dominio sin
# tener que preguntarlo (kobra: mvkobranzaia.com no tiene TLD nacional, así
# que ahí manda lo que diga la investigación de la fase 1).
TLD_PAIS: dict[str, str] = {
    ".uy": "UY", ".com.uy": "UY",
    ".ar": "AR", ".com.ar": "AR",
    ".br": "BR", ".com.br": "BR",
    ".cl": "CL", ".com.cl": "CL",
    ".py": "PY", ".com.py": "PY",
    ".bo": "BO", ".com.bo": "BO",
    ".pe": "PE", ".com.pe": "PE",
    ".co": "CO", ".com.co": "CO",
    ".ec": "EC", ".com.ec": "EC",
    ".mx": "MX", ".com.mx": "MX",
    ".cr": "CR", ".pa": "PA", ".gt": "GT", ".do": "DO",
    ".es": "ES", ".pt": "PT", ".us": "US", ".ca": "CA",
    ".uk": "GB", ".co.uk": "GB", ".ie": "IE", ".de": "DE",
    ".fr": "FR", ".it": "IT", ".nl": "NL", ".au": "AU",
    ".com.au": "AU", ".nz": "NZ", ".co.nz": "NZ", ".za": "ZA",
    ".co.za": "ZA", ".in": "IN", ".sg": "SG", ".ae": "AE",
}


def obtener(codigo: str | None) -> Pais:
    """País del catálogo. Un código desconocido cae en 'mundo', no revienta."""
    if not codigo:
        return PAIS_DEFAULT
    cod = codigo.strip().upper()
    pais = CATALOGO.get(cod)
    if pais:
        return pais
    return Pais(cod, cod, PRIORIDAD_MUNDO, "en", "USD", "en-US", "MUNDO")


def pais_de_dominio(dominio: str) -> Pais | None:
    """Deduce el país por el TLD. Devuelve None si el TLD es genérico."""
    d = (dominio or "").strip().lower().rstrip("/")
    if not d:
        return None
    # Se prueban primero los TLD de dos niveles (.com.uy antes que .uy).
    for sufijo in sorted(TLD_PAIS, key=len, reverse=True):
        if d.endswith(sufijo):
            return CATALOGO[TLD_PAIS[sufijo]]
    return None


def idioma_de(codigo_pais: str | None) -> str:
    """Idioma en que se le escribe a un decisor de ese país."""
    idioma = obtener(codigo_pais).idioma
    return idioma if idioma in IDIOMAS else IDIOMA_DEFAULT


def prioridad_de(codigo_pais: str | None) -> int:
    return obtener(codigo_pais).prioridad


def peso_de(codigo_pais: str | None) -> float:
    """Multiplicador geográfico del score de un prospecto (1.0 = Uruguay)."""
    return obtener(codigo_pais).peso


def paises_por_prioridad(zona: str | None = None) -> list[Pais]:
    """Catálogo ordenado: Uruguay, después LATAM, después el mundo."""
    paises = list(CATALOGO.values())
    if zona:
        paises = [p for p in paises if p.zona == zona.upper()]
    return sorted(paises, key=lambda p: (p.prioridad, p.nombre))


def orden_de_olas() -> list[tuple[str, int, list[str]]]:
    """
    Las tres olas de salida al mercado, en orden.
    Devuelve (nivel, prioridad, códigos de país).
    """
    olas: list[tuple[str, int, list[str]]] = []
    for zona, prioridad in (("UY", PRIORIDAD_LOCAL),
                            ("LATAM", PRIORIDAD_LATAM),
                            ("MUNDO", PRIORIDAD_MUNDO)):
        codigos = [p.codigo for p in paises_por_prioridad(zona)]
        olas.append((ETIQUETA_NIVEL[prioridad], prioridad, codigos))
    return olas
