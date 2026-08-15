"""La app de PC: versiones con soporte, árbol reproducible y CI alineado.

Estos tests nacieron subiendo Electron de la 33 (diez versiones mayores fuera
de soporte) a la 43. Dos cosas casi se publican rotas y no las agarraba nada:

  1. Electron 43 declara `engines: node >= 22.12` y el CI usaba Node 20. El
     `npm ci` de electron/ habría fallado recién en el job de Windows, al
     armar la Release.
  2. No existía `electron/package-lock.json`. Sin lock, dos builds del
     instalador en fechas distintas pueden traer árboles de dependencias
     distintos — y el instalador es lo que corre en la máquina del cliente.

No prueban que el instalador funcione (eso es el CI de Windows). Prueban que
las piezas estén alineadas, que es donde falla el olvido.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ELECTRON = RAIZ / "electron"
FLUJOS = RAIZ / ".github" / "workflows"

# Electron mantiene sólo las últimas versiones mayores. Este piso se sube a
# mano cuando se actualiza: es un recordatorio, no una comprobación de red.
MAJOR_MINIMO_ELECTRON = 41
# El que exige `engines` de Electron 43. Si se sube Electron, revisar los dos.
NODE_MINIMO = 22


def _paquete() -> dict:
    return json.loads((ELECTRON / "package.json").read_text(encoding="utf-8"))


def test_electron_esta_dentro_de_la_ventana_de_soporte():
    version = _paquete()["devDependencies"]["electron"]
    major = int(re.search(r"(\d+)", version).group(1))
    assert major >= MAJOR_MINIMO_ELECTRON, (
        f"Electron {major} está fuera de la ventana de soporte (mínimo "
        f"{MAJOR_MINIMO_ELECTRON}). Una versión sin soporte se lleva puesto "
        "el Chromium del instalador de PC, sin parches de seguridad.")


def test_existe_el_lock_de_electron_y_es_coherente():
    lock = ELECTRON / "package-lock.json"
    assert lock.exists(), (
        "Falta electron/package-lock.json. Sin lock el instalador no es "
        "reproducible: dos builds pueden traer dependencias distintas.")
    datos = json.loads(lock.read_text(encoding="utf-8"))
    assert datos.get("lockfileVersion", 0) >= 2

    # Que el lock hable del mismo Electron que package.json.
    declarado = _paquete()["devDependencies"]["electron"]
    nodo = datos["packages"].get("node_modules/electron", {})
    fijado = nodo.get("version", "")
    assert fijado, "el lock no fija ninguna versión de electron"
    assert fijado.split(".")[0] == re.search(r"(\d+)", declarado).group(1), (
        f"package.json pide electron {declarado} pero el lock fija {fijado}. "
        "Corré `npm install` dentro de electron/ y commiteá el lock.")


def test_el_lock_esta_versionado():
    """Un lock que no se commitea no sirve para nada."""
    ignorados = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    for linea in ignorados.splitlines():
        limpia = linea.strip()
        if limpia and not limpia.startswith("#"):
            assert "package-lock" not in limpia, (
                f".gitignore ignora los locks ({limpia!r}) — el de electron/ "
                "tiene que viajar en el repo.")


def _nodes_de(flujo: str) -> list[int]:
    texto = (FLUJOS / flujo).read_text(encoding="utf-8")
    return [int(v) for v in re.findall(r'node-version:\s*"(\d+)', texto)]


def test_el_ci_usa_un_node_que_electron_acepta():
    """El que casi se publica roto: Electron 43 no arranca con Node 20."""
    for flujo in ("build_windows.yml", "owner.yml", "ci.yml"):
        for version in _nodes_de(flujo):
            assert version >= NODE_MINIMO, (
                f"{flujo} usa Node {version}; Electron "
                f"{_paquete()['devDependencies']['electron']} exige >= "
                f"{NODE_MINIMO}. El `npm ci` de electron/ falla y no se arma "
                "el instalador.")


def test_los_workflows_que_arman_el_instalador_usan_npm_ci():
    """`npm install` puede resolver un árbol distinto en cada corrida."""
    for flujo in ("build_windows.yml", "owner.yml"):
        texto = (FLUJOS / flujo).read_text(encoding="utf-8")
        bloque = texto.split("cd electron", 1)[1][:600]
        assert "npm ci" in bloque, f"{flujo}: el paso de electron/ no usa npm ci"
        assert not re.search(r"^\s*npm install\s*$", bloque, re.M), (
            f"{flujo}: quedó un `npm install` en el paso de electron/")


def test_el_humo_de_electron_esta_en_el_repo_y_en_el_ci():
    humo = RAIZ / "packaging" / "humo_electron.js"
    assert humo.exists(), "falta packaging/humo_electron.js"
    fuente = humo.read_text(encoding="utf-8")
    # Lo que el humo tiene que seguir comprobando aunque alguien lo edite.
    for clave in ("nodeExpuesto", "contextIsolation", "ico-svg", "nav-item"):
        assert clave in fuente, f"el humo de Electron perdió la comprobación de {clave}"

    ci = (FLUJOS / "ci.yml").read_text(encoding="utf-8")
    assert "humo_electron.js" in ci, "el humo de Electron no corre en el CI"
    assert "xvfb-run" in ci, "sin xvfb no hay ventana que abrir en el runner"


def test_la_ventana_sigue_sin_darle_node_al_render():
    """contextIsolation y nodeIntegration son la diferencia entre una ventana y
    un intérprete con acceso al disco del usuario. No se tocan."""
    main = (ELECTRON / "main.js").read_text(encoding="utf-8")
    assert "contextIsolation: true" in main
    assert "nodeIntegration: false" in main
    assert "setWindowOpenHandler" in main, "se perdió el filtro de enlaces externos"
    assert "setPermissionRequestHandler" in main, "se perdió el bloqueo de permisos"
