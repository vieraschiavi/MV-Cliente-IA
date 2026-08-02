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


def test_catalogo_geo_devuelve_las_tres_olas_en_orden(cliente):
    olas = cliente.get("/api/geo").json()["olas"]
    assert [o["nivel"] for o in olas] == ["local", "latam", "mundo"]
    assert olas[0]["paises"] == [{"codigo": "UY", "nombre": "Uruguay", "idioma": "es"}]
    assert olas[0]["peso"] > olas[1]["peso"] > olas[2]["peso"]


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


@pytest.mark.parametrize("cuerpo", [
    {"dominio": "x"},                                    # dominio muy corto
    {"dominio": "ejemplo.com", "prospectos": 0},         # fuera de rango
    {"dominio": "ejemplo.com", "prospectos": 99999},     # fuera de rango
    {"dominio": "ejemplo.com", "proveedor_ia": "grok"},  # proveedor desconocido
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
