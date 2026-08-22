"""
MV Cliente IA · fase 6, redacción de los mensajes
==================================================
Cada decisor recibe el mensaje **en el idioma de su país** (`geo.idioma_de`):
español en Uruguay y la LATAM hispanohablante, portugués en Brasil y Portugal,
inglés en el resto del mundo. Son los tres idiomas del producto.

De cada contacto salen cuatro piezas, todas en ese mismo idioma:

| pieza            | dónde se usa                                        |
|------------------|-----------------------------------------------------|
| `cuerpo`         | correo en texto plano                                |
| `cuerpo_html`    | correo HTML: banner de marca, texto, botón y video   |
| `linkedin`       | mensaje directo / InMail                             |
| `linkedin_nota`  | nota de la invitación a conectar (tope 300 caracteres) |

La estructura del texto es siempre la misma —y es la que funciona en frío—:

1. una línea que demuestra que se miró a esa empresa (la señal de compra),
2. el dolor del sector, dicho como lo diría alguien del rubro,
3. qué hace el producto, en una frase, sin adjetivos,
4. un pedido chico y concreto (15 minutos), no "¿te interesa?".

Las plantillas viven acá y no en el LLM a propósito: el mensaje tiene que
salir igual con o sin clave de API.

Sobre el HTML: se escribe con tablas y estilos en línea porque Outlook no
soporta flexbox ni hojas de estilo embebidas, y el banner es una imagen para
que se vea igual en Gmail, Outlook y Apple Mail. Como la mitad de la gente
lee con las imágenes bloqueadas, **todo lo que dice el banner también está en
el texto**: sin imágenes el correo se entiende igual.

El ancho de la tarjeta se maneja con el patrón de la *ghost table*: la tabla
real va con `width="100%"` y `max-width:600px`, y adentro de un comentario
condicional `[if mso]` viaja una tabla de 600 px fijos que sólo ve Outlook —
que no entiende `max-width` y, sin eso, estira el correo a lo ancho de la
ventana. Antes la tabla llevaba `width="600"` a secas: en un celular de 375 px
el correo medía 624 y se leía moviéndolo de costado. Lo encontró una captura
del correo renderizado, no la lectura del HTML.
"""
from __future__ import annotations

from html import escape

from . import geo
from .enlaces import Enlaces
from .modelos import Campana, Decisor, Email, Empresa, Prospecto

