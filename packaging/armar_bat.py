"""
MV Cliente IA · armador de la edición BAT
==========================================
Arma `MVClienteIA_BAT_<edicion>.zip`: el programa entero para las empresas
que no dejan ejecutar un `.exe`. Adentro va el código, el build de React, los
`.bat` que lo abren e instalan, el sello de edición y —opcionalmente— las
ruedas de las dependencias para que instale sin internet.

    python3 packaging/armar_bat.py --edicion demo
    python3 packaging/armar_bat.py --edicion cliente --vendor 3.11,3.12,3.13

Es el mismo programa que el instalador `.exe`; lo único que cambia es cómo se
arranca. Por eso el ZIP se arma desde el mismo árbol de código y el mismo
`webapp/frontend/dist`, sin ninguna copia paralela que se pueda desincronizar.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cliente_ia import __version__  # noqa: E402
from cliente_ia.licencia import EDICIONES, NOMBRE_SELLO  # noqa: E402

CARPETA = "MVClienteIA"

# Código que viaja tal cual. `webapp/frontend` se copia aparte porque del
# frontend sólo va el build, nunca las fuentes ni node_modules.
ARBOL = [
    "cliente_ia",
    "webapp/__init__.py",
    "webapp/backend",
]
SUELTOS = [
    ("packaging/lanzador_escritorio.py", "packaging/lanzador_escritorio.py"),
    ("packaging/humo.py", "packaging/humo.py"),
    ("assets/brand/mv.ico", "assets/mv.ico"),
]
BATS = ["MVClienteIA.bat", "Instalar.bat", "Desinstalar.bat"]

# El `uvicorn[standard]` de requirements.txt arrastra httptools, watchfiles,
# websockets y uvloop, que son ruedas compiladas distintas por cada versión de
# Python y engordan el paquete sin internet. El programa no usa websockets ni
# necesita esa performance —es un servidor local para un solo usuario—, así
# que la edición BAT pide uvicorn pelado.
REQUISITOS = """\
# Dependencias de la edición BAT. Las instala MVClienteIA.bat con
# `pip --target`, primero desde vendor/ (sin internet) y sólo si no alcanza
# desde PyPI. uvicorn va sin [standard] a propósito: ver armar_bat.py.
fastapi>=0.110
uvicorn>=0.27
pydantic>=2.6
openpyxl>=3.1
"""

LEEME = """\
MV Cliente IA {version} - edicion BAT ({edicion})
==================================================

Para abrirlo
------------
Doble click en MVClienteIA.bat. Se abre en tu navegador.
Para cerrarlo, cerra la ventana negra.

Para dejarlo instalado (opcional)
---------------------------------
Doble click en Instalar.bat. Deja acceso directo en el Escritorio, entrada
en el Menu Inicio y en "Agregar o quitar programas". No pide permisos de
administrador.
Para sacarlo: Desinstalar.bat, o desde "Agregar o quitar programas".

Que necesita
------------
Python 3.11 o mas nuevo. Si no lo tenes, el propio MVClienteIA.bat te dice
como instalarlo. Desde la Microsoft Store no hace falta ser administrador.
{vendor}

Por que existe esta edicion
---------------------------
Es el MISMO programa que el instalador .exe, con la misma interfaz. La
diferencia es que no trae ningun ejecutable propio: sirve para las empresas
donde no se pueden abrir programas descargados de internet.

Donde guarda las cosas
----------------------
Tus busquedas y la configuracion quedan en:
  %LOCALAPPDATA%\\MVClienteIA
No se toca nada fuera de tu usuario.

