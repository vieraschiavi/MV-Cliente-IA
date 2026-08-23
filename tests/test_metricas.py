"""
El backend de métricas de envíos y conversión.

Lo que Explee no da: cruzar envíos con conversiones y decir a qué segmento,
día y hora le fue mejor. Cada test fija los timestamps a mano para que la
agregación sea determinista.
"""
from __future__ import annotations

import json

import pytest

from cliente_ia import metricas


@pytest.fixture(autouse=True)
def datos_limpios(tmp_path, monkeypatch):
    monkeypatch.setenv("MVCLIENTE_DIR_DATOS", str(tmp_path))
    metricas.borrar_todo()
    yield
    metricas.borrar_todo()


def _envio(programa="mvkobranzaia.com", canal="email", segmento="fintech",
           nivel="local", pais="UY", idioma="es", ts="2026-03-02T10:00:00+00:00", n=1):
    # 2026-03-02 es un lunes 10:00.
    return {"programa": programa, "canal": canal, "segmento": segmento,
            "nivel": nivel, "pais": pais, "idioma": idioma, "ts": ts, "n": n}


def test_registra_y_cuenta_envios():
    assert metricas.registrar_envios([_envio(), _envio(n=3)]) == 2
    r = metricas.resumen()
    assert r["envios"] == 4                     # 1 + 3
    assert r["conversiones"] == 0
    assert r["tasa_conversion"] == 0.0


def test_un_canal_desconocido_no_se_cuenta():
    assert metricas.registrar_envios([_envio(canal="telepatia")]) == 0
    assert metricas.resumen()["envios"] == 0


def test_la_tasa_de_conversion_cruza_los_dos_eventos():
    metricas.registrar_envios([_envio() for _ in range(10)])
    for _ in range(3):
        metricas.registrar_conversion({"programa": "mvkobranzaia.com",
                                       "segmento": "fintech", "canal": "email"})
    r = metricas.resumen()
    assert r["envios"] == 10
    assert r["conversiones"] == 3
    assert r["tasa_conversion"] == 0.3


def test_marca_el_mejor_dia_y_la_mejor_hora():
    """Lunes 10:00 convierte, viernes 18:00 no. Con muestra suficiente en
    cada bucket, el resumen tiene que coronar al lunes 10:00."""
    lunes_10 = "2026-03-02T10:00:00+00:00"
    viernes_18 = "2026-03-06T18:00:00+00:00"
    metricas.registrar_envios([_envio(ts=lunes_10) for _ in range(6)])
    metricas.registrar_envios([_envio(ts=viernes_18, segmento="retail") for _ in range(6)])
    for _ in range(5):
        metricas.registrar_conversion({"programa": "mvkobranzaia.com",
                                       "segmento": "fintech", "canal": "email",
                                       "ts": lunes_10})

    r = metricas.resumen()
    assert r["mejor_dia"]["clave"] == "lunes"
    assert r["mejor_hora"]["clave"] == "10:00"
    assert r["mejor_segmento"]["valor"] == "fintech"


def test_dia_y_hora_son_el_timing_del_click_no_del_envio():
    """El bug que destapó la prueba en vivo: el día en que se MANDA un correo
    y el día en que el destinatario hace CLICK no son el mismo. La tasa por
    segmento sigue siendo válida (envío y conversión comparten segmento), pero
    día/hora tienen que salir del click, no cruzar dos relojes distintos."""
    lunes_10 = "2026-03-02T10:00:00+00:00"       # se manda lunes 10
    martes_15 = "2026-03-03T15:00:00+00:00"      # entran martes 15

    metricas.registrar_envios([_envio(ts=lunes_10, segmento="fintech") for _ in range(20)])
    for _ in range(8):
        metricas.registrar_conversion({"programa": "mvkobranzaia.com",
                                       "segmento": "fintech", "canal": "email",
                                       "ts": martes_15})

    r = metricas.resumen()
    # La tasa por segmento es correcta: 8/20 de fintech.
    assert r["mejor_segmento"]["valor"] == "fintech"
    assert r["mejor_segmento"]["tasa"] == 0.4
    # El pico de conversión es cuando ENTRARON (martes 15), no cuando se mandó.
    assert r["mejor_dia"]["clave"] == "martes"
    assert r["mejor_hora"]["clave"] == "15:00"
    assert r["mejor_dia"]["conversiones"] == 8
    # Y día/hora NO fingen una tasa: son volumen de clicks.
    assert "tasa" not in r["mejor_dia"]