LARGO_MAX_PALABRAS = 130          # más largo que esto, en frío, no se lee
TOPE_NOTA_LINKEDIN = 300          # el límite real de la nota de invitación

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
            "¿Querés que te lo muestre sobre el caso de {empresa_prospecto}? Son 30 "
            "minutos, uno a uno, y la demo se pide desde el sitio. Si no es para "
            "vos, decime a quién le sirve más y no te escribo de nuevo.\n\n"
            "Saludos,\n{firma}"
        ),
        "seguimiento": (
            "Hola {nombre_pila}: te dejo esto arriba de todo por si se te "
            "perdió. La pregunta concreta es una sola — ¿hoy en {empresa_prospecto} "
            "el orden de la cartera lo decide un criterio común o cada gestor el "
            "suyo? Si es lo segundo, la demo son 30 minutos.\n\n"
            "Saludos,\n{firma}"
        ),
        # Enlaces, en texto plano — se pegan antes de la firma.
        "linea_video": "Video ({idioma_nombre}): {video_url}",
        "linea_sitio": "Más detalle: {landing_url}",
        "linea_demo": "Pedir la demo (30 min, con tu propio caso): {demo_url}",
        # HTML
        "boton": "Pedir la demo",
        "boton_sitio": "Ver el sitio",
        "boton_video": "▸ Mirar el video",
        "pie_demo": "La demo es una reunión de 30 minutos, uno a uno, con tu "
                    "propio caso de ejemplo. Se pide desde el formulario del sitio.",
        "alt_captura": "{producto} — la lista de clientes potenciales, priorizada",
        "alt_banner": "{producto} — tus próximos clientes, encontrados por vos",
        "pie_html": "Te escribo porque {empresa_prospecto} encaja con lo que hacemos. "
                    "Si preferís que no te escriba más, respondeme «bajá» y listo.",
        # LinkedIn
        # Sin URLs adentro: los enlaces que EXISTEN se pegan como bloque
        # aparte (ver `_bloque_enlaces`). Antes había dos plantillas —una con
        # video y otra con el sitio— y si no había ni sitio ni video quedaba
        # "Más detalle acá:" seguido de nada.
        "linkedin": (
            "Hola {nombre_pila}, vi que {empresa_prospecto} {senal}. "
            "En {sector_min} eso suele venir con {dolor_min}.\n\n"
            "{producto} {propuesta_corta}\n\n"
            "Si querés verlo sobre el caso de {empresa_prospecto}, la demo son "
            "30 minutos y se pide desde el sitio."
        ),
        "linkedin_nota": (
            "Hola {nombre_pila}, trabajo en {producto}: {propuesta_muy_corta} "
            "Vi lo de {empresa_prospecto} y creo que te puede servir. ¿Conectamos?"
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
            "Quer que eu mostre sobre o caso da {empresa_prospecto}? São 30 minutos, "
            "um a um, e a demo se pede pelo site. Se não for para você, me diga "
            "para quem faz mais sentido e não escrevo de novo.\n\n"
            "Abraço,\n{firma}"
        ),
        "seguimiento": (
            "Olá, {nombre_pila}! Subindo este e-mail caso tenha se perdido. "
            "A pergunta é uma só — hoje na {empresa_prospecto} a ordem da carteira "
            "segue um critério comum ou cada operador segue o seu? Se for a segunda, "
            "a demo leva 30 minutos.\n\n"
            "Abraço,\n{firma}"
        ),
        "linea_video": "Vídeo ({idioma_nombre}): {video_url}",
        "linea_sitio": "Mais detalhes: {landing_url}",
        "linea_demo": "Pedir a demo (30 min, com o seu próprio caso): {demo_url}",
        "boton": "Pedir a demo",
        "boton_sitio": "Ver o site",
        "boton_video": "▸ Assistir ao vídeo",
        "pie_demo": "A demo é uma reunião de 30 minutos, um a um, com o seu "
                    "próprio caso de exemplo. Peça pelo formulário do site.",
        "alt_captura": "{producto} — a lista de clientes potenciais, priorizada",
        "alt_banner": "{producto} — seus próximos clientes, encontrados para você",
        "pie_html": "Escrevo porque a {empresa_prospecto} combina com o que fazemos. "
                    "Se preferir não receber mais, responda «sair» e pronto.",
        "linkedin": (
            "Olá, {nombre_pila}! Vi que a {empresa_prospecto} {senal}. "
            "Em {sector_min} isso costuma vir com {dolor_min}.\n\n"
            "{producto} {propuesta_corta}\n\n"
            "Se quiser ver sobre o caso da {empresa_prospecto}, a demo leva 30 "
            "minutos e é pedida pelo site."
        ),
        "linkedin_nota": (
            "Olá, {nombre_pila}! Trabalho na {producto}: {propuesta_muy_corta} "
            "Vi o caso da {empresa_prospecto} e acho que pode ajudar. Vamos conectar?"
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
            "Want me to show you on {empresa_prospecto}'s own case? It's 30 minutes, "
            "one to one, and the demo is requested from the site. If this isn't "
            "your call, tell me who it is and I won't email you again.\n\n"
            "Best,\n{firma}"
        ),
        "seguimiento": (
            "Hi {nombre_pila} — bumping this in case it got buried. One question: "
            "at {empresa_prospecto} today, does the order of the collections book "
            "follow a shared rule, or does each agent pick their own? If it's the "
            "second, the demo takes 30 minutes.\n\n"
            "Best,\n{firma}"
        ),
        "linea_video": "Video ({idioma_nombre}): {video_url}",
        "linea_sitio": "More detail: {landing_url}",
        "linea_demo": "Request the demo (30 min, on your own case): {demo_url}",
        "boton": "Request the demo",
        "boton_sitio": "See the site",
        "boton_video": "▸ Watch the video",
        "pie_demo": "The demo is a 30-minute one-to-one call using your own "
                    "case as the example. Request it from the form on the site.",
        "alt_captura": "{producto} — your prospect list, already prioritised",
        "alt_banner": "{producto} — your next customers, found for you",
        "pie_html": "I'm writing because {empresa_prospecto} fits what we do. "
                    "If you'd rather not hear from me again, reply “stop” and that's it.",
        "linkedin": (
            "Hi {nombre_pila} — I saw that {empresa_prospecto} {senal}. "
            "In {sector_min} that usually comes with {dolor_min}.\n\n"
            "{producto} {propuesta_corta}\n\n"
            "If you'd like to see it on {empresa_prospecto}'s own case, the demo "
            "takes 30 minutes and is requested from the site."
        ),
        "linkedin_nota": (
            "Hi {nombre_pila} — I work on {producto}: {propuesta_muy_corta} "
            "Saw what {empresa_prospecto} is doing and think it could help. Connect?"
        ),
    },
}

