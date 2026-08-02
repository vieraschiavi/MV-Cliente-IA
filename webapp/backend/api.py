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

import hashlib
import hmac
import json
import os
import queue as colas
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

from cliente_ia import __version__, almacen, exportar, geo, modelos, pipeline, proveedores, rutas
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

app = FastAPI(title="MV Cliente IA", version=__version__)
app.add_middleware(
    CORSMiddleware,
    # El frontend se sirve desde el mismo origen en los tres empaquetados; en
    # desarrollo Vite proxya /api, así que tampoco hay cruce de origen. Se deja
    # abierto sólo para GET/POST y sin credenciales de cookie.
    allow_origins=["*"], allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"],
)

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
def cupo(request: Request):
    """Cuántas búsquedas reales gratis quedan en este navegador/IP."""
    if not SIN_ESTADO:
        return {"aplica": False, "gratis": 0, "usadas": 0, "owner": False}
    return {"aplica": True, "gratis": CUPO_GRATIS,
            "usadas": min(_cupo_usado(request), CUPO_GRATIS),
            "owner": _es_owner(request)}


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


@app.get("/api/geo")
def catalogo_geo():
    """Las tres olas y sus países — es lo que pinta el selector de mercado."""
    olas = []
    for nivel, prioridad, codigos in geo.orden_de_olas():
        olas.append({
            "nivel": nivel,
            "prioridad": prioridad,
            "peso": geo.PESO_PRIORIDAD[prioridad],
            "paises": [{"codigo": c, "nombre": geo.obtener(c).nombre,
                        "idioma": geo.obtener(c).idioma} for c in codigos],
        })
    return {"olas": olas, "idiomas": list(geo.IDIOMAS)}


# ---------------------------------------------------------------------------
# Corridas
# ---------------------------------------------------------------------------
class CorridaIn(BaseModel):
    dominio: str = Field(min_length=3, max_length=253)
    modo: str = "demo"
    # Recorte geográfico: "todos" (Uruguay primero, en proporción), "local"
    # (sólo Uruguay), "latam" o "mundo". Para productos que exigen presencia
    # física, «sólo Uruguay» evita gastar el cupo en empresas inalcanzables.
    mercado: str = "todos"
    nombre: str = ""
    firma: str = ""
    idioma: str = "es"
    # Enlaces de los mensajes (banner, video y web), cada uno en el idioma del
    # receptor. Sin nada de esto se derivan del propio dominio del producto.
    sitio: str = ""
    videos: dict[str, str] = Field(default_factory=dict)
    video_en_landing: bool = False
    # Clave de IA pegada por el usuario en Configuración. Vale para esta
    # corrida: no se guarda, no se loguea y no entra en la corrida.
    clave_ia: str = Field(default="", max_length=300)
    # Qué modelo hay detrás de la clave: claude | openai | gemini | copilot.
    # Copilot es Azure OpenAI y necesita además la URL del endpoint.
    proveedor_ia: str = "claude"
    endpoint_ia: str = Field(default="", max_length=500)
    prospectos: int = Field(default=pipeline.LIMITE_PROSPECTOS_DEFAULT, ge=5, le=400)
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
            mercado=entrada.mercado,
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
        mercado=entrada.mercado,
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
    if entrada.mercado not in ("todos", "local", "latam", "mundo"):
        raise HTTPException(422, f"Mercado inválido: {entrada.mercado}")
    if entrada.proveedor_ia not in ("claude", "openai", "gemini", "copilot"):
        raise HTTPException(422, f"Proveedor de IA inválido: {entrada.proveedor_ia}")

    if SIN_ESTADO:
        # Con clave pegada en la interfaz el modo IA corre igual: la clave
        # viaja en esta petición y no queda en ningún lado del servidor.
        if entrada.modo not in modos_en_serverless() and not entrada.clave_ia:
            raise HTTPException(422,
                "El modo de investigación con IA necesita una clave de la API "
                "de Claude: pegala en Configuración, o definí ANTHROPIC_API_KEY "
                "en el servidor. Mientras tanto usá «demo» o «leer mi sitio».")

        # Cupo gratis de la web: sólo las búsquedas reales lo gastan.
        usadas = 0
        cuenta = entrada.modo != "demo" and not _es_owner(request)
        if cuenta:
            usadas = _cupo_usado(request)
            if usadas >= CUPO_GRATIS:
                raise HTTPException(402,
                    f"Se terminaron las {CUPO_GRATIS} búsquedas reales gratis "
                    "de la web. La demo sigue libre, y el programa completo "
                    "(PC + Android, sin límite y con tus claves) se compra "
                    "desde la sección Precios de la portada.")
            usadas += 1
            _cupo_por_ip[_ip_de(request)] = usadas

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


@app.get("/api/corridas/{corrida_id}/csv", dependencies=[Depends(requiere_auth)])
def exportar_csv(corrida_id: str):
    corrida = _cargar_o_404(corrida_id)
    nombre = f"{corrida.dominio}_{corrida.id}.csv".replace("/", "_")
    return PlainTextResponse(
        exportar.a_csv(corrida), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@app.get("/api/corridas/{corrida_id}/xlsx", dependencies=[Depends(requiere_auth)])
def exportar_xlsx(corrida_id: str):
    corrida = _cargar_o_404(corrida_id)
    return _respuesta_xlsx(corrida)


def _respuesta_xlsx(corrida: Corrida):
    try:
        destino = exportar.guardar_xlsx(corrida)
    except RuntimeError as e:
        raise HTTPException(501, str(e)) from e
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
    nombre = f"{c.dominio}_{c.id}.csv".replace("/", "_")
    return PlainTextResponse(
        exportar.a_csv(c), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


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
