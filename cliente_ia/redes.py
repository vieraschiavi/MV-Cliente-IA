"""
MV Cliente IA · redes sociales (X y LinkedIn)
==============================================
Lo que se puede automatizar de verdad en cada red, y con qué límites. Está
todo en un módulo porque las tres cosas comparten la misma política: **las
claves son del usuario, viajan en la petición que las usa y se descartan**;
ninguna se guarda ni se escribe en un log.

X (Twitter)
-----------
Tiene API oficial de publicación. Se firma OAuth 1.0a a mano (HMAC-SHA1 con
la biblioteca estándar): el SDK no entra en el instalador de PC y para dos
peticiones no hace falta.

LinkedIn — por qué hace falta un proveedor
------------------------------------------
LinkedIn **no** expone al público endpoints para mandar invitaciones ni
mensajes 1:1: su Messages API está reservada a socios aprobados. Los "bots"
que le escriben a uno por LinkedIn no usan esa API — usan herramientas de
sesión (Unipile, PhantomBuster, Dripify, HeyReach…) que manejan una sesión
real conectada de una cuenta y hacen lo mismo que haría la persona.

Así que acá se hace lo honesto: se habla con el proveedor que **el usuario
eligió y paga**, con SU clave. El producto no maneja la sesión de LinkedIn de
nadie ni la guarda. Y la interfaz avisa lo que hay que avisar: automatizar
LinkedIn va contra su acuerdo de usuario y puede terminar en una cuenta
restringida. Es una decisión del dueño de la cuenta, tomada con el dato a la
vista, no una sorpresa escondida en un botón.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

TIMEOUT = 30

# Proveedores de LinkedIn soportados. Se empieza por Unipile porque su API
# REST está documentada y es la que usa media industria; agregar otro es una
# entrada más en este diccionario, no tocar el resto del código.
PROVEEDORES_LINKEDIN = ("unipile",)


@dataclass(frozen=True)
class ClavesX:
    consumer_key: str
    consumer_secret: str
    access_token: str
    access_secret: str

    def tachar(self, texto: str) -> str:
        """Ningún secreto puede llegar a un comprobante ni a la pantalla."""
        for s in (self.consumer_secret, self.access_secret,
                  self.access_token, self.consumer_key):
            if s:
                texto = texto.replace(s, "•••")
        return texto


@dataclass(frozen=True)
class ClavesLinkedIn:
    proveedor: str          # uno de PROVEEDORES_LINKEDIN
    dsn: str                # host del proveedor, ej. "api1.unipile.com:13111"
    api_key: str
    account_id: str         # la cuenta de LinkedIn ya conectada en el proveedor

    def tachar(self, texto: str) -> str:
        for s in (self.api_key, self.account_id):
            if s:
                texto = texto.replace(s, "•••")
        return texto


def _detalle_de_error(e: Exception) -> str:
    """El cuerpo del error del servicio dice más que el tipo de excepción."""
    if hasattr(e, "read"):
        try:
            return e.read().decode()[:300]
        except Exception:                                # noqa: BLE001
            pass
    return str(e)[:300]


# ---------------------------------------------------------------------------
# X (Twitter)
# ---------------------------------------------------------------------------
def _cabecera_oauth1(claves: ClavesX, metodo: str, url: str,
                     parametros_query: dict[str, str] | None = None) -> str:
    """Firma OAuth 1.0a. Los parámetros de query entran en la base de la firma;
    el cuerpo JSON no (lo dice la especificación y X lo aplica al pie)."""
    oauth = {
        "oauth_consumer_key": claves.consumer_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": claves.access_token,
        "oauth_version": "1.0",
    }
    todos = {**oauth, **(parametros_query or {})}
    params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted(todos.items()))
    base = "&".join((metodo, urllib.parse.quote(url, safe=""),
                     urllib.parse.quote(params, safe="")))
    llave = (f"{urllib.parse.quote(claves.consumer_secret, safe='')}&"
             f"{urllib.parse.quote(claves.access_secret, safe='')}")
    oauth["oauth_signature"] = base64.b64encode(
        hmac.new(llave.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth.items()))


def publicar_en_x(claves: ClavesX, texto: str) -> dict:
    """Publica un post. Devuelve {ok, id, url, detalle}."""
    url = "https://api.x.com/2/tweets"
    peticion = urllib.request.Request(
        url, data=json.dumps({"text": texto}).encode(),
        headers={"Authorization": _cabecera_oauth1(claves, "POST", url),
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as r:
            datos = json.load(r)
        tid = str((datos.get("data") or {}).get("id") or "")
        return {"ok": bool(tid), "id": tid,
                "url": f"https://x.com/i/status/{tid}" if tid else "",
                "detalle": ""}
    except Exception as e:                               # noqa: BLE001
        return {"ok": False, "id": "", "url": "",
                "detalle": claves.tachar(f"{type(e).__name__}: {_detalle_de_error(e)}")[:250]}


def metricas_de_x(claves: ClavesX, ids: list[str]) -> dict[str, dict]:
    """Métricas públicas de posts ya publicados: impresiones, likes, respuestas,
    retweets, citas y guardados. Es lo que alimenta el panel de métricas.

    Se piden de a 100 (el tope del endpoint) y en UNA llamada por tanda: mil
    posts no pueden ser mil peticiones.
    """
    salida: dict[str, dict] = {}
    limpios = [i for i in dict.fromkeys(ids) if i]
    for arranque in range(0, len(limpios), 100):
        tanda = limpios[arranque:arranque + 100]
        query = {"ids": ",".join(tanda), "tweet.fields": "public_metrics,created_at"}
        url = "https://api.x.com/2/tweets"
        peticion = urllib.request.Request(
            f"{url}?{urllib.parse.urlencode(query)}",
            headers={"Authorization": _cabecera_oauth1(claves, "GET", url, query)})
        try:
            with urllib.request.urlopen(peticion, timeout=TIMEOUT) as r:
                datos = json.load(r)
        except Exception as e:                           # noqa: BLE001
            detalle = claves.tachar(f"{type(e).__name__}: {_detalle_de_error(e)}")[:250]
            for i in tanda:
                salida[i] = {"ok": False, "detalle": detalle}
            continue
        for t in datos.get("data") or []:
            m = t.get("public_metrics") or {}
            salida[str(t.get("id"))] = {
                "ok": True, "detalle": "",
                "creado": t.get("created_at", ""),
                "impresiones": int(m.get("impression_count") or 0),
                "likes": int(m.get("like_count") or 0),
                "respuestas": int(m.get("reply_count") or 0),
                "retweets": int(m.get("retweet_count") or 0),
                "citas": int(m.get("quote_count") or 0),
                "guardados": int(m.get("bookmark_count") or 0),
            }
        # Un id que el modelo devuelve en `errors` (borrado, privado) no puede
        # quedar sin fila: si no, el panel muestra un post que "no existe".
        for err in datos.get("errors") or []:
            i = str(err.get("value") or err.get("resource_id") or "")
            if i and i not in salida:
                salida[i] = {"ok": False,
                             "detalle": str(err.get("detail") or "no disponible")[:200]}
    return salida


# ---------------------------------------------------------------------------
# LinkedIn (por proveedor del usuario)
# ---------------------------------------------------------------------------
def _url_unipile(dsn: str, ruta: str) -> str:
    d = (dsn or "").strip().rstrip("/")
    d = d.removeprefix("https://").removeprefix("http://")
    return f"https://{d}{ruta}"


def _multipart(campos: dict[str, str]) -> tuple[bytes, str]:
    """Unipile recibe multipart/form-data. Se arma a mano: agregar `requests`
    al instalador por un POST no se justifica."""
    frontera = f"----mvcliente{secrets.token_hex(12)}"
    partes = []
    for clave, valor in campos.items():
        partes.append(f"--{frontera}\r\n"
                      f'Content-Disposition: form-data; name="{clave}"\r\n\r\n'
                      f"{valor}\r\n")
    partes.append(f"--{frontera}--\r\n")
    return "".join(partes).encode(), f"multipart/form-data; boundary={frontera}"


def identificador_publico(perfil: str) -> str:
    """El slug de un perfil personal: linkedin.com/in/**elena-perez** → ese
    trozo. Devuelve "" para cualquier cosa que no sea un perfil de persona.

    Es un filtro, no sólo un parseo: las fichas de la corrida traen a veces
    la búsqueda de gente de una empresa (`/company/x/people/?keywords=…`), que
    NO identifica a nadie. Mandarle un mensaje a eso sería gastar una llamada
    del proveedor (se paga) para fallar.
    """
    p = (perfil or "").strip()
    if not p:
        return ""
    if "/" not in p and " " not in p:
        return p                                     # ya viene el slug pelado
    m = re.search(r"linkedin\.com/in/([^/?#\s]+)", p, re.I)
    return urllib.parse.unquote(m.group(1)) if m else ""


def resolver_perfil(claves: ClavesLinkedIn, perfil: str) -> dict:
    """URL de perfil → identificador interno del proveedor.

    Unipile pide `attendees_ids` con SU provider_id, no la URL. Resolverlo acá
    (y no pedirle al usuario que copie identificadores a mano para cada
    decisor) es la diferencia entre un botón que anda y una planilla.
    """
    slug = identificador_publico(perfil)
    if not slug:
        return {"ok": False, "id": "",
                "detalle": "No es una URL de perfil personal de LinkedIn"}
    query = urllib.parse.urlencode({"account_id": claves.account_id})
    peticion = urllib.request.Request(
        _url_unipile(claves.dsn, f"/api/v1/users/{urllib.parse.quote(slug)}?{query}"),
        headers={"X-API-KEY": claves.api_key, "accept": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as r:
            datos = json.load(r)
        pid = str(datos.get("provider_id") or datos.get("id") or "")
        return {"ok": bool(pid), "id": pid,
                "detalle": "" if pid else "El proveedor no devolvió provider_id"}
    except Exception as e:                               # noqa: BLE001
        return {"ok": False, "id": "",
                "detalle": claves.tachar(
                    f"{type(e).__name__}: {_detalle_de_error(e)}")[:250]}


def enviar_linkedin(claves: ClavesLinkedIn, destinatario: str,
                    texto: str) -> dict:
    """Manda UN mensaje de LinkedIn por el proveedor del usuario.

    `destinatario` puede ser el provider_id ya resuelto o la URL del perfil:
    si viene una URL, se resuelve antes con el mismo proveedor.
    """
    if claves.proveedor != "unipile":
        return {"ok": False, "detalle": f"Proveedor no soportado: {claves.proveedor}"}
    if not destinatario:
        return {"ok": False, "detalle": "Falta el identificador de LinkedIn"}

    if "linkedin.com" in destinatario.lower() or "/" in destinatario:
        resuelto = resolver_perfil(claves, destinatario)
        if not resuelto["ok"]:
            return {"ok": False, "id": "", "detalle": resuelto["detalle"]}
        destinatario = resuelto["id"]

    cuerpo, tipo = _multipart({
        "account_id": claves.account_id,
        "attendees_ids": destinatario,
        "text": texto,
    })
    peticion = urllib.request.Request(
        _url_unipile(claves.dsn, "/api/v1/chats"), data=cuerpo,
        headers={"X-API-KEY": claves.api_key, "Content-Type": tipo,
                 "accept": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as r:
            datos = json.load(r)
        chat = str(datos.get("chat_id") or "")
        return {"ok": bool(chat), "id": chat,
                "detalle": "" if chat else "El proveedor no devolvió chat_id"}
    except Exception as e:                               # noqa: BLE001
        return {"ok": False, "id": "",
                "detalle": claves.tachar(
                    f"{type(e).__name__}: {_detalle_de_error(e)}")[:250]}
