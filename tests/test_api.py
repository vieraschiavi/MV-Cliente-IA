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


def test_modo_invalido_se_rechaza(cliente):
    r = cliente.post("/api/corridas", json={"dominio": "x.com", "modo": "magia"})
    assert r.status_code == 422


@pytest.mark.parametrize("cuerpo", [
    {"dominio": "x"},                                    # dominio muy corto
    {"dominio": "ejemplo.com", "prospectos": 0},         # fuera de rango
    {"dominio": "ejemplo.com", "prospectos": 99999},     # fuera de rango
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