def test_no_corona_un_bucket_sin_muestra():
    """Una conversión sobre un envío es 100% y no dice nada: por debajo del
    mínimo, no se corona a nadie."""
    metricas.registrar_envios([_envio(segmento="nicho-raro")])
    metricas.registrar_conversion({"programa": "mvkobranzaia.com",
                                   "segmento": "nicho-raro", "canal": "email"})
    r = metricas.resumen()
    assert r["mejor_segmento"] is None
    assert r["muestra_suficiente"] is False


def test_cpm_y_cpa_solo_con_costo():
    metricas.registrar_envios([_envio() for _ in range(1000)])
    for _ in range(20):
        metricas.registrar_conversion({"programa": "mvkobranzaia.com", "canal": "email"})

    sin_costo = metricas.resumen()
    assert "cpm" not in sin_costo               # sin plata gastada no hay CPM

    con_costo = metricas.resumen(costo=100.0)
    assert con_costo["cpm"] == 100.0            # 100 / 1000 * 1000
    assert con_costo["cpa"] == 5.0              # 100 / 20


def test_filtra_por_programa():
    metricas.registrar_envios([_envio(programa="uno.com") for _ in range(4)])
    metricas.registrar_envios([_envio(programa="dos.com") for _ in range(6)])
    assert metricas.resumen(programa="uno.com")["envios"] == 4
    assert metricas.resumen(programa="dos.com")["envios"] == 6
    assert metricas.resumen()["envios"] == 10


def test_una_linea_corrupta_no_tumba_el_resumen(tmp_path):
    metricas.registrar_envios([_envio()])
    # Meter basura en el medio del archivo, como si una escritura se cortó.
    with open(tmp_path / metricas.ARCHIVO, "a", encoding="utf-8") as f:
        f.write("{esto no es json\n")
    metricas.registrar_envios([_envio()])
    assert metricas.resumen()["envios"] == 2    # ignora la línea rota


# ---------------------------------------------------------------------------
# El enlace de conversión firmado
# ---------------------------------------------------------------------------
def test_sin_secreto_el_traqueo_esta_apagado(monkeypatch):
    monkeypatch.delenv("MVCLIENTE_TRAQUEO_SECRETO", raising=False)
    assert metricas.hay_traqueo() is False
    assert metricas.verificar_traqueo("cualquier.cosa") is None


def test_el_token_de_conversion_viaja_y_vuelve(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "un-secreto-de-traqueo")
    token = metricas.firmar_traqueo("https://ejemplo.com/pt/",
                                    {"programa": "x.com", "canal": "email",
                                     "segmento": "fintech"})
    cuerpo = metricas.verificar_traqueo(token)
    assert cuerpo["u"] == "https://ejemplo.com/pt/"
    assert cuerpo["segmento"] == "fintech"


def test_un_token_manoseado_no_pasa(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "un-secreto-de-traqueo")
    token = metricas.firmar_traqueo("https://ejemplo.com/", {"canal": "email"})
    datos, _ = token.split(".", 1)
    assert metricas.verificar_traqueo(datos + ".firmafalsa") is None


def test_un_token_de_otro_secreto_no_pasa(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "el-secreto-de-alguien")
    token = metricas.firmar_traqueo("https://ejemplo.com/", {"canal": "email"})
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "otro-secreto-distinto")
    assert metricas.verificar_traqueo(token) is None


# ---------------------------------------------------------------------------
# Los endpoints, de punta a punta
# ---------------------------------------------------------------------------
def _cliente():
    from fastapi.testclient import TestClient

    from webapp.backend import api
    return TestClient(api.app)


def test_el_endpoint_registra_y_el_resumen_los_devuelve():
    cliente = _cliente()
    envios = {"eventos": [
        {"programa": "x.com", "canal": "email", "segmento": "fintech",
         "ts": "2026-03-02T10:00:00+00:00"} for _ in range(6)]}
    r = cliente.post("/api/metricas/envios", json=envios)
    assert r.status_code == 200 and r.json()["registrados"] == 6
    resumen = cliente.get("/api/metricas/resumen").json()
    assert resumen["envios"] == 6


