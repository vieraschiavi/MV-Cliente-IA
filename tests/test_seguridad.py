"""
Los agujeros que encontró la auditoría de seguridad, cada uno con su prueba.

No son tests de "buenas prácticas": cada uno reproduce un ataque que ANTES
funcionaba. Si alguno se pone rojo, es que volvió a abrirse esa puerta.
"""
from __future__ import annotations

import http.server
import socketserver
import threading

import pytest

from cliente_ia import exportar
from cliente_ia.modelos import Corrida, Decisor, Prospecto
from cliente_ia.proveedores.web import ErrorWeb, _revisar_destino, bajar

# ---------------------------------------------------------------------------
# Inyección de fórmulas en el export
# ---------------------------------------------------------------------------
# El texto de las celdas NO lo escribe quien descarga: sale del <title> y los
# <h1> de sitios ajenos y del JSON del modelo. Excel ejecuta la celda si
# arranca con "=", "+", "-" o "@", y este export existe para abrirse en el
# CRM del cliente — o sea que el ataque llega a su máquina por el camino
# normal del producto.
VENENOS = ["=cmd|'/c calc.exe'!A0", "+SUM(1)", "-2+3+cmd|'/c calc'!A0",
           "@SUM(1+1)*cmd|'/c calc'!A0", "=HYPERLINK(\"http://evil\",\"click\")"]


def _corrida_con(texto: str) -> Corrida:
    c = Corrida(id="seg001", dominio="ejemplo.com", estado="listo")
    c.prospectos = [Prospecto(id="p1", nombre=texto, dominio="a.com",
                              sector=texto, pais="UY", nivel="local",
                              prioridad=1, senales=[texto], campana_id="c1")]
    c.decisores = [Decisor(id="d1", prospecto_id="p1", empresa=texto, pais="UY",
                           nombre=texto, cargo=texto, email="x@a.com",
                           score=9.1, idioma="es")]
    return c


@pytest.mark.parametrize("veneno", VENENOS)
def test_el_csv_no_deja_una_formula_viva(veneno):
    csv_texto = exportar.a_csv(_corrida_con(veneno))
    for linea in csv_texto.splitlines()[1:]:
        for celda in linea.split(","):
            limpia = celda.strip('"')
            assert not limpia.startswith(("=", "+", "@")), celda
            # Un "-" seguido de dígito es un número negativo legítimo; lo que
            # no puede quedar es un "-" abriendo una expresión.
            assert not (limpia.startswith("-") and not limpia[1:2].isdigit()), celda


@pytest.mark.parametrize("veneno", VENENOS)
def test_el_xlsx_no_deja_una_formula_viva(veneno, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    destino = tmp_path / "x.xlsx"
    exportar.guardar_xlsx(_corrida_con(veneno), destino)
    libro = openpyxl.load_workbook(destino)
    for hoja in libro.worksheets:
        for fila in hoja.iter_rows():
            for celda in fila:
                # `data_type == "f"` es openpyxl diciendo «Excel va a evaluar
                # esto». Es exactamente lo que no puede pasar.
                assert celda.data_type != "f", f"{hoja.title}!{celda.coordinate}"


def test_el_export_directo_no_escribe_fuera_de_su_carpeta():
    """`POST /api/exportar/xlsx` reconstruye la corrida desde el cuerpo del
    pedido, así que el id llega de afuera: con "../../.." el archivo se
    escribía en cualquier ruta a la que llegara el proceso."""
    for id_malo in ["../../../pwned", "..\\..\\pwned", "a/b", "con espacio",
                    "", "x" * 65]:
        malo = Corrida(id=id_malo, dominio="", estado="listo")
        with pytest.raises(ValueError):
            exportar.guardar_xlsx(malo)
        with pytest.raises(ValueError):
            exportar.guardar_csv(malo)


# ---------------------------------------------------------------------------
# SSRF en el proveedor web
# ---------------------------------------------------------------------------
# El dominio lo elige quien usa el programa y el motor lo va a buscar DESDE EL
# SERVIDOR. Sin filtro, pedir la metadata de la nube devolvía sus credenciales
# adentro de `empresa.resumen_sitio`: no era un SSRF ciego, el texto volvía a
# la pantalla.
INTERNOS = [
    "http://127.0.0.1/", "https://127.0.0.1/", "http://localhost/",
    "http://[::1]/", "http://0.0.0.0/",
    "http://169.254.169.254/latest/meta-data/",      # AWS/Azure/GCP
    "http://192.168.1.1/", "http://10.0.0.1/", "http://172.16.0.1/",
]


@pytest.mark.parametrize("url", INTERNOS)
def test_no_se_puede_apuntar_el_motor_a_la_red_interna(url):
    with pytest.raises(ErrorWeb):
        _revisar_destino(url)


@pytest.mark.parametrize("url", [
    "http://http://127.0.0.1/",       # doble esquema: salteaba el forzado a https
    "file:///etc/passwd",
    "gopher://127.0.0.1:70/",
    "ftp://127.0.0.1/",
])
def test_los_esquemas_raros_y_el_doble_esquema_no_pasan(url):
    with pytest.raises(ErrorWeb):
        bajar(url, timeout=3)


def test_un_puerto_que_no_es_de_web_no_pasa():
    """Pedir puertos sueltos contra un host es escanear la red del servidor."""
    for url in ["http://ejemplo.com:22/", "http://ejemplo.com:6379/",
                "http://ejemplo.com:8810/"]:
        with pytest.raises(ErrorWeb):
            _revisar_destino(url)


def test_un_servicio_interno_de_verdad_no_se_puede_leer():
    """El PoC completo: se levanta un servicio interno con un secreto y se
    intenta llegar a él por el mismo camino que usa la fase 1."""
    class Mano(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<title>SECRETO_INTERNO=no-deberias-ver-esto</title>")

        def log_message(self, *a):
            pass

    servidor = socketserver.TCPServer(("127.0.0.1", 0), Mano)
    puerto = servidor.server_address[1]
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        for url in (f"http://127.0.0.1:{puerto}/",
                    f"http://localhost:{puerto}/",
                    f"http://http://127.0.0.1:{puerto}/"):
            with pytest.raises(ErrorWeb):
                bajar(url, timeout=3)
    finally:
        servidor.shutdown()
        servidor.server_close()
