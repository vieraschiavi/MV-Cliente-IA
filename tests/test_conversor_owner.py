"""
El conversor a edición dueño y su armador.

Es la metodología de MV Agendate IA (`INSTALADOR/OWNER/`), con dos cambios:
el conversor BUSCA la instalación en vez de exigir que lo copien adentro, y
pide un código de dueño porque este repositorio es público y el archivo, sin
candado, sería la versión completa publicada.

Lo que se puede probar desde Linux es el ARMADO y la forma del `.bat`. Que
la búsqueda encuentre de verdad una instalación de Windows lo prueba
`packaging/humo_conversor.py` en la Windows del CI.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "packaging"))

import armar_owner  # noqa: E402

PLANTILLA = RAIZ / "packaging" / "bat" / "Convertir-a-edicion-dueno.bat"


def test_la_plantilla_no_lleva_ningun_codigo_horneado():
    """La plantilla SÍ se versiona (es código del producto); lo que no puede
    llevar es un código de dueño real. Sin armar, no convierte nada."""
    texto = PLANTILLA.read_text(encoding="utf-8")
    assert armar_owner.MARCADOR in texto
    # Un SHA-256 suelto en la plantilla sería un código ya horneado.
    sueltos = re.findall(r"\b[0-9a-f]{64}\b", texto)
    assert not sueltos, f"la plantilla trae hashes horneados: {sueltos}"


def test_armar_hornea_el_hash_y_no_el_codigo(tmp_path):
    codigo = "un-codigo-de-dueno-largo-2026"
    destino, _ = armar_owner.armar(codigo, tmp_path / "OWNER")
    guion = (destino / PLANTILLA.name).read_text(encoding="ascii")

    esperado = hashlib.sha256(codigo.encode()).hexdigest()
    assert esperado in guion
    # El código en claro NUNCA puede quedar adentro: el .bat se guarda, se
    # copia a un pendrive y se manda por chat.
    assert codigo not in guion
    assert armar_owner.MARCADOR not in guion


def test_un_codigo_corto_no_se_acepta(tmp_path):
    """El hash queda dentro del .bat: si el archivo se filtra, se puede
    probar contra él sin límite de intentos y sin conexión. Un código de
    cuatro letras se rompe con un diccionario en minutos."""
    with pytest.raises(ValueError, match="12"):
        armar_owner.armar("corto", tmp_path / "OWNER")


def test_el_bat_armado_va_con_crlf_y_en_ascii(tmp_path):
    """Un .bat con finales de línea de Unix falla en Windows con errores que
    no dicen nada, y la consola escribe en cp1252, no en UTF-8."""
    destino, _ = armar_owner.armar("un-codigo-de-dueno-largo", tmp_path / "OWNER")
    crudo = (destino / PLANTILLA.name).read_bytes()
    assert b"\r\n" in crudo
    assert not re.search(rb"(?<!\r)\n", crudo), "hay saltos sin CR"
    crudo.decode("ascii")                      # revienta si no es ASCII puro

    leeme = (destino / "LEEME.txt").read_bytes()
    assert b"\r\n" in leeme
    leeme.decode("ascii")


def test_el_leeme_avisa_que_es_la_llave_maestra(tmp_path):
    destino, _ = armar_owner.armar("un-codigo-de-dueno-largo", tmp_path / "OWNER")
    leeme = (destino / "LEEME.txt").read_text(encoding="ascii").lower()
    assert "no se publica" in leeme
    assert "no se versiona" in leeme


def test_el_conversor_cubre_las_tres_formas_de_entrega():
    """Instalador y portable dejan el sello en `resources\\backend`; la
    edición BAT, en `packaging`. Si el conversor mirara una sola, serviría
    para un empaquetado y no para los otros dos."""
    texto = PLANTILLA.read_text(encoding="utf-8")
    assert "resources\\backend" in texto
    assert "'packaging'" in texto


def test_el_conversor_busca_por_registro_accesos_y_rutas():
    """El corazón del pedido: que ENCUENTRE la instalación en vez de exigir
    que lo copien adentro. El instalador deja elegir la carpeta
    (allowToChangeInstallationDirectory), así que una ruta fija no alcanza."""
    texto = PLANTILLA.read_text(encoding="utf-8")
    assert "CurrentVersion\\Uninstall" in texto      # registro
    assert "LOCALAPPDATA" in texto                   # carpeta por defecto
    assert "ProgramFiles" in texto
    assert "CreateShortcut" in texto                 # accesos directos
    assert "GetFolderPath('Desktop')" in texto


def test_el_conversor_deja_volver_atras():
    """Igual que el de Agendate: guarda `.original` y corriéndolo de nuevo
    ofrece revertir. Sin eso, probar la edición dueño sería irreversible."""
    texto = PLANTILLA.read_text(encoding="utf-8")
    assert ".original" in texto
    assert ":ya_esta" in texto


def test_la_carpeta_owner_no_se_versiona():
    """El .bat armado ES la versión completa del producto: en un repositorio
    público no puede estar. Se arma en la máquina del dueño."""
    ignore = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    assert "INSTALADOR/OWNER" in ignore
