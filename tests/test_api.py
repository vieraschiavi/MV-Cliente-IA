"""API HTTP: la puerta que usan la web, la app de PC y el APK."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def cliente():
    from webapp.backend import api
    return TestClient(api.app)


def _esperar(cliente, corrida_id, segundos=30):
    limite = time.time() + segundos
    while time.time() < limite:
        d = cliente.get(f"/api/corridas/{corrida_id}").json()
        if d.get("estado") in ("listo", "error"):
            return d
        time.sleep(0.05)
    raise AssertionError("la corrida no terminó a tiempo")


def test_salud(cliente):
    d = cliente.get("/api/salud").json()
    assert d["ok"] is True
    assert d["modos"] == ["demo", "web", "llm"]


def test_ningun_sitio_ajeno_puede_leer_las_corridas(cliente):
    """El programa instalado escucha en 127.0.0.1, pero una página web
    maliciosa corre en la MISMA máquina: sin allowlist, un `fetch` desde
    cualquier pestaña abierta se llevaba la investigación entera del cliente
    (prospectos, decisores, empresas objetivo). Escuchar en loopback no
    defiende de esto — el navegador sólo deja leer la respuesta si el
    servidor contesta con `Access-Control-Allow-Origin`."""
    r = cliente.get("/api/corridas", headers={"Origin": "https://sitio-malicioso.com"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}

    # El APK sí cruza de origen de verdad: el WebView de Capacitor es
    # `https://localhost` y le pega a un servidor configurado por el usuario.
    for origen in ("https://localhost", "http://localhost", "capacitor://localhost"):
        r = cliente.get("/api/corridas", headers={"Origin": origen})
        assert r.headers.get("access-control-allow-origin") == origen, origen


def test_las_respuestas_llevan_los_encabezados_de_seguridad(cliente):
    """`vercel.json` se los pone a la web, pero el programa INSTALADO no
    tiene Vercel adelante: es este uvicorn sirviendo el HTML y salía pelado.
    Importa porque la pantalla de Correos previsualiza HTML que redactó un
    modelo y las fichas muestran texto traído de sitios ajenos."""
    r = cliente.get("/api/salud")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert "object-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_catalogo_geo_devuelve_las_tres_olas_en_orden(cliente):
    d = cliente.get("/api/geo").json()
    olas = d["olas"]
    assert [o["nivel"] for o in olas] == ["local", "regional", "mundo"]
    assert olas[0]["paises"] == [{"codigo": "UY", "nombre": "Uruguay", "idioma": "es"}]
    assert olas[0]["peso"] > olas[1]["peso"] > olas[2]["peso"]
    # El desplegable «tu país» se llena con esto: tiene que ser mundial.
    assert len(d["paises"]) >= 90
    assert {"DE", "JP", "ZA", "AU", "US", "UY"} <= {p["codigo"] for p in d["paises"]}


def test_catalogo_geo_gira_las_olas_alrededor_del_pais_pedido(cliente):
    d = cliente.get("/api/geo?pais=DE&idioma=en").json()
    assert d["pais_base"] == "DE"
    assert d["region_base"] == "Europe"
    olas = {o["nivel"]: [p["codigo"] for p in o["paises"]] for o in d["olas"]}
    assert olas["local"] == ["DE"]
    assert "ES" in olas["regional"] and "UY" not in olas["regional"]
    assert "UY" in olas["mundo"]


def test_la_corrida_toma_el_pais_que_eligio_el_cliente(cliente):
    r = cliente.post("/api/corridas", json={
        "dominio": "mvkobranzaia.com", "modo": "demo", "prospectos": 20,
        "pais": "DE"})
    assert r.status_code == 200
    d = _esperar(cliente, r.json()["id"])
    assert d["estado"] == "listo"
    assert d["pais_base"] == "DE"
    assert d["pais_base_nombre"] == "Alemania"
    locales = [p for p in d["prospectos"] if p["nivel"] == "local"]
    assert locales and all(p["pais"] == "DE" for p in locales)


def test_corrida_completa_por_http(cliente):
    r = cliente.post("/api/corridas", json={"dominio": "mvkobranzaia.com", "modo": "demo",
                                            "nombre": "MV Kobra AI", "prospectos": 40})
    assert r.status_code == 200
    d = _esperar(cliente, r.json()["id"])
    assert d["estado"] == "listo"
    assert len(d["prospectos"]) == 40
    assert d["prospectos"][0]["nivel"] == "local"
    assert set(d["resumen"]["emails_por_idioma"]) == {"es", "pt", "en"}


def test_exportaciones(cliente):
    r = cliente.post("/api/corridas", json={"dominio": "mvkobranzaia.com",
                                            "modo": "demo", "prospectos": 20})
    cid = r.json()["id"]
    _esperar(cliente, cid)

    csv = cliente.get(f"/api/corridas/{cid}/csv")
    assert csv.status_code == 200
    assert "text/csv" in csv.headers["content-type"]
    assert "attachment" in csv.headers["content-disposition"]

    xlsx = cliente.get(f"/api/corridas/{cid}/xlsx")
    assert xlsx.status_code == 200
    assert len(xlsx.content) > 5000


def test_export_directo_con_cuerpo_invalido_da_422_no_500(cliente):
    """POST /api/exportar/csv con una corrida reconstruida de tipos malos:
    antes reventaba en round(score) fuera de toda validación → 500. Ahora 422."""
    corrida_mala = {
        "id": "abc123", "dominio": "ejemplo.com", "estado": "listo",
        "prospectos": [{"id": "p1", "nombre": "X", "dominio": "x.com",
                        "score": "no-es-numero", "senales": "no-es-lista"}],
    }
    r = cliente.post("/api/exportar/csv", json=corrida_mala)
    assert r.status_code == 422, f"esperaba 422, dio {r.status_code}"
    assert r.status_code != 500


def test_el_nombre_de_descarga_no_deja_inyectar_en_el_header(cliente):
    """Un dominio con comillas/CRLF no puede colarse crudo en
    Content-Disposition."""
    corrida = {"id": "zz99", "dominio": 'evil"\r\nX-Injected: 1', "estado": "listo",
               "prospectos": [], "decisores": [], "emails": []}
    r = cliente.post("/api/exportar/csv", json=corrida)
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    # La propiedad de seguridad: ni CR ni LF (romperían el header en dos) ni
    # una comilla que cierre el filename="..." antes de tiempo. Que la palabra
    # "X-Injected" sobreviva como texto del nombre es inofensivo.
    assert "\r" not in cd and "\n" not in cd
    assert cd.count('"') == 2                      # sólo las que abren y cierran


def test_listar_y_borrar(cliente):
    cid = cliente.post("/api/corridas", json={"dominio": "ejemplo.com.uy",
                                              "modo": "demo", "prospectos": 10}).json()["id"]
    _esperar(cliente, cid)
    assert any(c["id"] == cid for c in cliente.get("/api/corridas").json()["corridas"])
    assert cliente.delete(f"/api/corridas/{cid}").json()["borrada"] is True
    assert cliente.get(f"/api/corridas/{cid}").status_code == 404


def test_corrida_inexistente_da_404(cliente):
    assert cliente.get("/api/corridas/noexiste").status_code == 404


def test_analisis_sin_clave_da_numeros_pero_no_inventa_lo_cualitativo(cliente):
    r = cliente.post("/api/analisis", json={
        "empresa": {"nombre": "X", "dominio": "x.com", "pais": "UY"},
        "precio": 100, "nuevos_por_mes": 2, "churn_pct": 5, "gasto_fijo": 500,
    })
    assert r.status_code == 200
    d = r.json()
    assert d["financiero"]["escenarios"]["base"]["sin_ads"]["filas"]
    assert d["cualitativo"] is None
    assert "analisis_sin_clave" in d["avisos"]


def test_enviar_correos_usa_el_smtp_del_usuario(cliente, monkeypatch):
    """El envío real sale por la casilla del usuario; un destinatario que
    rebota no frena a los demás y las credenciales no quedan en el resultado."""
    import smtplib

    mandados = []

    class SmtpFalso:
        def __init__(self, host, puerto, timeout=30):
            assert (host, puerto) == ("smtp.prueba.com", 587)

        def starttls(self, context=None):
            pass

        def login(self, usuario, clave):
            assert usuario == "yo@prueba.com"

        def send_message(self, m):
            if m["To"] == "rebota@x.com":
                raise smtplib.SMTPRecipientsRefused({m["To"]: (550, b"no")})
            mandados.append(m)

        def quit(self):
            pass

    monkeypatch.setattr(smtplib, "SMTP", SmtpFalso)
    r = cliente.post("/api/enviar", json={
        "smtp": {"host": "smtp.prueba.com", "puerto": 587,
                 "usuario": "yo@prueba.com", "clave": "secreta"},
        "remitente": "MV",
        "correos": [
            {"para": "destino@x.com", "asunto": "Hola", "cuerpo": "Cuerpo",
             "cuerpo_html": "<table><tr><td>hola</td></tr></table>"},
            {"para": "rebota@x.com", "asunto": "Hola", "cuerpo": "Cuerpo"},
        ],
        "adjuntos": [{"nombre": "banner.png", "tipo": "image/png",
                      "contenido_b64": "aG9sYQ=="}],
    })
    assert r.status_code == 200
    d = r.json()
    assert d["enviados"] == 1
    ok = {x["para"]: x["ok"] for x in d["resultados"]}
    assert ok == {"destino@x.com": True, "rebota@x.com": False}
    assert "secreta" not in r.text
    assert len(mandados) == 1
    adjuntos = [p.get_filename() for p in mandados[0].iter_attachments()]
    assert adjuntos == ["banner.png"]


def test_modo_invalido_se_rechaza(cliente):
    r = cliente.post("/api/corridas", json={"dominio": "x.com", "modo": "magia"})
    assert r.status_code == 422


def test_modelos_ia_trae_la_lista_del_proveedor(cliente, monkeypatch):
    """El botón «Actualizar» de Configuración: pega en /api/ia/modelos y el
    servidor le pregunta al proveedor con la clave del usuario."""
    from cliente_ia.proveedores import llm as modulo_llm

    monkeypatch.setattr(modulo_llm, "listar_modelos",
                        lambda proveedor, clave: [f"{proveedor}-modelo-1",
                                                   f"{proveedor}-modelo-2"])
    r = cliente.post("/api/ia/modelos", json={"proveedor": "claude", "clave": "sk-x"})
    assert r.status_code == 200
    assert r.json() == {"modelos": ["claude-modelo-1", "claude-modelo-2"]}


def test_modelos_ia_sin_clave_da_422_no_500(cliente):
    r = cliente.post("/api/ia/modelos", json={"proveedor": "claude", "clave": ""})
    assert r.status_code == 422
    assert "clave" in r.json()["detail"].lower()


@pytest.mark.parametrize("cuerpo", [
    {"dominio": "x"},                                    # dominio muy corto
    {"dominio": "ejemplo.com", "prospectos": 0},         # fuera de rango
    {"dominio": "ejemplo.com", "prospectos": 99999},     # fuera de rango
    {"dominio": "ejemplo.com", "proveedor_ia": "bing"},  # proveedor desconocido
])
def test_entrada_invalida_se_rechaza(cliente, cuerpo):
    assert cliente.post("/api/corridas", json=cuerpo).status_code == 422


@pytest.mark.parametrize("ruta", [
    "/api/corridas/..%2F..%2Fetc%2Fpasswd",
    "/../../../../etc/passwd",
    "/..%2F..%2F..%2F..%2Fetc%2Fpasswd",
    "/assets/../../../../etc/passwd",
])
def test_ninguna_ruta_sirve_archivos_de_afuera_del_build(cliente, ruta):
    """
    Lo que importa no es el código de estado sino que NUNCA salga contenido de
    fuera del build de React: ni el índice de corridas ni el servido estático
    pueden convertirse en una lectura arbitraria de disco.
    """
    r = cliente.get(ruta)
    assert "root:x:" not in r.text
    if r.status_code == 200:
        assert r.text.lstrip().startswith("<!DOCTYPE html>")


def test_id_de_corrida_con_barra_no_escapa_del_directorio():
    """La capa de almacén también valida por su cuenta, sin depender de HTTP."""
    from cliente_ia import almacen
    with pytest.raises(ValueError):
        almacen.ruta_de("../../etc/passwd")


def test_sin_password_la_api_queda_abierta(cliente):
    assert cliente.get("/api/auth/estado").json()["auth"] is False


def test_con_password_la_api_exige_token(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_PASSWORD", "secreta")
    from webapp.backend import api
    cliente = TestClient(api.app)

    assert cliente.get("/api/auth/estado").json()["auth"] is True
    assert cliente.get("/api/corridas").status_code == 401
    assert cliente.post("/api/auth/login", json={"password": "otra"}).status_code == 401

    token = cliente.post("/api/auth/login", json={"password": "secreta"}).json()["token"]
    cabecera = {"Authorization": f"Bearer {token}"}
    assert cliente.get("/api/corridas", headers=cabecera).status_code == 200
    # Un token inventado no entra.
    assert cliente.get("/api/corridas",
                       headers={"Authorization": "Bearer 99999999999.falso"}).status_code == 401


def test_cupo_gratis_de_la_web(monkeypatch):
    """En el despliegue web las búsquedas reales tienen cupo; la demo no lo
    gasta, y el código de dueño exime. El aviso es un 402 con explicación."""
    import json as jsonmod

    from cliente_ia import modelos
    from webapp.backend import api

    monkeypatch.setattr(api, "SIN_ESTADO", True)
    monkeypatch.setattr(api, "CUPO_GRATIS", 2)
    api._cupo_por_ip.clear()
    api._cupo_por_email.clear()

    def corrida_falsa(dominio, **kwargs):
        return modelos.Corrida(id="fake01", dominio=dominio, estado="listo")

    monkeypatch.setattr(api.pipeline, "ejecutar", corrida_falsa)

    cliente = TestClient(api.app)
    real = {"dominio": "mvkobranzaia.com", "modo": "web", "prospectos": 5,
            "email": "alguien@empresa.com"}

    # Sin correo (o con uno inválido) la búsqueda real no arranca.
    sin_correo = {k: v for k, v in real.items() if k != "email"}
    assert cliente.post("/api/corridas", json=sin_correo).status_code == 422
    assert cliente.post("/api/corridas",
                        json={**real, "email": "no-es-correo"}).status_code == 422

    assert cliente.post("/api/corridas", json=real).status_code == 200
    assert cliente.get("/api/cupo").json()["usadas"] == 1
    assert cliente.post("/api/corridas", json=real).status_code == 200
    r = cliente.post("/api/corridas", json=real)
    assert r.status_code == 402
    assert "gratis" in r.json()["detail"]

    # El conteo también sigue al correo: mismo correo en un "navegador"
    # limpio no reinicia el cupo.
    otro = TestClient(api.app)
    assert otro.post("/api/corridas", json=real).status_code == 402

    # La demo sintética no descuenta nunca (y no pide correo).
    demo = {"dominio": "mvkobranzaia.com", "modo": "demo", "prospectos": 5}
    assert cliente.post("/api/corridas", json=demo).status_code == 200

    # El correo del dueño no descuenta ni se bloquea.
    assert cliente.post(
        "/api/corridas",
        json={**real, "email": api.OWNER_EMAIL}).status_code == 200
    assert cliente.get(f"/api/cupo?email={api.OWNER_EMAIL}").json()["owner"]

    # El dueño también queda exento con el código de MVCLIENTE_OWNER.
    monkeypatch.setenv("MVCLIENTE_OWNER", "clave-owner")
    assert cliente.post("/api/corridas", json=sin_correo,
                        headers={"X-MV-Owner": "clave-owner"}).status_code == 200

    # Y el streaming devuelve la corrida por líneas NDJSON.
    api._cupo_por_ip.clear()
    limpio = TestClient(api.app)
    rs = limpio.post("/api/corridas?stream=1", json=demo)
    assert rs.status_code == 200
    lineas = [jsonmod.loads(x) for x in rs.text.strip().splitlines()]
    assert lineas and lineas[-1]["estado"] == "listo"


def test_clave_de_ia_propia_no_gasta_cupo_ni_pide_correo(monkeypatch):
    """Si el usuario pega su propia clave de IA, el costo lo paga en su
    propia cuenta — no el servidor — así que la búsqueda no descuenta cupo
    ni exige correo, ni siquiera cuando ya se agotó el cupo gratis."""
    from cliente_ia import modelos
    from webapp.backend import api

    monkeypatch.setattr(api, "SIN_ESTADO", True)
    monkeypatch.setattr(api, "CUPO_GRATIS", 1)
    api._cupo_por_ip.clear()
    api._cupo_por_email.clear()

    monkeypatch.setattr(api.pipeline, "ejecutar",
                        lambda dominio, **kw: modelos.Corrida(
                            id="fake02", dominio=dominio, estado="listo"))

    cliente = TestClient(api.app)
    con_clave = {"dominio": "mvkobranzaia.com", "modo": "llm", "prospectos": 5,
                 "clave_ia": "sk-ant-lo-que-sea"}

    # Sin correo, y las veces que haga falta: la clave propia no cuenta.
    for _ in range(3):
        assert cliente.post("/api/corridas", json=con_clave).status_code == 200
    assert cliente.get("/api/cupo").json()["usadas"] == 0

    # La misma búsqueda real SIN clave propia sí gasta el cupo gratis de
    # siempre (acá con modo "web", que no exige clave para arrancar).
    sin_clave = {**con_clave, "modo": "web", "clave_ia": "",
                "email": "alguien@empresa.com"}
    assert cliente.post("/api/corridas", json=sin_clave).status_code == 200
    r = cliente.post("/api/corridas", json=sin_clave)
    assert r.status_code == 402


def test_el_que_pago_no_gasta_cupo_en_la_web_ni_en_el_apk(monkeypatch):
    """El comprador tiene que funcionar igual en el APK que en el .exe.

    Antes no era así, y era un agujero de PRODUCTO, no de código: la licencia
    sólo la entendía el programa INSTALADO (guarda estado en disco), y
    `POST /api/licencia` contesta 400 en serverless — "La web no usa
    licencias". El APK habla con ese backend, así que quien pagaba y usaba el
    celular seguía contra el cupo gratis, exactamente igual que alguien que
    no pagó nada.

    Se prueban las tres puntas que importan: la licencia válida no gasta
    cupo, una clave inventada NO desbloquea (si no, el candado no existe), y
    una vencida tampoco.
    """
    from cliente_ia import licencia, modelos
    from webapp.backend import api

    secreto = "secreto-de-prueba-del-test"
    monkeypatch.setenv("MVCLIENTE_LICENCIA_SECRETO", secreto)
    monkeypatch.setattr(api, "SIN_ESTADO", True)
    monkeypatch.setattr(api, "CUPO_GRATIS", 1)
    api._cupo_por_ip.clear()
    api._cupo_por_email.clear()

    monkeypatch.setattr(api.pipeline, "ejecutar",
                        lambda dominio, **kw: modelos.Corrida(
                            id="fake03", dominio=dominio, estado="listo"))

    clave = licencia.emitir("comprador@empresa.com", meses=12, secreto=secreto)
    cliente = TestClient(api.app)
    base = {"dominio": "mvkobranzaia.com", "modo": "web", "prospectos": 5}

    # 1. Con licencia: sin correo, y más veces que el cupo. No descuenta.
    con_licencia = {**base, "licencia_clave": clave}
    for _ in range(3):
        assert cliente.post("/api/corridas", json=con_licencia).status_code == 200
    assert cliente.get("/api/cupo").json()["usadas"] == 0

    # 2. Una clave inventada no puede desbloquear nada: cae al cupo gratis y
    #    se agota igual que sin licencia.
    trucha = {**base, "licencia_clave": "no.esunaclavereal",
              "email": "otro@empresa.com"}
    assert cliente.post("/api/corridas", json=trucha).status_code == 200
    assert cliente.post("/api/corridas", json=trucha).status_code == 402

    # 3. Y una licencia VENCIDA tampoco (firma válida, fecha pasada).
    api._cupo_por_ip.clear()
    api._cupo_por_email.clear()
    # La cookie firmada de cupo también cuenta (`_cupo_usado` la lee), y el
    # TestClient la arrastra entre pedidos: sin limpiarla, el paso 2 dejaba
    # el cupo agotado y este bloque medía eso en vez de la licencia vencida.
    cliente.cookies.clear()
    vencida = licencia.emitir("expirado@empresa.com", meses=-1, secreto=secreto)
    assert licencia.verificar(vencida, secreto)["ok"] is False, (
        "la licencia de prueba tenía que estar vencida")
    con_vencida = {**base, "licencia_clave": vencida,
                   "email": "expirado@empresa.com"}
    assert cliente.post("/api/corridas", json=con_vencida).status_code == 200
    assert cliente.post("/api/corridas", json=con_vencida).status_code == 402


def test_corrida_de_mil_prospectos(cliente):
    """El selector va en tramos hasta 1000: la API tiene que aceptarlo y el
    demo entregarlo entero (con 12 intentos de nombre único llegaba a 996)."""
    r = cliente.post("/api/corridas", json={
        "dominio": "mvkobranzaia.com", "modo": "demo", "prospectos": 1000})
    assert r.status_code == 200
    d = _esperar(cliente, r.json()["id"])
    assert d["estado"] == "listo"
    assert len(d["prospectos"]) == 1000
    assert cliente.post("/api/corridas", json={
        "dominio": "mvkobranzaia.com", "modo": "demo",
        "prospectos": 1001}).status_code == 422


def test_automatizar_sin_smtp_no_manda_nada(cliente):
    """Con credenciales SMTP inválidas el flujo NO arranca: 502 claro, sin
    medio lote enviado y medio no."""
    r = cliente.post("/api/automatizar", json={
        "smtp": {"host": "smtp.invalido.test", "puerto": 587,
                 "usuario": "nadie@test.com", "clave": "x"},
        "correos": [{"para": "a@b.com", "asunto": "Hola", "cuerpo": "Hola"}],
    })
    assert r.status_code == 502
    assert "SMTP" in r.json()["detail"]
    assert "x" != r.json()["detail"]                 # nunca la clave


def test_publicar_en_x_tacha_los_secretos(monkeypatch):
    """Si X rechaza la petición, el detalle del comprobante no puede llevar
    ninguna de las cuatro claves (va a un correo y a la pantalla)."""
    import urllib.request

    from cliente_ia import redes

    claves = redes.ClavesX("ck-123", "cs-456", "at-789", "as-000")

    def reventar(*_a, **_k):
        raise RuntimeError("rechazado: token at-789 con secreto as-000")

    monkeypatch.setattr(urllib.request, "urlopen", reventar)
    r = redes.publicar_en_x(claves, "hola")
    assert r["ok"] is False
    for secreto in ("cs-456", "at-789", "as-000", "ck-123"):
        assert secreto not in r["detalle"]


def test_automatizar_manda_lote_y_comprobante(cliente, monkeypatch):
    """El camino feliz del botón: salen los correos, el que rebota queda
    anotado, y el ÚLTIMO mensaje es el comprobante a la casilla elegida con
    el detalle honesto (incluida la cola manual sin API)."""
    import smtplib

    mandados = []

    class SmtpFalso:
        def __init__(self, host, puerto, timeout=30):
            pass

        def starttls(self, context=None):
            pass

        def login(self, usuario, clave):
            pass

        def send_message(self, m):
            if m["To"] == "rebota@x.com":
                raise smtplib.SMTPRecipientsRefused({m["To"]: (550, b"no")})
            mandados.append(m)

        def quit(self):
            pass

    monkeypatch.setattr(smtplib, "SMTP", SmtpFalso)
    r = cliente.post("/api/automatizar", json={
        "smtp": {"host": "smtp.prueba.com", "puerto": 587,
                 "usuario": "yo@prueba.com", "clave": "secreta"},
        "correos": [
            {"para": "destino@x.com", "asunto": "Hola", "cuerpo": "Cuerpo"},
            {"para": "rebota@x.com", "asunto": "Hola", "cuerpo": "Cuerpo"},
        ],
        "comprobante_a": "dueno@prueba.com",
        "manuales": {"linkedin": 12, "instagram": 1, "tiktok": 1, "vacio": 0},
    })
    assert r.status_code == 200
    d = r.json()
    assert d["correos"] == {"total": 2, "enviados": 1,
                            "resultados": d["correos"]["resultados"]}
    assert d["x"] is None                      # sin claves no se toca X
    assert d["manuales"] == {"linkedin": 12, "instagram": 1, "tiktok": 1}
    assert d["comprobante"]["a"] == "dueno@prueba.com"
    assert d["comprobante"]["ok"] is True
    assert "secreta" not in r.text

    # El comprobante es el último envío y cuenta lo que pasó, canal por canal.
    recibo = mandados[-1]
    assert recibo["To"] == "dueno@prueba.com"
    assert "1/2" in recibo["Subject"]
    cuerpo = recibo.get_body(("plain",)).get_content()
    assert "Linkedin: 12" in cuerpo and "Tiktok: 1" in cuerpo
    html = recibo.get_body(("html",)).get_content()
    assert "<table" in html and "<style" not in html   # regla Outlook


def test_corrida_con_proveedor_mal_config_no_queda_colgada(cliente, monkeypatch):
    """El ALTO de la auditoría: elegir copilot sin endpoint hacía que
    `construir` lanzara FUERA del try de `ejecutar`, dejando la corrida en
    'corriendo' para siempre (spinner infinito) o un 500 crudo en serverless.
    Ahora cae en el manejador y queda 'error' con el motivo."""
    # Sin estado (serverless): la corrida se ejecuta en la misma petición.
    monkeypatch.setattr("webapp.backend.api.SIN_ESTADO", True)
    r = cliente.post("/api/corridas", json={
        "dominio": "ejemplo.com", "modo": "llm", "proveedor_ia": "copilot",
        "clave_ia": "una-clave", "endpoint_ia": "", "prospectos": 5,
        "email": "x@y.com"})
    # No revienta con 500: sale un error controlado (502 con el motivo).
    assert r.status_code == 502
    assert "endpoint" in r.json()["detail"].lower() or "copilot" in r.json()["detail"].lower()


def test_una_corrida_vieja_con_un_campo_extra_no_da_500(cliente, monkeypatch, tmp_path):
    """El MEDIO: un JSON guardado por una versión previa que traiga una clave
    renombrada/quitada tumbaba `desde_dict` con TypeError -> 500 al abrir o
    exportar. Ahora las claves desconocidas se ignoran."""
    import json as _json

    from cliente_ia import almacen, rutas
    monkeypatch.setenv("MVCLIENTE_DIR_DATOS", str(tmp_path))
    # Corrida mínima válida + un campo que el dataclass Prospecto ya no tiene.
    corrida = {
        "id": "vieja01", "dominio": "ejemplo.com", "estado": "listo",
        "prospectos": [{"id": "p1", "nombre": "ACME", "dominio": "acme.com",
                        "sector": "x", "pais": "UY", "nivel": "local",
                        "prioridad": 1, "senales": [], "campana_id": "c1",
                        "campo_que_ya_no_existe": "basura"}],
    }
    (rutas.dir_corridas() / "vieja01.json").write_text(_json.dumps(corrida))
    # Reconstruir no revienta y conserva el prospecto.
    c = almacen.cargar("vieja01")
    assert c is not None and len(c.prospectos) == 1
    assert c.prospectos[0].nombre == "ACME"


def _pago_falso(monkeypatch, **campos):
    """Simula la respuesta de la API de pagos de MercadoPago."""
    import io
    import json as _json

    base = {"status": "approved", "transaction_amount": 6000.0,
            "external_reference": "mvcliente:licencia",
            "payer": {"email": "comprador@empresa.com"}}
    base.update(campos)

    def _urlopen(peticion, timeout=0):
        assert "api.mercadopago.com/v1/payments/" in peticion.full_url
        return io.BytesIO(_json.dumps(base).encode())

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)


def test_pagar_entrega_la_licencia_sola(monkeypatch):
    """Pagar tiene que ENTREGAR la licencia, no dejar al cliente escribiendo
    un correo para pedirla.

    Antes el cliente pagaba, MercadoPago lo devolvía a `/?pago=ok` y ahí
    terminaba todo: sin webhook, sin clave emitida y sin forma de que el
    programa se enterara. Ahora el `payment_id` de la vuelta se cambia por la
    clave, verificándolo contra MercadoPago — sin guardar nada, que es lo que
    permite hacerlo en un backend sin estado.
    """
    from cliente_ia import licencia
    from webapp.backend import api

    secreto = "secreto-de-prueba-del-test"
    monkeypatch.setenv("MVCLIENTE_LICENCIA_SECRETO", secreto)
    monkeypatch.setenv("MERCADOPAGO_ACCESS_TOKEN", "TEST-token")
    _pago_falso(monkeypatch)

    cliente = TestClient(api.app)
    r = cliente.post("/api/pago/licencia", json={"payment_id": "1234567890"})
    assert r.status_code == 200, r.text
    d = r.json()

    # La clave que sale tiene que ser VÁLIDA para el mismo servidor, y estar
    # a nombre del que pagó — no de cualquiera.
    comprobada = licencia.verificar(d["clave"], secreto)
    assert comprobada["ok"] is True, comprobada
    assert comprobada["email"] == "comprador@empresa.com"
    assert d["email"] == "comprador@empresa.com"

    # Y sirve de verdad para lo que se compró: sin cupo y sin correo.
    from cliente_ia import modelos
    monkeypatch.setattr(api, "SIN_ESTADO", True)
    monkeypatch.setattr(api, "CUPO_GRATIS", 1)
    api._cupo_por_ip.clear()
    api._cupo_por_email.clear()
    monkeypatch.setattr(api.pipeline, "ejecutar",
                        lambda dominio, **kw: modelos.Corrida(
                            id="fake04", dominio=dominio, estado="listo"))
    corrida = {"dominio": "mvkobranzaia.com", "modo": "web", "prospectos": 5,
               "licencia_clave": d["clave"]}
    for _ in range(3):
        assert cliente.post("/api/corridas", json=corrida).status_code == 200
    assert cliente.get("/api/cupo").json()["usadas"] == 0


def test_no_se_saca_licencia_sin_haber_pagado_de_verdad(monkeypatch):
    """Las cuatro formas de pedir una licencia sin haberla comprado. Si
    alguna pasara, el candado no existe y el producto se regala."""
    from webapp.backend import api

    monkeypatch.setenv("MVCLIENTE_LICENCIA_SECRETO", "secreto-de-prueba-del-test")
    monkeypatch.setenv("MERCADOPAGO_ACCESS_TOKEN", "TEST-token")
    cliente = TestClient(api.app)
    pedido = {"payment_id": "1234567890"}

    # 1. Pago no aprobado (pendiente o rechazado).
    for estado in ("pending", "rejected", "in_process"):
        _pago_falso(monkeypatch, status=estado)
        assert cliente.post("/api/pago/licencia", json=pedido).status_code == 402

    # 2. Pagó menos que el precio: cobrarse $1 de otra cosa no da licencia.
    _pago_falso(monkeypatch, transaction_amount=1.0)
    assert cliente.post("/api/pago/licencia", json=pedido).status_code == 402

    # 3. Un pago real, aprobado y por el monto, pero de OTRO cobro de la
    #    misma cuenta de MercadoPago.
    _pago_falso(monkeypatch, external_reference="otra-cosa")
    assert cliente.post("/api/pago/licencia", json=pedido).status_code == 422

    # 4. Sin número de pago, o inventado.
    assert cliente.post("/api/pago/licencia", json={"payment_id": ""}).status_code == 422
    assert cliente.post("/api/pago/licencia",
                        json={"payment_id": "no-numerico"}).status_code == 422


def test_el_panel_del_dueno_no_lo_ve_nadie_mas(monkeypatch):
    """El panel muestra cuánta plata entró y los correos de los compradores.
    Si se pudiera abrir sin el código, cualquiera vería la facturación."""
    from webapp.backend import api

    monkeypatch.setenv("MVCLIENTE_OWNER", "codigo-secreto-del-test")
    cliente = TestClient(api.app)

    assert cliente.get("/api/panel").status_code == 403
    assert cliente.get("/api/panel",
                       headers={"X-MV-Owner": "no-es-el-codigo"}).status_code == 403


def test_el_panel_junta_descargas_y_plata_sin_guardar_nada(monkeypatch):
    """Las dos fuentes ya tienen el dato: GitHub cuenta las descargas y
    MercadoPago las ventas. El panel las agrega; no hay base de datos que
    pueda quedar desincronizada de la realidad."""
    import io
    import json as _json

    from webapp.backend import api

    monkeypatch.setenv("MVCLIENTE_OWNER", "codigo-secreto-del-test")
    monkeypatch.setenv("MERCADOPAGO_ACCESS_TOKEN", "TEST-token")

    publicaciones = [{"assets": [
        {"name": "MVClienteIA.apk", "download_count": 30},
        {"name": "MVClienteIA.apk.sha256", "download_count": 999},   # no cuenta
        {"name": "MVClienteIA_Setup.exe", "download_count": 12},
        {"name": "MVClienteIA_BAT_demo.zip", "download_count": 5},
    ]}]
    pagos = {"paging": {"total": 2}, "results": [
        {"status": "approved", "transaction_amount": 6000.0, "id": 1,
         "date_approved": "2026-08-20T10:00:00Z",
         "payer": {"email": "uno@empresa.com"}},
        {"status": "rejected", "transaction_amount": 6000.0, "id": 2,
         "date_approved": "2026-08-20T11:00:00Z",
         "payer": {"email": "trucho@empresa.com"}},
    ]}

    def _urlopen(peticion, timeout=0):
        url = peticion.full_url
        if "api.github.com" in url:
            return io.BytesIO(_json.dumps(publicaciones).encode())
        if "api.mercadopago.com" in url:
            return io.BytesIO(_json.dumps(pagos).encode())
        raise AssertionError(f"pidió una URL inesperada: {url}")

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    cliente = TestClient(api.app)
    d = cliente.get("/api/panel", headers={"X-MV-Owner": "codigo-secreto-del-test"}).json()

    # Descargas: los .sha256 NO son descargas del producto.
    assert d["descargas"]["total"] == 47, d["descargas"]
    assert d["descargas"]["android"] == 30
    assert d["descargas"]["pc"] == 17

    # Plata: un pago RECHAZADO no es una venta ni un cliente.
    assert d["cobros"]["ventas"] == 1
    assert d["cobros"]["clientes"] == 1
    assert d["cobros"]["recaudado"] == 6000.0
    assert d["cobros"]["ultimos"][0]["email"] == "uno@empresa.com"


def test_si_una_fuente_falla_el_panel_muestra_la_otra(monkeypatch):
    """Un panel que devuelve 500 porque GitHub tardó no sirve de nada:
    saber la mitad sirve. Se devuelve lo que se pudo, con el motivo al lado."""
    import io
    import json as _json

    from webapp.backend import api

    monkeypatch.setenv("MVCLIENTE_OWNER", "codigo-secreto-del-test")
    monkeypatch.setenv("MERCADOPAGO_ACCESS_TOKEN", "TEST-token")

    def _urlopen(peticion, timeout=0):
        if "api.github.com" in peticion.full_url:
            raise TimeoutError("github no contestó")
        return io.BytesIO(_json.dumps({"results": [], "paging": {"total": 0}}).encode())

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    cliente = TestClient(api.app)
    r = cliente.get("/api/panel", headers={"X-MV-Owner": "codigo-secreto-del-test"})
    assert r.status_code == 200
    d = r.json()
    assert d["descargas"] is None and "error_descargas" in d
    assert d["cobros"] is not None            # la que sí anduvo, se muestra