# Cómo se llama el idioma del video, dicho en ese mismo idioma. Va entre
# paréntesis al lado del enlace para que quede claro que el video está en el
# idioma de quien lo va a ver, no en el de quien escribe.
NOMBRE_IDIOMA = {"es": "español", "pt": "português", "en": "English"}


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


# Palabras con las que una frase no puede terminar: si el recorte cae justo
# después de una de estas, la frase queda colgada ("…por valor esperado de.").
COLGADAS = {
    "es": {"de", "del", "la", "el", "los", "las", "y", "o", "por", "para", "con",
           "en", "a", "al", "un", "una", "que", "su", "sus"},
    "pt": {"de", "da", "do", "das", "dos", "a", "o", "os", "as", "e", "ou", "por",
           "para", "com", "em", "um", "uma", "que", "seu", "sua"},
    "en": {"of", "the", "a", "an", "and", "or", "by", "for", "with", "in", "on",
           "to", "at", "its", "their"},
}


def _clausula(texto: str, idioma: str, max_palabras: int = 14) -> str:
    """
    La primera cláusula de una frase — hasta la primera coma. Es lo que se usa
    en la nota de invitación de LinkedIn, donde entran 300 caracteres: cortar
    por cantidad de palabras dejaba cosas como "por valor esperado de.".
    """
    t = _primera_frase(texto, 60)
    if "," in t:
        t = t.split(",")[0]
    palabras = t.split()
    if len(palabras) > max_palabras:
        palabras = palabras[:max_palabras]
    while palabras and palabras[-1].lower().strip(".,;:") in COLGADAS.get(idioma, set()):
        palabras.pop()
    return " ".join(palabras).rstrip(",;:. ")


def _recortar(texto: str, tope: int) -> str:
    """Recorta al tope sin cortar una palabra por la mitad."""
    t = " ".join(texto.split())
    if len(t) <= tope:
        return t
    return t[:tope - 1].rsplit(" ", 1)[0].rstrip(",;:.") + "…"


# ---------------------------------------------------------------------------
# Correo HTML
# ---------------------------------------------------------------------------
_HTML = """\
<!DOCTYPE html>
<html lang="{lang}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{asunto}</title></head>
<body style="margin:0;padding:0;background:#f4f6fa;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#f4f6fa;padding:24px 12px;">
<tr><td align="center">
  <!--[if mso]><table role="presentation" width="600" cellpadding="0" cellspacing="0"
      border="0"><tr><td><![endif]-->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="max-width:600px;background:#ffffff;border-radius:14px;
                overflow:hidden;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
{banner}
    <tr><td style="padding:26px 30px 6px;">
      <div style="font-size:15px;line-height:1.6;color:#1c2b42;">{parrafos}</div>
    </td></tr>
    <tr><td style="padding:14px 30px 4px;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="background:#00c896;border-radius:9px;">
          <a href="{demo_url}" style="display:inline-block;padding:13px 26px;color:#062018;
             font-size:15px;font-weight:700;text-decoration:none;">{boton}</a>
        </td>
        <td style="padding-left:14px;">
          <a href="{landing_url}" style="font-size:14px;font-weight:600;color:#0a8f6c;
             text-decoration:none;">{boton_sitio}</a>
        </td>
      </tr></table>
    </td></tr>
{bloque_video}
{bloque_captura}
    <tr><td style="padding:20px 30px 6px;">
      <p style="margin:0;font-size:12.5px;line-height:1.6;color:#5b6b80;">{pie_demo}</p>
    </td></tr>
    <tr><td style="padding:6px 30px 26px;">
      <p style="margin:0;font-size:12px;line-height:1.6;color:#8a99ad;">{pie}</p>
    </td></tr>
  </table>
  <!--[if mso]></td></tr></table><![endif]-->
</td></tr></table>
</body>
</html>"""

