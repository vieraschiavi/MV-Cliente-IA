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


def main() -> int:
    ap = argparse.ArgumentParser(description="Motor de MV Cliente IA")
    ap.add_argument("--puerto", type=int,
                    default=int(os.getenv("MVCLIENTE_PUERTO", "8810")))
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    import uvicorn

    from webapp.backend.api import app
    uvicorn.run(app, host=args.host, port=args.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
