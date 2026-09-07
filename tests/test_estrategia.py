"""Estrategia y contenido (réplica del núcleo de okara.ai).

Los documentos salen de lo que la corrida MIDIÓ: sin sitio real se dice que
la ficha es del catálogo; con sitio real, los precios, los llamados a la
acción y la voz se leen del texto y no se inventan.
"""
from __future__ import annotations

import pytest

from cliente_ia import busqueda_social, estrategia, geo, modelos, pipeline, segmento

# Un fragmento como el que deja `ProveedorWeb` de un sitio rioplatense con
# tabla de planes: trato de vos, cifras, precios en dólares y en pesos.
_SITIO = (
    "MV Kobra AI. Tu cobranza gestionando 24/7, sin sumar gestores. "
    "Pedir una demo Planes desde USD 99 24/7 gestiona sin descanso 50 × llamadas "
    "en paralelo vs. un gestor. Probá gratis. Básico Para empezar chico. "
    "US$99 /mes 300 gestiones incluidas ≈ $U 3.960/mes · se cobra en pesos. "
    "Pro · Todo incluido Abrí y usá. US$349 /mes + uso · 1.000 gestiones incluidas. "
    "Enterprise Bancos, grandes estudios. A medida desde US$1.500/mes. "
    "Somos el mejor equipo. Conocé cómo funciona."
)


@pytest.fixture(scope="module")
def corrida():
    return pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                             limite_prospectos=30, nombre="MV Kobra AI")


def test_la_corrida_trae_los_cuatro_documentos_y_el_markdown(corrida):
    e = corrida.estrategia
    assert set(e) == {"producto", "competencia", "voz", "contenido", "markdown"}
    assert e["producto"]["nombre"] == "MV Kobra AI"
    assert e["markdown"].startswith("# MV Kobra AI · mvkobranzaia.com")
    assert "## Plan de contenido" in e["markdown"]


def test_sin_sitio_real_la_ficha_dice_que_es_del_catalogo(corrida):
    """Regla 5 del proyecto, versión estrategia: lo no medido se dice."""
    e = corrida.estrategia
    assert e["producto"]["medido"] is False
    assert e["voz"]["medido"] is False
    assert e["producto"]["precios"] == []
    assert e["voz"]["registro"] == "neutro"
    assert any("catálogo" in r for r in e["voz"]["reglas"])


def test_el_plan_de_contenido_reparte_las_olas_con_el_pais_propio_primero(corrida):
    """Con doce sectores locales, tomar las seis primeras campañas dejaba el
    plan sin un solo post en inglés. Las tres olas están, y la local manda."""
    niveles = [c["nivel"] for c in corrida.estrategia["contenido"]]
    assert len(niveles) == estrategia.TOPE_CAMPANAS
    assert niveles[0] == geo.NIVEL_LOCAL
    assert niveles.count(geo.NIVEL_LOCAL) == 3
    assert geo.NIVEL_REGIONAL in niveles and geo.NIVEL_MUNDO in niveles
    assert niveles == sorted(niveles, key=geo.NIVELES.index)


def test_cada_post_va_en_el_idioma_de_su_campana(corrida):
    """Regla 3: el idioma del receptor manda. La ola mundo escribe en inglés
    con la propuesta en inglés, no con la española traducida a medias."""
    for c in corrida.estrategia["contenido"]:
        if c["idioma"] == "en":
            assert "How does your team handle it today?" in c["linkedin"]
            assert corrida.empresa.texto("en", "propuesta") in c["linkedin"]
            assert "¿Cómo" not in c["linkedin"]
        if c["idioma"] == "es":
            assert "¿Cómo lo resuelven hoy en tu equipo?" in c["linkedin"]


def test_los_posts_de_x_entran_en_280_y_llevan_el_sitio(corrida):
    for c in corrida.estrategia["contenido"]:
        assert len(c["x"]) <= estrategia.LARGO_X
        assert c["x"].endswith("mvkobranzaia.com")


def test_reddit_es_una_consulta_con_el_dolor_ordenada_por_reciente(corrida):
    """Regla 12: consultas, no bots. Y la queja fresca es la que compra."""
    for c in corrida.estrategia["contenido"]:
        assert c["reddit"]["red"] == "reddit"
        assert c["reddit"]["url"].startswith("https://www.reddit.com/search/?q=")
        assert c["reddit"]["url"].endswith("&sort=new")
        assert c["reddit"]["consulta"]


def test_la_busqueda_por_redes_tambien_trae_reddit():
    huella = segmento.huella_de(modelos.Empresa(
        dominio="x.com", categoria="Software de cobranzas",
        resumen_sitio="gestión de cobranzas y mora temprana " * 30))
    redes = [b.red for b in busqueda_social.para_segmento(
        huella, "Bancos", "UY", "es", "la mora crece más rápido que el equipo")]
    assert "reddit" in redes
    reddit = [b for b in busqueda_social.para_segmento(
        huella, "Bancos", "UY", "es", "la mora crece más rápido que el equipo")
        if b.red == "reddit"][0]
    assert "mora crece" in reddit.consulta


