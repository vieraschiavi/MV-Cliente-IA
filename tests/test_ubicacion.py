"""Ubicación hasta el barrio: dirección publicada → ciudad y barrio."""
from __future__ import annotations

import json

import pytest

from cliente_ia import ubicacion
from cliente_ia.modelos import Prospecto

JSONLD = """<html><head><script type="application/ld+json">
{"@context":"https://schema.org","@graph":[{"@type":"WebSite","name":"X"},
 {"@type":"LocalBusiness","name":"Estudio X","address":{"@type":"PostalAddress",
  "streetAddress":"Av. Brasil 2550","addressLocality":"Montevideo",
  "addressCountry":{"@type":"Country","name":"Uruguay"}}}]}
</script></head><body>hola</body></html>"""

RESPUESTA_POCITOS = json.dumps([{"address": {
    "road": "Avenida Brasil", "suburb": "Pocitos", "city": "Montevideo",
    "country_code": "uy"}}])


@pytest.fixture
def nominatim(monkeypatch):
    """Nominatim falso que anota cada URL pedida; geocodificación prendida."""
    pedidos: list[str] = []
    monkeypatch.setenv("MVCLIENTE_GEOCODIFICAR", "1")
    monkeypatch.setattr(ubicacion, "ESPERA_ENTRE_PEDIDOS", 0)
    monkeypatch.setattr(ubicacion, "_cache", {})
    from cliente_ia.proveedores import web

    def bajar(url, timeout=0):
        pedidos.append(url)
        return RESPUESTA_POCITOS
    monkeypatch.setattr(web, "bajar", bajar)
    return pedidos


def test_lee_la_postaladdress_del_jsonld_aunque_este_anidada():
    d = ubicacion.direccion_de_html(JSONLD)
    assert d == {"calle": "Av. Brasil 2550", "ciudad": "Montevideo", "pais": "Uruguay"}


def test_lee_microdatos_y_la_etiqueta_address():
    micro = ('<div itemprop="streetAddress">Rua Augusta 100</div>'
             '<span itemprop="addressLocality">São Paulo</span>')
    assert ubicacion.direccion_de_html(micro) == {"calle": "Rua Augusta 100",
                                                  "ciudad": "São Paulo"}
    assert ubicacion.direccion_de_html(
        "<address>Calle Serrano 45, Madrid</address>") == {"calle": "Calle Serrano 45, Madrid"}


def test_un_address_con_solo_un_correo_no_es_una_direccion():
    assert ubicacion.direccion_de_html("<address>info@x.com</address>") == {}
    assert ubicacion.direccion_de_html("<p>sin dirección</p>") == {}


def test_jsonld_roto_no_rompe_y_sigue_buscando():
    html = ('<script type="application/ld+json">{roto</script>'
            '<address>Av. Corrientes 1234, Buenos Aires</address>')
    assert ubicacion.direccion_de_html(html)["calle"].startswith("Av. Corrientes")


def test_geocodifica_hasta_el_barrio_con_el_idioma_y_el_pais(nominatim):
    u = ubicacion.ubicar(JSONLD, "UY")
    assert u == {"direccion": "Av. Brasil 2550, Montevideo", "ciudad": "Montevideo",
                 "barrio": "Pocitos", "pais": "UY"}
    assert "countrycodes=uy" in nominatim[0]
    assert "accept-language=es" in nominatim[0]


def test_repetir_la_misma_direccion_no_vuelve_a_consultar(nominatim):
    ubicacion.ubicar(JSONLD, "UY")
    ubicacion.ubicar(JSONLD, "UY")
    assert len(nominatim) == 1


def test_apagado_usa_solo_la_ciudad_que_declara_el_sitio(nominatim, monkeypatch):
    monkeypatch.setenv("MVCLIENTE_GEOCODIFICAR", "0")
    u = ubicacion.ubicar(JSONLD, "UY")
    assert u == {"direccion": "Av. Brasil 2550, Montevideo", "ciudad": "Montevideo"}
    assert nominatim == []


def test_sin_red_no_inventa_barrio(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_GEOCODIFICAR", "1")
    monkeypatch.setattr(ubicacion, "ESPERA_ENTRE_PEDIDOS", 0)
    monkeypatch.setattr(ubicacion, "_cache", {})
    from cliente_ia.proveedores import web

    def caida(url, timeout=0):
        raise OSError("sin red")
    monkeypatch.setattr(web, "bajar", caida)
    u = ubicacion.ubicar(JSONLD, "UY")
    assert "barrio" not in u and u["ciudad"] == "Montevideo"


def test_un_sitio_sin_direccion_queda_sin_ubicacion(nominatim):
    assert ubicacion.ubicar("<p>100 % online</p>", "UY") == {}
    assert nominatim == []


def _prospecto(i: int) -> Prospecto:
    return Prospecto(id=f"p{i}", nombre=f"E{i}", dominio=f"e{i}.com.uy", sector="s",
                     pais="UY", ciudad="Canelones", sintetico=False)


def test_la_ciudad_medida_reemplaza_a_la_propuesta_y_el_tope_cuenta_intentos(
        nominatim, monkeypatch):
    from cliente_ia.proveedores import contactos
    monkeypatch.setattr(contactos, "MAX_GEOCODIFICAR", 2)
    # Direcciones distintas, para que la caché no ahorre pedidos.
    pares = [(_prospecto(i), JSONLD.replace("2550", str(2550 + i))) for i in range(4)]
    contactos._ubicar(pares)
    assert len(nominatim) == 2
    p0 = pares[0][0]
    assert (p0.ciudad, p0.barrio) == ("Montevideo", "Pocitos")
    # Pasado el tope: la ciudad que declara el sitio, sin barrio inventado.
    p3 = pares[3][0]
    assert (p3.ciudad, p3.barrio) == ("Montevideo", "")
    assert p3.direccion.startswith("Av. Brasil")


def test_demo_marca_barrio_sintetico_estable_y_de_la_ciudad(corrida_kobra):
    from cliente_ia.proveedores.demo import semilla
    barrios = semilla()["barrios"]
    con_barrio = [p for p in corrida_kobra.prospectos if p.barrio]
    assert con_barrio, "la demo tiene que mostrar barrios"
    for p in con_barrio:
        assert p.sintetico
        assert p.barrio in barrios[p.ciudad]
    from cliente_ia import pipeline
    otra = pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                             limite_prospectos=60, nombre="MV Kobra AI")
    assert [p.barrio for p in otra.prospectos] == [p.barrio for p in corrida_kobra.prospectos]
