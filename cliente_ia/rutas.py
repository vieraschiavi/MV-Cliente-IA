"""
MV Cliente IA · rutas escribibles
==================================
Mismo criterio que MV Kobra AI: en el repo (dev/tests) se escribe al lado
del código; instalado (Windows/Electron o Android) se escribe en una carpeta
del usuario, nunca en Program Files ni dentro del APK.

`MVCLIENTE_DIR_DATOS` fuerza el directorio — es lo que usan los tests para
no ensuciar el repo.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _empaquetado() -> bool:
    """True si corre dentro de un bundle de PyInstaller (instalador de PC)."""
    return getattr(sys, "frozen", False)


def _dir_usuario() -> Path:
    if sys.platform.startswith("win"):
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "MVClienteIA"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MVClienteIA"
    return Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "mv-cliente-ia"


def en_serverless() -> bool:
    """
    True en Vercel (o cualquier función serverless que exporte estas
    variables). Importa porque ahí el disco es de sólo lectura salvo /tmp, y
    /tmp ni siquiera se comparte entre invocaciones.
    """
    return bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
                or os.getenv("MVCLIENTE_SIN_ESTADO"))


def dir_datos() -> Path:
    forzado = os.getenv("MVCLIENTE_DIR_DATOS")
    if forzado:
        d = Path(forzado)
    elif en_serverless():
        # Lo único escribible en una función serverless. Es efímero y no se
        # comparte entre invocaciones: sirve para no reventar al escribir,
        # no para guardar nada que se vaya a leer después (por eso el modo
        # sin estado del backend devuelve la corrida entera en la respuesta).
        d = Path("/tmp/mv-cliente-ia")
    elif _empaquetado():
        d = _dir_usuario()
    else:
        d = RAIZ / "datos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def dir_corridas() -> Path:
    d = dir_datos() / "corridas"
    d.mkdir(parents=True, exist_ok=True)
    return d


def dir_exports() -> Path:
    d = dir_datos() / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def dir_frontend() -> Path:
    """Build de React. Empaquetado, viaja junto al ejecutable."""
    if _empaquetado():
        return Path(getattr(sys, "_MEIPASS", RAIZ)) / "frontend_dist"
    return RAIZ / "webapp" / "frontend" / "dist"
