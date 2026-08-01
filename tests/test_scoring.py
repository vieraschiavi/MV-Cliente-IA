"""
El scoring es lo que decide a quién se le escribe primero. Se testea la
fórmula pieza por pieza y, sobre todo, que el peso geográfico mande.
"""
from __future__ import annotations

from cliente_ia import scoring
from cliente_ia.modelos import Decisor, Empresa, Prospecto

EMPRESA = Empresa(
    dominio="mvkobranzaia.com", nombre="MV Kobra AI",
    sectores_objetivo=["Bancos y banca minorista", "Financieras y casas de crédito al consumo"],
    tamano_objetivo="50-6000 empleados",
)


def _prospecto(**kw):
    base = {"id": "p1", "nombre": "Ejemplo S.A.", "dominio": "ejemplo.com.uy",
            "sector": "Bancos y banca minorista", "pais": "UY",
            "empleados": 500, "senales": []}
    base.update(kw)
    return Prospecto(**base)


def test_sector_exacto_vale_mas_que_parecido_y_que_ajeno():
    exacto = scoring.ajuste_sector("Bancos y banca minorista", EMPRESA.sectores_objetivo)
    parecido = scoring.ajuste_sector("Bancos cooperativos", EMPRESA.sectores_objetivo)
    ajeno = scoring.ajuste_sector("Astilleros", EMPRESA.sectores_objetivo)
    assert exacto > parecido > ajeno


def test_tamano_dentro_del_rango_vale_uno_y_afuera_baja():
    assert scoring.ajuste_tamano(500, "50-6000 empleados") == 1.0
    assert scoring.ajuste_tamano(5, "50-6000 empleados") < 0.2
    assert scoring.ajuste_tamano(60000, "50-6000 empleados") < 0.2


def test_senales_saturan_en_uno():
    assert scoring.ajuste_senales([]) == 0.0
    assert scoring.ajuste_senales(["a"]) < scoring.ajuste_senales(["a", "b"])
    assert scoring.ajuste_senales(["a", "b", "c", "d", "e"]) == 1.0


def test_mencion_a_competidor_suma():
    con = scoring.ajuste_competencia(["evalúa CollectWise para su cartera"], ["CollectWise"])
    sin = scoring.ajuste_competencia(["creció su cartera"], ["CollectWise"])
    assert con == 1.0 and sin == 0.0


def test_uruguayo_le_gana_a_identico_de_afuera():
    """El corazón de la regla: mismo ICP, distinto país, distinto orden."""
    uy = scoring.puntuar_prospecto(_prospecto(id="uy", pais="UY"), EMPRESA)
    br = scoring.puntuar_prospecto(_prospecto(id="br", pais="BR"), EMPRESA)
    us = scoring.puntuar_prospecto(_prospecto(id="us", pais="US"), EMPRESA)
    assert uy.score > br.score > us.score
    assert (uy.nivel, br.nivel, us.nivel) == ("local", "latam", "mundo")
    assert (uy.idioma, br.idioma, us.idioma) == ("es", "pt", "en")


def test_orden_respeta_la_ola_aunque_el_de_afuera_sea_mejor():
    """
    Un prospecto perfecto de Estados Unidos NO puede colarse antes que uno
    uruguayo flojo: el orden es por ola primero y por score adentro. Si esto
    se rompe, el producto dejó de priorizar Uruguay.
    """
    uy_flojo = scoring.puntuar_prospecto(
        _prospecto(id="uy", pais="UY", sector="Astilleros", empleados=3), EMPRESA)
    us_perfecto = scoring.puntuar_prospecto(
        _prospecto(id="us", pais="US", empleados=500,
                   senales=["a", "b", "c", "evalúa CollectWise"]), EMPRESA)
    assert us_perfecto.score > uy_flojo.score          # gana por calidad…
    orden = scoring.ordenar_prospectos([us_perfecto, uy_flojo])
    assert [p.id for p in orden] == ["uy", "us"]       # …pero el orden es por ola


def test_seniority_ordena_dentro_de_la_misma_empresa():
    p = scoring.puntuar_prospecto(_prospecto(), EMPRESA)
    jefe = scoring.puntuar_decisor(
        Decisor(id="d1", prospecto_id="p1", nombre="A B", cargo="Chief Risk Officer",
                empresa="Ejemplo", pais="UY", seniority="c-level"), p)
    analista = scoring.puntuar_decisor(
        Decisor(id="d2", prospecto_id="p1", nombre="C D", cargo="Analista",
                empresa="Ejemplo", pais="UY", seniority="analista"), p)
    assert jefe.score > analista.score
