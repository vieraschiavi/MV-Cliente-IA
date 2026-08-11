"""
Tests de la edición BAT — la que se abre sin ningún `.exe`.

Buena parte de esto no se puede probar corriendo el `.bat`: la suite corre en
Linux y `cmd.exe` no existe. Lo que sí se puede es leerlos y comprobar las
cosas que en batch fallan en silencio y sólo se descubren en la máquina del
cliente: un `goto` a una etiqueta que no existe, un acento que la consola
rompe, finales de línea de Unix, o un archivo que el `.bat` invoca y que el
ZIP no trae.

La verificación de que el `.bat` de verdad arranca el programa la hace el CI
en una máquina Windows (ver .github/workflows/build_windows.yml).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cliente_ia import __version__  # noqa: E402

sys.path.insert(0, str(RAIZ / "packaging"))
import lanzador_escritorio as lanzador  # noqa: E402

BATS = RAIZ / "packaging" / "bat"
NOMBRES = ["MVClienteIA.bat", "Instalar.bat", "Desinstalar.bat"]

# Descargar.cmd es de la misma familia y se rompe igual, así que va al mismo
# control de etiquetas. Vive en otra carpeta, de ahí la ruta completa.
GUIONES = [BATS / n for n in NOMBRES] + [RAIZ / "INSTALADOR" / "Descargar.cmd"]


# ---------------------------------------------------------------------------
# Los .bat como texto
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nombre", NOMBRES)
def test_bat_es_ascii_puro(nombre):
    """Un acento en un .bat sale ilegible: la consola de Windows los
    interpreta con la página de códigos activa, que no es UTF-8."""
    crudo = (BATS / nombre).read_bytes()
    try:
        crudo.decode("ascii")
    except UnicodeDecodeError as e:
        linea = crudo[:e.start].count(b"\n") + 1
        contexto = crudo[max(0, e.start - 40):e.start + 20].decode("utf-8", "replace")
        pytest.fail(f"{nombre} tiene un carácter no ASCII en la línea {linea}: "
                    f"...{contexto}...")


@pytest.mark.parametrize("guion", GUIONES, ids=lambda g: g.name)
def test_todo_goto_tiene_etiqueta(guion):
    """En batch un `goto :que_no_existe` no avisa nada al escribirlo: recién
    en la máquina del cliente el script se muere con "no se encuentra la
    etiqueta". Es exactamente el bug que no se puede ver desde Linux."""
    nombre = guion.name
    texto = guion.read_text(encoding="utf-8")
    etiquetas = {m.group(1).lower()
                 for m in re.finditer(r"^\s*:([a-zA-Z_][\w]*)", texto, re.M)}
    etiquetas.add("eof")                       # :eof lo define el propio cmd
    destinos = {m.group(1).lower()
                for m in re.finditer(r"(?:goto|call)\s+:([a-zA-Z_][\w]*)", texto)}
    faltan = destinos - etiquetas
    assert not faltan, f"{nombre} salta a etiquetas que no existen: {sorted(faltan)}"


@pytest.mark.parametrize("nombre", NOMBRES)
def test_bat_no_deja_marcadores_sin_reemplazar(nombre):
    """@VERSION@ y @EDICION@ los reemplaza el armador. Si aparece alguno más
    en el original y el armador no lo conoce, viajaría literal al cliente."""
    texto = (BATS / nombre).read_text(encoding="utf-8")
    marcadores = set(re.findall(r"@([A-Z_]+)@", texto))
    assert marcadores <= {"VERSION", "EDICION"}, \
        f"{nombre} usa marcadores que el armador no reemplaza: {marcadores}"


def test_el_lanzador_que_invoca_el_bat_existe():
    """El .bat llama a un archivo por ruta; si se renombra, el programa no
    abre y el error recién se ve al hacer doble click."""
    texto = (BATS / "MVClienteIA.bat").read_text(encoding="utf-8")
    m = re.search(r'"(packaging\\[\w_]+\.py)"', texto)
    assert m, "MVClienteIA.bat ya no invoca ningún script de packaging/"
    assert (RAIZ / m.group(1).replace("\\", "/")).exists(), \
        f"MVClienteIA.bat invoca {m.group(1)}, que no existe en el repo"


@pytest.mark.parametrize(
    "guion", sorted((RAIZ / "packaging").glob("*.py")), ids=lambda g: g.name)
