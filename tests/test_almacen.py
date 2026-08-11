"""
Persistencia de corridas, con foco en la carrera lector/escritor de Windows.

El bug lo encontró el CI de Windows: el backend guarda el avance después de
cada fase mientras el frontend hace polling, y en Windows abrir un archivo
que se está renombrando lanza PermissionError (Errno 13). En POSIX no pasa
—el rename es atómico—, así que hay que SIMULAR la ventana para probar el
reintento desde Linux.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cliente_ia import almacen  # noqa: E402
from cliente_ia.modelos import Corrida  # noqa: E402


def _corrida(cid="abc123"):
    return Corrida(id=cid, dominio="mvkobranzaia.com", estado="corriendo")


def test_guarda_y_carga_ida_y_vuelta(tmp_path, monkeypatch):
    monkeypatch.setenv("MVCLIENTE_DIR_DATOS", str(tmp_path))
    almacen.guardar(_corrida())
    c = almacen.cargar("abc123")
    assert c and c.id == "abc123" and c.dominio == "mvkobranzaia.com"


def test_cargar_reintenta_ante_permissionerror(tmp_path, monkeypatch):
    """Simula la ventana de Windows: el primer open falla con
    PermissionError (como cuando el archivo se está renombrando) y el
    segundo funciona. `cargar` no debe rendirse al primer intento."""
    monkeypatch.setenv("MVCLIENTE_DIR_DATOS", str(tmp_path))
    almacen.guardar(_corrida())

    real_open = open
    fallos = {"quedan": 2}

    def open_que_falla(*args, **kwargs):
        if "abc123.json" in str(args[0]) and fallos["quedan"] > 0:
            fallos["quedan"] -= 1
            raise PermissionError(13, "simulado: renombrándose")
        return real_open(*args, **kwargs)

    monkeypatch.setattr("builtins.open", open_que_falla)
    monkeypatch.setattr(almacen, "_ESPERA", 0.001)      # que el test no espere
    c = almacen.cargar("abc123")
    assert c and c.id == "abc123"
    assert fallos["quedan"] == 0                         # de verdad reintentó


def test_cargar_se_rinde_si_el_bloqueo_no_cede(tmp_path, monkeypatch):
    """Si NUNCA se puede abrir, el error tiene que propagarse — un bloqueo
    eterno es un problema real, no algo para tragarse en silencio."""
    monkeypatch.setenv("MVCLIENTE_DIR_DATOS", str(tmp_path))
    almacen.guardar(_corrida())

    def open_siempre_falla(*args, **kwargs):
        if "abc123.json" in str(args[0]):
            raise PermissionError(13, "bloqueado para siempre")
        return open(*args, **kwargs)

    monkeypatch.setattr("builtins.open", open_siempre_falla)
    monkeypatch.setattr(almacen, "_ESPERA", 0.001)
    with pytest.raises(PermissionError):
        almacen.cargar("abc123")


def test_guardar_no_deja_tmp_tirado(tmp_path, monkeypatch):
    """El .tmp por-pid no puede quedar en la carpeta: ensuciaría el listado
    y, si el glob lo tomara, rompería el parseo."""
    monkeypatch.setenv("MVCLIENTE_DIR_DATOS", str(tmp_path))
    almacen.guardar(_corrida())
    restos = list((tmp_path / "corridas").glob("*.tmp"))
    assert not restos, f"quedaron temporales: {restos}"


def test_guardar_y_cargar_concurrente_no_se_rompe(tmp_path, monkeypatch):
    """La prueba de estrés del caso real: un hilo guarda en loop mientras
    otro carga en loop, como backend + polling. No debe saltar ninguna
    excepción ni leerse una corrida a medias."""
    monkeypatch.setenv("MVCLIENTE_DIR_DATOS", str(tmp_path))
    almacen.guardar(_corrida("carrera"))
    errores: list[Exception] = []
    parar = threading.Event()

    def escribir():
        i = 0
        while not parar.is_set():
            c = _corrida("carrera")
            c.estado = f"fase-{i}"
            try:
                almacen.guardar(c)
            except Exception as e:                      # noqa: BLE001
                errores.append(e)
            i += 1

    def leer():
        while not parar.is_set():
            try:
                c = almacen.cargar("carrera")
                assert c is None or c.id == "carrera"
            except Exception as e:                      # noqa: BLE001
                errores.append(e)

    hilos = [threading.Thread(target=escribir) for _ in range(2)]
    hilos += [threading.Thread(target=leer) for _ in range(3)]
    for h in hilos:
        h.start()
    time.sleep(1.5)
    parar.set()
    for h in hilos:
        h.join(timeout=5)
    assert not errores, f"la concurrencia rompió algo: {errores[:3]}"
