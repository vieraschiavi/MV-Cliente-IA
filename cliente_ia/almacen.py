"""
MV Cliente IA · persistencia de corridas
=========================================
Una corrida = un JSON en `datos/corridas/<id>.json`. Sin base de datos a
propósito: el mismo código tiene que correr en la nube, dentro del instalador
de Windows y dentro del APK, donde no hay servidor de base al que conectarse.

La escritura es atómica (archivo temporal + `os.replace`) porque el backend
guarda el avance después de *cada* fase: si el proceso se cae en el medio,
queda el último estado completo, no un JSON cortado a la mitad.
"""
from __future__ import annotations

import itertools
import json
import os
import re
import threading
import time
from pathlib import Path

from . import rutas
from .modelos import Corrida, desde_dict

# Windows bloquea el archivo mientras se lo renombra o se lo escribe: si un
# lector lo abre en ese instante salta PermissionError (Errno 13), y el
# backend guarda el avance después de CADA fase mientras el frontend hace
# polling — o sea que las dos cosas pasan a la vez todo el tiempo. En POSIX
# el rename es atómico y esto no ocurre nunca; en Windows es una ventana de
# milisegundos. Se reintenta un puñado de veces antes de rendirse.
_REINTENTOS = 8
_ESPERA = 0.03
_contador = itertools.count()


def _con_reintento(accion):
    ultimo: OSError | None = None
    for intento in range(_REINTENTOS):
        try:
            return accion()
        except PermissionError as e:                    # sharing violation de Windows
            ultimo = e
            time.sleep(_ESPERA * (intento + 1))
    raise ultimo                                        # se agotaron: que se vea


def ruta_de(corrida_id: str) -> Path:
    """
    Ruta del JSON de una corrida. El id se valida, no se "limpia": sanear
    "../../etc/passwd" a "etcpasswd" es seguro pero convierte una entrada
    hostil en un id distinto y válido, que después es imposible de rastrear.
    Los ids que genera el producto son hexadecimales, así que ser estricto no
    rechaza nada legítimo.
    """
    if not corrida_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", corrida_id):
        raise ValueError(f"id de corrida inválido: {corrida_id!r}")
    return rutas.dir_corridas() / f"{corrida_id}.json"


def guardar(corrida: Corrida) -> Path:
    destino = ruta_de(corrida.id)
    # El tmp tiene que ser único por ESCRITURA, no por proceso: dos fases de
    # la misma corrida guardando casi juntas —y en el mismo proceso, o sea
    # mismo pid— se pisaban el temporal y una perdía el replace (media suite
    # de estrés lo destapó). pid + hilo + contador no colisiona ni entre
    # procesos ni entre hilos.
    marca = f"{os.getpid()}.{threading.get_ident()}.{next(_contador)}"
    tmp = destino.with_suffix(f".{marca}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(corrida.a_dict(), f, ensure_ascii=False, indent=1)
    try:
        _con_reintento(lambda: os.replace(tmp, destino))
    finally:
        # Si el replace no llegó a concretarse, no dejar el tmp tirado.
        if tmp.exists() and tmp != destino:
            try:
                tmp.unlink()
            except OSError:
                pass
    return destino


def cargar(corrida_id: str) -> Corrida | None:
    destino = ruta_de(corrida_id)

    def _leer():
        # Sin `exists()` previo: entre el chequeo y el open, otra corrida podía
        # borrarse (TOCTOU). Se abre directo y "no está" se maneja como None.
        try:
            with open(destino, encoding="utf-8") as f:
                return desde_dict(json.load(f))
        except FileNotFoundError:
            return None

    return _con_reintento(_leer)


def listar(limite: int = 50) -> list[dict]:
    """Cabeceras de las corridas guardadas, de la más nueva a la más vieja."""
    salida: list[dict] = []
    # `*.json` y no `*` para no tomar los `.<pid>.tmp` a medio escribir.
    for p in rutas.dir_corridas().glob("*.json"):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Un JSON roto —o uno que en Windows está justo renombrándose—
            # no tumba el listado: se saltea y aparece en el próximo refresco.
            continue
        salida.append({
            "id": d.get("id", p.stem),
            "dominio": d.get("dominio", ""),
            "creada": d.get("creada", ""),
            "estado": d.get("estado", ""),
            "modo": d.get("modo", ""),
            "resumen": d.get("resumen", {}),
        })
    salida.sort(key=lambda x: x["creada"], reverse=True)
    return salida[:limite]


def borrar(corrida_id: str) -> bool:
    destino = ruta_de(corrida_id)
    if destino.exists():
        destino.unlink()
        return True
    return False
