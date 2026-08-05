"""
La regla del producto: el país que elige el cliente primero, después el resto
de su región, después el mundo. Es la que más fácil se rompe sin querer al
tocar el catálogo, así que se verifica sola, sin pasar por el pipeline.

Ojo con lo que verifican estos tests: que la prioridad sea RELATIVA. Cablear
un país (antes era Uruguay) rompe el producto para todos los demás clientes.
"""
from __future__ import annotations

import pytest

from cliente_ia import geo


def test_el_pais_base_es_el_unico_local():
    for base in ("UY", "DE", "JP", "US"):
        olas = geo.orden_de_olas(base)
        assert olas[0] == (geo.NIVEL_LOCAL, 1, [base])


def test_ningun_pais_del_catalogo_es_local_por_si_solo():
    """Nadie tiene prioridad 1 salvo el que eligió el cliente."""
    for codigo in geo.CATALOGO:
        if codigo != "DE":
            assert geo.nivel_de(codigo, "DE") != geo.NIVEL_LOCAL


def test_pesos_ordenados_local_regional_mundo():
    # Visto desde Uruguay.
    assert geo.peso_de("UY", "UY") > geo.peso_de("BR", "UY") > geo.peso_de("US", "UY")
    assert geo.peso_de("UY", "UY") == 1.0
    # Y visto desde Alemania se da vuelta: el peso 1.00 lo tiene Alemania y
    # Brasil pasa a ser "mundo".
    assert geo.peso_de("DE", "DE") > geo.peso_de("FR", "DE") > geo.peso_de("BR", "DE")
    assert geo.peso_de("DE", "DE") == 1.0


@pytest.mark.parametrize("base,pais,nivel", [
    ("UY", "UY", geo.NIVEL_LOCAL),
    ("UY", "AR", geo.NIVEL_REGIONAL),
    ("UY", "DE", geo.NIVEL_MUNDO),
    ("DE", "DE", geo.NIVEL_LOCAL),
    ("DE", "ES", geo.NIVEL_REGIONAL),
    ("DE", "UY", geo.NIVEL_MUNDO),
    ("JP", "SG", geo.NIVEL_REGIONAL),
    ("JP", "AU", geo.NIVEL_MUNDO),
])
def test_nivel_relativo_al_pais_base(base, pais, nivel):
    assert geo.nivel_de(pais, base) == nivel


@pytest.mark.parametrize("base", ["UY", "BR", "US", "DE", "ZA", "AU", "IN"])
def test_las_tres_olas_cubren_todo_el_catalogo(base):
    olas = geo.orden_de_olas(base)
    assert [nivel for nivel, _, _ in olas] == list(geo.NIVELES)
    assert [prioridad for _, prioridad, _ in olas] == [1, 2, 3]
    codigos = [c for _, _, cods in olas for c in cods]
    assert sorted(codigos) == sorted(geo.CATALOGO)
    assert len(codigos) == len(set(codigos)), "un país no puede estar en dos olas"


def test_el_alias_viejo_de_la_ola_regional_sigue_entendiendose():
    # Las corridas guardadas antes de que el país base fuera elegible dicen
    # "latam" donde ahora va "regional".
    assert geo.normalizar_nivel("latam") == geo.NIVEL_REGIONAL
    assert geo.normalizar_nivel("local") == geo.NIVEL_LOCAL
    assert geo.normalizar_nivel("") == geo.NIVEL_MUNDO


@pytest.mark.parametrize("pais,idioma", [
    ("UY", "es"), ("AR", "es"), ("MX", "es"), ("ES", "es"),
    ("BR", "pt"), ("PT", "pt"), ("AO", "pt"),
    ("US", "en"), ("GB", "en"), ("DE", "en"), ("JP", "en"),
])
def test_idioma_por_pais(pais, idioma):
    assert geo.idioma_de(pais) == idioma


def test_todo_pais_habla_uno_de_los_tres_idiomas():
    for codigo in geo.CATALOGO:
        assert geo.idioma_de(codigo) in geo.IDIOMAS


def test_todo_pais_tiene_region_conocida_y_ciudad():
    for pais in geo.CATALOGO.values():
        assert pais.region in geo.REGIONES, pais.codigo
        assert pais.capital, pais.codigo


def test_el_catalogo_es_mundial_no_solo_latam():
    # Lo que el usuario pidió: cualquier país del mundo tiene que poder ser el
    # mercado propio, no sólo los de la región de casa.
    por_region = {r: len(geo.paises_por_region(r)) for r in geo.REGIONES}
    assert all(n >= 2 for n in por_region.values()), por_region
    assert len(geo.CATALOGO) >= 90


def test_los_paises_tienen_nombre_en_los_tres_idiomas():
    for codigo in geo.CATALOGO:
        for idioma in geo.IDIOMAS:
            assert geo.nombre_pais(codigo, idioma).strip(), (codigo, idioma)
    # Y donde el nombre cambia de verdad, cambia: un selector mundial que
    # dice "Alemania" en la interfaz en inglés delata el producto.
    assert geo.nombre_pais("DE", "en") == "Germany"
    assert geo.nombre_pais("DE", "pt") == "Alemanha"
    assert geo.nombre_pais("BR", "en") == "Brazil"


def test_no_hay_traducciones_para_paises_que_no_existen():
    """Una entrada con un código mal escrito no traduce nada y no se ve."""
    for idioma, nombres in geo.NOMBRE_PAIS.items():
        sobrantes = set(nombres) - set(geo.CATALOGO)
        assert not sobrantes, (idioma, sobrantes)


@pytest.mark.parametrize("dominio,esperado", [
    ("banco.com.uy", "UY"),
    ("financiera.uy", "UY"),
    ("fintech.com.br", "BR"),
    ("empresa.co.uk", "GB"),
    ("cosa.com.ar", "AR"),
    ("firma.de", "DE"),
    ("kaisha.co.jp", "JP"),
])
def test_pais_por_tld(dominio, esperado):
    assert geo.pais_de_dominio(dominio).codigo == esperado


def test_tld_generico_no_inventa_pais():
    # mvkobranzaia.com no dice nada del mercado: tiene que devolver None y
    # dejar que lo decida la investigación de la fase 1.
    assert geo.pais_de_dominio("mvkobranzaia.com") is None
    # ".co" se vende como genérico: una startup con ".co" no es colombiana.
    assert geo.pais_de_dominio("startup.co") is None
    assert geo.pais_de_dominio("empresa.com.co").codigo == "CO"


def test_pais_desconocido_no_rompe():
    p = geo.obtener("XX")
    assert p.idioma == "en"
    assert geo.nivel_de("XX", "UY") == geo.NIVEL_MUNDO


def test_resolver_base_respeta_al_cliente_antes_que_al_tld():
    # Si el cliente eligió, manda su elección aunque el dominio diga otra cosa.
    assert geo.resolver_base("DE", "empresa.com.uy", "es").codigo == "DE"
    # Sin elección, el TLD.
    assert geo.resolver_base("", "empresa.com.uy", "en").codigo == "UY"
    # Sin elección ni TLD nacional, el idioma de la interfaz.
    assert geo.resolver_base("", "producto.com", "pt").codigo == "BR"
    assert geo.resolver_base("", "producto.com", "en").codigo == "US"
