"""
MV Cliente IA · geografía y prioridad de mercado
================================================
Regla del producto: **primero el país que elige el cliente, después el resto
de su región, después el resto del mundo**. Acá vive esa regla, en un solo
lugar, para que la usen por igual el scoring de prospectos
(`cliente_ia.scoring`), el orden de las campañas (`fases.f3_campanas`) y la
interfaz.

La prioridad es **relativa**: no hay un país privilegiado en el catálogo. Un
uruguayo que elige UY ve Uruguay en la ola local y el resto de LATAM en la
regional; un alemán que elige DE ve Alemania en la local y el resto de Europa
en la regional. Antes esto estaba cableado a Uruguay y a LATAM, lo que hacía
que el producto sólo tuviera sentido para un usuario uruguayo.

Además de la prioridad, el catálogo define el **idioma de salida** de cada
país: es el idioma en que se redacta el correo del decisor
(`fases.f6_emails`). Los tres idiomas del producto son los mismos que los de
MV Kobra AI: español, portugués (Brasil) e inglés. `locale` es otra cosa —
es el formato numérico local, que puede ser de un idioma que el producto no
habla (Alemania escribe en inglés pero formatea en `de-DE`).
"""
from __future__ import annotations

from dataclasses import dataclass

# Los tres idiomas del producto — mismos que Kobra (landing es/pt/en).
IDIOMAS = ("es", "pt", "en")
IDIOMA_DEFAULT = "es"

# Las tres olas de salida al mercado. Número más bajo = se trabaja antes.
NIVEL_LOCAL = "local"        # el país que eligió el cliente
NIVEL_REGIONAL = "regional"  # el resto de la región de ese país
NIVEL_MUNDO = "mundo"        # todo lo demás

NIVELES = (NIVEL_LOCAL, NIVEL_REGIONAL, NIVEL_MUNDO)

PRIORIDAD_LOCAL = 1
PRIORIDAD_REGIONAL = 2
PRIORIDAD_MUNDO = 3

PRIORIDAD_NIVEL = {
    NIVEL_LOCAL: PRIORIDAD_LOCAL,
    NIVEL_REGIONAL: PRIORIDAD_REGIONAL,
    NIVEL_MUNDO: PRIORIDAD_MUNDO,
}

PESO_PRIORIDAD = {
    PRIORIDAD_LOCAL: 1.00,
    PRIORIDAD_REGIONAL: 0.72,
    PRIORIDAD_MUNDO: 0.45,
}

ETIQUETA_NIVEL = {
    PRIORIDAD_LOCAL: NIVEL_LOCAL,
    PRIORIDAD_REGIONAL: NIVEL_REGIONAL,
    PRIORIDAD_MUNDO: NIVEL_MUNDO,
}

# La ola regional se llamó "latam" hasta que el país base se volvió elegible.
# Las corridas guardadas en disco y los filtros que quedaron en un navegador
# siguen mandando el nombre viejo, así que se acepta como alias.
ALIAS_NIVEL = {"latam": NIVEL_REGIONAL}

REGIONES = ("LATAM", "NORTEAMERICA", "EUROPA", "AFRICA", "ASIA", "OCEANIA")

NOMBRE_REGION: dict[str, dict[str, str]] = {
    "LATAM": {"es": "América Latina", "pt": "América Latina", "en": "Latin America"},
    "NORTEAMERICA": {"es": "América del Norte", "pt": "América do Norte",
                     "en": "North America"},
    "EUROPA": {"es": "Europa", "pt": "Europa", "en": "Europe"},
    "AFRICA": {"es": "África", "pt": "África", "en": "Africa"},
    "ASIA": {"es": "Asia", "pt": "Ásia", "en": "Asia"},
    "OCEANIA": {"es": "Oceanía", "pt": "Oceania", "en": "Oceania"},
}


@dataclass(frozen=True)
class Pais:
    codigo: str          # ISO 3166-1 alfa-2
    nombre: str
    region: str          # una de REGIONES
    idioma: str          # idioma en que se le escribe a un decisor de este país
    moneda: str
    locale: str          # BCP 47, para formateo en la interfaz
    capital: str         # ciudad de referencia (respaldo del proveedor demo)

    def nivel(self, base: str | None) -> str:
        """Ola de este país visto desde el país base elegido por el cliente."""
        return nivel_de(self.codigo, base)

    def prioridad(self, base: str | None) -> int:
        return PRIORIDAD_NIVEL[self.nivel(base)]

    def peso(self, base: str | None) -> float:
        return PESO_PRIORIDAD[self.prioridad(base)]


