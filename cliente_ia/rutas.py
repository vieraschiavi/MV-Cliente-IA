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


def dir_datos() -> Path:
    forzado = os.getenv("MVCLIENTE_DIR_DATOS")
    if forzado:
        d = Path(forzado)
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
