"""
MV Cliente IA · estrategia y contenido
=======================================
Lo que okara.ai llama «documentos estratégicos» y «agentes de contenido»,
derivado de una corrida ya hecha: ficha del producto, cuadro de competencia,
voz de marca y un plan de contenido por campaña (LinkedIn, X y Reddit) en el
idioma de cada ola.

Qué se replica y qué no
-----------------------
Okara arma cinco documentos (producto, marketing, competencia, voz de marca,
contenido) leyendo la web del cliente y de ahí salen agentes que escriben
posts y contestan hilos. Acá se replica el NÚCLEO —los documentos y los
borradores de contenido— y se deja afuera lo que no cabe en este producto:
publicar solo en el CMS del cliente, SEO/GEO, UGC con avatares y agentes que
comenten en Reddit por uno (Reddit lo bloquea igual que LinkedIn; la regla
12 del proyecto manda: consultas, no listas ni bots).

Todo sale de lo que la corrida ya MIDIÓ sobre el sitio real
(`empresa.resumen_sitio`, la huella de `cliente_ia.segmento`, los
competidores verificados) más los textos en tres idiomas de la fase 1. No se
inventa nada que la web no diga: los precios son los que aparecen escritos,
las pruebas son frases con cifras del propio sitio y la voz de marca se
deduce de cómo escribe la web (vos / tú / usted, largo de frase). Sin sitio
real (modo demo) la ficha se arma con el catálogo y lo dice (`medido=False`).

Es determinista y de biblioteca estándar, como el resto del motor: la misma
corrida da siempre la misma estrategia, con o sin clave de IA.
"""
from __future__ import annotations

import re

from . import busqueda_social, geo, segmento

TOPE_CAMPANAS = 6          # la interfaz no puede mostrar treinta planes
TOPE_PRECIOS = 8
TOPE_CTAS = 6
TOPE_PRUEBAS = 5
LARGO_X = 280              # el límite real de un post en X
LARGO_CONTEXTO = 90        # cuánto texto alrededor de un precio se guarda

# Un precio es una moneda pegada a un número, o un número seguido de su
# moneda. El período (mes/año) se busca en el texto que sigue.
_RE_PRECIO = re.compile(
    r"(?:(?:USD|US\$|U\$S|\$U|R\$|EUR|€|\$)\s?\d[\d.,]*\d|\d[\d.,]*\d\s?"
    r"(?:USD|EUR|d[oó]lares|reais|euros))", re.I)
_RE_PERIODO = re.compile(
    r"^\s*(?:/|por|per|al|ao|a)?\s*(mes|m[eê]s|month|mo\b|mensual|mensal|monthly|"
    r"a[ñn]o|ano|year|yr|anual|annual|yearly)", re.I)
_PERIODO = {"mes": "mes", "mês": "mes", "month": "mes", "mo": "mes", "mensual": "mes",
            "mensal": "mes", "monthly": "mes", "año": "anio", "ano": "anio",
            "year": "anio", "yr": "anio", "anual": "anio", "annual": "anio",
            "yearly": "anio"}

# Frases con cifras que sostienen un argumento: porcentajes, «24/7», «x3»,
# cantidades con unidad. Son las «pruebas» que un post puede citar sin
# inventar nada.
_RE_PRUEBA = re.compile(
    r"\d+\s?%|\b\d+x\b|\bx\d+\b|24/7|\b\d[\d.]*\s?(?:d[ií]as|dias|minutos|horas|"
    r"llamadas|ligações|clientes|pa[ií]ses|a[ñn]os|anos|gestiones|contactos|"
    r"years|days|hours|minutes|calls|customers|countries|simult[aâ]neas|"
    r"simultaneous)\b", re.I)

# Verbos con los que empieza un llamado a la acción, en los tres idiomas y
# en los tres tratos del español. Un CTA es una frase corta que arranca con
# uno de estos.
_VERBOS_CTA = {
    "es": "solicit|agend|prob|ped|conoc|descubr|empez|comenz|habl|contact|"
          "mir|reserv|sum|prueb|pid|empiez|comienz|escrib|llam|regist|ver",
    "pt": "solicit|agend|experiment|conhe|descubr|come|fal|pe|vej|cadastr|entr",
    "en": "request|book|schedule|try|get|start|talk|contact|see|watch|discover|"
          "sign|learn|join|explore",
}
# Después del verbo entran hasta cuatro palabras EN MINÚSCULA: el texto
# plano de una web pega un bloque con el siguiente sin puntuación, y la
# mayúscula del bloque que sigue («Pedir una demo Planes desde…») es el
# único corte que queda.
_VERBOS = "|".join(f"[{v[0].upper()}{v[0]}]{v[1:]}"
                   for grupo in _VERBOS_CTA.values() for v in grupo.split("|"))
