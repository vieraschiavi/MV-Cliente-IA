"""
Licencias del programa de escritorio.

Lo que estos tests cuidan es la plata: que la edición demo se venza sola, que
una clave inventada no pase, y —lo más fácil de romper sin darse cuenta— que
el default cuando algo falta sea CERRADO, no abierto.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from cliente_ia import licencia

SECRETO = "secreto-de-prueba-del-dueno"


@pytest.fixture(autouse=True)
def entorno(tmp_path, monkeypatch):
    """Cada test con su carpeta de datos: la marca de «primera vez» y la clave
    guardada viven ahí y se pisarían entre sí."""
    monkeypatch.setenv("MVCLIENTE_DIR_DATOS", str(tmp_path))
    monkeypatch.setenv("MVCLIENTE_LICENCIA_SECRETO", SECRETO)
    monkeypatch.delenv("MVCLIENTE_EDICION", raising=False)
    return tmp_path


# ---------------------------------------------------------------------------
# Edición
# ---------------------------------------------------------------------------
def test_sin_sello_la_edicion_es_demo(monkeypatch):
    """El default tiene que ser el MÁS cerrado. Si un instalador sale sin
    sello, que se comporte como prueba — no que regale la versión completa."""
    monkeypatch.setattr(licencia, "_ruta_sello", lambda: None)
    assert licencia.edicion() == "demo"


def test_el_sello_del_instalador_define_la_edicion(tmp_path, monkeypatch):
    sello = tmp_path / licencia.NOMBRE_SELLO
    sello.write_text(json.dumps({"edicion": "owner"}), encoding="utf-8")
    monkeypatch.setattr(licencia, "_ruta_sello", lambda: sello)
    assert licencia.edicion() == "owner"


def test_un_sello_con_basura_no_asciende_a_nadie(tmp_path, monkeypatch):
    sello = tmp_path / licencia.NOMBRE_SELLO
    sello.write_text("{no es json", encoding="utf-8")
    monkeypatch.setattr(licencia, "_ruta_sello", lambda: sello)
    assert licencia.edicion() == "demo"

    sello.write_text(json.dumps({"edicion": "dios"}), encoding="utf-8")
    assert licencia.edicion() == "demo"


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------
def test_owner_no_pide_clave_ni_vence(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_EDICION", "owner")
    e = licencia.estado()
    assert e.edicion == "owner"
    assert e.activa is True
    assert e.vence == "" and e.dias_restantes == -1


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def test_la_demo_arranca_activa_con_catorce_dias(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_EDICION", "demo")
    e = licencia.estado()
    assert e.activa is True
    assert e.dias_restantes == licencia.DIAS_DEMO


def test_la_demo_se_vence_sola(monkeypatch, entorno):
    monkeypatch.setenv("MVCLIENTE_EDICION", "demo")
    # Se antedata la primera vez: la prueba empezó hace un mes.
    (entorno / "primera_vez.json").write_text(json.dumps(
        {"fecha": (datetime.now(UTC) - timedelta(days=30)).isoformat()}),
        encoding="utf-8")
    e = licencia.estado()
    assert e.activa is False
    assert "prueba" in e.motivo.lower()


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------
def test_cliente_sin_clave_esta_cerrado(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_EDICION", "cliente")
    e = licencia.estado()
    assert e.activa is False
    assert "clave" in e.motivo.lower()


def test_una_clave_emitida_por_el_dueno_abre_el_programa(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_EDICION", "cliente")
    clave = licencia.emitir("comprador@ejemplo.com", meses=12)
    assert licencia.guardar_clave(clave)["ok"] is True

    e = licencia.estado()
    assert e.activa is True
    assert e.email == "comprador@ejemplo.com"
    assert e.dias_restantes > 300


def test_una_clave_inventada_no_pasa(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_EDICION", "cliente")
    for basura in ("", "cualquier-cosa", "a.b", "eyJhIjoxfQ.firmafalsa"):
        assert licencia.verificar(basura)["ok"] is False
    assert licencia.guardar_clave("no-sirve")["ok"] is False
    assert licencia.estado().activa is False


def test_una_clave_de_OTRO_secreto_no_pasa():
    """El corazón del asunto: sin el secreto del dueño no se pueden fabricar
    claves. Si esto se rompe, cualquiera se emite la suya."""
    ajena = licencia.emitir("vivo@ejemplo.com", meses=12, secreto="otro-secreto")
    assert licencia.verificar(ajena)["ok"] is False


def test_una_clave_manoseada_no_pasa():
    clave = licencia.emitir("comprador@ejemplo.com", meses=12)
    datos, firma = clave.split(".")
    # Cambiarle el correo al cuerpo invalida la firma.
    import base64
    cuerpo = json.loads(base64.urlsafe_b64decode(datos + "=" * (-len(datos) % 4)))
    cuerpo["email"] = "otro@ejemplo.com"
    nuevo = base64.urlsafe_b64encode(
        json.dumps(cuerpo, separators=(",", ":"), sort_keys=True).encode()
    ).decode().rstrip("=")
    assert licencia.verificar(f"{nuevo}.{firma}")["ok"] is False


def test_una_licencia_vencida_se_rechaza_y_lo_dice(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_EDICION", "cliente")
    # Un mes negativo emite con fecha pasada.
    clave = licencia.emitir("viejo@ejemplo.com", meses=-1)
    r = licencia.verificar(clave)
    assert r["ok"] is False
    assert "venció" in r["motivo"]


def test_sin_secreto_el_programa_no_valida_nada(monkeypatch):
    """Un instalador mal armado (sin con qué verificar) no puede quedar
    abierto: sin secreto, ninguna clave sirve."""
    monkeypatch.setenv("MVCLIENTE_EDICION", "cliente")
    clave = licencia.emitir("x@y.com", meses=12)
    monkeypatch.delenv("MVCLIENTE_LICENCIA_SECRETO")
    monkeypatch.delenv("MVCLIENTE_OWNER", raising=False)
    assert licencia.verificar(clave)["ok"] is False
    assert licencia.estado().activa is False


# ---------------------------------------------------------------------------
# La puerta del backend
# ---------------------------------------------------------------------------
def test_el_backend_traba_las_busquedas_reales_sin_licencia(monkeypatch):
    """En el programa instalado, una corrida real con la licencia vencida
    tiene que dar 402 — y la demo sintética tiene que seguir libre."""
    from fastapi.testclient import TestClient

    from webapp.backend import api

    monkeypatch.setattr(api, "SIN_ESTADO", False)
    monkeypatch.setattr(api.licencia, "estado", lambda: licencia.Estado(
        "demo", False, "2026-01-01", 0, "", "La prueba de 14 días terminó."))
    cliente = TestClient(api.app)

    r = cliente.post("/api/corridas", json={
        "dominio": "mvkobranzaia.com", "modo": "web", "prospectos": 10})
    assert r.status_code == 402
    assert "prueba" in r.json()["detail"].lower()

    # La demo sintética es la vidriera: nunca se traba.
    assert cliente.post("/api/corridas", json={
        "dominio": "mvkobranzaia.com", "modo": "demo",
        "prospectos": 10}).status_code == 200


def test_la_web_no_usa_licencias(monkeypatch):
    """En serverless manda el cupo gratis; /api/licencia lo dice y no
    pretende que la web tenga una edición instalada."""
    from fastapi.testclient import TestClient

    from webapp.backend import api

    monkeypatch.setattr(api, "SIN_ESTADO", True)
    d = TestClient(api.app).get("/api/licencia").json()
    assert d == {"aplica": False, "edicion": "web"}
