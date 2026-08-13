"""
MV Cliente IA · backend (FastAPI)
==================================
Expone el motor de `cliente_ia` y sirve el build de React. Es el mismo
proceso en los tres empaquetados: en la nube detrás de un dominio, dentro
del instalador de PC (lo levanta Electron en 127.0.0.1) y dentro del APK
(lo levanta el WebView contra el servidor configurado).

Correr en desarrollo:

    python -m uvicorn webapp.backend.api:app --port 8810 --reload

Autenticación
-------------
Si existe la variable `MVCLIENTE_PASSWORD`, la API exige el encabezado
`Authorization: Bearer <token>` y el token se saca de `POST /api/auth/login`.
Si no existe, la API queda abierta: es el modo con el que corre el
instalador de PC, donde el servidor escucha sólo en 127.0.0.1 y poner una
contraseña para hablar con tu propia máquina no protege de nada. **Para un
despliegue expuesto a internet la variable es obligatoria** — sin ella,
cualquiera que llegue al puerto puede lanzar corridas.

Dos modos de ejecución
----------------------
- **Con estado** (servidor propio, instalador de PC, APK apuntando a tu
  servidor): las corridas se ejecutan en un pool de hilos y van guardando el
  avance después de cada fase, así que el frontend consulta el estado mientras
  corren (`GET /api/corridas/{id}`) y el historial queda en disco.
- **Sin estado** (Vercel y cualquier serverless): no hay disco compartido ni
  hilos que sobrevivan a la respuesta, así que `POST /api/corridas` ejecuta la
  corrida en la misma petición y la devuelve entera. No hay historial ni
  sondeo, y el modo de investigación con IA queda deshabilitado porque no
  entra en el tiempo de la función. Se detecta solo (`VERCEL`) o se fuerza con
  `MVCLIENTE_SIN_ESTADO=1`.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import queue as colas
import re
import secrets
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cliente_ia import (
    __version__,
    almacen,
    exportar,
    geo,
    licencia,
    modelos,
    pipeline,
    proveedores,
    redes,
    rutas,
)
from cliente_ia.modelos import Corrida

# Cuántas corridas pueden estar en vuelo a la vez. Cada una es corta (el modo
# demo son milisegundos; el modo LLM, minutos), pero sin tope un cliente que
# apreta el botón diez veces deja el proceso sin hilos.
MAX_CORRIDAS_PARALELAS = 4
TTL_TOKEN = 12 * 3600

# En serverless (Vercel) no hay disco compartido ni hilos que sobrevivan a la
# respuesta: la corrida se ejecuta EN LA MISMA petición y vuelve entera en el
# cuerpo, sin sondeo. El frontend detecta ese caso y no consulta el avance.
SIN_ESTADO = rutas.en_serverless()

# En serverless el modo `llm` sólo se ofrece cuando hay ANTHROPIC_API_KEY:
# sin clave caería en silencio a `web` y el usuario creería que la IA "no
# busca nada" (pasó con el despliegue de Vercel). Con clave sí corre — el
# maxDuration de vercel.json está subido justamente para darle tiempo.
def modos_en_serverless() -> tuple[str, ...]:
    if proveedores.modo_efectivo("llm") == "llm":
        return ("demo", "web", "llm")
    return ("demo", "web")

# Los ÚNICOS orígenes que cruzan de verdad. Electron carga
# `http://127.0.0.1:<puerto>/` y la web se sirve desde su propio dominio: los
# dos son mismo-origen y no pasan por CORS. El APK es el único que cruza —
# el WebView de Capacitor tiene origen `https://localhost` (androidScheme en
# capacitor.config.json) y le pega a un servidor que el usuario configura.
#
# Antes acá decía `*`, y eso convertía al programa instalado en una API
# abierta para CUALQUIER pestaña del navegador: el motor escucha en
# 127.0.0.1, pero una página web maliciosa corre en la misma máquina, así
# que `fetch("http://127.0.0.1:8810/api/corridas")` le devolvía —y con
# `*` el navegador la dejaba LEER— la investigación entera del cliente:
# prospectos, decisores, empresas objetivo. Verificado con curl antes de
# cambiarlo. Escuchar sólo en loopback no defiende de esto; el allowlist sí.
ORIGENES_PERMITIDOS = [
    "https://localhost",        # Capacitor con androidScheme "https" (el actual)
    "http://localhost",         # Capacitor viejo / WebView sin TLS
    "capacitor://localhost",    # iOS y algunas versiones de Android
]

app = FastAPI(title="MV Cliente IA", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENES_PERMITIDOS, allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"],
)

# Los mismos encabezados de seguridad que `vercel.json` le pone a la web,
# pero puestos acá para que también los tenga el programa INSTALADO: ahí no
# hay Vercel delante, es este uvicorn sirviendo el HTML, y hasta ahora salía
# sin ninguno. Importa porque la pantalla de Correos previsualiza en un
# iframe HTML que redactó un modelo, y las fichas muestran texto traído de
# sitios ajenos: si algo de eso trae un <script>, el CSP es lo que lo frena.
#
# `unsafe-inline` en style y script no es un descuido: Vite emite el módulo
# con un pequeño inline y los componentes usan `style=`. Es el mismo CSP que
# ya corre en producción hace meses, así que no rompe nada conocido.
_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
        "font-src 'self' data:; media-src 'self'; connect-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; "
        "frame-ancestors 'self'")
_SEGURIDAD = {
    "Content-Security-Policy": _CSP,
    "X-Content-Type-Options": "nosniff",
    # Redundante con `frame-ancestors`, pero los WebView viejos de Android
    # entienden éste y no el CSP.
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=(), payment=(), usb=()",
}


@app.middleware("http")
async def encabezados_de_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    for clave, valor in _SEGURIDAD.items():
        respuesta.headers.setdefault(clave, valor)
    return respuesta

_ejecutor = ThreadPoolExecutor(max_workers=MAX_CORRIDAS_PARALELAS,
                              thread_name_prefix="autogtm")
_lock = threading.Lock()
_en_curso: set[str] = set()
_secreto = secrets.token_bytes(32)          # se renueva en cada arranque


# ---------------------------------------------------------------------------
# Cupo gratis del despliegue web
# ---------------------------------------------------------------------------
# En la web pública las búsquedas REALES («leer mi sitio» e IA) son una
# prueba: 3 gratis y después se compra el programa. La demo sintética no
# descuenta — es la vidriera. El dueño queda exento con el código de
# `MVCLIENTE_OWNER` (variable en Vercel + Configuración de la app).
#
# El conteo va en una cookie firmada (sirve entre instancias serverless
# porque el secreto es determinista) más un mapa por IP como refuerzo dentro
# de cada instancia caliente. No es un candado criptográfico contra alguien
# decidido a borrarla — es el aviso honesto de dónde termina lo gratis.
CUPO_GRATIS = int(os.getenv("MVCLIENTE_CUPO_GRATIS", "3"))
_COOKIE_CUPO = "mv_cupo"
_cupo_por_ip: dict[str, int] = {}
# Las búsquedas reales piden además un correo: suma una dimensión más al
# conteo (cookie + IP + correo) y deja un dato de contacto del interesado.
# El correo del dueño queda exento — atención: es un dato público, así que
# es una cortesía para el dueño, no un candado; el candado de verdad sigue
# siendo el código MVCLIENTE_OWNER.
OWNER_EMAIL = os.getenv("MVCLIENTE_OWNER_EMAIL", "vieraschiavi@gmail.com").lower()
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_cupo_por_email: dict[str, int] = {}


def _es_owner_email(email: str) -> bool:
    return bool(OWNER_EMAIL) and hmac.compare_digest(email.strip().lower(),
                                                     OWNER_EMAIL)


def _secreto_cupo() -> bytes:
    base = ("mv-cupo-v1" + os.getenv("MVCLIENTE_OWNER", "")
            + os.getenv("MVCLIENTE_PASSWORD", ""))
    return hashlib.sha256(base.encode()).digest()


def _firmar_cupo(n: int) -> str:
    mac = hmac.new(_secreto_cupo(), str(n).encode(), hashlib.sha256).hexdigest()
    return f"{n}.{mac}"


def _ip_de(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _es_owner(request: Request) -> bool:
    owner = os.getenv("MVCLIENTE_OWNER", "")
    return bool(owner) and hmac.compare_digest(
        request.headers.get("x-mv-owner", ""), owner)


def _cupo_usado(request: Request) -> int:
    de_cookie = 0
    crudo = request.cookies.get(_COOKIE_CUPO, "")
    try:
        n, mac = crudo.split(".", 1)
        if hmac.compare_digest(mac, hmac.new(_secreto_cupo(), n.encode(),
                                             hashlib.sha256).hexdigest()):
            de_cookie = max(0, int(n))
    except (ValueError, AttributeError):
        pass
    return max(de_cookie, _cupo_por_ip.get(_ip_de(request), 0))


def _poner_cookie_cupo(respuesta: Response, n: int) -> None:
    respuesta.set_cookie(_COOKIE_CUPO, _firmar_cupo(n),
                         max_age=365 * 24 * 3600, samesite="lax")


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------
def _password() -> str:
    return os.getenv("MVCLIENTE_PASSWORD", "")


def auth_activa() -> bool:
    return bool(_password())


def _firmar(vence: int) -> str:
    mac = hmac.new(_secreto, str(vence).encode(), hashlib.sha256).hexdigest()
    return f"{vence}.{mac}"


def _token_valido(token: str) -> bool:
    try:
        crudo, mac = token.split(".", 1)
        vence = int(crudo)
    except (ValueError, AttributeError):
        return False
    if vence < time.time():
        return False
    return hmac.compare_digest(mac, hmac.new(_secreto, crudo.encode(),
                                             hashlib.sha256).hexdigest())


def requiere_auth(authorization: str = Header(default="")) -> None:
    if not auth_activa():
        return
    token = authorization.removeprefix("Bearer ").strip()
    if not _token_valido(token):
        raise HTTPException(status_code=401, detail="Sesión vencida o token inválido")


class LoginIn(BaseModel):
    password: str


@app.post("/api/auth/login")
def login(datos: LoginIn):
    if not auth_activa():
        return {"token": "", "auth": False}
    # compare_digest evita que el tiempo de respuesta filtre cuántos
    # caracteres de la contraseña son correctos.
    if not hmac.compare_digest(datos.password, _password()):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    return {"token": _firmar(int(time.time()) + TTL_TOKEN), "auth": True}


@app.get("/api/auth/estado")
def estado_auth():
    return {"auth": auth_activa(), "version": __version__}


# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------
@app.get("/api/salud")
def salud():
    return {"ok": True, "version": __version__,
            "modos": list(modos_en_serverless() if SIN_ESTADO else proveedores.MODOS),
            "sin_estado": SIN_ESTADO,
            "modo_llm_disponible": proveedores.modo_efectivo("llm") == "llm"}


@app.get("/api/cupo")
def cupo(request: Request, email: str = ""):
    """Cuántas búsquedas reales gratis quedan en este navegador/IP/correo.
    `pide_email` le dice a la interfaz que el campo de correo es obligatorio
    para lanzar una búsqueda real."""
    if not SIN_ESTADO:
        return {"aplica": False, "gratis": 0, "usadas": 0, "owner": False,
                "pide_email": False}
    owner = _es_owner(request) or _es_owner_email(email)
    correo = email.strip().lower()
    usadas = max(_cupo_usado(request), _cupo_por_email.get(correo, 0))
    return {"aplica": True, "gratis": CUPO_GRATIS,
            "usadas": min(usadas, CUPO_GRATIS),
            "owner": owner, "pide_email": True}


# ---------------------------------------------------------------------------
# Pago (MercadoPago, mismo esquema que MV Kobra AI)
# ---------------------------------------------------------------------------
# El botón de la landing hace POST acá; el backend crea la preferencia con el
# token del dueño (variable MERCADOPAGO_ACCESS_TOKEN en el servidor) y
# devuelve la URL de pago. La plata cae directo en la cuenta de MercadoPago
# del dueño — nunca pasa por acá. Precio de referencia en dólares, se cobra
# en pesos uruguayos, igual que Kobra.
PLANES = {
    "licencia": {
        "titulo": "MV Cliente IA · Licencia completa (PC + Android)",
        "usd": int(os.getenv("MVCLIENTE_PRECIO_USD", "149")),
        "uyu": int(os.getenv("MVCLIENTE_PRECIO_UYU", "6000")),
    },
}


class CheckoutIn(BaseModel):
    plan: str = "licencia"


@app.post("/api/checkout")
def checkout(datos: CheckoutIn, request: Request):
    plan = PLANES.get(datos.plan)
    if plan is None:
        raise HTTPException(404, f"Plan desconocido: {datos.plan}")
    token = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "")
    if not token:
        raise HTTPException(503,
            "El pago todavía no está configurado en este servidor. "
            "Escribinos a vieraschiavi@gmail.com y lo resolvemos a mano.")

    origen = request.headers.get("origin") or f"https://{request.headers.get('host', '')}"
    cuerpo = {
        "items": [{"title": plan["titulo"], "quantity": 1,
                   "unit_price": float(plan["uyu"]), "currency_id": "UYU"}],
        "back_urls": {"success": f"{origen}/?pago=ok",
                      "pending": f"{origen}/?pago=pendiente",
                      "failure": f"{origen}/?pago=error"},
        "auto_return": "approved",
        "statement_descriptor": "MV CLIENTE IA",
    }
    peticion = urllib.request.Request(
        "https://api.mercadopago.com/checkout/preferences",
        data=json.dumps(cuerpo).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=20) as r:
            d = json.load(r)
    except Exception as e:                              # noqa: BLE001
        raise HTTPException(502, f"MercadoPago no respondió: {e}") from e
    url = d.get("init_point") or d.get("sandbox_init_point")
    if not url:
        raise HTTPException(502, "MercadoPago no devolvió la URL de pago")
    return {"url": url}


class AnalisisIn(BaseModel):
    """Entrada de la pestaña Análisis. La empresa y los competidores vienen
    de la corrida que el navegador ya tiene; los números financieros los
    escribe el usuario y son la única fuente de la proyección."""
    empresa: dict = Field(default_factory=dict)
    competidores: list[dict] = Field(default_factory=list)
    mercado: str = "todos"
    idioma: str = "es"
    # Todo en la misma moneda (la que el usuario use en su negocio).
    precio: float = Field(ge=0)                    # por cliente, por mes
    clientes_iniciales: float = Field(default=0, ge=0)
    nuevos_por_mes: float = Field(default=0, ge=0)  # sin publicidad
    churn_pct: float = Field(default=0, ge=0, le=100)
    gasto_fijo: float = Field(default=0, ge=0)     # mensual
    costo_por_cliente: float = Field(default=0, ge=0)
    gasto_ads: float = Field(default=0, ge=0)      # mensual
    cac: float = Field(default=0, ge=0)            # costo por cliente vía ads
    clave_ia: str = Field(default="", max_length=300)
    proveedor_ia: str = "claude"
    endpoint_ia: str = Field(default="", max_length=500)


@app.post("/api/analisis", dependencies=[Depends(requiere_auth)])
def analizar(entrada: AnalisisIn, request: Request):
    """Proyección financiera (matemática pura sobre los números del usuario)
    + análisis cualitativo con IA (probabilidad de éxito, mercado potencial,
    FODA de la competencia). La parte con IA usa la clave del usuario — sin
    clave no se inventa: vuelve vacía con su aviso."""
    from cliente_ia import analisis as motor_analisis

    financiero = motor_analisis.proyectar(
        precio=entrada.precio, nuevos_por_mes=entrada.nuevos_por_mes,
        churn_pct=entrada.churn_pct, gasto_fijo=entrada.gasto_fijo,
        costo_por_cliente=entrada.costo_por_cliente,
        gasto_ads=entrada.gasto_ads, cac=entrada.cac,
        clientes_iniciales=entrada.clientes_iniciales)

    cualitativo, avisos = None, []
    from cliente_ia.proveedores.llm import ErrorLLM, ProveedorLLM, hay_clave
    # La clave del usuario manda; la del servidor sólo la usa el dueño (si
    # no, cualquiera quemaría el crédito del servidor desde esta ruta).
    con_clave = bool(entrada.clave_ia) or (_es_owner(request) and hay_clave())
    if not con_clave:
        avisos.append("analisis_sin_clave")
    else:
        try:
            llm = ProveedorLLM(entrada.idioma, clave=entrada.clave_ia,
                               proveedor=entrada.proveedor_ia if entrada.clave_ia
                               else "claude",
                               endpoint=entrada.endpoint_ia,
                               mercado=entrada.mercado)
            cualitativo = motor_analisis.cualitativo(
                llm, entrada.empresa, entrada.competidores,
                entrada.mercado, entrada.idioma)
        except ErrorLLM as e:
            avisos.append(str(e))
    return {"financiero": financiero, "cualitativo": cualitativo,
            "avisos": avisos}


class SmtpIn(BaseModel):
    """Credenciales SMTP del usuario. Misma política que la clave de IA:
    viajan en esta petición, se usan y se descartan — nunca se guardan ni
    se escriben en un log del servidor."""
    host: str = Field(min_length=3, max_length=200)
    puerto: int = Field(default=587, ge=1, le=65535)
    usuario: str = Field(min_length=3, max_length=200)
    clave: str = Field(min_length=1, max_length=200)
    ssl: bool = False                              # True = SSL directo (465)


class CorreoEnvioIn(BaseModel):
    para: str = Field(min_length=5, max_length=200)
    asunto: str = Field(min_length=1, max_length=300)
    cuerpo: str = Field(min_length=1, max_length=20000)
    cuerpo_html: str = Field(default="", max_length=120000)


class AdjuntoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    tipo: str = Field(default="application/octet-stream", max_length=100)
    # ~5 MB reales; alcanza para un banner o un PDF. Un video no va adjunto
    # (los filtros de spam lo matan): va como enlace dentro del correo.
    contenido_b64: str = Field(max_length=7_000_000)


class EnvioIn(BaseModel):
    smtp: SmtpIn
    remitente: str = Field(default="", max_length=120)   # nombre visible
    correos: list[CorreoEnvioIn] = Field(min_length=1, max_length=50)
    adjuntos: list[AdjuntoIn] = Field(default_factory=list, max_length=3)


def _conectar_smtp(smtp: SmtpIn):
    import smtplib
    import ssl as modulo_ssl

    try:
        if smtp.ssl:
            servidor = smtplib.SMTP_SSL(smtp.host, smtp.puerto, timeout=30)
        else:
            servidor = smtplib.SMTP(smtp.host, smtp.puerto, timeout=30)
            servidor.starttls(context=modulo_ssl.create_default_context())
        servidor.login(smtp.usuario, smtp.clave)
        return servidor
    except Exception as e:                              # noqa: BLE001
        # Tipo y mensaje del servidor SMTP: nunca la clave.
        raise HTTPException(
            502, f"No se pudo conectar al SMTP: {type(e).__name__}: "
                 f"{str(e)[:200]}") from e


def _mandar_uno(servidor, smtp: SmtpIn, remitente: str, c: CorreoEnvioIn,
                adjuntos: list[AdjuntoIn]) -> dict:
    from email.message import EmailMessage
    from email.utils import formataddr

    m = EmailMessage()
    m["From"] = formataddr((remitente or smtp.usuario, smtp.usuario))
    m["To"] = c.para
    m["Subject"] = c.asunto
    m.set_content(c.cuerpo)
    if c.cuerpo_html:
        m.add_alternative(c.cuerpo_html, subtype="html")
    for a in adjuntos:
        try:
            datos = base64.b64decode(a.contenido_b64)
        except Exception:                                # noqa: BLE001
            continue
        tipo, _, subtipo = (a.tipo or "application/octet-stream").partition("/")
        m.add_attachment(datos, maintype=tipo or "application",
                         subtype=subtipo or "octet-stream", filename=a.nombre)
    try:
        servidor.send_message(m)
        return {"para": c.para, "ok": True, "detalle": ""}
    except Exception as e:                               # noqa: BLE001
        return {"para": c.para, "ok": False,
                "detalle": f"{type(e).__name__}: {str(e)[:200]}"}


@app.post("/api/enviar", dependencies=[Depends(requiere_auth)])
def enviar_correos(entrada: EnvioIn):
    """Envía los correos generados por el SMTP del usuario (su casilla
    corporativa o personal). Devuelve el resultado por destinatario: un
    rebote no frena a los demás."""
    servidor = _conectar_smtp(entrada.smtp)
    resultados = []
    try:
        for c in entrada.correos:
            resultados.append(_mandar_uno(servidor, entrada.smtp,
                                          entrada.remitente, c, entrada.adjuntos))
    finally:
        try:
            servidor.quit()
        except Exception:                                # noqa: BLE001
            pass
    return {"resultados": resultados,
            "enviados": sum(1 for r in resultados if r["ok"])}


# ---------------------------------------------------------------------------
# Automatizar el flujo: un click, todo enviado, comprobante a tu casilla
# ---------------------------------------------------------------------------
class XClavesIn(BaseModel):
    """Claves de la API de X (developer.x.com). Misma política que el SMTP y
    la clave de IA: viajan, se usan y se descartan."""
    consumer_key: str = Field(min_length=3, max_length=120)
    consumer_secret: str = Field(min_length=3, max_length=120)
    access_token: str = Field(min_length=3, max_length=160)
    access_secret: str = Field(min_length=3, max_length=120)


class LinkedInClavesIn(BaseModel):
    """Credenciales del proveedor de LinkedIn del usuario. El producto no
    guarda ni maneja la sesión de LinkedIn de nadie: habla con el proveedor
    que el usuario contrató, con SU clave, y la descarta."""
    proveedor: str = Field(default="unipile", max_length=30)
    dsn: str = Field(min_length=4, max_length=200)
    api_key: str = Field(min_length=8, max_length=300)
    account_id: str = Field(min_length=3, max_length=120)


class MensajeRedIn(BaseModel):
    destinatario: str = Field(min_length=1, max_length=200)
    texto: str = Field(min_length=1, max_length=8000)
    # Sólo para mostrar en el comprobante ("Elena · Banco Sur"), no se envía.
    etiqueta: str = Field(default="", max_length=160)


class MetricasXIn(BaseModel):
    x: XClavesIn
    ids: list[str] = Field(min_length=1, max_length=100)


class AutomatizarIn(BaseModel):
    smtp: SmtpIn
    remitente: str = Field(default="", max_length=120)
    correos: list[CorreoEnvioIn] = Field(default_factory=list, max_length=500)
    adjuntos: list[AdjuntoIn] = Field(default_factory=list, max_length=3)
    # A qué casilla llega el comprobante (por defecto, la propia del SMTP).
    comprobante_a: str = Field(default="", max_length=200)
    # Publicación real en X, sólo si el usuario cargó sus claves de API.
    x: XClavesIn | None = None
    x_texto: str = Field(default="", max_length=280)
    # LinkedIn por el proveedor que el usuario eligió y paga (ver
    # cliente_ia/redes.py: LinkedIn no expone API pública de mensajes).
    linkedin: LinkedInClavesIn | None = None
    linkedin_mensajes: list[MensajeRedIn] = Field(default_factory=list,
                                                  max_length=500)
    # Canales SIN API de envío alcanzable (Instagram y TikTok exigen una app
    # aprobada por Meta/ByteDance). Van al comprobante como cola manual, con
    # honestidad — no se simula un envío que no existe.
    manuales: dict[str, int] = Field(default_factory=dict)


def _claves_x(x: XClavesIn) -> redes.ClavesX:
    return redes.ClavesX(x.consumer_key, x.consumer_secret,
                         x.access_token, x.access_secret)


def _mandar_linkedin(entrada: AutomatizarIn) -> dict | None:
    """Los mensajes de LinkedIn, uno por uno, por el proveedor del usuario.
    Devuelve None si no configuró proveedor: no es un fallo, es que ese canal
    no está enchufado."""
    if not entrada.linkedin or not entrada.linkedin_mensajes:
        return None
    claves = redes.ClavesLinkedIn(
        proveedor=entrada.linkedin.proveedor, dsn=entrada.linkedin.dsn,
        api_key=entrada.linkedin.api_key, account_id=entrada.linkedin.account_id)
    resultados = []
    for m in entrada.linkedin_mensajes:
        r = redes.enviar_linkedin(claves, m.destinatario, m.texto)
        resultados.append({"a": m.etiqueta or m.destinatario,
                           "ok": r["ok"], "detalle": r.get("detalle", "")})
    return {"proveedor": entrada.linkedin.proveedor,
            "total": len(resultados),
            "enviados": sum(1 for r in resultados if r["ok"]),
            "resultados": resultados}


@app.post("/api/metricas/x", dependencies=[Depends(requiere_auth)])
def metricas_x(entrada: MetricasXIn):
    """Métricas públicas de los posts ya publicados — es lo que refresca el
    panel de métricas. El historial vive en el dispositivo del usuario; acá
    sólo se consultan los números de X con sus claves."""
    return {"metricas": redes.metricas_de_x(_claves_x(entrada.x), entrada.ids)}


def _html_comprobante(comp: dict) -> str:
    """El correo del comprobante. Tablas y estilos en línea, nada de flexbox
    ni <style>: Outlook no los soporta (regla de la casa)."""
    filas_correos = "".join(
        f'<tr><td style="padding:6px 12px;border-bottom:1px solid #e3e8ef">{r["para"]}</td>'
        f'<td style="padding:6px 12px;border-bottom:1px solid #e3e8ef;'
        f'color:{"#0a7d55" if r["ok"] else "#b3261e"}">'
        f'{"✔ enviado" if r["ok"] else "✘ " + (r["detalle"] or "falló")}</td></tr>'
        for r in comp["correos"]["resultados"])
    x = comp.get("x")
    fila_x = ""
    if x is not None:
        estado = (f'✔ publicado — <a href="{x["url"]}">{x["url"]}</a>'
                  if x["ok"] else f'✘ {x["detalle"] or "falló"}')
        fila_x = (f'<tr><td style="padding:6px 12px">X (Twitter)</td>'
                  f'<td style="padding:6px 12px">{estado}</td></tr>')
    li = comp.get("linkedin")
    fila_li = ""
    if li:
        fallas = [r for r in li["resultados"] if not r["ok"]]
        detalle = (f'✔ {li["enviados"]} de {li["total"]} enviados por '
                   f'{li["proveedor"]}')
        if fallas:
            detalle += (f' · ✘ {len(fallas)} fallaron '
                        f'({fallas[0]["detalle"] or "sin detalle"})')
        fila_li = (f'<tr><td style="padding:6px 12px">LinkedIn</td>'
                   f'<td style="padding:6px 12px">{detalle}</td></tr>')
    filas_manuales = "".join(
        f'<tr><td style="padding:6px 12px">{canal.title()}</td>'
        f'<td style="padding:6px 12px;color:#8a6d1a">⏳ {n} para publicar a mano '
        f'(sin API de envío)</td></tr>'
        for canal, n in (comp.get("manuales") or {}).items())
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="font-family:Arial,Helvetica,sans-serif;color:#15243c">'
        '<tr><td style="padding:18px 12px;font-size:20px;font-weight:bold">'
        "Comprobante de automatización · MV Cliente IA</td></tr>"
        f'<tr><td style="padding:0 12px 14px;color:#4a5a74">{comp["fecha"]} · '
        f'{comp["correos"]["enviados"]} de {comp["correos"]["total"]} correos '
        "enviados</td></tr>"
        '<tr><td><table role="presentation" cellpadding="0" cellspacing="0" '
        'style="font-size:14px;border:1px solid #e3e8ef;border-radius:6px" width="100%">'
        f"{filas_correos}{fila_x}{fila_li}{filas_manuales}"
        "</table></td></tr>"
        '<tr><td style="padding:14px 12px;color:#8a97ab;font-size:12px">'
        "Generado automáticamente al aprobar el flujo. Los canales sin API de "
        "envío quedan listos en la app para publicarlos con un click.</td></tr>"
        "</table>")


@app.post("/api/automatizar", dependencies=[Depends(requiere_auth)])
def automatizar_flujo(entrada: AutomatizarIn):
    """El botón «Automatizar flujo»: con el flujo YA aprobado por el usuario,
    un solo click envía todos los correos por su SMTP, publica en X si cargó
    sus claves, y manda el comprobante a su propia casilla con el detalle de
    qué salió, qué falló y qué quedó en cola manual."""
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    servidor = _conectar_smtp(entrada.smtp)
    resultados: list[dict] = []
    try:
        for c in entrada.correos:
            resultados.append(_mandar_uno(servidor, entrada.smtp,
                                          entrada.remitente, c, entrada.adjuntos))

        comp: dict = {
            "fecha": _dt.now(_UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "correos": {"total": len(resultados),
                        "enviados": sum(1 for r in resultados if r["ok"]),
                        "resultados": resultados},
            "x": (redes.publicar_en_x(_claves_x(entrada.x),
                                      entrada.x_texto.strip())
                  if entrada.x and entrada.x_texto.strip() else None),
            "linkedin": _mandar_linkedin(entrada),
            "manuales": {k: v for k, v in entrada.manuales.items() if v > 0},
        }

        # El comprobante viaja a la casilla del usuario por el mismo SMTP.
        destino = (entrada.comprobante_a or entrada.smtp.usuario).strip()
        recibo = CorreoEnvioIn(
            para=destino,
            asunto=f"Comprobante · {comp['correos']['enviados']}/"
                   f"{comp['correos']['total']} correos enviados · MV Cliente IA",
            cuerpo=(f"Automatización del {comp['fecha']}.\n"
                    f"Correos: {comp['correos']['enviados']} de "
                    f"{comp['correos']['total']} enviados.\n"
                    + (f"X: {'publicado ' + comp['x']['url'] if comp['x']['ok'] else 'falló'}\n"
                       if comp.get("x") else "")
                    + (f"LinkedIn: {comp['linkedin']['enviados']} de "
                       f"{comp['linkedin']['total']} enviados por "
                       f"{comp['linkedin']['proveedor']}\n"
                       if comp.get("linkedin") else "")
                    + "".join(f"{c.title()}: {n} para publicar a mano\n"
                              for c, n in comp["manuales"].items())),
            cuerpo_html=_html_comprobante(comp))
        r = _mandar_uno(servidor, entrada.smtp, entrada.remitente, recibo, [])
        comp["comprobante"] = {"a": destino, "ok": r["ok"], "detalle": r["detalle"]}
    finally:
        try:
            servidor.quit()
        except Exception:                                # noqa: BLE001
            pass
    return comp


class LicenciaIn(BaseModel):
    clave: str = Field(min_length=8, max_length=400)


@app.get("/api/licencia")
def ver_licencia():
    """Qué edición es esta copia y si su licencia está activa. La web
    (serverless) no tiene licencia: ahí manda el cupo gratis."""
    if SIN_ESTADO:
        return {"aplica": False, "edicion": "web"}
    return {"aplica": True, **licencia.estado().a_dict()}


@app.post("/api/licencia/validar")
def validar_licencia(entrada: LicenciaIn):
    """Valida una clave contra el secreto del SERVIDOR. Es lo que llama el
    programa instalado al activarse: así el secreto de firma no viaja adentro
    de ningún .exe. Sin autenticación a propósito — el que activa todavía no
    es usuario de nada, y lo único que se puede hacer acá es preguntar si una
    clave es válida."""
    r = licencia.verificar(entrada.clave)
    if not r["ok"]:
        # 200 con ok:false, no 4xx: el programa distingue «clave inválida» de
        # «no pude llegar al servidor», y un 4xx se confunde con lo segundo.
        return {"ok": False, "motivo": r["motivo"]}
    return {"ok": True, "email": r.get("email", ""), "vence": r.get("vence", "")}


@app.post("/api/licencia", dependencies=[Depends(requiere_auth)])
def activar_licencia(entrada: LicenciaIn):
    """Guarda la clave que el comprador recibió. La firma se verifica contra
    el secreto del dueño: el programa NO puede fabricar claves."""
    if SIN_ESTADO:
        raise HTTPException(400, "La web no usa licencias: usa el cupo gratis.")
    r = licencia.guardar_clave(entrada.clave)
    if not r["ok"]:
        raise HTTPException(422, r["motivo"])
    return {"ok": True, **licencia.estado().a_dict()}


@app.get("/api/geo")
def catalogo_geo(pais: str = "", idioma: str = "es"):
    """Las tres olas vistas desde el país del cliente, más el catálogo mundial
    que llena el selector de país. `pais` vacío = el que sale del idioma."""
    base = geo.resolver_base(pais, "", idioma)
    olas = []
    for nivel, prioridad, codigos in geo.orden_de_olas(base.codigo):
        olas.append({
            "nivel": nivel,
            "prioridad": prioridad,
            "peso": geo.PESO_PRIORIDAD[prioridad],
            "paises": [{"codigo": c, "nombre": geo.nombre_pais(c, idioma),
                        "idioma": geo.obtener(c).idioma} for c in codigos],
        })
    return {
        "olas": olas,
        "idiomas": list(geo.IDIOMAS),
        "pais_base": base.codigo,
        "pais_base_nombre": geo.nombre_pais(base.codigo, idioma),
        "region_base": geo.nombre_region(base.region, idioma),
        # Todos los países elegibles, agrupados por región y ordenados por
        # nombre: es lo que llena el desplegable «Tu país».
        "paises": [
            {"codigo": p.codigo, "nombre": geo.nombre_pais(p.codigo, idioma),
             "region": p.region,
             "region_nombre": geo.nombre_region(p.region, idioma),
             "idioma": p.idioma}
            for p in sorted(geo.paises_por_region(),
                            key=lambda x: (geo.REGIONES.index(x.region),
                                           geo.nombre_pais(x.codigo, idioma)))
        ],
    }


# ---------------------------------------------------------------------------
# Modelos de IA disponibles para la clave del usuario
# ---------------------------------------------------------------------------
class ModelosIaIn(BaseModel):
    proveedor: str = "claude"
    clave: str = Field(default="", max_length=300)


@app.post("/api/ia/modelos", dependencies=[Depends(requiere_auth)])
def modelos_ia(entrada: ModelosIaIn):
    """El botón «Actualizar» de Configuración: le pregunta a la API del
    proveedor elegido qué modelos puede usar ESTA clave ahora mismo, para
    que el selector nunca quede atrás de lo que el proveedor lanzó último.
    La clave viaja en el cuerpo y se descarta al terminar, igual que en una
    corrida — nunca se guarda ni se loguea."""
    from cliente_ia.proveedores.llm import ErrorLLM, listar_modelos
    try:
        return {"modelos": listar_modelos(entrada.proveedor, entrada.clave)}
    except ErrorLLM as e:
        raise HTTPException(422, str(e)) from e


# ---------------------------------------------------------------------------
# Corridas
# ---------------------------------------------------------------------------
class CorridaIn(BaseModel):
    dominio: str = Field(min_length=3, max_length=253)
    modo: str = "demo"
    # Recorte geográfico: "todos" (el país base primero, en proporción),
    # "local" (sólo ese país), "regional" (su región) o "mundo". Para productos
    # que exigen presencia física, «sólo mi país» evita gastar el cupo en
    # empresas inalcanzables.
    mercado: str = "todos"
    # País propio del cliente: el que ocupa la ola local. Vacío = deducilo del
    # TLD del dominio y, si es genérico, del idioma de la interfaz.
    pais: str = Field(default="", max_length=2)
    nombre: str = ""
    firma: str = ""
    idioma: str = "es"
    # Enlaces de los mensajes (banner, video y web), cada uno en el idioma del
    # receptor. Sin nada de esto se derivan del propio dominio del producto.
    sitio: str = ""
    videos: dict[str, str] = Field(default_factory=dict)
    video_en_landing: bool = False
    # Correo del usuario: obligatorio para las búsquedas reales gratis de la
    # web (el del dueño no descuenta). No entra en la corrida ni en logs.
    email: str = Field(default="", max_length=200)
    # Clave de IA pegada por el usuario en Configuración. Vale para esta
    # corrida: no se guarda, no se loguea y no entra en la corrida.
    clave_ia: str = Field(default="", max_length=300)
    # Qué modelo hay detrás de la clave: claude | openai | gemini | copilot |
    # grok. Copilot es Azure OpenAI y necesita además la URL del endpoint.
    proveedor_ia: str = "claude"
    endpoint_ia: str = Field(default="", max_length=500)
    # El modelo puntual dentro del proveedor (p. ej. "claude-opus-5"): lo
    # elige el usuario en Configuración para regular su propio consumo de
    # tokens. Vacío usa el default del servidor para ese proveedor.
    modelo_ia: str = Field(default="", max_length=100)
    # Hasta mil por corrida — los tramos del selector (50/100/200/500/1000).
    # La corrida de mil pesa ~1,7 MB en JSON: entra en el límite de Vercel.
    prospectos: int = Field(default=pipeline.LIMITE_PROSPECTOS_DEFAULT, ge=5, le=1000)
    decisores: int = Field(default=pipeline.DECISORES_POR_EMPRESA_DEFAULT, ge=1, le=5)
    emails: int = Field(default=pipeline.LIMITE_EMAILS_DEFAULT, ge=1, le=300)


def _lanzar(entrada: CorridaIn, corrida_id: str) -> None:
    def guardar_avance(c: Corrida):
        with _lock:
            almacen.guardar(c)

    try:
        pipeline.ejecutar(
            entrada.dominio, modo=entrada.modo,
            limite_prospectos=entrada.prospectos,
            decisores_por_empresa=entrada.decisores,
            limite_emails=entrada.emails,
            idioma_ui=entrada.idioma, firma=entrada.firma, nombre=entrada.nombre,
            enlaces=_config_enlaces(entrada),
            al_avanzar=guardar_avance, corrida_id=corrida_id,
            clave_ia=entrada.clave_ia,
            proveedor_ia=entrada.proveedor_ia,
            endpoint_ia=entrada.endpoint_ia,
            modelo_ia=entrada.modelo_ia,
            mercado=entrada.mercado,
            pais_base=entrada.pais,
        )
    finally:
        with _lock:
            _en_curso.discard(corrida_id)


def _config_enlaces(entrada: CorridaIn) -> dict:
    return {"sitio": entrada.sitio or entrada.dominio,
            "videos": {k: v for k, v in entrada.videos.items() if k in geo.IDIOMAS},
            "video_en_landing": entrada.video_en_landing}


def _ejecutar_sin_estado(entrada: CorridaIn, al_avanzar=None):
    t0 = time.monotonic()
    corrida = pipeline.ejecutar(
        entrada.dominio, modo=entrada.modo,
        limite_prospectos=entrada.prospectos,
        decisores_por_empresa=entrada.decisores,
        limite_emails=entrada.emails,
        idioma_ui=entrada.idioma, firma=entrada.firma, nombre=entrada.nombre,
        enlaces=_config_enlaces(entrada),
        clave_ia=entrada.clave_ia,
        proveedor_ia=entrada.proveedor_ia,
        endpoint_ia=entrada.endpoint_ia,
        modelo_ia=entrada.modelo_ia,
        mercado=entrada.mercado,
        pais_base=entrada.pais,
        al_avanzar=al_avanzar,
    )
    # Una línea por corrida en el log del servidor (sin secretos): fue lo
    # que faltó cuando el modo IA "no funcionaba" y no se veía por qué.
    reales = sum(1 for p in corrida.prospectos if not p.sintetico)
    print(f"[corrida] modo={corrida.modo} estado={corrida.estado} "
          f"{time.monotonic() - t0:.0f}s competidores={len(corrida.competidores)} "
          f"prospectos_reales={reales}/{len(corrida.prospectos)} "
          f"avisos={corrida.avisos or 'ninguno'}", flush=True)
    return corrida


@app.post("/api/corridas", dependencies=[Depends(requiere_auth)])
def crear_corrida(entrada: CorridaIn, request: Request, stream: int = 0):
    if entrada.modo not in proveedores.MODOS:
        raise HTTPException(422, f"Modo inválido: {entrada.modo}")
    if geo.normalizar_nivel(entrada.mercado) != entrada.mercado \
            and entrada.mercado not in ("todos", "latam"):
        raise HTTPException(422, f"Mercado inválido: {entrada.mercado}")
    if entrada.proveedor_ia not in ("claude", "openai", "gemini", "copilot", "grok"):
        raise HTTPException(422, f"Proveedor de IA inválido: {entrada.proveedor_ia}")

    # Programa instalado (no serverless): manda la LICENCIA, no el cupo. La
    # demo sintética queda libre siempre — es la vidriera y no consume nada.
    if not SIN_ESTADO and entrada.modo != "demo":
        lic = licencia.estado()
        if not lic.activa:
            raise HTTPException(402, lic.motivo or
                                "La licencia de este programa no está activa.")

    if SIN_ESTADO:
        # Con clave pegada en la interfaz el modo IA corre igual: la clave
        # viaja en esta petición y no queda en ningún lado del servidor.
        if entrada.modo not in modos_en_serverless() and not entrada.clave_ia:
            raise HTTPException(422,
                "El modo de investigación con IA necesita una clave de la API "
                "de Claude: pegala en Configuración, o definí ANTHROPIC_API_KEY "
                "en el servidor. Mientras tanto usá «demo» o «leer mi sitio».")

        # Cupo gratis de la web: sólo las búsquedas reales lo gastan, y piden
        # un correo válido (el del dueño no descuenta). Con clave propia
        # pegada, el costo de la IA lo paga el usuario en su propia cuenta —
        # no el servidor — así que tampoco descuenta cupo ni pide correo.
        usadas = 0
        correo = entrada.email.strip().lower()
        cuenta = (entrada.modo != "demo" and not _es_owner(request)
                  and not entrada.clave_ia)
        if cuenta:
            if not _EMAIL_RE.match(correo):
                raise HTTPException(422,
                    "Las búsquedas reales gratis piden un correo válido: "
                    "escribilo en el formulario de Explorar y lanzá de nuevo.")
            if _es_owner_email(correo):
                cuenta = False
        if cuenta:
            usadas = max(_cupo_usado(request), _cupo_por_email.get(correo, 0))
            if usadas >= CUPO_GRATIS:
                raise HTTPException(402,
                    f"Se terminaron las {CUPO_GRATIS} búsquedas reales gratis "
                    "de la web. La demo sigue libre, y el programa completo "
                    "(PC + Android, sin límite y con tus claves) se compra "
                    "desde la sección Precios de la portada.")
            usadas += 1
            # Los dos dicts con el MISMO tope: la IP sale de X-Forwarded-For,
            # que el cliente controla, así que sin cota un atacante inflaba
            # _cupo_por_ip con IPs al azar hasta comerse la memoria. El de
            # correo ya tenía tope; el de IP no — quedaba la asimetría.
            ip = _ip_de(request)
            if ip in _cupo_por_ip or len(_cupo_por_ip) < 50000:
                _cupo_por_ip[ip] = usadas
            if correo in _cupo_por_email or len(_cupo_por_email) < 50000:
                _cupo_por_email[correo] = usadas

        if stream:
            # La corrida va saliendo por fases (NDJSON): el navegador pinta
            # empresa, competidores, campañas y prospectos a medida que
            # existen, en vez de mirar "Buscando…" un par de minutos.
            cola: colas.Queue = colas.Queue()

            def correr():
                try:
                    corrida = _ejecutar_sin_estado(
                        entrada, al_avanzar=lambda c: cola.put(c.a_dict()))
                    cola.put(corrida.a_dict())
                except Exception as e:                  # noqa: BLE001
                    cola.put({"estado": "error", "error": f"{type(e).__name__}: {e}"})
                finally:
                    cola.put(None)

            def generar():
                hilo = threading.Thread(target=correr, daemon=True)
                hilo.start()
                while True:
                    item = cola.get()
                    if item is None:
                        break
                    yield json.dumps(item, ensure_ascii=False) + "\n"

            respuesta = StreamingResponse(generar(),
                                          media_type="application/x-ndjson")
            if cuenta:
                _poner_cookie_cupo(respuesta, usadas)
            return respuesta

        corrida = _ejecutar_sin_estado(entrada)
        if corrida.estado == "error":
            raise HTTPException(502, corrida.error or "La corrida falló")
        # La corrida entera, ya terminada: no hay dónde guardarla ni a quién
        # preguntarle después.
        respuesta = JSONResponse(corrida.a_dict())
        if cuenta:
            _poner_cookie_cupo(respuesta, usadas)
        return respuesta

    with _lock:
        if len(_en_curso) >= MAX_CORRIDAS_PARALELAS:
            raise HTTPException(429, "Hay demasiadas corridas en curso — probá en un minuto")
        corrida_id = secrets.token_hex(6)
        _en_curso.add(corrida_id)
    _ejecutor.submit(_lanzar, entrada, corrida_id)
    return {"id": corrida_id, "estado": "corriendo",
            "modo": proveedores.modo_efectivo(entrada.modo)}


@app.get("/api/corridas", dependencies=[Depends(requiere_auth)])
def listar_corridas(limite: int = 50):
    return {"corridas": almacen.listar(max(1, min(limite, 200)))}


@app.get("/api/corridas/{corrida_id}", dependencies=[Depends(requiere_auth)])
def ver_corrida(corrida_id: str):
    try:
        corrida = almacen.cargar(corrida_id)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if corrida is None:
        # Recién lanzada: el primer guardado puede no haber ocurrido todavía.
        # Devolver 404 haría que el frontend abandone el sondeo apenas empieza.
        with _lock:
            arrancando = corrida_id in _en_curso
        if arrancando:
            return {"id": corrida_id, "estado": "corriendo", "pasos": [],
                    "prospectos": [], "decisores": [], "emails": [],
                    "competidores": [], "campanas": [], "empresa": None,
                    "resumen": {}, "dominio": "", "modo": "", "error": ""}
        raise HTTPException(404, "No existe esa corrida")
    return corrida.a_dict()


@app.delete("/api/corridas/{corrida_id}", dependencies=[Depends(requiere_auth)])
def borrar_corrida(corrida_id: str):
    try:
        return {"borrada": almacen.borrar(corrida_id)}
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


def _cargar_o_404(corrida_id: str) -> Corrida:
    try:
        corrida = almacen.cargar(corrida_id)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if corrida is None:
        raise HTTPException(404, "No existe esa corrida")
    return corrida


def _nombre_descarga(corrida: Corrida, ext: str) -> str:
    """Nombre de archivo seguro para el header Content-Disposition. El dominio
    llega de la corrida (entrada de red en el POST directo) y sólo se le
    quitaba la barra: comillas o CR/LF colaban parámetros o rompían el header.
    Acá se deja sólo lo alfanumérico, punto y guiones."""
    base = f"{corrida.dominio}_{corrida.id}"
    limpio = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._") or "corrida"
    return f"{limpio[:100]}.{ext}"


def _csv_o_422(corrida: Corrida) -> str:
    """El CSV, o 422 si la corrida (reconstruida de un cuerpo no confiable)
    tiene tipos que rompen la serialización. `a_csv` hace `round(score)` y
    `join(senales)` fuera de toda validación: un score="abc" daba 500."""
    try:
        return exportar.a_csv(corrida)
    except (TypeError, ValueError, KeyError, AttributeError) as e:
        raise HTTPException(422, f"Corrida inválida para exportar: {e}") from e


@app.get("/api/corridas/{corrida_id}/csv", dependencies=[Depends(requiere_auth)])
def exportar_csv(corrida_id: str):
    corrida = _cargar_o_404(corrida_id)
    return PlainTextResponse(
        _csv_o_422(corrida), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":
                 f'attachment; filename="{_nombre_descarga(corrida, "csv")}"'})


@app.get("/api/corridas/{corrida_id}/xlsx", dependencies=[Depends(requiere_auth)])
def exportar_xlsx(corrida_id: str):
    corrida = _cargar_o_404(corrida_id)
    return _respuesta_xlsx(corrida)


def _respuesta_xlsx(corrida: Corrida):
    try:
        destino = exportar.guardar_xlsx(corrida)
    except RuntimeError as e:
        raise HTTPException(501, str(e)) from e
    except (TypeError, ValueError, KeyError, AttributeError) as e:
        # Cuerpo reconstruido con tipos inválidos: 422, no 500.
        raise HTTPException(422, f"Corrida inválida para exportar: {e}") from e
    return FileResponse(destino, filename=destino.name,
                        media_type="application/vnd.openxmlformats-officedocument."
                                   "spreadsheetml.sheet")


def _desde_cuerpo(datos: dict) -> Corrida:
    """
    Reconstruye la corrida que manda el navegador. Sin estado no hay dónde
    buscarla: la tiene el cliente, y la manda para que el servidor arme el
    archivo. Se valida acá porque es entrada de red, no un JSON de confianza.
    """
    try:
        return modelos.desde_dict(datos)
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(422, f"Corrida inválida: {e}") from e


@app.post("/api/exportar/csv", dependencies=[Depends(requiere_auth)])
def exportar_csv_directo(corrida: dict):
    c = _desde_cuerpo(corrida)
    return PlainTextResponse(
        _csv_o_422(c), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":
                 f'attachment; filename="{_nombre_descarga(c, "csv")}"'})


@app.post("/api/exportar/xlsx", dependencies=[Depends(requiere_auth)])
def exportar_xlsx_directo(corrida: dict):
    return _respuesta_xlsx(_desde_cuerpo(corrida))


# ---------------------------------------------------------------------------
# Frontend (build de React). Va al final: las rutas /api ya quedaron tomadas.
# ---------------------------------------------------------------------------
_DIST = rutas.dir_frontend()
if (_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{ruta:path}", include_in_schema=False)
    def spa(ruta: str):
        # El router de React usa hash (#/...), así que cualquier ruta que no
        # sea un archivo real devuelve el index y el navegador resuelve.
        #
        # La comprobación de contención NO es decorativa: `_DIST / ruta` con
        # un `../` en el medio apunta fuera del build y serviría cualquier
        # archivo del disco. Hoy Starlette normaliza la ruta antes de llegar
        # acá, pero eso es un detalle del framework, no una garantía de este
        # endpoint — se verifica igual.
        if ruta:
            try:
                archivo = (_DIST / ruta).resolve()
                if archivo.is_file() and archivo.is_relative_to(_DIST.resolve()):
                    return FileResponse(archivo)
            except (OSError, ValueError):
                pass                                # ruta inválida → cae al index
        return FileResponse(_DIST / "index.html")
else:                                                    # pragma: no cover
    @app.get("/", include_in_schema=False)
    def sin_build():
        return Response(
            "<h1>MV Cliente IA</h1><p>Falta compilar el frontend: "
            "<code>cd webapp/frontend && npm install && npm run build</code></p>",
            media_type="text/html")
