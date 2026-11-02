"""Clave de IA rechazada por el proveedor.

Caso real (captura del dueño, desde el celular): con una clave de Claude que
Anthropic ya no aceptaba, la pantalla mostraba el JSON crudo del 401 dos
veces y, debajo, el cartel «algunas fases con IA fallaron y se cubrieron con
datos sintéticos» — cuando en realidad la búsqueda se había cortado. Además
el motor hacía DOS llamadas con la clave mala (perfilar y competencia) antes
de rendirse. Estos tests fijan lo que tiene que pasar en su lugar.
"""
from __future__ import annotations

import io
import urllib.error

import pytest

from cliente_ia import modelos, pipeline
from cliente_ia.proveedores import llm
from cliente_ia.proveedores.base import Proveedor, ProveedorEncadenado

HTML_SITIO = """
<html><head><title>MV Kobra AI</title>
<meta name="description" content="Software de gestión de cobranzas con IA.">
</head><body><h1>MV Kobra AI</h1></body></html>
"""


def _http_error(codigo: int, cuerpo: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.x", codigo, "err", {},
                                  io.BytesIO(cuerpo.encode()))


@pytest.mark.parametrize("codigo, cuerpo", [
    (401, '{"type":"error","error":{"type":"authentication_error",'
          '"message":"invalid x-api-key"}}'),
    (403, '{"error":{"type":"permission_error"}}'),
    (400, '{"error":{"status":"INVALID_ARGUMENT","details":[{"reason":"API_KEY_INVALID"}]}}'),
])
def test_un_rechazo_de_clave_sale_como_error_de_clave(monkeypatch, codigo, cuerpo):
    p = llm.ProveedorLLM("es", clave="sk-ant-mala", proveedor="claude")

    def urlopen_falso(*_a, **_k):
        raise _http_error(codigo, cuerpo)

    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen_falso)
    with pytest.raises(llm.ErrorClaveIA) as e:
        p._post_json("https://api.anthropic.com/v1/messages", {}, {})
    texto = str(e.value)
    assert texto.startswith("[clave_ia_invalida:claude]")
    assert "console.anthropic.com" in texto
    assert "sk-ant-mala" not in texto          # la clave nunca va al mensaje
    assert "authentication_error" not in texto  # nada de JSON crudo


def test_un_400_cualquiera_no_es_culpa_de_la_clave(monkeypatch):
    p = llm.ProveedorLLM("es", clave="sk-ant-buena", proveedor="claude")
    monkeypatch.setattr(llm.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(
                            _http_error(400, '{"error":"max_tokens demasiado alto"}')))
    with pytest.raises(llm.ErrorLLM) as e:
        p._post_json("https://api.anthropic.com/v1/messages", {}, {})
    assert not isinstance(e.value, llm.ErrorClaveIA)


def test_el_boton_actualizar_modelos_tambien_dice_que_es_la_clave(monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(
                            _http_error(401, '{"error":"invalid x-api-key"}')))
    with pytest.raises(llm.ErrorClaveIA) as e:
        llm.listar_modelos("claude", "sk-ant-mala")
    assert str(e.value).startswith("[clave_ia_invalida:claude]")


def test_la_cadena_no_tapa_una_clave_rechazada_con_otro_proveedor():
    """Aunque el proveedor no sea el decisivo, una clave rechazada no se
    cubre con datos sintéticos: hay que cambiar la clave, no seguir."""
    class ConClaveMala(Proveedor):
        nombre = "llm"

        def competencia(self, empresa):
            raise llm.ErrorClaveIA("claude", 401)

    class Respaldo(Proveedor):
        nombre = "demo"

        def competencia(self, empresa):
            return [modelos.Competidor(dominio="inventado.com")]

    cadena = ProveedorEncadenado(ConClaveMala(), Respaldo())
    with pytest.raises(llm.ErrorClaveIA):
        cadena.competencia(modelos.Empresa(dominio="x.com"))


def test_la_corrida_corta_en_la_primera_llamada_con_un_mensaje_y_sin_cartel(monkeypatch):
    llamadas = []

    def pedir_falso(self, prompt, max_tokens=8000):
        llamadas.append(prompt[:20])
        raise llm.ErrorClaveIA("claude", 401)

    monkeypatch.setattr("cliente_ia.proveedores.web.bajar", lambda url, timeout=12: HTML_SITIO)
    monkeypatch.setattr(llm.ProveedorLLM, "_pedir_una_vez", pedir_falso)

    c = pipeline.ejecutar("mvkobranzaia.com", modo="llm", clave_ia="sk-ant-mala",
                          limite_prospectos=5, limite_emails=2)

    assert c.estado == "error"
    assert c.error.startswith("[clave_ia_invalida:claude]")   # sin «ErrorClaveIA:»
    assert len(llamadas) == 1, "siguió llamando a la IA con una clave que ya rechazó"
    # Nada de «se cubrieron con datos sintéticos»: no se cubrió nada.
    assert not [a for a in c.avisos if a.tipo == modelos.AVISO_FALLO]
    assert c.competidores == []
