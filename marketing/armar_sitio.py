"""
MV Cliente IA · ensamblador del sitio para Vercel
==================================================
Junta en `public/` todo lo que se publica, con la misma estructura de URLs que
mvkobranzaia.com:

    /            → landing en español          (landing/index.html)
    /pt/  /en/   → landing en portugués/inglés
    /descarga    → página de descargas
    /app/        → la aplicación (build de React)
    /banners/    → los banners de los correos
    /video/      → los videos por idioma
    /mv_icon.png → el isotipo

Se arma en un directorio aparte en vez de publicar el repo entero por dos
motivos: el `outputDirectory` de Vercel tiene que contener sólo lo servible
(el código del motor no se publica), y así las rutas del `vercel.json` son
las mismas en local y en producción.

    python3 -m marketing.armar_sitio          # asume el build de React hecho
    npm run vercel-build                      # build + ensamblado, como en Vercel
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PUBLICO = RAIZ / "public"
LANDING = RAIZ / "landing"
APP = RAIZ / "webapp" / "frontend" / "dist"


def _copiar_dir(origen: Path, destino: Path) -> int:
    if not origen.exists():
        return 0
    shutil.copytree(origen, destino, dirs_exist_ok=True)
    return sum(1 for p in destino.rglob("*") if p.is_file())


def armar(estricto: bool = True) -> Path:
    if PUBLICO.exists():
        shutil.rmtree(PUBLICO)
    PUBLICO.mkdir(parents=True)

    faltan: list[str] = []

    # --- landing en los tres idiomas -----------------------------------
    requeridos = ((LANDING / "index.html", PUBLICO / "index.html"),
                  (LANDING / "pt" / "index.html", PUBLICO / "pt" / "index.html"),
                  (LANDING / "en" / "index.html", PUBLICO / "en" / "index.html"))
    opcionales = ((LANDING / "descarga.html", PUBLICO / "descarga.html"),
                  (LANDING / "pt" / "descarga.html", PUBLICO / "pt" / "descarga.html"),
                  (LANDING / "en" / "descarga.html", PUBLICO / "en" / "descarga.html"))
    for origen, destino in requeridos + opcionales:
        if origen.exists():
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origen, destino)
        elif (origen, destino) in requeridos:
            faltan.append(str(origen.relative_to(RAIZ)))

    # --- estáticos de la landing ---------------------------------------
    for nombre in ("mv_icon.png",):
        if (LANDING / nombre).exists():
            shutil.copy2(LANDING / nombre, PUBLICO / nombre)

    _copiar_dir(LANDING / "banners", PUBLICO / "banners")
    # Los videos son opcionales: si el usuario todavía no los puso, el sitio
    # se publica igual y la sección de video muestra su aviso.
    _copiar_dir(LANDING / "video", PUBLICO / "video")

    # --- la aplicación --------------------------------------------------
    if APP.exists():
        _copiar_dir(APP, PUBLICO / "app")
    else:
        faltan.append("webapp/frontend/dist (falta `npm run build:web`)")

    if faltan and estricto:
        raise SystemExit("No se puede armar el sitio, falta:\n  - " + "\n  - ".join(faltan))
    return PUBLICO


def _resumen() -> str:
    archivos = [p for p in PUBLICO.rglob("*") if p.is_file()]
    peso = sum(p.stat().st_size for p in archivos)
    lineas = [f"  ✓ public/  ({len(archivos)} archivos · {peso / 1024:.0f} KB)"]
    for sub in ("", "pt", "en", "app", "banners", "video"):
        d = PUBLICO / sub if sub else PUBLICO
        n = sum(1 for p in d.glob("*") if p.is_file()) if d.exists() else 0
        lineas.append(f"      /{sub or ''}{'/' if sub else ''}  {n} archivo(s)")
    return "\n".join(lineas)


if __name__ == "__main__":
    armar(estricto="--permisivo" not in sys.argv)
    print(_resumen())
