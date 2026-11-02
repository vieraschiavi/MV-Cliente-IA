"""
MV Cliente IA · métricas públicas de las redes de cada competidor
=================================================================
Seguidores, publicaciones y «me gusta» de los perfiles que el competidor
publica en su propio sitio (`Competidor.redes`).

Esto antes estaba prohibido por la regla 12 del proyecto, y la regla tenía
razón en lo que protegía: no inventar perfiles y no armar un scraper que se
rompe. El dueño del producto decidió medir igual las cifras PÚBLICAS, y se
hace dentro de estos límites, que no se negocian:

- **Una visita anónima a la página pública del perfil**, la misma que ve
  cualquiera sin cuenta, con el User-Agent que identifica a la app. Sin
  sesión, sin cookies de nadie, sin proxies, sin rotar identidades y sin
  esquivar un bloqueo: si la red pide iniciar sesión o responde «demasiados
  pedidos», esa métrica queda «no disponible» y la red no se vuelve a tocar
  en la corrida (`MAX_BLOQUEOS_SEGUIDOS`).
- **Sólo perfiles de EMPRESAS** — los que el competidor enlaza desde su web.
  Nunca personas.
- **Cada número dice de dónde y de cuándo salió** (`fuente`, `fecha`): es una
  foto de ese día, no una serie.
- **Poco volumen**: un pedido por perfil, con pausa entre pedidos a la misma
  red.

Qué devuelve cada red hoy a una visita anónima (probado en vivo):
TikTok publica las cifras del perfil en el HTML; LinkedIn las pone en la
descripción de la página de empresa; Instagram las pone en la descripción
cuando no limita la IP (desde servidores de datos suele responder 429; desde
la PC de un usuario, normalmente no); Facebook muestra el muro de inicio de
sesión, así que casi siempre queda «no disponible». Que a veces no haya
número no es un error: es la red diciendo que no.

Se apaga entero con `MVCLIENTE_METRICAS_REDES=0`.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from html import unescape

TIMEOUT = 6
PAUSA_MISMA_RED = 1.0
MAX_BLOQUEOS_SEGUIDOS = 2
REDES = ("linkedin", "instagram", "tiktok", "facebook")

OK = "ok"
NO_DISPONIBLE = "no_disponible"

_RE_DESCRIPCION = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:description|description)["\'][^>]*'
    r'content=["\']([^"\']{4,600})', re.I)
_RE_DESCRIPCION_INV = re.compile(
    r'<meta[^>]+content=["\']([^"\']{4,600})["\'][^>]*'
    r'(?:property|name)=["\'](?:og:description|description)["\']', re.I)

# Un número como lo escribe cada idioma: 7.150.164 · 7,150,164 · 2,2 M ·
# 1.5K · 15 mil · 1,2 mi. El sufijo es lo que decide la escala.
_NUM = r"(\d{1,3}(?:[.,  ]\d{3})+|\d+(?:[.,]\d+)?)\s*(k|m|mil|mi|mill\.?|millones|milhões|b)?\b"
_SEGUIDORES = r"(?:followers|seguidores)"
_PUBLICACIONES = r"(?:posts|publicaciones|publicações)"

_ESCALA = {"k": 1_000, "mil": 1_000, "m": 1_000_000, "mi": 1_000_000,
           "mill": 1_000_000, "mill.": 1_000_000, "millones": 1_000_000,
           "milhões": 1_000_000, "b": 1_000_000_000}


def _activo() -> bool:
    return os.getenv("MVCLIENTE_METRICAS_REDES", "1") != "0"


def numero(texto: str, sufijo: str = "") -> int | None:
    """«7.150.164» → 7150164; «2,2» + «M» → 2200000; «15» + «mil» → 15000."""
    t = (texto or "").replace(" ", " ").strip()
    if not t:
        return None
    escala = _ESCALA.get((sufijo or "").lower().strip(), 1)
    if re.fullmatch(r"\d{1,3}(?:[., ]\d{3})+", t) and escala == 1:
        return int(re.sub(r"[., ]", "", t))
    try:
        return int(round(float(t.replace(",", ".")) * escala))
    except ValueError:
        return None


def _cifra_antes_de(texto: str, palabra: str) -> int | None:
    m = re.search(_NUM + r"\s*" + palabra, texto, re.I)
    return numero(m.group(1), m.group(2) or "") if m else None


def _descripcion(html: str) -> str:
    m = _RE_DESCRIPCION.search(html) or _RE_DESCRIPCION_INV.search(html)
    return " ".join(unescape(m.group(1)).split()) if m else ""


def de_descripcion(html: str) -> dict:
    """LinkedIn e Instagram: «7.150.164 seguidores en LinkedIn», «96M
    Followers, 77 Following, 4,290 Posts»."""
    d = _descripcion(html)
    salida = {"seguidores": _cifra_antes_de(d, _SEGUIDORES),
              "publicaciones": _cifra_antes_de(d, _PUBLICACIONES)}
    return {k: v for k, v in salida.items() if v is not None}


def de_tiktok(html: str, usuario: str = "") -> dict:
    """TikTok embebe las cifras del perfil en el JSON de la página. Se toma
    el bloque que sigue al `uniqueId` del perfil pedido, no el primero que
    aparezca: la página también trae cuentas sugeridas."""
    inicio = 0
    if usuario:
        m = re.search(f'"uniqueId":"{re.escape(usuario)}"', html, re.I)
        if not m:
            return {}
        inicio = m.start()
    tramo = html[inicio:inicio + 20000]
    m = (re.search(r'"statsV2":\{([^}]*)\}', tramo)
         or re.search(r'"stats":\{([^}]*)\}', tramo))
    if not m:
        return {}

    def campo(nombre: str) -> int | None:
        c = re.search(f'"{nombre}":"?(\\d+)', m.group(1))
        return int(c.group(1)) if c else None
    salida = {"seguidores": campo("followerCount"),
              "publicaciones": campo("videoCount"),
              "me_gusta": campo("heartCount")}
    return {k: v for k, v in salida.items() if v is not None}


def _usuario_tiktok(url: str) -> str:
    m = re.search(r"tiktok\.com/@([A-Za-z0-9_.]+)", url)
    return m.group(1) if m else ""


def _leer(red: str, url: str, bajar) -> dict:
    html = bajar(url, TIMEOUT)
    if red == "tiktok":
        return de_tiktok(html, _usuario_tiktok(url))
    return de_descripcion(html)


def _medir_red(red: str, pedidos: list[tuple[object, str]], bajar, fecha: str,
               candado: threading.Lock) -> None:
    bloqueos = 0
    for i, (comp, url) in enumerate(pedidos):
        registro = {"fuente": url, "fecha": fecha, "estado": NO_DISPONIBLE}
        if bloqueos < MAX_BLOQUEOS_SEGUIDOS:
            if i:
                time.sleep(PAUSA_MISMA_RED)
            try:
                cifras = _leer(red, url, bajar)
            except Exception:                              # noqa: BLE001
                cifras = {}
            if cifras.get("seguidores") is not None:
                registro.update(cifras, estado=OK)
                bloqueos = 0
            else:
                # Muro de login, 429 o página sin cifras: la red dijo que no.
                # Insistir sería empezar a esquivarla.
                bloqueos += 1
        # Dos redes escriben en el mismo competidor desde hilos distintos.
        with candado:
            comp.metricas = {**comp.metricas, red: registro}


def medir(competidores, bajar=None) -> int:
    """Carga `Competidor.metricas` con las cifras públicas de sus redes.
    Una red por hilo (redes distintas no se esperan entre sí); dentro de cada
    red, de a un perfil con pausa. Devuelve cuántas métricas se obtuvieron."""
    if not _activo():
        return 0
    if bajar is None:
        from .proveedores.web import bajar
    fecha = _dt.date.today().isoformat()
    por_red: dict[str, list] = {r: [] for r in REDES}
    for c in competidores:
        for red in REDES:
            url = (c.redes or {}).get(red)
            if url:
                por_red[red].append((c, url))
    candado = threading.Lock()
    activas = [r for r in REDES if por_red[r]]
    if activas:
        with ThreadPoolExecutor(max_workers=len(activas)) as pool:
            list(pool.map(lambda r: _medir_red(r, por_red[r], bajar, fecha, candado),
                          activas))
    return sum(1 for c in competidores for m in c.metricas.values()
               if m.get("estado") == OK)
