"""Configuración común de la suite."""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def datos_aislados(tmp_path, monkeypatch):
    """
    Cada test escribe en su propio directorio temporal. Sin esto, la suite
    ensucia `datos/corridas/` del repo y los tests se ven entre sí (el
    listado de corridas de uno aparece en el del siguiente).
    """
    monkeypatch.setenv("MVCLIENTE_DIR_DATOS", str(tmp_path / "datos"))
    # La contraseña se hereda del entorno del desarrollador si está puesta y
    # haría fallar los tests de la API con 401.
    monkeypatch.delenv("MVCLIENTE_PASSWORD", raising=False)
    yield


@pytest.fixture
def corrida_kobra():
    """Corrida determinista sobre el caso real del proyecto: MV Kobra AI."""
    from cliente_ia import pipeline
    return pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                             limite_prospectos=60, nombre="MV Kobra AI")


os.environ.setdefault("PYTHONHASHSEED", "0")