# Catálogo mundial. Cada fila: código, nombre, ciudad de referencia, idioma de
# salida (uno de los tres del producto), moneda, locale.
_FILAS: dict[str, list[tuple[str, str, str, str, str, str]]] = {
    "LATAM": [
        ("AR", "Argentina", "Buenos Aires", "es", "ARS", "es-AR"),
        ("BO", "Bolivia", "Santa Cruz", "es", "BOB", "es-BO"),
        ("BR", "Brasil", "São Paulo", "pt", "BRL", "pt-BR"),
        ("CL", "Chile", "Santiago", "es", "CLP", "es-CL"),
        ("CO", "Colombia", "Bogotá", "es", "COP", "es-CO"),
        ("CR", "Costa Rica", "San José", "es", "CRC", "es-CR"),
        ("CU", "Cuba", "La Habana", "es", "CUP", "es-CU"),
        ("DO", "República Dominicana", "Santo Domingo", "es", "DOP", "es-DO"),
        ("EC", "Ecuador", "Guayaquil", "es", "USD", "es-EC"),
        ("SV", "El Salvador", "San Salvador", "es", "USD", "es-SV"),
        ("GT", "Guatemala", "Ciudad de Guatemala", "es", "GTQ", "es-GT"),
        ("HN", "Honduras", "Tegucigalpa", "es", "HNL", "es-HN"),
        ("MX", "México", "Ciudad de México", "es", "MXN", "es-MX"),
        ("NI", "Nicaragua", "Managua", "es", "NIO", "es-NI"),
        ("PA", "Panamá", "Ciudad de Panamá", "es", "PAB", "es-PA"),
        ("PY", "Paraguay", "Asunción", "es", "PYG", "es-PY"),
        ("PE", "Perú", "Lima", "es", "PEN", "es-PE"),
        ("PR", "Puerto Rico", "San Juan", "es", "USD", "es-PR"),
        ("UY", "Uruguay", "Montevideo", "es", "UYU", "es-UY"),
        ("VE", "Venezuela", "Caracas", "es", "VES", "es-VE"),
    ],
    "NORTEAMERICA": [
        ("US", "Estados Unidos", "Nueva York", "en", "USD", "en-US"),
        ("CA", "Canadá", "Toronto", "en", "CAD", "en-CA"),
    ],
    "EUROPA": [
        ("ES", "España", "Madrid", "es", "EUR", "es-ES"),
        ("PT", "Portugal", "Lisboa", "pt", "EUR", "pt-PT"),
        ("GB", "Reino Unido", "Londres", "en", "GBP", "en-GB"),
        ("IE", "Irlanda", "Dublín", "en", "EUR", "en-IE"),
        ("DE", "Alemania", "Berlín", "en", "EUR", "de-DE"),
        ("FR", "Francia", "París", "en", "EUR", "fr-FR"),
        ("IT", "Italia", "Milán", "en", "EUR", "it-IT"),
        ("NL", "Países Bajos", "Ámsterdam", "en", "EUR", "nl-NL"),
        ("BE", "Bélgica", "Bruselas", "en", "EUR", "nl-BE"),
        ("LU", "Luxemburgo", "Luxemburgo", "en", "EUR", "fr-LU"),
        ("CH", "Suiza", "Zúrich", "en", "CHF", "de-CH"),
        ("AT", "Austria", "Viena", "en", "EUR", "de-AT"),
        ("SE", "Suecia", "Estocolmo", "en", "SEK", "sv-SE"),
        ("NO", "Noruega", "Oslo", "en", "NOK", "nb-NO"),
        ("DK", "Dinamarca", "Copenhague", "en", "DKK", "da-DK"),
        ("FI", "Finlandia", "Helsinki", "en", "EUR", "fi-FI"),
        ("IS", "Islandia", "Reikiavik", "en", "ISK", "is-IS"),
        ("PL", "Polonia", "Varsovia", "en", "PLN", "pl-PL"),
        ("CZ", "Chequia", "Praga", "en", "CZK", "cs-CZ"),
        ("SK", "Eslovaquia", "Bratislava", "en", "EUR", "sk-SK"),
        ("HU", "Hungría", "Budapest", "en", "HUF", "hu-HU"),
        ("RO", "Rumania", "Bucarest", "en", "RON", "ro-RO"),
        ("BG", "Bulgaria", "Sofía", "en", "BGN", "bg-BG"),
        ("GR", "Grecia", "Atenas", "en", "EUR", "el-GR"),
        ("HR", "Croacia", "Zagreb", "en", "EUR", "hr-HR"),
        ("SI", "Eslovenia", "Liubliana", "en", "EUR", "sl-SI"),
        ("RS", "Serbia", "Belgrado", "en", "RSD", "sr-RS"),
        ("EE", "Estonia", "Tallin", "en", "EUR", "et-EE"),
        ("LV", "Letonia", "Riga", "en", "EUR", "lv-LV"),
        ("LT", "Lituania", "Vilna", "en", "EUR", "lt-LT"),
        ("UA", "Ucrania", "Kiev", "en", "UAH", "uk-UA"),
        ("TR", "Turquía", "Estambul", "en", "TRY", "tr-TR"),
        ("CY", "Chipre", "Nicosia", "en", "EUR", "el-CY"),
        ("MT", "Malta", "La Valeta", "en", "EUR", "en-MT"),
    ],
    "AFRICA": [
        ("ZA", "Sudáfrica", "Johannesburgo", "en", "ZAR", "en-ZA"),
        ("NG", "Nigeria", "Lagos", "en", "NGN", "en-NG"),
        ("KE", "Kenia", "Nairobi", "en", "KES", "en-KE"),
        ("GH", "Ghana", "Acra", "en", "GHS", "en-GH"),
        ("EG", "Egipto", "El Cairo", "en", "EGP", "ar-EG"),
        ("MA", "Marruecos", "Casablanca", "en", "MAD", "fr-MA"),
        ("TN", "Túnez", "Túnez", "en", "TND", "fr-TN"),
        ("DZ", "Argelia", "Argel", "en", "DZD", "fr-DZ"),
        ("AO", "Angola", "Luanda", "pt", "AOA", "pt-AO"),
        ("MZ", "Mozambique", "Maputo", "pt", "MZN", "pt-MZ"),
        ("TZ", "Tanzania", "Dar es Salaam", "en", "TZS", "en-TZ"),
        ("UG", "Uganda", "Kampala", "en", "UGX", "en-UG"),
        ("ET", "Etiopía", "Adís Abeba", "en", "ETB", "am-ET"),
        ("CI", "Costa de Marfil", "Abiyán", "en", "XOF", "fr-CI"),
        ("SN", "Senegal", "Dakar", "en", "XOF", "fr-SN"),
    ],
    "ASIA": [
        ("IN", "India", "Bombay", "en", "INR", "en-IN"),
        ("SG", "Singapur", "Singapur", "en", "SGD", "en-SG"),
        ("AE", "Emiratos Árabes Unidos", "Dubái", "en", "AED", "en-AE"),
        ("SA", "Arabia Saudita", "Riad", "en", "SAR", "ar-SA"),
        ("QA", "Catar", "Doha", "en", "QAR", "ar-QA"),
        ("KW", "Kuwait", "Kuwait", "en", "KWD", "ar-KW"),
        ("BH", "Baréin", "Manama", "en", "BHD", "ar-BH"),
        ("OM", "Omán", "Mascate", "en", "OMR", "ar-OM"),
        ("IL", "Israel", "Tel Aviv", "en", "ILS", "he-IL"),
        ("JO", "Jordania", "Amán", "en", "JOD", "ar-JO"),
        ("LB", "Líbano", "Beirut", "en", "LBP", "ar-LB"),
        ("JP", "Japón", "Tokio", "en", "JPY", "ja-JP"),
        ("KR", "Corea del Sur", "Seúl", "en", "KRW", "ko-KR"),
        ("CN", "China", "Shanghái", "en", "CNY", "zh-CN"),
        ("HK", "Hong Kong", "Hong Kong", "en", "HKD", "zh-HK"),
        ("TW", "Taiwán", "Taipéi", "en", "TWD", "zh-TW"),
        ("MY", "Malasia", "Kuala Lumpur", "en", "MYR", "ms-MY"),
        ("TH", "Tailandia", "Bangkok", "en", "THB", "th-TH"),
        ("ID", "Indonesia", "Yakarta", "en", "IDR", "id-ID"),
        ("VN", "Vietnam", "Ciudad Ho Chi Minh", "en", "VND", "vi-VN"),
        ("PH", "Filipinas", "Manila", "en", "PHP", "en-PH"),
        ("PK", "Pakistán", "Karachi", "en", "PKR", "en-PK"),
        ("BD", "Bangladés", "Daca", "en", "BDT", "bn-BD"),
        ("KZ", "Kazajistán", "Almatý", "en", "KZT", "kk-KZ"),
    ],
    "OCEANIA": [
        ("AU", "Australia", "Sídney", "en", "AUD", "en-AU"),
        ("NZ", "Nueva Zelanda", "Auckland", "en", "NZD", "en-NZ"),
        ("FJ", "Fiyi", "Suva", "en", "FJD", "en-FJ"),
    ],
}