_RE_CTA = re.compile(
    r"(?:^|[.!?\n•·|])\s*((?:" + _VERBOS + r")[a-záéíóúñãçê-]*"
    r"(?:\s+[a-záéíóúñãçê0-9-]+){1,4})(?=[\s.!?,;:]|$)")

# Lo que separa dos bloques en el texto plano de una web: puntuación, o una
# palabra que arranca en mayúscula (el título del bloque siguiente).
_RE_CORTE_PRUEBA = re.compile(r"[.!?\n|≈]|\s·\s")
_RE_MAYUSCULA = re.compile(r"\s(?=[A-ZÁÉÍÓÚÑ][a-záéíóúñ])")

# Trato al lector: cómo escribe la web decide cómo escribe el contenido.
# El voseo se reconoce por el imperativo agudo («solicitá», «usá», «abrí»);
# las palabras agudas que NO son imperativos («está», «así», «acá») se
# descartan por lista, si no cualquier web en español «trataba de vos».
_RE_VOSEO = re.compile(r"\b(?:[a-záéíóúñ]{2,}[áéí]|ten[eé]s|pod[eé]s|quer[eé]s|sos|vos)\b")
_NO_VOSEO = frozenset(
    "esta estan sera seran seras podra podran habra tendra hara dara dira ira vera "
    "ahi aqui alli aca asi que quiza ojala cafe sofa papa mama bebe comite jose "
    "maria ademas".split())
_SIN_ACENTO = str.maketrans("áéíóúñ", "aeioun")

# Las palabras más frecuentes de cada idioma, para saber en cuál está
# escrita la portada. El `lang` del HTML no alcanza: un sitio con versiones
# en tres idiomas las declara todas y la primera en orden alfabético es «en».
_MARCAS_IDIOMA = {
    "es": ("el", "la", "los", "las", "para", "con", "que", "una", "por"),
    "pt": ("o", "os", "as", "para", "com", "que", "uma", "não", "você", "seu", "sua"),
    "en": ("the", "and", "for", "with", "your", "you", "that", "our"),
}


def idioma_del_texto(texto: str, defecto: str = "es") -> str:
    """En qué idioma está escrito `texto`, contando sus palabras vacías."""
    palabras = re.findall(r"[a-záéíóúñãçêõ]+", (texto or "").lower())
    if not palabras:
        return defecto
    conteo = {idi: sum(1 for p in palabras if p in marcas)
              for idi, marcas in _MARCAS_IDIOMA.items()}
    mejor = max(conteo, key=lambda k: (conteo[k], k == defecto))
    return mejor if conteo[mejor] else defecto
# «prueba» y «agenda» quedan afuera a propósito: son sustantivos la mitad
# de las veces («la prueba gratis», «tu agenda») y contaban como tuteo.
_RE_TUTEO = re.compile(r"\b(?:tienes|puedes|quieres|eres|tú|tus|conoce|descubre|"
                       r"solicita|empieza|comienza|regístrate|contáctanos)\b")
_RE_USTED = re.compile(r"\b(?:usted|solicite|pruebe|descubra|conozca|agende|comience|"
                       r"empiece|contáctenos|su empresa|su equipo|su cartera)\b")

_SUPERLATIVOS = ("el mejor", "la mejor", "líder", "lider", "revolucionari", "único",
                 "unico", "#1", "número uno", "numero uno", "o melhor", "a melhor",
                 "the best", "leading", "revolutionary", "world-class", "cutting-edge")

