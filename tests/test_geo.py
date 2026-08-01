"""
La regla del producto: Uruguay primero, después LATAM, después el mundo.
Es la que más fácil se rompe sin querer al tocar el catálogo, así que se
verifica sola, sin pasar por el pipeline.
"""
from __future__ import annotations

import pytest

from cliente_ia import geo


def test_uruguay_es_el_unico_de_prioridad_1():
    locales = [p for p in geo.CATALOGO.values() if p.prioridad == geo.PRIORIDAD_LOCAL]
    assert [p.codigo for p in locales] == ["UY"]


def test_pesos_ordenados_uy_latam_mundo():
    assert (geo.peso_de("UY") > geo.peso_de("BR") > geo.peso_de("US"))
    assert geo.peso_de("UY") == 1.0


def test_las_tres_olas_cubren_todo_el_catalogo():
    olas = geo.orden_de_olas()
    assert [nivel for nivel, _, _ in olas] == ["local", "latam", "mundo"]
    assert [prioridad for _, prioridad, _ in olas] == [1, 2, 3]
    codigos = [c for _, _, cods in olas for c in cods]
    assert sorted(codigos) == sorted(geo.CATALOGO)
    assert len(codigos) == len(set(codigos)), "un país no puede estar en dos olas"


@pytest.mark.parametrize("pais,idioma", [
    ("UY", "es"), ("AR", "es"), ("MX", "es"),
    ("BR", "pt"), ("PT", "pt"),
    ("US", "en"), ("GB", "en"), ("DE", "en"),
])
def test_idioma_por_pais(pais, idioma):
    assert geo.idioma_de(pais) == idioma


def test_todo_pais_habla_uno_de_los_tres_idiomas():
    for codigo in geo.CATALOGO:
        assert geo.idioma_de(codigo) in geo.IDIOMAS


@pytest.mark.parametrize("dominio,esperado", [
    ("banco.com.uy", "UY"),
    ("financiera.uy", "UY"),
    ("fintech.com.br", "BR"),
    ("empresa.co.uk", "GB"),
    ("cosa.com.ar", "AR"),
])
def test_pais_por_tld(dominio, esperado):
    assert geo.pais_de_dominio(dominio).codigo == esperado


def test_tld_generico_no_inventa_pais():
    # mvkobranzaia.com no dice nada del mercado: tiene que devolver None y
    # dejar que lo decida la investigación de la fase 1.
    assert geo.pais_de_dominio("mvkobranzaia.com") is None


def test_pais_desconocido_cae_en_mundo_sin_romper():
    p = geo.obtener("XX")
    assert p.prioridad == geo.PRIORIDAD_MUNDO
    assert p.idioma == "en"
