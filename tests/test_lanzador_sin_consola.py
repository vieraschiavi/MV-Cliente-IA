"""
Que el motor arranque aunque no haya consola.

Esto existe por un bug que llegó a estar publicado: el ejecutable de PC se
compila con `console=False`, y PyInstaller en modo ventana deja `sys.stdout`
y `sys.stderr` en None cuando nadie le dio una consola ni una tubería. uvicorn
arma su logging con `sys.stdout.isatty()`, así que moría con AttributeError
ANTES de escuchar: el programa abría, no servía nada y se cerraba sin decir
por qué.

No se veía porque el único camino que alguien probaba era el de Electron, que
lo lanza con tuberías y ahí los streams existen. Se descubrió al hacer que el
CI corriera el .exe por su cuenta.

Los dos lanzadores se prueban en un proceso aparte: hay que romper `sys.stdout`
de verdad para reproducirlo, y hacerlo dentro de pytest se lleva puesto al
propio pytest.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

# Cada lanzador arma su logging por su cuenta, así que cada uno tiene que
# sobrevivir por su cuenta: `lanzador.py` es el que empaqueta PyInstaller y
# `lanzador_escritorio.py` el de la edición BAT, que no lo puede importar
# porque no viaja en su ZIP.
LANZADORES = ["lanzador", "lanzador_escritorio"]

GUION = """
import sys, os
sys.path.insert(0, {raiz!r})
sys.path.insert(0, os.path.join({raiz!r}, "packaging"))

# Exactamente lo que deja PyInstaller --windowed cuando no hay consola.
sys.stdout = None
sys.stderr = None

from {modulo} import asegurar_salidas
asegurar_salidas()

# Lo que reventaba: uvicorn.Config configura el logging en su __init__.
import uvicorn
from webapp.backend.api import app
uvicorn.Config(app, host="127.0.0.1", port=0, log_level="info")

# Y que se pueda escribir sin romper nada (el motor imprime su banner).
print("con el arreglo, esto no revienta")
os._exit(0)
"""


@pytest.mark.parametrize("modulo", LANZADORES)
def test_el_motor_arranca_sin_consola(modulo, tmp_path):
    r = subprocess.run(
        [sys.executable, "-c", GUION.format(raiz=str(RAIZ), modulo=modulo)],
        capture_output=True, text=True,
        env={**dict(__import__("os").environ),
             "MVCLIENTE_DIR_DATOS": str(tmp_path)})
    assert r.returncode == 0, (
        f"{modulo} no sobrevive sin consola — es el bug que dejaba el "
        f"programa abriendo y cerrándose sin explicación:\n{r.stderr[-2000:]}")


@pytest.mark.parametrize("modulo", LANZADORES)
def test_sin_el_arreglo_el_motor_moriria(modulo, tmp_path):
    """El contrario, para que el test de arriba no quede pasando por casualidad
    el día que uvicorn deje de mirar `sys.stdout`. Si esto empieza a fallar,
    el arreglo dejó de hacer falta y se puede sacar."""
    sin_arreglo = GUION.format(raiz=str(RAIZ), modulo=modulo).replace(
        "asegurar_salidas()", "pass")
    r = subprocess.run(
        [sys.executable, "-c", sin_arreglo], capture_output=True, text=True,
        env={**dict(__import__("os").environ),
             "MVCLIENTE_DIR_DATOS": str(tmp_path)})
    assert r.returncode != 0, (
        "uvicorn ya no necesita sys.stdout: `asegurar_salidas` quedó de más "
        "y este test se puede borrar junto con ella")
