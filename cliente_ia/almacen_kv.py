"""
MV Cliente IA · almacén durable de métricas (Vercel KV / Upstash Redis)
========================================================================
El motivo de que esto exista: en la web pública el programa corre serverless y
**el disco es efímero**. Cada petición puede caer en una instancia nueva, así
que el JSONL de métricas se perdía entre invocaciones: el pixel contaba una
apertura y a los cinco minutos ya no estaba. En el programa instalado (PC/BAT)
no pasa —ahí hay disco de verdad— y por eso el archivo sigue siendo el camino
por defecto.

Se habla con la API **REST** de Upstash Redis, que es la que hay debajo de
Vercel KV. REST y no un cliente de Redis a propósito: son peticiones HTTPS con
`urllib`, sin dependencias nuevas y sin sockets que mantener abiertos, que es
justo lo que sirve en una función serverless que vive unos segundos.

Se enciende solo si están las variables (Vercel las inyecta al crear el store):

    KV_REST_API_URL / KV_REST_API_TOKEN                (Vercel KV)
    UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN  (Upstash directo)

Sin ellas, `activo()` es False y `metricas` sigue con el archivo local. No hay
un tercer camino ni un modo "a medias": o persiste en KV, o persiste en disco.

Regla que atraviesa todo el módulo: **si el almacén falla, no se rompe nada**.
Un contador es una función accesoria; que Upstash tenga un mal minuto no puede
convertir el pixel de un correo en un error ni tumbar una corrida. Los fallos
se tragan y se anota el tipo en el log (nunca el token).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

# La lista donde viven los eventos. Un nombre fijo: un store por proyecto.
CLAVE_EVENTOS = "mvcliente:metricas"
# Prefijo de los nonces ya vistos (dedup de clicks, aperturas y respuestas).
PREFIJO_NONCE = "mvcliente:nonce:"

# Techo de la lista, equivalente al de bytes del archivo. `resumen()` lee todo
# en cada llamada: sin tope, la lectura crecería sin fin y el plan gratis de
# KV tiene un límite de comandos por día que conviene no gastar en historia
# vieja. Se recorta por la punta vieja, igual que el archivo deja de crecer.
MAX_EVENTOS = int(os.getenv("MVCLIENTE_KV_MAX_EVENTOS", "50000"))

# Cuánto vive la marca de un nonce. 90 días cubre de sobra el ciclo de un
# correo en frío con su seguimiento; más que eso sería pagar almacenamiento
# para impedir un doble conteo que ya no le importa a nadie.
TTL_NONCE = int(os.getenv("MVCLIENTE_KV_TTL_NONCE", str(90 * 24 * 3600)))

# Corto a propósito: el pixel y el redirect están en el camino del
# destinatario. Antes que hacerlo esperar, se pierde el evento.
TIMEOUT = float(os.getenv("MVCLIENTE_KV_TIMEOUT", "3"))


def _config() -> tuple[str, str]:
    """(url, token) del store, o ('', '') si no hay ninguno configurado."""
    url = (os.getenv("KV_REST_API_URL")
           or os.getenv("UPSTASH_REDIS_REST_URL") or "").strip().rstrip("/")
    token = (os.getenv("KV_REST_API_TOKEN")
             or os.getenv("UPSTASH_REDIS_REST_TOKEN") or "").strip()
    return (url, token) if url and token else ("", "")


def activo() -> bool:
    return bool(_config()[0])


# Centinela de "no hubo respuesta". Hace falta un valor aparte porque `None`
# es una respuesta VÁLIDA de Redis: `SET NX` sobre una clave que ya existe
# devuelve null, y confundir eso con un fallo hacía que el dedup dejara pasar
# todo — el click repetido volvía a contar. Lo agarró el test, no la lectura.
FALLO = object()


def _pedir(comando: list) -> object:
    """Un comando de Redis por REST. Devuelve `FALLO` si no hubo respuesta —
    nunca una excepción hacia afuera: ver la regla del encabezado."""
    url, token = _config()
    if not url:
        return FALLO
    cuerpo = json.dumps(comando).encode()
    pedido = urllib.request.Request(
        url, data=cuerpo,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT) as r:
            return json.loads(r.read()).get("result")
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as e:
        # El tipo del fallo, jamás el token ni la URL (que lo lleva en el host).
        print(f"[kv] {comando[0]} falló: {type(e).__name__}", flush=True)
        return FALLO


def agregar(evento: dict) -> bool:
    """Un evento al final de la lista. Devuelve si se guardó de verdad."""
    linea = json.dumps(evento, ensure_ascii=False, sort_keys=True)
    largo = _pedir(["RPUSH", CLAVE_EVENTOS, linea])
    if largo is FALLO:
        return False
    # Recorte perezoso: sólo cuando la lista pasó el techo, para no gastar un
    # comando por evento. LTRIM con índices negativos deja los últimos N.
    try:
        if int(largo) > MAX_EVENTOS:
            _pedir(["LTRIM", CLAVE_EVENTOS, f"-{MAX_EVENTOS}", "-1"])
    except (TypeError, ValueError):
        pass
    return True


def leer() -> list[dict]:
    """Todos los eventos guardados. Lista vacía si el store no responde: es
    preferible un tablero en blanco a uno con la mitad de los números."""
    crudos = _pedir(["LRANGE", CLAVE_EVENTOS, "0", "-1"])
    if not isinstance(crudos, list):
        return []
    eventos = []
    for linea in crudos:
        try:
            e = json.loads(linea)
        except (ValueError, TypeError):
            continue                             # una entrada rota no tumba el resto
        if isinstance(e, dict):
            eventos.append(e)
    return eventos


def nonce_nuevo(nonce: str) -> bool | None:
    """True la primera vez que se ve el nonce, False si ya estaba.

    `SET NX EX` es una sola operación atómica del lado de Redis, y ahí está la
    gracia: el dedup en memoria del proceso NO sirve en serverless, donde cada
    petición puede caer en una instancia recién creada que no vio nada. Con el
    archivo local eso hacía que reproducir el enlace de un correo inflara la
    conversión en la web pública, aunque el test en una máquina con disco
    pasara perfecto.

    Devuelve `None` si el store no contestó, para que quien llama decida:
    `metricas` cae al dedup en memoria en vez de perder el evento.
    """
    if not nonce:
        return True
    r = _pedir(["SET", PREFIJO_NONCE + nonce, "1", "NX", "EX", str(TTL_NONCE)])
    if r is FALLO:
        return None
    # "OK" si guardó (nonce nuevo); null si la clave ya existía (repetido).
    return r == "OK"


def borrar_todo() -> None:
    """Vacía la lista. Los nonces se dejan vencer solos: borrarlos exigiría
    recorrer las claves (SCAN), que en el plan gratis es caro, y un nonce
    huérfano no molesta a nadie."""
    _pedir(["DEL", CLAVE_EVENTOS])
