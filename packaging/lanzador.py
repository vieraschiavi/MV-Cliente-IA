"""
MV Cliente IA · lanzador del motor para el instalador de PC
============================================================
Es el punto de entrada que empaqueta PyInstaller (ver `mvclienteia.spec`).
Levanta uvicorn en 127.0.0.1 sobre el puerto que le pasa Electron.

Escucha SÓLO en la interfaz local a propósito: la app de escritorio no
expone el motor a la red, así que no hay puerto abierto para nadie más.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Empaquetado, los módulos viven junto al ejecutable y no en el cwd desde el
# que Windows haya arrancado el proceso.
if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(sys.executable).parent))
    sys.path.insert(0, getattr(sys, "_MEIPASS", ""))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _resolver_puerto(pedido: int | None, host: str) -> int:
    """
    Con `--puerto` explícito (es lo que manda Electron) se respeta tal cual:
    si está ocupado hay que fallar rápido para que Electron reintente con
    otro, no cambiarlo en silencio mientras la ventana espera en el viejo.

    Sin puerto explícito (doble clic al ejecutable, o corrida a mano) se
    intenta el default y, si otra aplicación ya lo usa, se pide uno libre al
    sistema en vez de morir con "address already in use".
    """
    import socket

    if pedido is not None:
        return pedido
    default = int(os.getenv("MVCLIENTE_PUERTO", "8810"))
    with socket.socket() as s:
        try:
            s.bind((host, default))
            return default
        except OSError:
            pass
    with socket.socket() as s:
        s.bind((host, 0))
        libre = s.getsockname()[1]
    print(f"[MV Cliente IA] el puerto {default} está ocupado por otra "
          f"aplicación; el motor usa el {libre}", flush=True)
    return libre


def main() -> int:
    ap = argparse.ArgumentParser(description="Motor de MV Cliente IA")
    ap.add_argument("--puerto", type=int, default=None)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    puerto = _resolver_puerto(args.puerto, args.host)

    import uvicorn

    from webapp.backend.api import app
    print(f"[MV Cliente IA] motor en http://{args.host}:{puerto}", flush=True)
    uvicorn.run(app, host=args.host, port=puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