def test_el_redirect_de_conversion_cuenta_el_click_y_rebota(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-redirect")
    cliente = _cliente()
    # Diez envíos para tener muestra, y una conversión vía el redirect.
    cliente.post("/api/metricas/envios", json={"eventos": [
        {"programa": "x.com", "canal": "email", "segmento": "fintech",
         "ts": "2026-03-02T10:00:00+00:00"} for _ in range(10)]})

    token = metricas.firmar_traqueo("https://ejemplo.com/pt/",
                                    {"programa": "x.com", "canal": "email",
                                     "segmento": "fintech"})
    r = cliente.get(f"/api/ir?t={token}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://ejemplo.com/pt/"

    resumen = cliente.get("/api/metricas/resumen?programa=x.com").json()
    assert resumen["conversiones"] == 1
    assert resumen["tasa_conversion"] == 0.1


def test_reproducir_el_mismo_enlace_no_infla_la_conversion(monkeypatch):
    """El hallazgo de la auditoría: sin dedup, un atacante que recibe UN correo
    extrae el token y lo repite N veces, inflando la conversión. El nonce
    único por enlace hace que el mismo click cuente una sola vez."""
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-anti-replay")
    cliente = _cliente()
    cliente.post("/api/metricas/envios", json={"eventos": [
        {"programa": "x.com", "canal": "email", "segmento": "fintech",
         "ts": "2026-03-02T10:00:00+00:00"} for _ in range(10)]})

    token = metricas.firmar_traqueo("https://ejemplo.com/", {"programa": "x.com",
                                    "canal": "email", "segmento": "fintech"})
    # Seis clicks con el MISMO token: seis 302 (el destinatario igual llega a
    # la web) pero UNA sola conversión contada.
    for _ in range(6):
        r = cliente.get(f"/api/ir?t={token}", follow_redirects=False)
        assert r.status_code == 302
    assert cliente.get("/api/metricas/resumen?programa=x.com").json()["conversiones"] == 1


def test_dos_enlaces_distintos_cuentan_dos_conversiones(monkeypatch):
    """Que el dedup no coma conversiones legítimas: dos ENVÍOS distintos (dos
    nonces) tienen que contar dos veces."""
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-anti-replay")
    cliente = _cliente()
    for _ in range(2):
        tok = metricas.firmar_traqueo("https://ejemplo.com/", {"canal": "email"})
        cliente.get(f"/api/ir?t={tok}", follow_redirects=False)
    assert metricas.resumen()["conversiones"] == 2


def test_el_archivo_de_metricas_tiene_techo(monkeypatch):
    """Sin techo, spamear envíos llenaría el disco de la edición instalada y
    `resumen()` releería un archivo cada vez más grande. Al toparlo, se deja
    de agregar en vez de tumbar la máquina."""
    monkeypatch.setattr(metricas, "MAX_BYTES", 2000)     # techo minúsculo para el test
    for _ in range(50):
        metricas.registrar_envios([_envio() for _ in range(20)])
    import os
    assert os.path.getsize(metricas._ruta()) < 2000 + 500   # no crece sin control


def test_el_redirect_rechaza_firma_falsa(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-redirect")
    cliente = _cliente()
    r = cliente.get("/api/ir?t=cualquier.cosa", follow_redirects=False)
    assert r.status_code == 400
    assert metricas.resumen()["conversiones"] == 0     # no contó nada


def test_el_redirect_no_es_un_open_redirect(monkeypatch):
    """Aunque alguien lograra firmar un token (no puede sin el secreto), un
    esquema que no sea http/https se rechaza igual: el redirect nunca se
    convierte en un `javascript:` ni un `file:`."""
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-redirect")
    cliente = _cliente()
    for veneno in ("javascript:alert(1)", "file:///etc/passwd",
                   "//evil.tld/phishing"):
        token = metricas.firmar_traqueo(veneno, {"canal": "email"})
        r = cliente.get(f"/api/ir?t={token}", follow_redirects=False)
        assert r.status_code == 400, veneno


def test_con_traqueo_el_correo_de_una_corrida_lleva_el_enlace_de_conversion(monkeypatch):
    """El cierre del lazo: con el traqueo encendido, una corrida real produce
    correos cuya landing pasa por `/api/ir`, y ese enlace, verificado, trae el
    segmento del prospecto — que es lo que hace medible la conversión."""
    from urllib.parse import parse_qs, urlsplit

    from cliente_ia import pipeline

    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-de-la-corrida")
    monkeypatch.setenv("MVCLIENTE_URL_TRAQUEO", "https://mv-cliente-ia.vercel.app")

    corrida = pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                                limite_prospectos=20, limite_emails=5,
                                enlaces={"sitio": "mvkobranzaia.com"})
    con_landing = [e for e in corrida.emails if e.landing_url]
    assert con_landing, "la corrida no produjo correos con landing"

    correo = con_landing[0]
    assert "/api/ir?" in correo.landing_url, correo.landing_url
    token = parse_qs(urlsplit(correo.landing_url).query)["t"][0]
    cuerpo = metricas.verificar_traqueo(token)
    assert cuerpo and cuerpo["u"].startswith("https://mvkobranzaia.com")
    assert cuerpo["canal"] == "email"
    assert cuerpo["programa"] == "mvkobranzaia.com"
    assert cuerpo.get("segmento")           # el sector del prospecto viajó


# --- pixel de apertura -------------------------------------------------------

def test_el_pixel_cuenta_la_apertura_y_devuelve_un_gif(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-pixel")
    cliente = _cliente()
    cliente.post("/api/metricas/envios", json={"eventos": [
        {"programa": "x.com", "canal": "email", "segmento": "fintech",
         "ts": "2026-03-02T10:00:00+00:00"} for _ in range(10)]})

    token = metricas.firmar_apertura({"programa": "x.com", "canal": "email",
                                      "segmento": "fintech"})
    r = cliente.get(f"/api/abierto?t={token}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/gif"
    assert r.content.startswith(b"GIF89a")
    # Sin `no-store`, el proxy de imágenes de Gmail sirve la respuesta
    # cacheada y las aperturas siguientes no llegan nunca al servidor.
    assert "no-store" in r.headers["cache-control"]

    d = cliente.get("/api/metricas/resumen?programa=x.com").json()
    assert d["aperturas"] == 1
    assert d["tasa_apertura"] == 0.1
    fila = next(f for f in d["por_segmento"] if f["valor"] == "fintech")
    assert fila["aperturas"] == 1 and fila["tasa_apertura"] == 0.1


def test_reabrir_el_mismo_correo_no_infla_la_apertura(monkeypatch):
    """El pixel se pide de nuevo cada vez que la persona vuelve al mensaje. Sin
    dedup por nonce, diez relecturas del mismo correo darían 1000% de
    apertura."""
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-pixel")
    cliente = _cliente()
    cliente.post("/api/metricas/envios", json={"eventos": [
        {"programa": "x.com", "canal": "email", "ts": "2026-03-02T10:00:00+00:00"}
        for _ in range(10)]})
    token = metricas.firmar_apertura({"programa": "x.com", "canal": "email"})
    for _ in range(6):
        assert cliente.get(f"/api/abierto?t={token}").status_code == 200
    assert cliente.get("/api/metricas/resumen?programa=x.com").json()["aperturas"] == 1


def test_dos_correos_distintos_cuentan_dos_aperturas(monkeypatch):
    """Que el dedup no se coma aperturas legítimas."""
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-pixel")
    cliente = _cliente()
    for _ in range(2):
        cliente.get(f"/api/abierto?t={metricas.firmar_apertura({'canal': 'email'})}")
    assert metricas.resumen()["aperturas"] == 2


def test_el_pixel_devuelve_la_imagen_aunque_el_token_este_roto(monkeypatch):
    """Un contador que falla no puede ensuciar el correo del cliente: si
    respondiera un error, el destinatario vería el icono de imagen rota en
    medio del mensaje. Devuelve el GIF igual, pero NO cuenta."""
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-pixel")
    cliente = _cliente()
    for basura in ("", "cualquier.cosa", "sin-punto", "a.b.c"):
        r = cliente.get(f"/api/abierto?t={basura}")
        assert r.status_code == 200 and r.content.startswith(b"GIF89a")
    assert metricas.resumen()["aperturas"] == 0


def test_un_token_de_apertura_no_sirve_para_redirigir(monkeypatch):
    """El token del pixel no lleva destino, así que aunque alguien lo pase por
    `/api/ir` no se convierte en un redirect a ninguna parte."""
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-pixel")
    cliente = _cliente()
    token = metricas.firmar_apertura({"canal": "email"})
    r = cliente.get(f"/api/ir?t={token}", follow_redirects=False)
    assert r.status_code == 400
    # Y al revés: el token del redirect tampoco cuenta como apertura.
    tok_ir = metricas.firmar_traqueo("https://ejemplo.com/", {"canal": "email"})
    assert metricas.verificar_apertura(tok_ir) is None


def test_sin_traqueo_configurado_el_correo_sale_sin_pixel(monkeypatch):
    """No se le mete una imagen invisible al mensaje de nadie por defecto: el
    traqueo se enciende poniendo las dos variables, no solo."""
    from cliente_ia.enlaces import Enlaces

    monkeypatch.delenv("MVCLIENTE_TRAQUEO_SECRETO", raising=False)
    monkeypatch.delenv("MVCLIENTE_URL_TRAQUEO", raising=False)
    e = Enlaces.desde_dominio("ejemplo.com")
    assert e.pixel({"canal": "email"}) == ""

    # Con el secreto pero sin URL pública tampoco: hacen falta las DOS.
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-pixel")
    assert e.pixel({"canal": "email"}) == ""

    monkeypatch.setenv("MVCLIENTE_URL_TRAQUEO", "https://mi-servidor.test")
    url = e.pixel({"canal": "email"})
    assert url.startswith("https://mi-servidor.test/api/abierto?t=")


def test_el_correo_lleva_el_pixel_al_final_cuando_hay_traqueo(monkeypatch):
    """El pixel va ÚLTIMO: algunos clientes recortan el correo pasados ~102 KB,
    y si estuviera arriba contaría aperturas de gente que no vio el mensaje."""
    from cliente_ia.enlaces import Enlaces
    from cliente_ia.modelos import Decisor, Empresa, Prospecto
    from cliente_ia.redaccion import redactar

    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-pixel")
    monkeypatch.setenv("MVCLIENTE_URL_TRAQUEO", "https://mi-servidor.test")
    p = Prospecto(id="p1", nombre="Acme S.A.", dominio="acme.com.uy",
                  sector="Bancos", pais="UY", empleados=100)
    d = Decisor(id="d1", prospecto_id="p1", nombre="Ana Pérez", cargo="Gerente",
                empresa=p.nombre, pais="UY", email="a@acme.com.uy", idioma="es")
    email = redactar(d, p, Empresa(dominio="x.com", nombre="X"), None,
                     enlaces=Enlaces.desde_dominio("x.com"))
    html = email.cuerpo_html
    assert "/api/abierto?t=" in html, "falta el pixel de apertura"
    # `rindex`, no `index`: el correo tiene varias tablas anidadas y comparar
    # contra la PRIMERA hacía pasar el test con el pixel adentro de la
    # tarjeta. Lo que importa es que esté después de la ÚLTIMA.
    assert html.index("/api/abierto?t=") > html.rindex("</table>"), (
        "el pixel tiene que ir DESPUÉS de la tarjeta, no adentro")
    # Y el mensaje de LinkedIn no puede llevarlo: es texto plano.
    assert "/api/abierto" not in email.linkedin
    assert "/api/abierto" not in email.cuerpo


# --- tráfico de la web -------------------------------------------------------

def test_la_visita_guarda_el_dominio_de_origen_y_no_la_url_entera():
    """La URL de referencia puede llevar los términos de búsqueda de la
    persona o datos de la sesión de otro sitio. Para el KPI —«qué parte del
    tráfico lo trae la prospección»— alcanza el dominio, así que se guarda
    sólo eso: menos dato guardado y el mismo número."""
    cliente = _cliente()
    for origen in ("https://www.google.com/search?q=cobranzas+ia",
                   "https://www.google.com/", "https://t.co/abc", ""):
        assert cliente.post("/api/visita",
                            json={"idioma": "es", "origen": origen}).status_code == 204

    d = cliente.get("/api/metricas/resumen").json()
    assert d["visitas"] == 4
    por = {f["clave"]: f["visitas"] for f in d["por_origen"]}
    assert por == {"www.google.com": 2, "t.co": 1, "directo": 1}
    assert "cobranzas" not in json.dumps(d), "se guardó la búsqueda de la persona"


def test_el_trafico_dice_que_parte_lo_trajo_la_prospeccion(monkeypatch):
    """El número que el usuario pidió: sin esto, «10 clicks desde el correo»
    no dice si son el 90% del tráfico o el 3%."""
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-trafico")
    cliente = _cliente()
    for _ in range(10):
        cliente.post("/api/visita", json={"idioma": "es"})
    for _ in range(2):
        tok = metricas.firmar_traqueo("https://ejemplo.com/", {"canal": "email"})
        cliente.get(f"/api/ir?t={tok}", follow_redirects=False)
    d = cliente.get("/api/metricas/resumen").json()
    assert d["visitas"] == 10 and d["conversiones"] == 2
    assert d["parte_del_trafico"] == 0.2


# --- respuestas (IMAP) -------------------------------------------------------

class _BuzonFalso:
    """Un IMAP mínimo, con lo que usa `/api/respuestas`. Registra qué se le
    pidió: así el test puede afirmar que NUNCA se leyó el cuerpo de un correo
    ajeno, sólo las cabeceras."""

    creado_con = None
    pedidos: list = []

    def __init__(self, host, puerto, ssl_context=None):
        _BuzonFalso.creado_con = (host, puerto)
        self.solo_lectura = None
        self.mensajes: dict[bytes, bytes] = {}

    def login(self, usuario, clave):
        if clave != "la-correcta":
            raise OSError("credenciales rechazadas")

    def select(self, carpeta, readonly=False):
        self.solo_lectura = readonly
        return "OK", [b"1"]

    def search(self, charset, *criterios):
        _BuzonFalso.pedidos.append(("search", criterios))
        return "OK", [b" ".join(self.mensajes)]

    def fetch(self, num, partes):
        _BuzonFalso.pedidos.append(("fetch", partes))
        return "OK", [(b"1 (cabeceras)", self.mensajes[num])]

    def close(self):
        pass

    def logout(self):
        pass


def _con_buzon(monkeypatch, cabeceras: list[bytes]):
    import imaplib

    _BuzonFalso.pedidos = []

    def fabricar(host, puerto, ssl_context=None):
        b = _BuzonFalso(host, puerto, ssl_context)
        b.mensajes = {str(i).encode(): c for i, c in enumerate(cabeceras, 1)}
        return b

    monkeypatch.setattr(imaplib, "IMAP4_SSL", fabricar)
    return fabricar


def _pedir(cliente, dias=30, clave="la-correcta"):
    return cliente.post("/api/respuestas", json={
        "imap": {"host": "imap.prueba.com", "puerto": 993,
                 "usuario": "yo@prueba.com", "clave": clave},
        "dias": dias})


def test_una_respuesta_en_la_bandeja_se_atribuye_al_segmento_del_envio(monkeypatch):
    """El punto de todo esto: no es «tuviste 3 respuestas», es «fintech te
    responde y retail no». La respuesta hereda la meta del envío original."""
    cliente = _cliente()
    cliente.post("/api/metricas/envios", json={"eventos": [
        {"programa": "acme.com", "canal": "email", "segmento": "fintech",
         "pais": "UY", "mid": "<mv-1@acme.com>"},
        {"programa": "acme.com", "canal": "email", "segmento": "retail",
         "pais": "UY", "mid": "<mv-2@acme.com>"},
        {"programa": "acme.com", "canal": "email", "segmento": "retail",
         "pais": "UY", "mid": "<mv-3@acme.com>"},
    ]})
    _con_buzon(monkeypatch, [b"In-Reply-To: <mv-1@acme.com>\r\n\r\n"])

    r = _pedir(cliente)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["nuevas"] == 1 and d["respuestas"] == 1
    assert d["rastreables"] == 3
    assert round(d["tasa_respuesta"], 4) == round(1 / 3, 4)

    resumen = cliente.get("/api/metricas/resumen?programa=acme.com").json()
    por = {f["valor"]: f for f in resumen["por_segmento"]}
    assert por["fintech"]["respuestas"] == 1 and por["fintech"]["tasa_respuesta"] == 1.0
    assert por["retail"]["respuestas"] == 0


def test_la_respuesta_tambien_se_reconoce_por_references(monkeypatch):
    """No todos los clientes mandan `In-Reply-To`: algunos sólo acumulan el
    hilo en `References`, y ahí el id nuestro viene entre otros."""
    cliente = _cliente()
    cliente.post("/api/metricas/envios", json={"eventos": [
        {"canal": "email", "mid": "<mv-9@acme.com>"}]})
    _con_buzon(monkeypatch, [
        b"References: <otro@x.com>\r\n <mv-9@acme.com> <mas@y.com>\r\n\r\n"])
    assert _pedir(cliente).json()["nuevas"] == 1


def test_correr_el_conteo_dos_veces_no_duplica_respuestas(monkeypatch):
    """Se puede apretar «actualizar» todas las veces que uno quiera. Y si la
    persona contesta tres veces al mismo hilo, sigue siendo UN prospecto que
    respondió — contar tres inflaría la tasa."""
    cliente = _cliente()
    cliente.post("/api/metricas/envios", json={"eventos": [
        {"canal": "email", "mid": "<mv-1@acme.com>"}]})
    _con_buzon(monkeypatch, [
        b"In-Reply-To: <mv-1@acme.com>\r\n\r\n",
        b"In-Reply-To: <mv-1@acme.com>\r\n\r\n",
        b"References: <mv-1@acme.com>\r\n\r\n",
    ])
    primera = _pedir(cliente).json()
    assert primera["nuevas"] == 1 and primera["respuestas"] == 1
    segunda = _pedir(cliente).json()
    assert segunda["nuevas"] == 0 and segunda["respuestas"] == 1


def test_un_correo_ajeno_no_cuenta_como_respuesta(monkeypatch):
    """La bandeja está llena de correo que no tiene nada que ver. Sólo cuenta
    lo que responde a un Message-ID que emitimos nosotros."""
    cliente = _cliente()
    cliente.post("/api/metricas/envios", json={"eventos": [
        {"canal": "email", "mid": "<mv-1@acme.com>"}]})
    _con_buzon(monkeypatch, [
        b"In-Reply-To: <newsletter@otracosa.com>\r\n\r\n",
        b"\r\n\r\n",                                   # sin cabeceras de hilo
        b"References: <spam@x.com>\r\n\r\n",
    ])
    d = _pedir(cliente).json()
    assert d["nuevas"] == 0 and d["respuestas"] == 0
    assert d["revisados"] == 3          # los miró a todos y descartó los tres


def test_el_conteo_no_abre_el_cuerpo_de_ningun_correo(monkeypatch):
    """Es la casilla entera del usuario. Se leen las cabeceras del hilo y
    nada más: `BODY.PEEK` (que además no marca como leído) y `readonly`, para
    no poder mover ni borrar nada aunque quisiéramos."""
    cliente = _cliente()
    cliente.post("/api/metricas/envios", json={"eventos": [
        {"canal": "email", "mid": "<mv-1@acme.com>"}]})
    _con_buzon(monkeypatch, [b"In-Reply-To: <mv-1@acme.com>\r\n\r\n"])
    assert _pedir(cliente).status_code == 200

    fetches = [p for tipo, p in _BuzonFalso.pedidos if tipo == "fetch"]
    assert fetches, "no se pidió ningún mensaje"
    for p in fetches:
        assert "BODY.PEEK[HEADER.FIELDS" in p, f"se pidió más que cabeceras: {p}"
        assert "TEXT" not in p and "BODY[]" not in p


def test_sin_envios_rastreables_lo_dice_en_vez_de_devolver_cero(monkeypatch):
    """«0 respuestas» se lee como «nadie te contestó». Si todavía no salió
    ningún correo con identificador, eso es lo que hay que decir."""
    cliente = _cliente()
    _con_buzon(monkeypatch, [b"In-Reply-To: <mv-1@acme.com>\r\n\r\n"])
    d = _pedir(cliente).json()
    assert d["motivo"] == "sin_mensajes"
    assert "enviados" in d["detalle"]


def test_el_imap_que_rechaza_la_clave_da_un_error_sin_la_clave(monkeypatch):
    cliente = _cliente()
    cliente.post("/api/metricas/envios", json={"eventos": [
        {"canal": "email", "mid": "<mv-1@acme.com>"}]})
    _con_buzon(monkeypatch, [])
    r = _pedir(cliente, clave="la-equivocada")
    assert r.status_code == 502
    assert "IMAP" in r.json()["detail"]
    assert "la-equivocada" not in r.text


def test_solo_se_mira_la_ventana_de_dias_pedida(monkeypatch):
    """Releer la casilla entera en cada actualización es caro y no cambia el
    número: sólo se pide lo posterior a la fecha de corte."""
    cliente = _cliente()
    cliente.post("/api/metricas/envios", json={"eventos": [
        {"canal": "email", "mid": "<mv-1@acme.com>"}]})
    _con_buzon(monkeypatch, [b"In-Reply-To: <mv-1@acme.com>\r\n\r\n"])
    _pedir(cliente, dias=7)
    busquedas = [c for tipo, c in _BuzonFalso.pedidos if tipo == "search"]
    assert busquedas and busquedas[0][0] == "SINCE"