def test_los_scripts_de_windows_no_usan_caracteres_que_la_consola_no_sabe(guion):
    """La consola de Windows escribe en cp1252, no en UTF-8. Un carácter
    fuera de esa página —un `✓` en un print, por ejemplo— revienta con
    UnicodeEncodeError y se lleva puesto el paso entero del CI.

    Ya pasó: un `✓` decorativo en `armar_bat.py` tumbó el armado del ZIP.
    Los acentos y la mayoría de los signos del español sí entran en cp1252;
    lo que no entra son los adornos tipográficos."""
    problemas = {}
    for i, linea in enumerate(guion.read_text(encoding="utf-8").splitlines(), 1):
        for c in linea:
            try:
                c.encode("cp1252")
            except UnicodeEncodeError:
                problemas.setdefault(f"{c!r} (U+{ord(c):04X})", []).append(i)
    assert not problemas, (
        f"{guion.name} usa caracteres que la consola de Windows no sabe "
        f"escribir: {problemas}")


@pytest.mark.parametrize("nombre", NOMBRES)
def test_ninguna_pausa_queda_sin_escape(nombre):
    """Un `pause` suelto cuelga la verificación de Windows PARA SIEMPRE en vez
    de fallar: el job se queda en "Presione una tecla" hasta que expira a los
    360 minutos, y encima el build sale en verde. Todos tienen que pasar por
    :pausa, que se saltea cuando está MVCLIENTE_SIN_PAUSA."""
    lineas = (BATS / nombre).read_text(encoding="utf-8").splitlines()
    for i, linea in enumerate(lineas):
        if re.match(r"^\s*pause\s*$", linea):
            previas = " ".join(lineas[max(0, i - 3):i])
            assert "MVCLIENTE_SIN_PAUSA" in previas, \
                f"{nombre}:{i + 1} tiene un `pause` sin el escape del CI"


@pytest.mark.parametrize("nombre", NOMBRES)
def test_ninguna_pregunta_queda_sin_escape(nombre):
    """Lo mismo con `set /p`: sin escape se queda esperando una respuesta que
    en el CI no va a llegar nunca."""
    for i, linea in enumerate((BATS / nombre).read_text(encoding="utf-8").splitlines()):
        if "set /p" in linea:
            assert "if not defined MVCLIENTE_SIN_PAUSA" in linea, \
                f"{nombre}:{i + 1} pregunta sin el escape del CI: {linea.strip()}"


# ---------------------------------------------------------------------------
# El ZIP armado
# ---------------------------------------------------------------------------
def _frontend_de_prueba(tmp_path: Path) -> Path:
    """Un build de React mínimo, para no depender de que alguien haya corrido
    npm. El portón de CI es sólo Python: ahí `webapp/frontend/dist` no existe,
    y estos tests son sobre el EMPAQUETADO, no sobre el frontend. Que el build
    real entre y se sirva lo comprueba `packaging/humo.py` contra un motor
    vivo, en Linux y en la Windows del CI."""
    dist = tmp_path / "dist-falso"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!DOCTYPE html><html><body><div id="root"></div>'
        '<script src="./assets/index-000.js"></script></body></html>',
        encoding="utf-8")
    (dist / "assets" / "index-000.js").write_text("// prueba", encoding="utf-8")
    return dist


def _armar(tmp_path: Path, edicion: str) -> Path:
    r = subprocess.run(
        [sys.executable, str(RAIZ / "packaging" / "armar_bat.py"),
         "--edicion", edicion, "--salida", str(tmp_path),
         "--frontend", str(_frontend_de_prueba(tmp_path))],
        capture_output=True, text=True)
    assert r.returncode == 0, f"armar_bat falló:\n{r.stdout}\n{r.stderr}"
    return tmp_path / f"MVClienteIA_BAT_{edicion}.zip"


def test_se_niega_a_armar_sin_el_build_de_react(tmp_path):
    """Un ZIP sin el build levanta el motor y sirve un 404 en blanco: el
    usuario ve una pestaña rota y cree que el programa no anda. Tiene que
    fallar al armarlo, no al abrirlo."""
    r = subprocess.run(
        [sys.executable, str(RAIZ / "packaging" / "armar_bat.py"),
         "--edicion", "demo", "--salida", str(tmp_path),
         "--frontend", str(tmp_path / "no-existe")],
        capture_output=True, text=True)
    assert r.returncode != 0, "armó el ZIP sin el build de React"
    assert "build de React" in (r.stdout + r.stderr)
    assert not list(tmp_path.glob("*.zip")), "dejó un ZIP a medio armar"


