"""
MV Cliente IA · huella de segmento
===================================
Qué vende ESTE producto, en palabras, sacadas de su propia web — y cuánto se
le parece cualquier otro texto.

El problema que resuelve
------------------------
Hasta acá el filtro de rubro dependía de dos cosas que el modelo **declara**:
el `sector` que él mismo eligió y un `solapamiento` que él mismo puntúa. Eso
alcanza para ordenar, no para filtrar: un competidor inventado o de un rubro
vecino llega con `solapamiento: 0.9` y nadie lo contradice. Acá el filtro pasa
a ser **medido**: se baja la web del candidato y se compara contra la huella
del producto real. Si no habla del mismo tema, se nota y se dice.

Cómo funciona
-------------
1. `huella_de(empresa)` arma un vocabulario pesado del producto: unigramas y
   bigramas del texto REAL del sitio, más la categoría y los sectores objetivo.
   Los bigramas pesan más que los unigramas — "gestión de cobranzas" identifica
   un rubro, "gestión" sola no identifica nada.
2. `afinidad(huella, texto)` devuelve 0..1: qué parte del peso de la huella
   aparece en ese texto.

Reglas que se respetan acá
--------------------------
- **Determinista** (regla 7 del proyecto): sin azar, sin sets sin ordenar, sin
  depender del orden de un dict. La misma web da siempre la misma huella.
- **Sólo biblioteca estándar**, como todo el motor.
- **Tres idiomas**: las palabras vacías de es/pt/en van juntas en una sola
  lista. Un sitio uruguayo puede tener la portada en inglés y no por eso deja
  de ser del rubro.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Los bigramas identifican rubro; los unigramas apenas lo sugieren. La
# proporción se eligió mirando salidas reales: con bigramas al mismo peso, la
# huella de un software de cobranzas se parecía a la de cualquier software.
PESO_BIGRAMA = 2.5
PESO_UNIGRAMA = 1.0

TOPE_TERMINOS = 26           # más que esto es cola larga y sólo agrega ruido
MIN_LARGO = 4                # "ia", "app", "web" solas no discriminan nada
MAX_TEXTO = 40_000           # una portada enorme no puede colgar el análisis

# Umbrales de decisión. No son mágicos: son el punto donde, mirando salidas
# reales, un sitio deja de hablar del mismo tema. `AFIN_DUDOSA` sólo degrada
# el orden; `AFIN_AJENA` es la que descarta, y por eso está bien abajo — es
# preferible dejar pasar un competidor flojo que borrar uno bueno.
AFIN_BUENA = 0.30
AFIN_DUDOSA = 0.15
AFIN_AJENA = 0.06

# Para BUSCAR sólo sirven los términos que definen el producto. Un término con
# menos de este porcentaje del peso máximo es cola larga: metido en una
# consulta con AND, devuelve cero resultados.
PISO_BUSQUEDA = 0.35

# Menos términos que esto y la huella no describe un rubro: describe una
# portada vacía. Verificar contra ella descartaría a todo el mundo por igual.
MIN_TERMINOS_VERIFICAR = 8

# Palabras vacías de los tres idiomas + la paja universal de toda web
# comercial (cookies, política de privacidad, menús). Sin esto la huella de
# cualquier sitio incluía "política de privacidad" y todo se parecía a todo.
#
# Van separadas por idioma y unidas al final —y no en un set literal enorme—
# porque los tres comparten palabras ("sobre", "todo", "menu") y en un literal
# único eso es una repetición silenciosa que nadie ve al agregar una más.
_VACIAS_ES = frozenset("""
para como esta este esto estos estas pero porque cuando donde desde hasta
sobre entre todo toda todos todas otro otra otros otras cada mismo misma
tambien solo mas menos muy poco mucho nuestro nuestra nuestros nuestras
puede pueden hacer tiene tienen somos estamos quienes nosotros contacto
inicio servicios productos empresa empresas acerca aviso legal terminos
condiciones privacidad politica cookies derechos reservados copyright menu
buscar leer aqui click clic aceptar cerrar enviar nombre correo telefono
mensaje sitio pagina
""".split())

_VACIAS_PT = frozenset("""
como esta este isso porque quando onde desde sobre entre todo toda todos
todas outro outra cada mesmo tambem apenas mais menos muito pouco nosso
nossa nossos nossas pode podem fazer temos somos estamos quem contato
inicio servicos produtos empresa aviso termos condicoes privacidade politica
direitos reservados
""".split())

_VACIAS_EN = frozenset("""
the and for with from that this these those but because when where until
about between all each same also only more less very much our your their
can make have has are were was who contact home services products company
legal terms conditions privacy policy cookies rights reserved copyright menu
search read here click accept close send name email phone message site page
learn sign login register subscribe
""".split())

_VACIAS = _VACIAS_ES | _VACIAS_PT | _VACIAS_EN

_ACENTOS = str.maketrans("áàäâãéèëêíìïîóòöôõúùüûñç", "aaaaaeeeeiiiiooooouuuunc")
_RE_ETIQUETA = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_NO_LETRA = re.compile(r"[^a-z0-9 ]+")
# Los bigramas NO pueden cruzar un punto, una coma ni un salto de línea: sin
# este corte salían pares como «atraso motor» (fin de una oración + principio
# de la siguiente), que no significan nada y ensuciaban las búsquedas.
_RE_CORTE = re.compile(r"[.,;:!?()\[\]{}|/\n\r\t·—–\"«»]+")


def texto_plano(html: str) -> str:
    """El texto visible de un HTML. `script` y `style` se sacan ENTEROS: el
    JavaScript de un sitio tiene cientos de palabras que no dicen nada del
    rubro y ahogaban la huella."""
    sin_codigo = _RE_ETIQUETA.sub(" ", html or "")
    return _RE_TAG.sub(" ", sin_codigo)


def frases(texto: str) -> list[list[str]]:
    """El texto en tramos de palabras útiles, cortado por puntuación.

    Los tramos existen para que un bigrama no una el final de una oración con
    el principio de la siguiente. Las palabras vacías se sacan DESPUÉS de
    cortar, así «gestión de cobranzas» sigue dando el bigrama «gestion
    cobranzas» aunque «de» se caiga.
    """
    t = (texto or "")[:MAX_TEXTO].lower().translate(_ACENTOS)
    salida: list[list[str]] = []
    for tramo in _RE_CORTE.split(t):
        palabras = [p for p in _RE_NO_LETRA.sub(" ", tramo).split()
                    if len(p) >= MIN_LARGO and p not in _VACIAS]
        if palabras:
            salida.append(palabras)
    return salida


def normalizar(texto: str) -> list[str]:
    """Todas las palabras útiles, en orden, sin los cortes de frase."""
    return [p for tramo in frases(texto) for p in tramo]


def _bigramas(tramos: list[list[str]]) -> list[str]:
    # `strict=False` a propósito: `tramo[1:]` es siempre uno más corto que
    # `tramo` — el desfasaje ES el bigrama, no un error de largos.
    return [f"{a} {b}" for tramo in tramos
            for a, b in zip(tramo, tramo[1:], strict=False)]


@dataclass
class Huella:
    """El vocabulario que identifica a un producto, con su peso."""
    pesos: dict[str, float] = field(default_factory=dict)

    @property
    def terminos(self) -> list[str]:
        """Los términos de mayor a menor peso. El desempate es alfabético a
        propósito: sin él la huella cambiaba entre corridas iguales."""
        return sorted(self.pesos, key=lambda t: (-self.pesos[t], t))

    @property
    def total(self) -> float:
        return sum(self.pesos.values())

    def __bool__(self) -> bool:
        return bool(self.pesos)


def huella_del_texto(texto: str, tope: int = TOPE_TERMINOS) -> Huella:
    tramos = frases(texto)
    palabras = [p for tramo in tramos for p in tramo]
    if not palabras:
        return Huella()
    conteo: dict[str, float] = {}
    for p in palabras:
        conteo[p] = conteo.get(p, 0.0) + PESO_UNIGRAMA
    for par in _bigramas(tramos):
        conteo[par] = conteo.get(par, 0.0) + PESO_BIGRAMA
    # Un término que aparece UNA vez en toda la web no identifica al producto:
    # es una palabra suelta de un pie de página. Se pide repetición salvo que
    # el texto sea tan corto que no haya lugar para repetir nada.
    minimo = 2.0 if len(palabras) > 120 else 1.0
    candidatos = {t: p for t, p in conteo.items()
                  if p >= minimo * (PESO_BIGRAMA if " " in t else PESO_UNIGRAMA)}
    orden = sorted(candidatos, key=lambda t: (-candidatos[t], t))[:tope]
    return Huella({t: candidatos[t] for t in orden})


def huella_de(empresa, tope: int = TOPE_TERMINOS) -> Huella:
    """La huella del producto del cliente: QUÉ ES, no a quién le vende.

    Los `sectores_objetivo` quedan afuera a propósito, y la distinción no es
    sutil: describen al COMPRADOR, no al producto. Metidos acá pasaban dos
    cosas malas a la vez —se veían en vivo—: la lista de «palabras que definen
    tu segmento» mostraba «bancos banca minorista» y «companias seguros» en
    vez de «gestión de cobranzas»; y al verificar un competidor se le exigía
    hablar de NUESTROS sectores objetivo, que su web no tiene por qué nombrar.

    Los sectores ya cumplen su papel donde corresponde: en el `sector` de cada
    campaña, que es lo que arma las búsquedas de compradores
    (cliente_ia/busqueda_social.py).
    """
    partes = [getattr(empresa, "resumen_sitio", "") or "",
              getattr(empresa, "propuesta", "") or ""]
    huella = huella_del_texto("\n".join(partes), tope)
    pesos = dict(huella.pesos)
    # La categoría entra aunque no esté en la web: es la respuesta explícita a
    # "de qué es esto", y sin sitio (modo demo) es lo único que hay.
    techo = max(pesos.values(), default=PESO_BIGRAMA)
    for etiqueta in [getattr(empresa, "categoria", "") or ""]:
        bigramas, unigramas = _terminos_de_etiqueta(etiqueta)
        for t in bigramas:
            pesos[t] = max(pesos.get(t, 0.0), techo)
        # El unigrama de una etiqueta entra con la MITAD del techo: de
        # «Software de cobranzas», lo que identifica al rubro es el par, no la
        # palabra «software» — que sola pesaba tanto como el bigrama y hacía
        # que cualquier página que dijera «software» sumara afinidad.
        for t in unigramas:
            pesos[t] = max(pesos.get(t, 0.0), techo / 2)
    return Huella(pesos)


def huella_verificable(empresa, tope: int = TOPE_TERMINOS) -> Huella | None:
    """La huella SÓLO si sirve para verificar a terceros; si no, None.

    Distinción que costó un test y vale la pena tener explícita: la huella
    siempre se puede armar —con la categoría y los sectores alcanza para
    orientar un prompt—, pero **medir** la web de otra empresa contra ella
    exige que la nuestra venga del texto REAL del sitio. Con una huella hecha
    de dos etiquetas del catálogo, cualquier sitio da afinidad casi cero y el
    filtro descarta a todos por igual: no está midiendo el rubro, está
    midiendo que la huella es pobre.

    Esto también deja la fase determinista donde tiene que serlo: en modo demo
    no hay `resumen_sitio`, así que no se sale a la red y la corrida es
    reproducible (regla 7 del proyecto).

    Se puede apagar del todo con `MVCLIENTE_VERIFICAR_SEGMENTO=0`, para las
    instalaciones que no quieren que el motor visite sitios de terceros.
    """
    import os

    if os.getenv("MVCLIENTE_VERIFICAR_SEGMENTO", "1") == "0":
        return None
    if not (getattr(empresa, "resumen_sitio", "") or "").strip():
        return None
    huella = huella_de(empresa, tope)
    # Una web real pero casi vacía (una portada que es una imagen) tampoco da
    # para medir: se pide un mínimo de vocabulario propio.
    return huella if len(huella.pesos) >= MIN_TERMINOS_VERIFICAR else None


def _terminos_de_etiqueta(etiqueta: str) -> tuple[list[str], list[str]]:
    """De 'Software de cobranzas': (['software cobranzas'], ['software',
    'cobranzas'])."""
    tramos = frases(etiqueta)
    unigramas = [p for tramo in tramos for p in tramo]
    return _bigramas(tramos), unigramas


def afinidad(huella: Huella, texto: str) -> float:
    """Cuánto del peso de la huella aparece en `texto` (0..1).

    Se mide por PESO y no por cantidad de términos: que un competidor mencione
    el bigrama que define el rubro vale más que quince coincidencias sueltas
    de palabras genéricas.
    """
    if not huella:
        return 0.0
    tramos = frases(texto)
    palabras = [p for tramo in tramos for p in tramo]
    if not palabras:
        return 0.0
    presentes = set(palabras) | set(_bigramas(tramos))
    encontrado = sum(peso for t, peso in huella.pesos.items() if t in presentes)
    return round(min(1.0, encontrado / huella.total), 4)


def afinidad_de_html(huella: Huella, html: str) -> float:
    return afinidad(huella, texto_plano(html))


def clasificar(valor: float) -> str:
    """La afinidad en una palabra, que es lo que se muestra en pantalla."""
    if valor >= AFIN_BUENA:
        return "alta"
    if valor >= AFIN_DUDOSA:
        return "media"
    if valor >= AFIN_AJENA:
        return "baja"
    return "ajena"


def palabras_de_busqueda(huella: Huella, tope: int = 6) -> list[str]:
    """Los términos que sirven para BUSCAR, no para comparar.

    Se prefieren los bigramas: escribir «software de cobranzas» en el buscador
    de una red social devuelve el rubro; escribir «software» devuelve internet
    entero.

    El corte por peso relativo NO es un detalle: sin él salían pares de cola
    larga como «atraso motor» —dos palabras que quedaron pegadas por
    casualidad— y una búsqueda con eso adentro devuelve cero resultados. Sólo
    entran los términos que de verdad definen al producto.
    """
    if not huella:
        return []
    techo = max(huella.pesos.values())
    fuertes = [t for t in huella.terminos if huella.pesos[t] >= techo * PISO_BUSQUEDA]
    bigramas = [t for t in fuertes if " " in t]
    unigramas = [t for t in fuertes if " " not in t and len(t) >= 6]
    return (bigramas + unigramas)[:tope]