def test_la_estrategia_sobrevive_el_guardado_y_una_corrida_vieja(corrida):
    de_vuelta = modelos.desde_dict(corrida.a_dict())
    assert de_vuelta.estrategia == corrida.estrategia
    vieja = dict(corrida.a_dict())
    del vieja["estrategia"]
    assert modelos.desde_dict(vieja).estrategia == {}


def test_es_determinista():
    a = pipeline.ejecutar("mvkobranzaia.com", modo="demo", limite_prospectos=20).estrategia
    b = pipeline.ejecutar("mvkobranzaia.com", modo="demo", limite_prospectos=20).estrategia
    assert a == b


# --- con sitio real (texto fijo, sin red) ------------------------------------

def _con_sitio(corrida, idioma_ui="es"):
    c = modelos.desde_dict(corrida.a_dict())
    c.idioma_ui = idioma_ui
    c.empresa.resumen_sitio = _SITIO[:400]
    c.empresa.texto_sitio = _SITIO
    return estrategia.armar(c)


def test_los_precios_se_leen_del_sitio_con_su_periodo_y_sin_repetir(corrida):
    """«USD 99» del hero y «US$99 /mes» de la tabla son el mismo plan."""
    precios = _con_sitio(corrida)["producto"]["precios"]
    montos = {estrategia._clave_precio(p["monto"]): p["periodo"] for p in precios}
    assert montos["USD99"] == "mes"
    assert montos["USD349"] == "mes"
    assert montos["USD1500"] == "mes"
    assert list(montos).count("USD99") == 1
    # La moneda dura va primero: es la del plan, no la del ejemplo.
    assert estrategia._clave_precio(precios[0]["monto"]).startswith("USD")


def test_la_voz_se_mide_del_sitio(corrida):
    voz = _con_sitio(corrida)["voz"]
    assert voz["medido"] is True
    assert voz["registro"] == "voseo"
    assert any("24/7" in p for p in voz["pruebas"])
    assert "el mejor" in voz["superlativos"]
    assert any("de vos" in r for r in voz["reglas"])
    assert any("el mejor" in r for r in voz["reglas"])


def test_los_llamados_a_la_accion_cortan_donde_arranca_el_bloque_siguiente(corrida):
    """El texto plano pega «Pedir una demo» con «Planes desde…»: el CTA es
    la frase corta, no el párrafo."""
    ctas = _con_sitio(corrida)["producto"]["ctas"]
    assert "Pedir una demo" in ctas
    assert "Probá gratis" in ctas
    assert not any("Planes" in c for c in ctas)


def test_las_pruebas_no_arrastran_la_portada_entera(corrida):
    for p in _con_sitio(corrida)["voz"]["pruebas"]:
        assert len(p) <= 140, p


def test_el_markdown_sale_en_el_idioma_de_la_interfaz(corrida):
    en = _con_sitio(corrida, "en")
    assert "## Product brief" in en["markdown"]
    assert "Address the reader as «vos»" in en["markdown"]
    pt = _con_sitio(corrida, "pt")
    assert "## Ficha do produto" in pt["markdown"]


@pytest.mark.parametrize("texto, idioma, esperado", [
    ("Solicitá tu demo y conocé cómo funciona. Tenés 14 días.", "es", "voseo"),
    ("Solicita tu demo, tú decides. Tienes 14 días de prueba.", "es", "tuteo"),
    ("Solicite una demo. Su empresa decide; usted tiene 14 días.", "es", "usted"),
    ("Plataforma de cobranzas para bancos y financieras.", "es", "neutro"),
    ("Você agenda a demonstração e conhece a plataforma.", "pt", "voce"),
    ("Book your demo today and see how it works.", "en", "directo"),
])
def test_el_trato_al_lector_se_reconoce_en_los_tres_idiomas(texto, idioma, esperado):
    assert estrategia.registro(texto, idioma) == esperado


def test_la_estrategia_no_puede_tumbar_la_corrida(monkeypatch):
    """Si algo falla acá la corrida sigue lista y el aviso dice qué faltó:
    los seis pasos ya están hechos y no se tiran por un documento."""
    def rota(*_a, **_k):
        raise RuntimeError("se rompió a propósito")
    monkeypatch.setattr(estrategia, "armar", rota)
    c = pipeline.ejecutar("mvkobranzaia.com", modo="demo", limite_prospectos=10)
    assert c.estado == "listo"
    assert c.estrategia == {}
    assert any(a.tipo == modelos.AVISO_FALLO and "estrategia" in str(a) for a in c.avisos)