@pytest.mark.parametrize("edicion", ["demo", "cliente", "owner"])
def test_el_zip_trae_todo_lo_que_el_programa_necesita(tmp_path, edicion):
    with zipfile.ZipFile(_armar(tmp_path, edicion)) as z:
        dentro = set(z.namelist())
        for obligatorio in [
            "MVClienteIA/MVClienteIA.bat",
            "MVClienteIA/Instalar.bat",
            "MVClienteIA/Desinstalar.bat",
            "MVClienteIA/LEEME.txt",
            "MVClienteIA/requirements.txt",
            "MVClienteIA/packaging/lanzador_escritorio.py",
            "MVClienteIA/packaging/edicion.json",
            "MVClienteIA/cliente_ia/pipeline.py",
            # La semilla del catálogo de mercado: sin esto el proveedor demo
            # no arranca y la corrida muere en la fase 1.
            "MVClienteIA/cliente_ia/datos/mercado.json",
            "MVClienteIA/webapp/backend/api.py",
            # El build de React. Si falta, el motor levanta y sirve un 404 en
            # blanco: el usuario ve una pestaña rota y cree que no anda.
            "MVClienteIA/webapp/frontend/dist/index.html",
        ]:
            assert obligatorio in dentro, f"al ZIP de {edicion} le falta {obligatorio}"

        assert not [n for n in dentro if "__pycache__" in n], \
            "el ZIP se llevó __pycache__"

        sello = json.loads(z.read("MVClienteIA/packaging/edicion.json"))
        assert sello == {"edicion": edicion}


@pytest.mark.parametrize("edicion", ["demo", "cliente"])
def test_los_bat_del_zip_van_con_crlf_y_la_version_puesta(tmp_path, edicion):
    with zipfile.ZipFile(_armar(tmp_path, edicion)) as z:
        for nombre in NOMBRES:
            crudo = z.read(f"MVClienteIA/{nombre}")
            assert b"\r\n" in crudo, f"{nombre} quedó con finales de línea de Unix"
            assert b"\n" not in crudo.replace(b"\r\n", b""), \
                f"{nombre} mezcla finales de línea"
            assert b"@VERSION@" not in crudo and b"@EDICION@" not in crudo
        texto = z.read("MVClienteIA/Instalar.bat").decode("ascii")
        assert __version__ in texto
        assert f"set \"EDICION={edicion}\"" in texto


# ---------------------------------------------------------------------------
# El lanzador
# ---------------------------------------------------------------------------
def test_puerto_libre_devuelve_uno_usable():
    import socket

    p = lanzador.puerto_libre("127.0.0.1", lanzador.PUERTO_DEFAULT)
    assert 1 <= p <= 65535
    with socket.socket() as s:
        s.bind(("127.0.0.1", p))               # tiene que poder tomarse


def test_puerto_libre_esquiva_uno_ocupado():
    """Si el 8810 ya lo usa otra aplicación hay que correrse, no morir con
    "address already in use" delante del cliente."""
    import socket

    with socket.socket() as ocupado:
        ocupado.bind(("127.0.0.1", 0))
        ocupado.listen(1)
        tomado = ocupado.getsockname()[1]
        assert lanzador.puerto_libre("127.0.0.1", tomado) != tomado


def test_la_version_minima_de_python_es_la_que_el_codigo_necesita():
    """3.11 sale de `datetime.UTC`, que se usa en licencia.py y pipeline.py.
    Si alguien baja el mínimo, el programa arranca y muere con ImportError."""
    assert lanzador.VERSION_MINIMA == (3, 11)
    assert not lanzador.version_soportada((3, 10))
    assert lanzador.version_soportada((3, 11))
    assert lanzador.version_soportada((3, 13))
    assert "3.11" in lanzador.texto_version_vieja((3, 10))


def test_el_bat_exige_la_misma_version_que_el_lanzador():
    """El .bat filtra intérpretes por su cuenta. Si ese número se desincroniza
    del de Python, el .bat acepta uno con el que el programa no arranca."""
    texto = (BATS / "MVClienteIA.bat").read_text(encoding="utf-8")
    m = re.search(r"version_info\[:2\]>=\((\d+),\s*(\d+)\)", texto)
    assert m, "MVClienteIA.bat ya no comprueba la versión de Python"
    assert (int(m.group(1)), int(m.group(2))) == lanzador.VERSION_MINIMA


def test_esperar_motor_se_rinde_si_no_hay_nadie():
    """Sin esto el navegador se abriría contra un puerto muerto."""
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        libre = s.getsockname()[1]
    assert not lanzador.esperar_motor(f"http://127.0.0.1:{libre}", espera=1.0)


def test_el_zip_no_lleva_el_secreto_de_licencias(tmp_path):
    """El secreto de firma vive en la máquina del dueño y en el servidor.
    Adentro de una descarga sería regalar la fábrica de claves."""
    with zipfile.ZipFile(_armar(tmp_path, "cliente")) as z:
        for nombre in z.namelist():
            if nombre.endswith((".py", ".txt", ".json", ".bat")):
                crudo = z.read(nombre).decode("utf-8", "replace")
                assert "MVCLIENTE_LICENCIA_SECRETO=" not in crudo, \
                    f"{nombre} lleva el secreto de licencias escrito"
