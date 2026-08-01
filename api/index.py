"""
MV Cliente IA · punto de entrada de la función serverless (Vercel)
===================================================================
Vercel toma cualquier archivo dentro de `api/` y lo publica como función. El
runtime de Python detecta el objeto ASGI llamado `app`, así que alcanza con
reexportar el mismo FastAPI que usan la web, el instalador de PC y el APK: no
hay una segunda implementación del backend que se pueda desincronizar.

El `vercel.json` rutea `/api/:path*` acá, y el backend arranca solo en **modo
sin estado** porque detecta la variable `VERCEL` (ver `cliente_ia.rutas` y el
docstring de `webapp.backend.api`): la corrida se ejecuta dentro de la misma
petición y vuelve entera en la respuesta, sin historial ni sondeo.
"""
from __future__ import annotations

import sys
from pathlib import Path

# La función corre con el repo como raíz, pero no necesariamente en sys.path.
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from webapp.backend.api import app  # noqa: E402

__all__ = ["app"]
