"""
Redes sociales: lo que se automatiza de verdad y lo que no.

La regla que estos tests cuidan es una sola y es de confianza: **ninguna
clave del usuario puede salir en un detalle de error**, porque esos detalles
viajan al comprobante por correo y a la pantalla.
"""
from __future__ import annotations

import json
import urllib.request

import pytest

from cliente_ia import redes

CLAVES_X = redes.ClavesX("ck-123", "cs-456", "at-789", "as-000")
CLAVES_LI = redes.ClavesLinkedIn("unipile", "api1.unipile.com:13111",
                                 "llave-secreta-larga", "cuenta-abc")


class _Respuesta:
    """Respuesta mínima con la forma que espera json.load()."""

    def __init__(self, datos):
        self._crudo = json.dumps(datos).encode()

    def read(self):
        return self._crudo

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _responder(monkeypatch, datos, capturar=None):
    def falso(peticion, timeout=None):
        if capturar is not None:
            capturar.append(peticion)
        return _Respuesta(datos)
    monkeypatch.setattr(urllib.request, "urlopen", falso)


def _reventar(monkeypatch, mensaje):
    def falso(*_a, **_k):
        raise RuntimeError(mensaje)
    monkeypatch.setattr(urllib.request, "urlopen", falso)


# ---------------------------------------------------------------------------
# X
# ---------------------------------------------------------------------------
def test_publicar_en_x_devuelve_el_enlace(monkeypatch):
    peticiones = []
    _responder(monkeypatch, {"data": {"id": "1899", "text": "hola"}}, peticiones)
    r = redes.publicar_en_x(CLAVES_X, "hola")
    assert r == {"ok": True, "id": "1899",
                 "url": "https://x.com/i/status/1899", "detalle": ""}
    # La firma va en la cabecera y lleva los seis campos obligatorios.
    cabecera = peticiones[0].headers["Authorization"]
    for campo in ("oauth_consumer_key", "oauth_nonce", "oauth_signature",
                  "oauth_signature_method", "oauth_timestamp", "oauth_token"):
        assert campo in cabecera
    assert "cs-456" not in cabecera and "as-000" not in cabecera


def test_metricas_de_x_trae_los_numeros_de_cada_post(monkeypatch):
    _responder(monkeypatch, {"data": [
        {"id": "1", "created_at": "2026-08-01T10:00:00Z",
         "public_metrics": {"impression_count": 1200, "like_count": 34,
                            "reply_count": 5, "retweet_count": 7,
                            "quote_count": 1, "bookmark_count": 9}},
    ]})
    m = redes.metricas_de_x(CLAVES_X, ["1"])
    assert m["1"]["ok"] is True
    assert m["1"]["impresiones"] == 1200
    assert m["1"]["likes"] == 34
    assert m["1"]["respuestas"] == 5


def test_un_post_borrado_igual_aparece_en_el_panel(monkeypatch):
    """X devuelve los ids que no puede resolver en `errors`. Si se ignoran, el
    panel muestra una fila vacía sin explicación."""
    _responder(monkeypatch, {
        "data": [{"id": "1", "public_metrics": {"like_count": 2}}],
        "errors": [{"value": "2", "detail": "Could not find tweet with id: 2"}],
    })
    m = redes.metricas_de_x(CLAVES_X, ["1", "2"])
    assert m["1"]["ok"] is True
    assert m["2"]["ok"] is False
    assert "Could not find" in m["2"]["detalle"]


def test_las_metricas_se_piden_de_a_cien(monkeypatch):
    """Mil posts no pueden ser mil peticiones: el endpoint acepta 100 por
    llamada y así se usa."""
    peticiones = []
    _responder(monkeypatch, {"data": []}, peticiones)
    redes.metricas_de_x(CLAVES_X, [str(i) for i in range(250)])
    assert len(peticiones) == 3


def test_un_error_de_x_no_filtra_las_claves(monkeypatch):
    _reventar(monkeypatch, "rechazado: at-789 firmado con as-000 y cs-456")
    r = redes.publicar_en_x(CLAVES_X, "hola")
    assert r["ok"] is False
    for secreto in ("ck-123", "cs-456", "at-789", "as-000"):
        assert secreto not in r["detalle"]

    _reventar(monkeypatch, "rechazado: at-789 y cs-456")
    m = redes.metricas_de_x(CLAVES_X, ["1"])
    for secreto in ("cs-456", "at-789"):
        assert secreto not in m["1"]["detalle"]


# ---------------------------------------------------------------------------
# LinkedIn
# ---------------------------------------------------------------------------
def test_enviar_linkedin_habla_con_el_proveedor_del_usuario(monkeypatch):
    peticiones = []
    _responder(monkeypatch, {"chat_id": "chat-1", "message_id": "msg-1"}, peticiones)
    r = redes.enviar_linkedin(CLAVES_LI, "ACoAAB123", "Hola Elena")
    assert r["ok"] is True and r["id"] == "chat-1"

    p = peticiones[0]
    assert p.full_url == "https://api1.unipile.com:13111/api/v1/chats"
    assert p.headers["X-api-key"] == "llave-secreta-larga"
    cuerpo = p.data.decode()
    assert "ACoAAB123" in cuerpo and "Hola Elena" in cuerpo
    assert "cuenta-abc" in cuerpo


def test_linkedin_sin_destinatario_no_llama_al_proveedor(monkeypatch):
    """Un prospecto sin identificador de LinkedIn no puede gastar una llamada
    (el proveedor las cobra) ni contarse como enviado."""
    _reventar(monkeypatch, "no se tendría que haber llamado")
    r = redes.enviar_linkedin(CLAVES_LI, "", "Hola")
    assert r["ok"] is False
    assert "identificador" in r["detalle"]


def test_proveedor_de_linkedin_desconocido_se_rechaza():
    claves = redes.ClavesLinkedIn("magia", "x.com", "k", "a")
    r = redes.enviar_linkedin(claves, "abc", "Hola")
    assert r["ok"] is False and "magia" in r["detalle"]


def test_un_error_de_linkedin_no_filtra_la_clave(monkeypatch):
    _reventar(monkeypatch, "401: llave-secreta-larga inválida para cuenta-abc")
    r = redes.enviar_linkedin(CLAVES_LI, "abc", "Hola")
    assert r["ok"] is False
    assert "llave-secreta-larga" not in r["detalle"]
    assert "cuenta-abc" not in r["detalle"]


@pytest.mark.parametrize("dsn", [
    "api1.unipile.com:13111",
    "https://api1.unipile.com:13111",
    "https://api1.unipile.com:13111/",
])
def test_el_dsn_se_acepta_como_lo_pegue_el_usuario(monkeypatch, dsn):
    """El proveedor muestra el DSN con y sin https; pegarlo como venga no
    puede terminar en una URL rota."""
    peticiones = []
    _responder(monkeypatch, {"chat_id": "c"}, peticiones)
    claves = redes.ClavesLinkedIn("unipile", dsn, "k" * 10, "cuenta")
    redes.enviar_linkedin(claves, "abc", "Hola")
    assert peticiones[0].full_url == "https://api1.unipile.com:13111/api/v1/chats"
