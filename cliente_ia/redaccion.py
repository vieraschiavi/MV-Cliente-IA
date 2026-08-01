"""
MV Cliente IA · fase 6, redacción de los correos
=================================================
Cada decisor recibe el correo **en el idioma de su país** (`geo.idioma_de`):
español en Uruguay y la LATAM hispanohablante, portugués en Brasil y
Portugal, inglés en el resto del mundo. Son los tres idiomas de MV Kobra AI.

La estructura del correo es siempre la misma —y es la que funciona en frío—:

1. una línea que demuestra que se miró a esa empresa (la señal de compra),
2. el dolor del sector, dicho como lo diría alguien del rubro,
3. qué hace el producto, en una frase, sin adjetivos,
4. un pedido chico y concreto (15 minutos), no "¿te interesa?".

Las plantillas viven acá y no en el LLM a propósito: el correo tiene que
salir igual con o sin clave de API. Con `ANTHROPIC_API_KEY` el pipeline puede
pedirle al modelo que reescriba el cuerpo, pero la versión de plantilla es la
que garantiza que la fase 6 nunca queda vacía.
"""
from __future__ import annotations

from . import geo
from .modelos import Campana, Decisor, Email, Empresa, Prospecto

LARGO_MAX_PALABRAS = 130          # más largo que esto, en frío, no se lee

PLANTILLAS: dict[str, dict[str, str]] = {
    "es": {
        "asunto": "{empresa_prospecto}: {gancho}",
        "gancho": "priorizar la cartera por lo que se va a cobrar",
        "cuerpo": (
            "Hola {nombre_pila}:\n\n"
            "Vi que {empresa_prospecto} {senal}. Cuando eso pasa en {sector_min}, "
            "lo que suele aparecer después es {dolor_min}.\n\n"
            "{producto} {propuesta_corta}\n\n"
            "{diferencial}\n\n"
            "¿Tenés 15 minutos esta semana o la que viene para que te lo muestre "
            "sobre una cartera de ejemplo? Si no es para vos, decime a quién le "
            "sirve más y no te escribo de nuevo.\n\n"
            "Saludos,\n{firma}"
        ),
        "seguimiento": (
            "Hola {nombre_pila}: te dejo esto arriba de todo por si se te "
            "perdió. La pregunta concreta es una sola — ¿hoy en {empresa_prospecto} "
            "el orden de la cartera lo decide un criterio común o cada gestor el "
            "suyo? Si es lo segundo, la demo son 15 minutos.\n\n"
            "Saludos,\n{firma}"
        ),
    },
    "pt": {
        "asunto": "{empresa_prospecto}: {gancho}",
        "gancho": "priorizar a carteira pelo que vai ser recuperado",
        "cuerpo": (
            "Olá, {nombre_pila}!\n\n"
            "Vi que a {empresa_prospecto} {senal}. Quando isso acontece em "
            "{sector_min}, o que costuma vir depois é {dolor_min}.\n\n"
            "{producto} {propuesta_corta}\n\n"
            "{diferencial}\n\n"
            "Você tem 15 minutos esta semana ou na próxima para eu mostrar sobre "
            "uma carteira de exemplo? Se não for para você, me diga para quem faz "
            "mais sentido e não escrevo de novo.\n\n"
            "Abraço,\n{firma}"
        ),
        "seguimiento": (
            "Olá, {nombre_pila}! Subindo este e-mail caso tenha se perdido. "
            "A pergunta é uma só — hoje na {empresa_prospecto} a ordem da carteira "
            "segue um critério comum ou cada operador segue o seu? Se for a segunda, "
            "a demo leva 15 minutos.\n\n"
            "Abraço,\n{firma}"
        ),
    },
    "en": {
        "asunto": "{empresa_prospecto}: {gancho}",
        "gancho": "ordering the book by what will actually be collected",
        "cuerpo": (
            "Hi {nombre_pila},\n\n"
            "I saw that {empresa_prospecto} {senal}. When that happens in "
            "{sector_min}, what usually follows is {dolor_min}.\n\n"
            "{producto} {propuesta_corta}\n\n"
            "{diferencial}\n\n"
            "Do you have 15 minutes this week or next so I can show you on a sample "
            "book? If this isn't your call, tell me who it is and I won't email you "
            "again.\n\n"
            "Best,\n{firma}"
        ),
        "seguimiento": (
            "Hi {nombre_pila} — bumping this in case it got buried. One question: "
            "at {empresa_prospecto} today, does the order of the collections book "
            "follow a shared rule, or does each agent pick their own? If it's the "
            "second, the demo takes 15 minutes.\n\n"
            "Best,\n{firma}"
        ),
    },
}