Edicion {edicion}
{subrayado}
{explicacion}
"""

EXPLICACION = {
    "demo": "14 dias con todo abierto y sin poner ninguna clave. Cuando se\n"
            "vence, la demo sintetica sigue libre y las busquedas reales piden\n"
            "licencia.",
    "cliente": "Pide una vez la clave de licencia que llego con la compra.\n"
               "Se pega en Configuracion > Licencia y queda activo hasta la\n"
               "fecha de vencimiento de la clave.",
    "owner": "Sin clave y sin vencimiento. No se publica: se arma a mano.",
}

CON_VENDOR = """
Este ZIP trae la carpeta vendor\\ con las dependencias adentro, asi que
instala sin conexion a internet.
"""
SIN_VENDOR = """
Este ZIP NO trae la carpeta vendor\\: la primera vez necesita internet para
bajar las dependencias. Si la maquina no llega a PyPI, pedi la version que
trae vendor\\ incluido.
"""


def _ignorar(_carpeta: str, nombres: list[str]) -> set[str]:
    return {n for n in nombres if n == "__pycache__" or n.endswith((".pyc", ".pyo"))}


def copiar_arbol(destino: Path, frontend: Path | None = None) -> None:
    for rel in ARBOL:
        origen = RAIZ / rel
        fin = destino / rel
        fin.parent.mkdir(parents=True, exist_ok=True)
        if origen.is_dir():
            shutil.copytree(origen, fin, ignore=_ignorar, dirs_exist_ok=True)
        else:
            shutil.copy2(origen, fin)

    # `frontend` se puede apuntar a otro lado (`--frontend`) para que los tests
    # armen el ZIP sin depender de que alguien haya corrido npm: el portón de
    # CI es sólo Python y ahí `webapp/frontend/dist` no existe.
    dist = frontend or (RAIZ / "webapp" / "frontend" / "dist")
    if not (dist / "index.html").exists():
        raise SystemExit(
            f"Falta el build de React ({dist}). Corré `npm run build:web` "
            "antes de armar la edición BAT: sin eso el programa levanta el "
            "motor y sirve un 404 en blanco.")
    shutil.copytree(dist, destino / "webapp" / "frontend" / "dist",
                    dirs_exist_ok=True)

    for rel, dentro in SUELTOS:
        fin = destino / dentro
        fin.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / rel, fin)


def escribir_bats(destino: Path, edicion: str) -> None:
    for nombre in BATS:
        texto = (RAIZ / "packaging" / "bat" / nombre).read_text(encoding="utf-8")
        texto = texto.replace("@VERSION@", __version__).replace("@EDICION@", edicion)
        # CRLF: un .bat con finales de línea de Unix funciona de casualidad y
        # falla justo en las líneas con `goto`, que es lo peor que puede pasar.
        (destino / nombre).write_bytes(texto.replace("\n", "\r\n").encode("utf-8"))


def escribir_sello(destino: Path, edicion: str) -> None:
    """El mismo sello que hornea el instalador .exe, en el lugar donde lo
    busca `licencia._ruta_sello()` cuando el programa NO está congelado."""
    sello = destino / "packaging" / NOMBRE_SELLO
    sello.parent.mkdir(parents=True, exist_ok=True)
    sello.write_text(json.dumps({"edicion": edicion}), encoding="utf-8")


def bajar_ruedas(destino: Path, versiones: list[str]) -> int:
    """Ruedas de Windows para cada versión de Python soportada.

    Hace falta una por versión porque `pydantic_core` es una extensión
    compilada (`cp311`, `cp312`, …); el resto son puras y se repiten sin
    costo, que pip deduplica por nombre de archivo.
    """
    vendor = destino / "vendor"
    vendor.mkdir(parents=True, exist_ok=True)
    req = destino / "requirements.txt"
    for v in versiones:
        cmd = [sys.executable, "-m", "pip", "download", "-r", str(req),
               "--dest", str(vendor), "--only-binary=:all:",
               "--platform", "win_amd64", "--python-version", v]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"pip download falló para Python {v}:\n"
                             f"{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return len(list(vendor.glob("*.whl")))


def armar(edicion: str, versiones: list[str], salida: Path,
          frontend: Path | None = None) -> Path:
    if edicion not in EDICIONES:
        raise SystemExit(f"Edición desconocida: {edicion} (son {EDICIONES})")

    trabajo = salida / f"_bat_{edicion}"
    if trabajo.exists():
        shutil.rmtree(trabajo)
    raiz = trabajo / CARPETA
    raiz.mkdir(parents=True)

    copiar_arbol(raiz, frontend)
    (raiz / "requirements.txt").write_text(REQUISITOS, encoding="utf-8")
    escribir_bats(raiz, edicion)
    escribir_sello(raiz, edicion)

    ruedas = bajar_ruedas(raiz, versiones) if versiones else 0
    (raiz / "LEEME.txt").write_text(
        LEEME.format(version=__version__, edicion=edicion,
                     subrayado="-" * (8 + len(edicion)),
                     explicacion=EXPLICACION[edicion],
                     vendor=CON_VENDOR if ruedas else SIN_VENDOR),
        encoding="utf-8")

    salida.mkdir(parents=True, exist_ok=True)
    zip_final = salida / f"MVClienteIA_BAT_{edicion}.zip"
    if zip_final.exists():
        zip_final.unlink()
    with zipfile.ZipFile(zip_final, "w", zipfile.ZIP_DEFLATED) as z:
        for archivo in sorted(trabajo.rglob("*")):
            if archivo.is_file():
                z.write(archivo, archivo.relative_to(trabajo).as_posix())
    shutil.rmtree(trabajo)

    mb = zip_final.stat().st_size / 1_048_576
    print(f"  ✓ {zip_final.name}  ({mb:.1f} MB · {ruedas} ruedas offline)")
    return zip_final


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Arma la edición BAT")
    ap.add_argument("--edicion", default="demo",
                    help="demo | cliente | owner (o 'todas')")
    ap.add_argument("--vendor", default="",
                    help="versiones de Python para las ruedas offline, "
                         "ej. 3.11,3.12,3.13 (vacío = sin vendor)")
    ap.add_argument("--salida", default=str(RAIZ / "dist"))
    ap.add_argument("--frontend", default="",
                    help="build de React a empaquetar (por defecto "
                         "webapp/frontend/dist); lo usan los tests")
    args = ap.parse_args(argv)

    versiones = [v.strip() for v in args.vendor.split(",") if v.strip()]
    ediciones = list(EDICIONES) if args.edicion == "todas" else [args.edicion]
    frontend = Path(args.frontend) if args.frontend else None
    for ed in ediciones:
        armar(ed, versiones, Path(args.salida), frontend)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