# Nombre del país en los otros dos idiomas del producto. Sólo van los que
# CAMBIAN respecto del español: el resto cae al nombre del catálogo. Sin esto
# el selector mundial mostraba "Alemania" en la interfaz en inglés, que es
# justo el detalle que delata que el producto se pensó en un solo idioma.
NOMBRE_PAIS: dict[str, dict[str, str]] = {
    "en": {
        "BR": "Brazil", "DO": "Dominican Republic", "MX": "Mexico",
        "PA": "Panama", "PE": "Peru", "US": "United States", "CA": "Canada",
        "ES": "Spain", "GB": "United Kingdom", "IE": "Ireland",
        "DE": "Germany", "FR": "France", "IT": "Italy", "NL": "Netherlands",
        "BE": "Belgium", "LU": "Luxembourg", "CH": "Switzerland",
        "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "FI": "Finland",
        "IS": "Iceland", "PL": "Poland", "CZ": "Czechia", "SK": "Slovakia",
        "HU": "Hungary", "RO": "Romania", "GR": "Greece", "HR": "Croatia",
        "SI": "Slovenia", "RS": "Serbia", "LV": "Latvia", "LT": "Lithuania",
        "UA": "Ukraine", "TR": "Türkiye", "CY": "Cyprus",
        "ZA": "South Africa", "KE": "Kenya", "EG": "Egypt", "MA": "Morocco",
        "TN": "Tunisia", "DZ": "Algeria", "ET": "Ethiopia",
        "CI": "Côte d'Ivoire", "SG": "Singapore",
        "AE": "United Arab Emirates", "SA": "Saudi Arabia", "QA": "Qatar",
        "BH": "Bahrain", "OM": "Oman", "JO": "Jordan", "LB": "Lebanon",
        "JP": "Japan", "KR": "South Korea", "TW": "Taiwan", "MY": "Malaysia",
        "TH": "Thailand", "PH": "Philippines", "PK": "Pakistan",
        "BD": "Bangladesh", "KZ": "Kazakhstan", "NZ": "New Zealand",
        "FJ": "Fiji", "PR": "Puerto Rico", "EE": "Estonia", "BG": "Bulgaria",
    },
    "pt": {
        "CO": "Colômbia", "PY": "Paraguai", "UY": "Uruguai", "BO": "Bolívia",
        "EC": "Equador", "NI": "Nicarágua", "PR": "Porto Rico", "PE": "Peru",
        "ES": "Espanha", "DE": "Alemanha", "FR": "França", "IT": "Itália",
        "NL": "Países Baixos", "CH": "Suíça", "AT": "Áustria",
        "SE": "Suécia", "FI": "Finlândia", "IS": "Islândia",
        "PL": "Polônia", "CZ": "Chéquia", "SK": "Eslováquia", "HU": "Hungria",
        "RO": "Romênia", "BG": "Bulgária", "GR": "Grécia", "HR": "Croácia",
        "SI": "Eslovênia", "RS": "Sérvia", "EE": "Estônia", "LV": "Letônia",
        "LT": "Lituânia", "UA": "Ucrânia", "TR": "Turquia",
        "ZA": "África do Sul", "NG": "Nigéria", "KE": "Quênia", "GH": "Gana",
        "EG": "Egito", "MA": "Marrocos", "TN": "Tunísia", "DZ": "Argélia",
        "ET": "Etiópia", "CI": "Costa do Marfim",
        "IN": "Índia", "SG": "Singapura", "AE": "Emirados Árabes Unidos",
        "SA": "Arábia Saudita", "BH": "Barein", "OM": "Omã",
        "JO": "Jordânia", "JP": "Japão", "KR": "Coreia do Sul",
        "TW": "Taiwan", "MY": "Malásia", "TH": "Tailândia",
        "ID": "Indonésia", "VN": "Vietnã", "PK": "Paquistão",
        "KZ": "Cazaquistão", "AU": "Austrália", "NZ": "Nova Zelândia",
    },
}