def _minuscula_inicial(texto: str) -> str:
    """Para encajar una frase dentro de otra sin una mayúscula en el medio."""
    t = (texto or "").strip()
    if not t:
        return t
    return t[0].lower() + t[1:]


def _primera_frase(texto: str, max_palabras: int = 28) -> str:
    t = (texto or "").strip().rstrip(".")
    for corte in (". ", " — ", "; "):
        if corte in t:
            t = t.split(corte)[0]
            break
    palabras = t.split()
    if len(palabras) > max_palabras:
        t = " ".join(palabras[:max_palabras])
    return t


def redactar(decisor: Decisor, prospecto: Prospecto, empresa: Empresa,
             campana: Campana | None, firma: str = "") -> Email:
    idioma = decisor.idioma if decisor.idioma in PLANTILLAS else geo.idioma_de(decisor.pais)
    if idioma not in PLANTILLAS:
        idioma = geo.IDIOMA_DEFAULT
    plantilla = PLANTILLAS[idioma]

    senal = _minuscula_inicial(prospecto.senales[0]) if prospecto.senales else {
        "es": "viene creciendo en cartera",
        "pt": "vem crescendo em carteira",
        "en": "has been growing its book",
    }[idioma]

    # Cada pieza en el idioma del decisor. El dolor del prospecto ya viene en
    # su idioma; la campaña sólo se usa si el prospecto no lo trae (por eso el
    # orden), y los textos de la empresa salen del diccionario multi-idioma.
    dolor = prospecto.dolor or (campana.dolor if campana else "") or ""
    de_empresa = empresa.textos.get(idioma) or {}
    if not dolor:
        dolores = de_empresa.get("dolores") or empresa.dolores
        dolor = dolores[0] if dolores else ""
    diferenciales = de_empresa.get("diferenciales") or empresa.diferenciales
    diferencial = diferenciales[0] if diferenciales else ""
    # La plantilla ya antepone el nombre del producto; si la propuesta también
    # arranca con él (es el caso del campo plano, que se arma para la interfaz)
    # se saca, o el correo lo dice dos veces seguidas.
    propuesta = de_empresa.get("propuesta") or empresa.propuesta
    if empresa.nombre and propuesta.lower().startswith(empresa.nombre.lower()):
        propuesta = _minuscula_inicial(propuesta[len(empresa.nombre):].lstrip(" ,:—-"))

    contexto = {
        "nombre_pila": decisor.nombre.split()[0],
        "empresa_prospecto": prospecto.nombre,
        "sector_min": _minuscula_inicial(prospecto.sector),
        "senal": senal,
        "dolor_min": _minuscula_inicial(_primera_frase(dolor)),
        "producto": empresa.nombre,
        "propuesta_corta": _minuscula_inicial(_primera_frase(propuesta, 34)) + ".",
        "diferencial": (diferencial[0].upper() + diferencial[1:]).rstrip(".") + "."
                       if diferencial else "",
        "gancho": plantilla["gancho"],
        "firma": firma or empresa.nombre,
    }

    cuerpo = plantilla["cuerpo"].format(**contexto).replace("\n\n\n", "\n\n").strip()
    return Email(
        id=f"e{decisor.id[1:]}",
        decisor_id=decisor.id,
        prospecto_id=prospecto.id,
        para=decisor.email,
        idioma=idioma,
        asunto=plantilla["asunto"].format(**contexto),
        cuerpo=cuerpo,
        seguimiento=plantilla["seguimiento"].format(**contexto).strip(),
        campana_id=prospecto.campana_id,
        palabras=len(cuerpo.split()),
    )
