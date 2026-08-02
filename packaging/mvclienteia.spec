# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller · motor de MV Cliente IA
=====================================
Genera dist/MVClienteIA/, que es lo que electron-builder copia a
resources/backend/ del instalador (ver electron/package.json).

    pyinstaller packaging/mvclienteia.spec --noconfirm

Dos cosas tienen que viajar sí o sí adentro del bundle:
  - `cliente_ia/datos/mercado.json` — la semilla del catálogo de mercado;
    sin ella el proveedor demo no arranca.
  - `webapp/frontend/dist` — el build de React, que el backend sirve como
    estático. Va a `frontend_dist/`, que es donde lo busca `rutas.dir_frontend()`
    cuando corre empaquetado.
"""
from pathlib import Path

RAIZ = Path(SPECPATH).parent          # noqa: F821 — SPECPATH lo inyecta PyInstaller

datos = [
    (str(RAIZ / "cliente_ia" / "datos" / "mercado.json"), "cliente_ia/datos"),
]
frontend = RAIZ / "webapp" / "frontend" / "dist"
if frontend.exists():
    datos.append((str(frontend), "frontend_dist"))

a = Analysis(
    [str(RAIZ / "packaging" / "lanzador.py")],
    pathex=[str(RAIZ)],
    binaries=[],
    datas=datos,
    hiddenimports=[
        # uvicorn resuelve estos por nombre en runtime: PyInstaller no los ve
        # en el árbol de imports y el ejecutable arranca y muere.
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        # Estos tres se importan DENTRO de funciones (para no pagarlos en
        # cada arranque). Van explícitos por las dudas: si alguno faltara,
        # la app de PC se quedaría sin pestaña de Análisis, sin contactos
        # públicos o sin modo IA, y recién se notaría al usarla.
        "cliente_ia.analisis",
        "cliente_ia.proveedores.contactos",
        "cliente_ia.proveedores.llm",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)                     # noqa: F821

exe = EXE(                            # noqa: F821
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="MVClienteIA",
    console=False,
    icon=str(RAIZ / "assets" / "brand" / "mv.ico"),
)
coll = COLLECT(                       # noqa: F821
    exe, a.binaries, a.datas,
    strip=False, upx=False, name="MVClienteIA",
)