CATALOGO: dict[str, Pais] = {
    fila[0]: Pais(fila[0], fila[1], region, fila[3], fila[4], fila[5], fila[2])
    for region, filas in _FILAS.items()
    for fila in filas
}

PAIS_DEFAULT = CATALOGO["UY"]

# País por defecto según el idioma de la interfaz. Es sólo el valor con el que
# arranca el selector: el cliente lo cambia por el suyo y ése manda.
PAIS_POR_IDIOMA = {"es": "UY", "pt": "BR", "en": "US"}

# ccTLD de dos niveles que se usan de verdad ("banco.com.uy"). Los de un nivel
# se derivan del código ISO, salvo las excepciones de abajo.
_TLD_EXTRA: dict[str, tuple[str, ...]] = {
    "AR": (".com.ar",), "BO": (".com.bo",), "BR": (".com.br",),
    "CO": (".com.co",), "CR": (".co.cr",), "DO": (".com.do",),
    "EC": (".com.ec",), "GT": (".com.gt",), "MX": (".com.mx",),
    "NI": (".com.ni",), "PA": (".com.pa",), "PE": (".com.pe",),
    "PY": (".com.py",), "SV": (".com.sv",), "UY": (".com.uy",),
    "VE": (".com.ve",), "AU": (".com.au",), "NZ": (".co.nz",),
    "ZA": (".co.za",), "NG": (".com.ng",), "KE": (".co.ke",),
    "GH": (".com.gh",), "EG": (".com.eg",), "IL": (".co.il",),
    "JP": (".co.jp",), "KR": (".co.kr",), "IN": (".co.in",),
    "CN": (".com.cn",), "HK": (".com.hk",), "SG": (".com.sg",),
    "MY": (".com.my",), "PH": (".com.ph",), "PK": (".com.pk",),
    "BD": (".com.bd",), "TR": (".com.tr",), "GB": (".co.uk", ".uk"),
    "TW": (".com.tw",), "VN": (".com.vn",), "ID": (".co.id",),
}

