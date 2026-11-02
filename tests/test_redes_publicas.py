"""Métricas públicas de redes de competidores: parseo, límites y honestidad."""
from __future__ import annotations

import pytest

from cliente_ia import redes_publicas as rp
from cliente_ia.modelos import Competidor


@pytest.fixture(autouse=True)
def prendido(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_METRICAS_REDES", "1")
    monkeypatch.setattr(rp, "PAUSA_MISMA_RED", 0)


@pytest.mark.parametrize("texto,sufijo,esperado", [
    ("7.150.164", "", 7_150_164),
    ("7,150,164", "", 7_150_164),
    ("2,2", "M", 2_200_000),
    ("1.5", "K", 1_500),
    ("15", "mil", 15_000),
    ("1,2", "mi", 1_200_000),
    ("96", "M", 96_000_000),
    ("412", "", 412),
])
def test_lee_los_numeros_como_los_escribe_cada_idioma(texto, sufijo, esperado):
    assert rp.numero(texto, sufijo) == esperado


@pytest.mark.parametrize("descripcion,seguidores,publicaciones", [
    ("NASA | 7.150.164 seguidores en LinkedIn. Explore…", 7_150_164, None),
    ("Acme | 12,345 followers on LinkedIn. We build…", 12_345, None),
    ("96M Followers, 77 Following, 4,290 Posts - See Instagram photos", 96_000_000, 4_290),
    ("15 mil seguidores, 300 seguidos, 1.204 publicaciones - Ver fotos", 15_000, 1_204),
    ("1,2 mi seguidores, 80 seguindo, 950 publicações", 1_200_000, 950),
])
def test_lee_la_descripcion_de_linkedin_e_instagram(descripcion, seguidores, publicaciones):
    html = f'<head><meta property="og:description" content="{descripcion}"></head>'
    m = rp.de_descripcion(html)
    assert m.get("seguidores") == seguidores
    assert m.get("publicaciones") == publicaciones


def test_tiktok_toma_las_cifras_del_perfil_pedido_y_no_de_una_sugerida():
    html = ('{"uniqueId":"otra","stats":{"followerCount":9,"heartCount":9,"videoCount":9}}'
            '{"userInfo":{"user":{"uniqueId":"acme"},'
            '"stats":{"followerCount":2200000,"heartCount":11500000,"videoCount":62},'
            '"statsV2":{"followerCount":"2153136","heartCount":"11488833","videoCount":"62"}}}')
    assert rp.de_tiktok(html, "acme") == {"seguidores": 2_153_136, "publicaciones": 62,
                                          "me_gusta": 11_488_833}
    assert rp.de_tiktok(html, "nadie") == {}


def _comp(i: int, **redes) -> Competidor:
    return Competidor(dominio=f"c{i}.com", nombre=f"C{i}", posicionamiento="", redes=redes)


def test_cada_cifra_lleva_fuente_fecha_y_estado():
    c = _comp(1, linkedin="https://www.linkedin.com/company/c1/")
    n = rp.medir([c], bajar=lambda url, t=0:
                 '<meta name="description" content="C1 | 3.400 seguidores en LinkedIn">')
    assert n == 1
    m = c.metricas["linkedin"]
    assert m["estado"] == rp.OK and m["seguidores"] == 3400
    assert m["fuente"] == "https://www.linkedin.com/company/c1/" and len(m["fecha"]) == 10


def test_muro_de_login_queda_no_disponible_sin_estimar_nada():
    c = _comp(1, facebook="https://www.facebook.com/c1")
    rp.medir([c], bajar=lambda url, t=0: "<title>Facebook</title> Iniciá sesión")
    assert c.metricas["facebook"] == {"fuente": "https://www.facebook.com/c1",
                                      "fecha": c.metricas["facebook"]["fecha"],
                                      "estado": rp.NO_DISPONIBLE}


def test_tras_dos_bloqueos_seguidos_no_vuelve_a_tocar_esa_red():
    pedidos: list[str] = []

    def bajar(url, t=0):
        pedidos.append(url)
        raise OSError("HTTP Error 429: Too Many Requests")
    comps = [_comp(i, instagram=f"https://www.instagram.com/c{i}/") for i in range(6)]
    rp.medir(comps, bajar=bajar)
    assert len(pedidos) == rp.MAX_BLOQUEOS_SEGUIDOS
    assert all(c.metricas["instagram"]["estado"] == rp.NO_DISPONIBLE for c in comps)


def test_redes_distintas_del_mismo_competidor_no_se_pisan():
    c = _comp(1, linkedin="https://www.linkedin.com/company/c1/",
              tiktok="https://www.tiktok.com/@c1", facebook="https://www.facebook.com/c1",
              instagram="https://www.instagram.com/c1/")

    def bajar(url, t=0):
        if "tiktok" in url:
            return '"uniqueId":"c1","stats":{"followerCount":5,"heartCount":7,"videoCount":2}'
        return '<meta property="og:description" content="10 followers">'
    rp.medir([c], bajar=bajar)
    assert set(c.metricas) == {"linkedin", "tiktok", "facebook", "instagram"}


def test_apagado_no_hace_ningun_pedido(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_METRICAS_REDES", "0")
    c = _comp(1, tiktok="https://www.tiktok.com/@c1")

    def bajar(url, t=0):
        raise AssertionError("no debía salir a la red")
    assert rp.medir([c], bajar=bajar) == 0
    assert c.metricas == {}


def test_la_corrida_demo_no_sale_a_las_redes(corrida_kobra):
    # Regla 7: la demo es determinista y no depende de la red.
    assert all(not c.metricas for c in corrida_kobra.competidores)