_BANNER = """\
    <tr><td style="padding:0;">
      <a href="{destino}"><img src="{banner_url}" width="600" alt="{alt}"
         style="display:block;width:100%;max-width:600px;height:auto;border:0;"></a>
    </td></tr>"""

_BLOQUE_VIDEO = """\
    <tr><td style="padding:10px 30px 0;">
      <a href="{video_url}" style="font-size:14px;font-weight:600;color:#0a8f6c;
         text-decoration:none;">{boton_video}</a>
      <span style="font-size:13px;color:#8a99ad;"> · {idioma_nombre}</span>
    </td></tr>"""

# La segunda imagen: una captura REAL del producto trabajando (la lista de
# prospectos priorizada). El banner dice de qué se trata; la captura muestra
# lo que la persona se lleva. Va enlazada al formulario de demo, que es la
# acción que se le pide.
_BLOQUE_CAPTURA = """\
    <tr><td style="padding:16px 30px 0;">
      <a href="{destino}"><img src="{captura_url}" width="540" alt="{alt}"
         style="display:block;width:100%;max-width:540px;height:auto;border:0;
                border-radius:10px;"></a>
    </td></tr>"""


def _con_enlaces(texto: str, plantilla: dict, contexto: dict,
                 video_url: str, landing_url: str, demo_url: str,
                 antes_del_ultimo: bool) -> str:
    """Pega el bloque de enlaces al texto, con UNA línea por URL que exista.

    Antes cada plantilla traía las URLs adentro, y había dos versiones —con
    video y sin video— para elegir. Con un sitio sin configurar quedaba «Más
    detalle acá:» seguido de nada: la plantilla no puede saber qué enlaces
    existen, así que el bloque se arma acá, donde sí se sabe.

    `antes_del_ultimo` mete el bloque delante del último párrafo (la firma del
    correo); en falso lo agrega al final, que es lo que corresponde en
    LinkedIn, donde no hay firma.
    """
    lineas = []
    if video_url:
        lineas.append(plantilla["linea_video"].format(**contexto))
    if landing_url:
        lineas.append(plantilla["linea_sitio"].format(**contexto))
    if demo_url:
        lineas.append(plantilla["linea_demo"].format(**contexto))
    if not lineas:
        return texto
    bloque = "\n".join(lineas)
    if not antes_del_ultimo:
        return texto + "\n\n" + bloque
    partes = texto.rsplit("\n\n", 1)
    return partes[0] + "\n\n" + bloque + "\n\n" + partes[-1]


def _a_html(cuerpo: str) -> str:
    """Texto plano → párrafos HTML, escapando lo que venga del prospecto."""
    partes = [p.strip() for p in cuerpo.split("\n\n") if p.strip()]
    return "".join(
        f'<p style="margin:0 0 14px;">{escape(p).replace(chr(10), "<br>")}</p>'
        for p in partes)