# ccTLD que en la práctica se vende como genérico: un ".co" es casi siempre
# una startup, no una empresa colombiana. Deducir el país desde ahí le metía
# al usuario un mercado que no eligió. ".com.co" sí queda: ése es nacional.
_TLD_GENERICOS = {"CO"}


def _mapa_tld() -> dict[str, str]:
    mapa: dict[str, str] = {}
    for codigo in CATALOGO:
        if codigo not in _TLD_GENERICOS:
            mapa[f".{codigo.lower()}"] = codigo
        for extra in _TLD_EXTRA.get(codigo, ()):
            mapa[extra] = codigo
    return mapa


TLD_PAIS: dict[str, str] = _mapa_tld()


def obtener(codigo: str | None) -> Pais:
    """País del catálogo. Un código desconocido no revienta: cae en ASIA
    genérico con idioma inglés, que es lo más neutro que hay."""
    if not codigo:
        return PAIS_DEFAULT
    cod = codigo.strip().upper()
    pais = CATALOGO.get(cod)
    if pais:
        return pais
    return Pais(cod, cod, "ASIA", "en", "USD", "en-US", cod)


def normalizar_nivel(nivel: str | None) -> str:
    """Nombre de ola canónico, aceptando el alias viejo ('latam')."""
    n = (nivel or "").strip().lower()
    n = ALIAS_NIVEL.get(n, n)
    return n if n in NIVELES else NIVEL_MUNDO


