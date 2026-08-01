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

Las corridas se ejecutan en un pool de hilos y van guardando el avance
después de cada fase, así que el frontend puede consultar el estado mientras
corren (`GET /api/corridas/{id}`) sin esperar a que terminen.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cliente_ia import __version__, almacen, exportar, geo, pipeline, proveedores, rutas
from cliente_ia.modelos import Corrida

# Cuántas corridas pueden estar en vuelo a la vez. Cada una es corta (el modo
# demo son milisegundos; el modo LLM, minutos), pero sin tope un cliente que
# apreta el botón diez veces deja el proceso sin hilos.
MAX_CORRIDAS_PARALELAS = 4
TTL_TOKEN = 12 * 3600

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
    return {"ok": True, "version": __version__, "modos": list(proveedores.MODOS),
            "modo_llm_disponible": proveedores.modo_efectivo("llm") == "llm"}


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
    nombre: str = ""
    firma: str = ""
    idioma: str = "es"
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
            al_avanzar=guardar_avance, corrida_id=corrida_id,
        )
    finally:
        with _lock:
            _en_curso.discard(corrida_id)


@app.post("/api/corridas", dependencies=[Depends(requiere_auth)])
def crear_corrida(entrada: CorridaIn):
    if entrada.modo not in proveedores.MODOS:
        raise HTTPException(422, f"Modo inválido: {entrada.modo}")
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
    try:
        destino = exportar.guardar_xlsx(corrida)
    except RuntimeError as e:
        raise HTTPException(501, str(e)) from e
    return FileResponse(destino, filename=destino.name,
                        media_type="application/vnd.openxmlformats-officedocument."
                                   "spreadsheetml.sheet")


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