def _armar_html(contexto: dict, plantilla: dict, cuerpo: str, idioma: str,
                landing_url: str, video_url: str, banner_url: str,
                demo_url: str = "", captura_url: str = "") -> str:
    # Todo lo que se puede clickear apunta a la demo si existe: es la acción
    # que se le pide a quien recibe el correo. Si no hay sitio configurado, el
    # botón cae al enlace de la web y, sin eso, a "#" — nunca a un href vacío,
    # que en Outlook abre una ventana en blanco.
    accion = demo_url or landing_url
    alt = plantilla["alt_banner"].format(**contexto)
    banner = ""
    if banner_url:
        banner = _BANNER.format(destino=escape(video_url or accion, quote=True),
                                banner_url=escape(banner_url, quote=True),
                                alt=escape(alt, quote=True))
    bloque_video = ""
    if video_url:
        bloque_video = _BLOQUE_VIDEO.format(
            video_url=escape(video_url, quote=True),
            boton_video=escape(plantilla["boton_video"]),
            idioma_nombre=NOMBRE_IDIOMA[idioma])
    bloque_captura = ""
    if captura_url:
        bloque_captura = _BLOQUE_CAPTURA.format(
            destino=escape(accion or "#", quote=True),
            captura_url=escape(captura_url, quote=True),
            alt=escape(plantilla["alt_captura"].format(**contexto), quote=True))
    return _HTML.format(
        lang="pt-BR" if idioma == "pt" else idioma,
        asunto=escape(plantilla["asunto"].format(**contexto), quote=True),
        banner=banner,
        parrafos=_a_html(cuerpo),
        demo_url=escape(accion or "#", quote=True),
        landing_url=escape(landing_url or accion or "#", quote=True),
        boton=escape(plantilla["boton"]),
        boton_sitio=escape(plantilla["boton_sitio"]),
        bloque_video=bloque_video,
        bloque_captura=bloque_captura,
        pie_demo=escape(plantilla["pie_demo"]),
        pie=escape(plantilla["pie_html"].format(**contexto)),
    )