# Etiquetas de la interfaz que viajan en el markdown y en las reglas. Están
# acá y no en el JSON de i18n del frontend porque el markdown se arma en el
# motor (lo copian desde la app y lo exportan por la API).
_T = {
    "es": {
        "producto": "Ficha del producto", "competencia": "Competencia",
        "voz": "Voz de marca", "contenido": "Plan de contenido",
        "propuesta": "Propuesta", "categoria": "Categoría", "sectores": "A quién le vende",
        "dolores": "Dolores que resuelve", "diferenciales": "Diferenciales",
        "precios": "Precios publicados", "ctas": "Llamados a la acción del sitio",
        "sin_precios": "El sitio no publica precios.",
        "registro": "Trato al lector", "tono": "Tono", "largo": "Largo de frase",
        "palabras": "Palabras que definen el segmento", "pruebas": "Pruebas con cifras",
        "evitar": "Superlativos que ya usa el sitio (sostenerlos con datos o sacarlos)",
        "reglas": "Reglas para escribir", "tema": "Tema", "linkedin": "Post para LinkedIn",
        "x": "Post para X", "reddit": "Hilos en Reddit donde se habla del problema",
        "mes": "por mes", "anio": "por año", "voseo": "de vos", "tuteo": "de tú",
        "usted": "de usted", "neutro": "sin trato marcado", "voce": "de você",
        "directo": "de «you», directo", "corto": "directo", "medio": "equilibrado",
        "largo_": "explicativo",
        "r_registro": "Tratá al lector {registro}, como hace tu web.",
        "r_registro_neutro": "Tu web no marca un trato (vos/tú/usted): elegí uno y sostenelo.",
        "r_largo": "Frases de {n} palabras en promedio: tono {tono}. Mantenelo.",
        "r_pruebas": "Citá cifras del propio sitio ({n} disponibles); sin cifra, no afirmes.",
        "r_sin_pruebas": "El sitio no publica cifras: escribí con casos concretos, no con adjetivos.",
        "r_superlativos": "El sitio usa superlativos ({lista}): en el contenido, cambialos por un dato.",
        "r_sin_superlativos": "El sitio no usa superlativos. Que el contenido tampoco.",
        "r_palabras": "Nombrá el segmento con sus palabras: {lista}.",
        "posicion": "De {n} competidores, {base} tienen base en {pais} y {venden} le venden a tu "
                    "mercado; solapamiento promedio {sol}. Tu diferencial más fuerte contra "
                    "ellos: «{dif}».",
        "posicion_vacia": "La corrida no encontró competidores: el diferencial se sostiene solo.",
        "pregunta": "¿Cómo lo resuelven hoy en tu equipo?",
        "vemos": "Lo escuchamos seguido en {sector} de {pais}",
        "no_medido": "Ficha armada con el catálogo genérico: corré en modo web o con IA "
                     "para leerla del sitio real.",
    },
    "pt": {
        "producto": "Ficha do produto", "competencia": "Concorrência",
        "voz": "Voz da marca", "contenido": "Plano de conteúdo",
        "propuesta": "Proposta", "categoria": "Categoria", "sectores": "Para quem vende",
        "dolores": "Dores que resolve", "diferenciales": "Diferenciais",
        "precios": "Preços publicados", "ctas": "Chamadas para ação do site",
        "sin_precios": "O site não publica preços.",
        "registro": "Tratamento do leitor", "tono": "Tom", "largo": "Tamanho da frase",
        "palabras": "Palavras que definem o segmento", "pruebas": "Provas com números",
        "evitar": "Superlativos que o site já usa (sustentar com dados ou tirar)",
        "reglas": "Regras para escrever", "tema": "Tema", "linkedin": "Post para LinkedIn",
        "x": "Post para X", "reddit": "Tópicos no Reddit onde se fala do problema",
        "mes": "por mês", "anio": "por ano", "voseo": "de «vos»", "tuteo": "de «tú»",
        "usted": "de «usted»", "neutro": "sem tratamento marcado", "voce": "de você",
        "directo": "de «you», direto", "corto": "direto", "medio": "equilibrado",
        "largo_": "explicativo",
        "r_registro": "Trate o leitor {registro}, como faz o seu site.",
        "r_registro_neutro": "Seu site não marca um tratamento: escolha um e mantenha.",
        "r_largo": "Frases de {n} palavras em média: tom {tono}. Mantenha.",
        "r_pruebas": "Cite números do próprio site ({n} disponíveis); sem número, não afirme.",
        "r_sin_pruebas": "O site não publica números: escreva com casos concretos, não com adjetivos.",
        "r_superlativos": "O site usa superlativos ({lista}): no conteúdo, troque por um dado.",
        "r_sin_superlativos": "O site não usa superlativos. O conteúdo também não.",
        "r_palabras": "Nomeie o segmento com as palavras dele: {lista}.",
        "posicion": "De {n} concorrentes, {base} têm base em {pais} e {venden} vendem para o "
                    "seu mercado; sobreposição média {sol}. Seu diferencial mais forte "
                    "contra eles: «{dif}».",
        "posicion_vacia": "A busca não encontrou concorrentes: o diferencial se sustenta sozinho.",
        "pregunta": "Como resolvem isso hoje na sua equipe?",
        "vemos": "Ouvimos isso com frequência em {sector} de {pais}",
        "no_medido": "Ficha montada com o catálogo genérico: rode em modo web ou com IA "
                     "para lê-la do site real.",
    },
    "en": {
        "producto": "Product brief", "competencia": "Competitors",
        "voz": "Brand voice", "contenido": "Content plan",
        "propuesta": "Value proposition", "categoria": "Category", "sectores": "Who buys it",
        "dolores": "Pains it solves", "diferenciales": "Differentiators",
        "precios": "Published pricing", "ctas": "Calls to action on the site",
        "sin_precios": "The site does not publish pricing.",
        "registro": "Reader address", "tono": "Tone", "largo": "Sentence length",
        "palabras": "Words that define the segment", "pruebas": "Proof with numbers",
        "evitar": "Superlatives the site already uses (back them with data or drop them)",
        "reglas": "Writing rules", "tema": "Topic", "linkedin": "LinkedIn post",
        "x": "X post", "reddit": "Reddit threads discussing the problem",
        "mes": "per month", "anio": "per year", "voseo": "as «vos»", "tuteo": "as «tú»",
        "usted": "as «usted»", "neutro": "no marked address", "voce": "as «você»",
        "directo": "as «you», direct", "corto": "direct", "medio": "balanced",
        "largo_": "explanatory",
        "r_registro": "Address the reader {registro}, as your site does.",
        "r_registro_neutro": "Your site does not settle on an address: pick one and keep it.",
        "r_largo": "Sentences average {n} words: {tono} tone. Keep it.",
        "r_pruebas": "Quote figures from the site itself ({n} available); no figure, no claim.",
        "r_sin_pruebas": "The site publishes no figures: write with concrete cases, not adjectives.",
        "r_superlativos": "The site uses superlatives ({lista}): in content, replace them with a fact.",
        "r_sin_superlativos": "The site uses no superlatives. Neither should the content.",
        "r_palabras": "Name the segment with its own words: {lista}.",
        "posicion": "Of {n} competitors, {base} are based in {pais} and {venden} sell into your "
                    "market; average overlap {sol}. Your strongest differentiator against "
                    "them: «{dif}».",
        "posicion_vacia": "The run found no competitors: the differentiator stands on its own.",
        "pregunta": "How does your team handle it today?",
        "vemos": "We hear it often from {sector} in {pais}",
        "no_medido": "Brief built from the generic catalogue: run in web or AI mode to read "
                     "it from the real site.",
    },
}