def region_de(codigo_pais: str | None) -> str:
    return obtener(codigo_pais).region


def nombre_pais(codigo_pais: str | None, idioma: str = IDIOMA_DEFAULT) -> str:
    """Nombre del país en el idioma pedido; el catálogo está en español."""
    pais = obtener(codigo_pais)
    return NOMBRE_PAIS.get(idioma, {}).get(pais.codigo, pais.nombre)


def nombre_region(region: str, idioma: str = IDIOMA_DEFAULT) -> str:
    nombres = NOMBRE_REGION.get((region or "").upper(), {})
    return nombres.get(idioma) or nombres.get(IDIOMA_DEFAULT) or region


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


def resolver_base(elegido: str | None = None, dominio: str = "",
                  idioma_ui: str = IDIOMA_DEFAULT) -> Pais:
    """
    De dónde sale el país base, en orden: lo que eligió el cliente, el TLD de
    su propio dominio, el idioma de la interfaz. Nunca devuelve None — sin
    país base no hay olas que calcular.
    """
    if elegido and (elegido or "").strip().lower() not in ("auto", ""):
        return obtener(elegido)
    del_dominio = pais_de_dominio(dominio)
    if del_dominio:
        return del_dominio
    return obtener(PAIS_POR_IDIOMA.get(idioma_ui, "UY"))


def idioma_de(codigo_pais: str | None) -> str:
    """Idioma en que se le escribe a un decisor de ese país."""
    idioma = obtener(codigo_pais).idioma
    return idioma if idioma in IDIOMAS else IDIOMA_DEFAULT


def nivel_de(codigo_pais: str | None, base: str | None) -> str:
    """Ola de `codigo_pais` visto desde `base`: local, regional o mundo."""
    pais = obtener(codigo_pais)
    pais_base = obtener(base) if base else PAIS_DEFAULT
    if pais.codigo == pais_base.codigo:
        return NIVEL_LOCAL
    if pais.region == pais_base.region:
        return NIVEL_REGIONAL
    return NIVEL_MUNDO


def prioridad_de(codigo_pais: str | None, base: str | None) -> int:
    return PRIORIDAD_NIVEL[nivel_de(codigo_pais, base)]


def peso_de(codigo_pais: str | None, base: str | None) -> float:
    """Multiplicador geográfico del score (1.0 = el país base del cliente)."""
    return PESO_PRIORIDAD[prioridad_de(codigo_pais, base)]


def paises_por_region(region: str | None = None) -> list[Pais]:
    """Catálogo ordenado por nombre, opcionalmente filtrado por región."""
    paises = list(CATALOGO.values())
    if region:
        paises = [p for p in paises if p.region == region.upper()]
    return sorted(paises, key=lambda p: p.nombre)


def orden_de_olas(base: str | None) -> list[tuple[str, int, list[str]]]:
    """
    Las tres olas de salida al mercado vistas desde el país base, en orden.
    Devuelve (nivel, prioridad, códigos de país). El país base va solo en la
    primera; su región (sin él) en la segunda; todo lo demás en la tercera.
    """
    pais_base = obtener(base) if base else PAIS_DEFAULT
    if pais_base.codigo not in CATALOGO:
        # Un código fuera del catálogo igual tiene que poder ser la ola local:
        # el cliente lo eligió y no hay por qué obligarlo a estar en la lista.
        regionales: list[str] = []
        resto = [p.codigo for p in paises_por_region()]
    else:
        regionales = [p.codigo for p in paises_por_region(pais_base.region)
                      if p.codigo != pais_base.codigo]
        resto = [p.codigo for p in paises_por_region()
                 if p.region != pais_base.region]
    return [
        (NIVEL_LOCAL, PRIORIDAD_LOCAL, [pais_base.codigo]),
        (NIVEL_REGIONAL, PRIORIDAD_REGIONAL, regionales),
        (NIVEL_MUNDO, PRIORIDAD_MUNDO, resto),
    ]