# ---------------------------------------------------------------------------
def redactar(decisor: Decisor, prospecto: Prospecto, empresa: Empresa,
             campana: Campana | None, firma: str = "",
             enlaces: Enlaces | None = None) -> Email:
    idioma = decisor.idioma if decisor.idioma in PLANTILLAS else geo.idioma_de(decisor.pais)
    if idioma not in PLANTILLAS:
        idioma = geo.IDIOMA_DEFAULT
    plantilla = PLANTILLAS[idioma]
    enlaces = enlaces or Enlaces()

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
    # se saca, o el mensaje lo dice dos veces seguidas.
    propuesta = de_empresa.get("propuesta") or empresa.propuesta
    if empresa.nombre and propuesta.lower().startswith(empresa.nombre.lower()):
        propuesta = _minuscula_inicial(propuesta[len(empresa.nombre):].lstrip(" ,:—-"))

    # Los tres enlaces, en el idioma del receptor. El de la landing se
    # envuelve por el redirect de conversión con los datos de ESTE prospecto
    # (segmento, ola, país): así, si el traqueo está encendido, cada click
    # queda atribuido a su celda del tablero de métricas. Sin traqueo
    # configurado, `traqueada` devuelve el enlace tal cual.
    def _meta(canal: str) -> dict:
        return {"canal": canal, "segmento": prospecto.sector,
                "nivel": prospecto.nivel, "pais": prospecto.pais, "idioma": idioma}

    landing_url = enlaces.traqueada(
        enlaces.landing(idioma, prospecto.campana_id, prospecto.id, "email"),
        _meta("email"))
    video_url = enlaces.video(idioma, prospecto.campana_id, prospecto.id, "email")
    banner_url = enlaces.banner(idioma)
    captura_url = enlaces.captura(idioma)
    demo_url = enlaces.traqueada(
        enlaces.demo(idioma, prospecto.campana_id, prospecto.id, "email"),
        _meta("email"))
    landing_li = enlaces.traqueada(
        enlaces.landing(idioma, prospecto.campana_id, prospecto.id, "linkedin"),
        _meta("linkedin"))
    video_li = enlaces.video(idioma, prospecto.campana_id, prospecto.id, "linkedin")
    demo_li = enlaces.traqueada(
        enlaces.demo(idioma, prospecto.campana_id, prospecto.id, "linkedin"),
        _meta("linkedin"))

    # Los decisores de empresas reales viajan sin nombre (no se inventan
    # personas): el saludo lleva un hueco explícito para completar cuando se
    # encuentre a la persona en LinkedIn, no un "Hola :" mudo.
    hueco_nombre = {"es": "[nombre]", "pt": "[nome]", "en": "[name]"}[idioma]
    contexto = {
        "nombre_pila": decisor.nombre.split()[0] if decisor.nombre else hueco_nombre,
        "empresa_prospecto": prospecto.nombre,
        "sector_min": _minuscula_inicial(prospecto.sector),
        "senal": senal,
        "dolor_min": _minuscula_inicial(_primera_frase(dolor)),
        "producto": empresa.nombre,
        "propuesta_corta": _minuscula_inicial(_primera_frase(propuesta, 34)) + ".",
        "propuesta_muy_corta": _minuscula_inicial(_clausula(propuesta, idioma)) + ".",
        "diferencial": (diferencial[0].upper() + diferencial[1:]).rstrip(".") + "."
                       if diferencial else "",
        "gancho": plantilla["gancho"],
        "firma": firma or empresa.nombre,
        "idioma_nombre": NOMBRE_IDIOMA[idioma],
        "video_url": video_url,
        "landing_url": landing_url,
        "demo_url": demo_url,
    }

    # El texto base no lleva enlaces: es el que se convierte en los párrafos
    # del HTML, donde el video y la web ya están como banner, botón y enlace.
    # Pegar además las URLs crudas ahí las mostraba dos veces y quedaba feo.
    base = plantilla["cuerpo"].format(**contexto).replace("\n\n\n", "\n\n").strip()

    # En texto plano sí van, en su propio bloque antes de la firma: metidas en
    # medio de un párrafo, los filtros de correo las leen peor y la persona las
    # saltea. Cada línea se arma SÓLO si su URL existe — de ahí que no pueda
    # quedar un "Más detalle:" seguido de nada.
    cuerpo = _con_enlaces(base, plantilla, contexto,
                          video_url, landing_url, demo_url, antes_del_ultimo=True)

    # En LinkedIn el bloque va al final: no hay firma que respetar, y el
    # mensaje cierra invitando a pedir la demo — poner los enlaces antes de esa
    # frase dejaba las URLs explicándose después de aparecer. Tampoco lleva el
    # enlace al sitio suelto: el de la demo ya es el sitio, y dos URLs casi
    # iguales en un mensaje corto se leen como spam.
    contexto_li = {**contexto, "video_url": video_li,
                   "landing_url": landing_li, "demo_url": demo_li}
    linkedin = _con_enlaces(plantilla["linkedin"].format(**contexto_li).strip(),
                            plantilla, contexto_li,
                            video_li, "", demo_li, antes_del_ultimo=False)

    return Email(
        id=f"e{decisor.id[1:]}",
        decisor_id=decisor.id,
        prospecto_id=prospecto.id,
        # Empresa real sin persona identificada: el destinatario es la casilla
        # COMERCIAL que la propia empresa publica en su sitio (info@/ventas@)
        # — escribirle ahí es outreach normal, no una casilla adivinada.
        para=decisor.email or (prospecto.contactos.get("email", "")
                               if not prospecto.sintetico else ""),
        idioma=idioma,
        asunto=plantilla["asunto"].format(**contexto),
        cuerpo=cuerpo,
        seguimiento=plantilla["seguimiento"].format(**contexto).strip(),
        cuerpo_html=_armar_html(contexto, plantilla, base, idioma,
                                landing_url, video_url, banner_url,
                                demo_url, captura_url),
        linkedin=linkedin,
        linkedin_nota=_recortar(plantilla["linkedin_nota"].format(**contexto),
                                TOPE_NOTA_LINKEDIN),
        landing_url=landing_url,
        video_url=video_url,
        banner_url=banner_url,
        demo_url=demo_url,
        captura_url=captura_url,
        campana_id=prospecto.campana_id,
        palabras=len(cuerpo.split()),
    )