def _t(idioma: str) -> dict:
    return _T.get(idioma) or _T["es"]


def _mayuscula(texto: str) -> str:
    t = " ".join((texto or "").split())
    return t[:1].upper() + t[1:] if t else t


def _recortar(texto: str, tope: int) -> str:
    t = " ".join((texto or "").split())
    if len(t) <= tope:
        return t
    return t[:tope - 1].rsplit(" ", 1)[0].rstrip(",;:.") + "…"


def _frases(texto: str) -> list[str]:
    return [f.strip() for f in re.split(r"[.!?\n]+", texto or "") if f.strip()]


# ---------------------------------------------------------------------------
# Producto
# ---------------------------------------------------------------------------

def precios(texto: str) -> list[dict]:
    """Los precios ESCRITOS en el texto, en orden de aparición y sin repetir.
    Cada uno con su período si el texto lo dice al lado."""
    salida: list[dict] = []
    vistos: dict[str, dict] = {}
    for m in _RE_PRECIO.finditer(texto or ""):
        monto = " ".join(m.group(0).split())
        # «USD 99» del hero y «US$99 /mes» de la tabla de planes son el mismo
        # precio: se guarda una vez, con el período si alguna de las dos lo
        # trae.
        clave = _clave_precio(monto)
        resto = texto[m.end():m.end() + 16]
        per = _RE_PERIODO.match(resto)
        periodo = _PERIODO.get(per.group(1).lower().rstrip(" "), "") if per else ""
        if clave in vistos:
            if periodo and not vistos[clave]["periodo"]:
                vistos[clave]["periodo"] = periodo
            continue
        ini = max(0, m.start() - LARGO_CONTEXTO // 2)
        contexto = " ".join(texto[ini:m.end() + LARGO_CONTEXTO // 2].split())
        vistos[clave] = {"monto": monto, "periodo": periodo, "contexto": contexto}
        salida.append(vistos[clave])
    # Primero los precios en moneda dura, que son los del plan; después los
    # equivalentes locales y las cifras de los ejemplos.
    salida.sort(key=lambda p: 0 if _clave_precio(p["monto"]).startswith(("USD", "EUR")) else 1)
    return salida[:TOPE_PRECIOS]


_MONEDA = (("US$", "USD"), ("U$S", "USD"), ("USD", "USD"), ("$U", "UYU"), ("R$", "BRL"),
           ("€", "EUR"), ("EUR", "EUR"), ("$", "$"))


def _clave_precio(monto: str) -> str:
    m = monto.upper().replace(" ", "")
    moneda = next((canon for alias, canon in _MONEDA if alias in m), "?")
    return moneda + re.sub(r"[^\d]", "", m)


def llamados(texto: str) -> list[str]:
    """Los llamados a la acción del sitio: frases cortas que arrancan con un
    verbo de acción. Es lo que el contenido tiene que repetir al cierre."""
    salida: list[str] = []
    vistos: set[str] = set()
    for m in _RE_CTA.finditer(texto or ""):
        if not m.group(1)[0].isupper():
            continue                         # un verbo en medio de una frase
        cta = _mayuscula(m.group(1)).rstrip(" ,;:")
        clave = cta.lower()
        if clave in vistos or len(cta) < 8:
            continue
        vistos.add(clave)
        salida.append(cta)
        if len(salida) >= TOPE_CTAS:
            break
    return salida


def _texto_largo(empresa) -> str:
    """El texto del sitio más largo que haya: los precios y los llamados a
    la acción viven abajo del pliegue, donde el resumen no llega."""
    return (getattr(empresa, "texto_sitio", "") or "") or (empresa.resumen_sitio or "")


def _producto(empresa, idioma: str) -> dict:
    texto = _texto_largo(empresa)
    return {
        "nombre": empresa.nombre,
        "dominio": empresa.dominio,
        "propuesta": empresa.propuesta,
        "categoria": empresa.categoria,
        "sectores": list(empresa.texto(idioma, "sectores_objetivo", []) or
                         empresa.sectores_objetivo),
        "dolores": list(empresa.texto(idioma, "dolores", []) or empresa.dolores),
        "diferenciales": list(empresa.texto(idioma, "diferenciales", []) or
                              empresa.diferenciales),
        "tamano_objetivo": empresa.tamano_objetivo,
        "idiomas": list(empresa.idiomas),
        "precios": precios(texto),
        "ctas": llamados(texto),
        "medido": bool((empresa.resumen_sitio or "").strip()),
    }


# ---------------------------------------------------------------------------
# Competencia
# ---------------------------------------------------------------------------

def _competencia(corrida, idioma: str) -> dict:
    filas = []
    for c in corrida.competidores:
        filas.append({
            "nombre": c.nombre or c.dominio, "dominio": c.dominio, "pais": c.pais,
            "pais_nombre": geo.nombre_pais(c.pais, idioma) if c.pais else "",
            "solapamiento": c.solapamiento, "afinidad": c.afinidad,
            "clase": segmento.clasificar(c.afinidad) if c.afinidad >= 0 else "",
            "posicionamiento": c.posicionamiento,
            "vende_en_objetivo": c.vende_en_objetivo, "fuente": c.fuente,
        })
    t = _t(idioma)
    difs = list(corrida.empresa.texto(idioma, "diferenciales", []) or
                corrida.empresa.diferenciales) if corrida.empresa else []
    if not filas:
        posicion = t["posicion_vacia"]
    else:
        base = sum(1 for f in filas if f["pais"] == corrida.pais_base)
        venden = sum(1 for f in filas if f["vende_en_objetivo"] or
                     f["pais"] == corrida.pais_base)
        sol = sum(f["solapamiento"] for f in filas) / len(filas)
        posicion = t["posicion"].format(
            n=len(filas), base=base, venden=venden,
            pais=geo.nombre_pais(corrida.pais_base, idioma), sol=f"{sol:.0%}",
            dif=difs[0] if difs else "—")
    return {"filas": filas, "posicion": posicion, "diferenciales": difs}


# ---------------------------------------------------------------------------
# Voz de marca
# ---------------------------------------------------------------------------

def registro(texto: str, idioma_sitio: str) -> str:
    """Cómo le habla la web al lector. En español importa de verdad: un
    contenido de «tú» debajo de una web de «vos» se nota al instante."""
    t = (texto or "").lower()
    if idioma_sitio == "pt":
        return "voce" if "você" in t or "voce" in t else "neutro"
    if idioma_sitio == "en":
        return "directo" if re.search(r"\byou\b|\byour\b", t) else "neutro"
    voseo = [w for w in _RE_VOSEO.findall(t) if w.translate(_SIN_ACENTO) not in _NO_VOSEO]
    conteo = {"voseo": len(voseo), "tuteo": len(_RE_TUTEO.findall(t)),
              "usted": len(_RE_USTED.findall(t))}
    mejor = max(conteo, key=lambda k: (conteo[k], k))
    if conteo[mejor] == 0 or list(conteo.values()).count(conteo[mejor]) > 1:
        return "neutro"
    return mejor


def pruebas(texto: str) -> list[str]:
    """Frases del sitio que traen una cifra: lo único que un post puede
    afirmar sin inventar."""
    salida: list[str] = []
    fin_anterior = 0
    texto = texto or ""
    for m in _RE_PRUEBA.finditer(texto):
        if m.start() < fin_anterior:
            continue                         # la misma frase, otra cifra
        # Una ventana alrededor de la cifra, cortada en la puntuación más
        # cercana: la «frase» de una web sin puntos es la portada entera.
        ini = max(0, m.start() - LARGO_CONTEXTO)
        fin = min(len(texto), m.end() + LARGO_CONTEXTO)
        antes_crudo, despues_crudo = texto[ini:m.start()], texto[m.end():fin]
        # El bloque anterior termina donde arranca la última palabra en
        # mayúscula; el siguiente, donde arranca la primera.
        antes = _RE_MAYUSCULA.split(_RE_CORTE_PRUEBA.split(antes_crudo)[-1])[-1]
        despues = _RE_MAYUSCULA.split(_RE_CORTE_PRUEBA.split(despues_crudo)[0])[0]
        # Si la ventana cayó en medio de una palabra, esa palabra se saca. Si
        # cayó en un espacio o en un corte, la primera palabra está entera.
        if (ini > 0 and len(antes) == len(antes_crudo)
                and not texto[ini - 1].isspace() and " " in antes):
            antes = antes.split(" ", 1)[1]
        if (fin < len(texto) and len(despues) == len(despues_crudo)
                and not texto[fin].isspace() and " " in despues):
            despues = despues.rsplit(" ", 1)[0]
        frase = " ".join((antes + m.group(0) + despues).split()).strip(" ,;:·")
        fin_anterior = m.end() + len(despues)
        if len(frase.split()) >= 3 and frase not in salida:
            salida.append(frase)
        if len(salida) >= TOPE_PRUEBAS:
            break
    return salida


def superlativos(texto: str) -> list[str]:
    t = (texto or "").lower()
    return [s for s in _SUPERLATIVOS if s in t]


def _voz(empresa, huella, idioma: str) -> dict:
    texto = _texto_largo(empresa) if (empresa.resumen_sitio or "").strip() else ""
    t = _t(idioma)
    palabras = segmento.palabras_de_busqueda(huella, 8)
    idioma_sitio = idioma_del_texto(texto, empresa.idiomas[0] if empresa.idiomas else idioma)
    regla_palabras = t["r_palabras"].format(lista=", ".join(palabras[:5])) if palabras else ""
    if not texto.strip():
        # Sin sitio real no hay voz que medir: decir «tu web trata de tú»
        # sobre los textos del catálogo sería inventar. Queda la regla que sí
        # es de este producto (sus palabras) y el aviso de que falta medir.
        return {"registro": "neutro", "idioma": idioma_sitio, "largo_frase": 0,
                "tono": "medio", "palabras": palabras, "pruebas": [], "ctas": [],
                "superlativos": [], "medido": False,
                "reglas": [r for r in (t["no_medido"], regla_palabras) if r]}
    frases = [f for f in _frases(texto) if len(f.split()) >= 4]
    largo = (sum(len(f.split()) for f in frases) / len(frases)) if frases else 0
    tono = "corto" if largo and largo <= 14 else ("largo_" if largo > 22 else "medio")
    reg = registro(texto, idioma_sitio)
    pr = pruebas(texto)
    sup = superlativos(texto)
    reglas = [
        t["r_registro"].format(registro=t[reg]) if reg != "neutro" else t["r_registro_neutro"],
        t["r_largo"].format(n=round(largo), tono=t[tono]) if largo else "",
        t["r_pruebas"].format(n=len(pr)) if pr else t["r_sin_pruebas"],
        t["r_superlativos"].format(lista=", ".join(sup)) if sup else t["r_sin_superlativos"],
        regla_palabras,
    ]
    return {
        "registro": reg, "idioma": idioma_sitio, "largo_frase": round(largo, 1),
        "tono": tono, "palabras": palabras, "pruebas": pr,
        "ctas": llamados(texto), "superlativos": sup,
        "reglas": [r for r in reglas if r], "medido": True,
    }


# ---------------------------------------------------------------------------
# Contenido por campaña
# ---------------------------------------------------------------------------

def _post_linkedin(campana, empresa, prueba: str, pais: str, hashtags: list[str]) -> str:
    idi = campana.idioma if campana.idioma in geo.IDIOMAS else "es"
    t = _t(idi)
    propuesta = empresa.texto(idi, "propuesta", "") or empresa.propuesta
    lineas = [_mayuscula(campana.dolor).rstrip(".") + "."]
    # El ángulo entra sólo si agrega algo: el proveedor demo lo arma
    # repitiendo el dolor, y un post que dice lo mismo dos veces no se lee.
    angulo = " ".join((campana.angulo or "").split())
    if angulo and campana.dolor.lower()[:40] not in angulo.lower():
        lineas.append(_mayuscula(angulo).rstrip(".") + ".")
    lineas.append(t["vemos"].format(sector=campana.sector, pais=pais) + ".")
    quien = f"{empresa.nombre} {propuesta}".strip().rstrip(".") + "."
    lineas.append(quien + (f" {_mayuscula(prueba).rstrip('.')}." if prueba else ""))
    lineas.append(t["pregunta"])
    if hashtags:
        lineas.append(" ".join(f"#{h}" for h in hashtags))
    return "\n\n".join(lineas)


def _post_x(campana, empresa, sitio: str) -> str:
    idi = campana.idioma if campana.idioma in geo.IDIOMAS else "es"
    propuesta = empresa.texto(idi, "propuesta", "") or empresa.propuesta
    cola = f" {sitio}" if sitio else ""
    dolor = _mayuscula(campana.dolor).rstrip(".") + "."
    quien = f"{empresa.nombre} {propuesta}".strip().rstrip(".") + "."
    cuerpo = f"{dolor} {quien}"
    return _recortar(cuerpo, LARGO_X - len(cola)) + cola


# Cuántos planes de contenido lleva cada ola. El país del cliente se lleva la
# mitad y las tres olas están siempre: si se tomaran las seis primeras
# campañas por prioridad, con doce sectores locales no aparecía ni un post en
# portugués ni en inglés — y el contenido en tres idiomas es la mitad del
# producto.
REPARTO_CAMPANAS = {geo.NIVEL_LOCAL: 3, geo.NIVEL_REGIONAL: 2, geo.NIVEL_MUNDO: 1}


def _elegir_campanas(campanas) -> list:
    """Hasta `TOPE_CAMPANAS`, repartidas por ola y con el país propio
    primero. Lo que una ola no llena lo llena la siguiente en prioridad."""
    por_nivel = {n: [] for n in geo.NIVELES}
    for c in sorted(campanas, key=lambda c: (c.prioridad, c.sector)):
        por_nivel[geo.normalizar_nivel(c.nivel)].append(c)
    elegidas = []
    for nivel in geo.NIVELES:
        elegidas += por_nivel[nivel][:REPARTO_CAMPANAS[nivel]]
        por_nivel[nivel] = por_nivel[nivel][REPARTO_CAMPANAS[nivel]:]
    for nivel in geo.NIVELES:                     # sobrantes, país propio primero
        while len(elegidas) < TOPE_CAMPANAS and por_nivel[nivel]:
            elegidas.append(por_nivel[nivel].pop(0))
    return elegidas[:TOPE_CAMPANAS]


def _contenido(corrida, huella) -> list[dict]:
    empresa = corrida.empresa
    sitio = (corrida.enlaces or {}).get("sitio") or ""
    claves = segmento.palabras_de_busqueda(huella, 4)
    pr = pruebas(_texto_largo(empresa))
    salida = []
    for i, c in enumerate(_elegir_campanas(corrida.campanas)):
        idi = c.idioma if c.idioma in geo.IDIOMAS else "es"
        pais_cod = c.paises[0] if c.paises else ""
        pais = geo.nombre_pais(pais_cod, idi) if pais_cod else ""
        hashtags = [h for h in (busqueda_social.hashtag(c.sector),
                                busqueda_social.hashtag(claves[0]) if claves else "") if h]
        reddit = busqueda_social.reddit(huella, c.dolor, c.sector)
        # Cada campaña cita una prueba distinta mientras haya: seis posts con
        # la misma cifra parecen escritos por una máquina.
        prueba = pr[i % len(pr)] if pr else (
            empresa.texto(idi, "diferenciales", [None])[0] or "")
        salida.append({
            "campana_id": c.id, "sector": c.sector, "nivel": c.nivel,
            "pais": pais_cod, "pais_nombre": pais, "idioma": idi,
            "tema": _mayuscula(c.dolor),
            "linkedin": _post_linkedin(c, empresa, prueba, pais, hashtags),
            "x": _post_x(c, empresa, sitio),
            "reddit": reddit.a_dict(), "hashtags": hashtags,
        })
    return salida


# ---------------------------------------------------------------------------
# Todo junto
# ---------------------------------------------------------------------------

def armar(corrida, huella=None) -> dict:
    """Los cuatro documentos de una corrida terminada, más su markdown."""
    if corrida.empresa is None:
        return {}
    idioma = corrida.idioma_ui if corrida.idioma_ui in geo.IDIOMAS else "es"
    huella = huella if huella is not None else segmento.huella_de(corrida.empresa)
    doc = {
        "producto": _producto(corrida.empresa, idioma),
        "competencia": _competencia(corrida, idioma),
        "voz": _voz(corrida.empresa, huella, idioma),
        "contenido": _contenido(corrida, huella),
    }
    doc["markdown"] = a_markdown(doc, idioma)
    return doc


def a_markdown(doc: dict, idioma: str = "es") -> str:
    """Los documentos como un solo texto para copiar o mandar: es la forma en
    que se comparten con quien escribe el contenido."""
    t = _t(idioma)
    p, comp, voz = doc["producto"], doc["competencia"], doc["voz"]
    lineas = [f"# {p['nombre']} · {p['dominio']}", "", f"## {t['producto']}", ""]
    if not p["medido"]:
        lineas += [f"> {t['no_medido']}", ""]
    lineas += [f"**{t['propuesta']}:** {p['propuesta']}",
               f"**{t['categoria']}:** {p['categoria']}", ""]
    for clave in ("sectores", "dolores", "diferenciales"):
        if p[clave]:
            lineas += [f"**{t[clave]}:**", *(f"- {x}" for x in p[clave]), ""]
    if p["precios"]:
        lineas += [f"**{t['precios']}:**", *(
            f"- {x['monto']}" + (f" {t[x['periodo']]}" if x["periodo"] else "")
            + f" — «{x['contexto']}»" for x in p["precios"]), ""]
    else:
        lineas += [t["sin_precios"], ""]
    if p["ctas"]:
        lineas += [f"**{t['ctas']}:** " + " · ".join(p["ctas"]), ""]
    lineas += [f"## {t['competencia']}", "", comp["posicion"], ""]
    for f in comp["filas"]:
        afin = f" · {f['clase']} ({f['afinidad']:.0%})" if f["clase"] else ""
        lineas.append(f"- **{f['nombre']}** ({f['pais_nombre'] or f['dominio']}) · "
                      f"{f['solapamiento']:.0%}{afin} — {f['posicionamiento']}")
    lineas += ["", f"## {t['voz']}", "",
               f"**{t['registro']}:** {t[voz['registro']]}",
               f"**{t['largo']}:** {voz['largo_frase']} · **{t['tono']}:** {t[voz['tono']]}",
               f"**{t['palabras']}:** " + ", ".join(voz["palabras"]), ""]
    if voz["pruebas"]:
        lineas += [f"**{t['pruebas']}:**", *(f"- {x}" for x in voz["pruebas"]), ""]
    if voz["superlativos"]:
        lineas += [f"**{t['evitar']}:** " + ", ".join(voz["superlativos"]), ""]
    lineas += [f"**{t['reglas']}:**", *(f"{i}. {r}" for i, r in enumerate(voz["reglas"], 1)),
               "", f"## {t['contenido']}", ""]
    for c in doc["contenido"]:
        lineas += [f"### {c['sector']} · {c['pais_nombre']} ({c['idioma']})", "",
                   f"**{t['tema']}:** {c['tema']}", "",
                   f"**{t['linkedin']}:**", "", c["linkedin"], "",
                   f"**{t['x']}:**", "", c["x"], "",
                   f"**{t['reddit']}:** {c['reddit']['url']}", ""]
    return "\n".join(lineas).strip() + "\n"
