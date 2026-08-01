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

import json
import os
import re
from pathlib import Path

from . import rutas
from .modelos import Corrida, desde_dict


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
    tmp = destino.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(corrida.a_dict(), f, ensure_ascii=False, indent=1)
    os.replace(tmp, destino)
    return destino


def cargar(corrida_id: str) -> Corrida | None:
    destino = ruta_de(corrida_id)
    if not destino.exists():
        return None
    with open(destino, encoding="utf-8") as f:
        return desde_dict(json.load(f))


def listar(limite: int = 50) -> list[dict]:
    """Cabeceras de las corridas guardadas, de la más nueva a la más vieja."""
    salida: list[dict] = []
    for p in rutas.dir_corridas().glob("*.json"):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue                                    # un JSON roto no tumba el listado
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
