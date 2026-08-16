"""La huella de segmento y las búsquedas por redes.

Lo que estos tests protegen es una idea concreta: el filtro de rubro pasó de
ser **declarado** por el modelo (un `solapamiento` que él mismo se pone) a ser
**medido** contra la web real. Si la huella deja de discriminar, el filtro
vuelve a ser una promesa y nadie se entera.
"""
from __future__ import annotations

import pytest

from cliente_ia import busqueda_social, scoring, segmento
from cliente_ia.modelos import Campana, Empresa, Prospecto

WEB_COBRANZAS = """
MV Kobra AI - Software de gestión de cobranzas con inteligencia artificial.
Priorizá la cartera por valor esperado de recupero, no por días de atraso.
Nuestro motor de cobranzas predice qué deudores van a pagar y automatiza la
gestión de cobranzas por voz y WhatsApp. Gestión de cobranzas para fintech,
bancos y financieras. Recupero de cartera vencida con scoring de deudores.
"""


def _empresa(**kw) -> Empresa:
    base = {"dominio": "mvkobranzaia.com", "nombre": "MV Kobra AI",
            "resumen_sitio": WEB_COBRANZAS, "categoria": "Software de cobranzas",
            "sectores_objetivo": ["Fintech de préstamos", "Bancos"]}
    base.update(kw)
    return Empresa(**base)


# --- la huella --------------------------------------------------------------

def test_la_huella_es_determinista():
    """Regla 7 del proyecto. Si la huella cambia entre corridas iguales, el
    filtro deja pasar cosas distintas cada vez y nadie puede reproducir un bug."""
    e = _empresa()
    primera = segmento.huella_de(e)
    for _ in range(5):
        assert segmento.huella_de(e).terminos == primera.terminos


def test_la_huella_prefiere_los_bigramas_que_identifican_el_rubro():
    h = segmento.huella_de(_empresa())
    assert "gestion cobranzas" in h.terminos
    # Y pesa más que la palabra suelta, que no identifica nada.
    assert h.pesos["gestion cobranzas"] > h.pesos.get("gestion", 0)


def test_un_bigrama_no_cruza_el_punto_de_una_frase():
    """«…inteligencia artificial. Priorizá…» no puede dar «artificial prioriza»:
    son dos oraciones distintas y ese par no significa nada. Metido en una
    búsqueda, devolvía cero resultados."""
    h = segmento.huella_del_texto("Cobranzas con inteligencia artificial. "
                                  "Prioriza la cartera vencida.")
    assert not any(t == "artificial prioriza" for t in h.terminos)


@pytest.mark.parametrize("texto, minimo, maximo, que_es", [
    (WEB_COBRANZAS, 0.5, 1.0, "su propia web"),
    ("Sistema de cobranzas y recupero de cartera para financieras. "
     "Gestión de cobranzas con scoring de deudores.", 0.10, 0.9, "competidor directo"),
    ("CRM de ventas para equipos comerciales. Pipeline y oportunidades "
     "con inteligencia artificial.", 0.0, 0.06, "rubro vecino"),
    ("Inmobiliaria Delta. Venta y alquiler de casas y apartamentos en "
     "Montevideo. Tasación gratuita.", 0.0, 0.06, "otro rubro"),
])
def test_la_afinidad_separa_el_rubro_del_vecino(texto, minimo, maximo, que_es):
    a = segmento.afinidad(segmento.huella_de(_empresa()), texto)
    assert minimo <= a <= maximo, f"{que_es}: afinidad {a}"


def test_el_rubro_vecino_queda_por_debajo_del_umbral_de_descarte():
    """El umbral tiene que separar de verdad; si no, filtrar no sirve."""
    h = segmento.huella_de(_empresa())
    vecino = segmento.afinidad(h, "CRM de ventas para equipos comerciales con IA.")
    propio = segmento.afinidad(h, WEB_COBRANZAS)
    assert vecino < segmento.AFIN_AJENA <= segmento.AFIN_DUDOSA < propio


def test_el_html_se_mide_sin_el_javascript():
    """El JS de un sitio tiene cientos de palabras que no dicen nada del rubro
    y ahogaban la huella."""
    h = segmento.huella_de(_empresa())
    html = ("<html><head><script>var cobranzas='x';function gestion(){}</script>"
            "</head><body><h1>Inmobiliaria</h1><p>Venta de casas.</p></body></html>")
    assert segmento.afinidad_de_html(h, html) < segmento.AFIN_AJENA


# --- cuándo se puede verificar ----------------------------------------------

def test_sin_web_real_no_hay_huella_verificable():
    """Sin `resumen_sitio` la huella son dos etiquetas del catálogo: medir
    contra eso descarta a todos por igual. Y de paso el modo demo queda
    determinista, sin salir a la red."""
    assert segmento.huella_verificable(_empresa(resumen_sitio="")) is None
    # Con web real sí.
    assert segmento.huella_verificable(_empresa()) is not None


def test_una_portada_casi_vacia_tampoco_se_verifica():
    assert segmento.huella_verificable(
        _empresa(resumen_sitio="Bienvenidos.", categoria="", sectores_objetivo=[])) is None


def test_se_puede_apagar_la_verificacion_por_entorno(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_VERIFICAR_SEGMENTO", "0")
    assert segmento.huella_verificable(_empresa()) is None


# --- el scoring --------------------------------------------------------------

def _prospecto(**kw) -> Prospecto:
    base = {"id": "p1", "nombre": "Fin Delta", "dominio": "findelta.com.uy",
            "sector": "Fintech de préstamos", "pais": "UY", "empleados": 200,
            "senales": ["contrataron cobranzas"]}
    base.update(kw)
    return Prospecto(**base)


def test_la_afinidad_no_medida_no_premia_ni_castiga():
    """Media corrida demo no tiene sitio que visitar; castigarla sería inventar
    una diferencia que no existe."""
    assert scoring.ajuste_afinidad(-1.0) == scoring.AFINIDAD_NEUTRA


def test_un_prospecto_del_rubro_verificado_le_gana_a_uno_sin_verificar():
    e = _empresa()
    medido = scoring.puntuar_prospecto(_prospecto(id="a", afinidad=0.45), e)
    sin_medir = scoring.puntuar_prospecto(_prospecto(id="b"), e)
    ajeno = scoring.puntuar_prospecto(_prospecto(id="c", afinidad=0.0), e)
    assert medido.score > sin_medir.score > ajeno.score


def test_la_afinidad_no_da_vuelta_la_regla_de_olas():
    """Regla 1 del proyecto: el país del cliente va primero, siempre. Ni la
    señal nueva ni ninguna calibración puede colar a uno de afuera adelante."""
    e = _empresa()
    local_flojo = scoring.puntuar_prospecto(
        _prospecto(id="uy", pais="UY", afinidad=0.0, empleados=1, senales=[]), e)
    mundo_perfecto = scoring.puntuar_prospecto(
        _prospecto(id="us", pais="US", afinidad=1.0, empleados=200,
                   senales=["a", "b", "c"]), e)
    orden = scoring.ordenar_prospectos([mundo_perfecto, local_flojo])
    assert orden[0].id == "uy", "un prospecto de afuera se coló adelante del propio"


def test_los_pesos_del_icp_suman_uno():
    total = (scoring.PESO_SECTOR + scoring.PESO_AFINIDAD + scoring.PESO_TAMANO
             + scoring.PESO_SENALES + scoring.PESO_COMPETENCIA)
    assert abs(total - 1.0) < 1e-9


# --- búsquedas por redes -----------------------------------------------------

def _busquedas(**kw):
    kw.setdefault("sector", "Fintech de préstamos")
    kw.setdefault("pais", "UY")
    return busqueda_social.para_segmento(segmento.huella_de(_empresa()), **kw)


def test_la_busqueda_de_empresas_usa_el_sector_no_el_producto():
    """El error que este módulo casi comete: una empresa cuya web habla como
    nuestra web es un COMPETIDOR, no un cliente. Para encontrar compradores la
    palabra es la del sector."""
    empresas = [b for b in _busquedas() if b.red == "linkedin"
                and b.etiqueta == "empresas del rubro"][0]
    assert "Fintech de préstamos" in empresas.consulta
    assert "software cobranzas" not in empresas.consulta.lower()


def test_la_busqueda_de_intencion_si_usa_el_dolor():
    x = [b for b in _busquedas(dolor="la mora crece más rápido que el equipo")
         if b.red == "x"][0]
    assert "mora crece" in x.consulta


def test_los_decisores_se_buscan_por_cargo_y_en_su_idioma():
    gente_es = [b for b in _busquedas(idioma="es") if b.etiqueta == "decisores"][0]
    gente_pt = [b for b in _busquedas(idioma="pt", pais="BR")
                if b.etiqueta == "decisores"][0]
    assert "gerente" in gente_es.consulta and "jefe" in gente_es.consulta
    assert "diretor" in gente_pt.consulta and "Brasil" in gente_pt.consulta


def test_el_hashtag_va_sin_acentos_ni_mayusculas():
    """Instagram y TikTok no indexan «#Fintechdepréstamos»: ese enlace abría
    una etiqueta vacía."""
    ig = [b for b in _busquedas() if b.red == "instagram"][0]
    etiqueta = ig.consulta.lstrip("#")
    assert etiqueta == etiqueta.lower()
    assert etiqueta.isalnum(), etiqueta
    assert "é" not in etiqueta


def test_no_se_repite_el_mismo_termino_escrito_distinto():
    """«Fintech de préstamos» y «fintech prestamos» son lo mismo; las dos en
    una consulta con AND daban cero resultados."""
    for b in _busquedas():
        palabras = segmento.normalizar(b.consulta)
        assert len(palabras) == len(set(palabras)) or b.red == "buscador", b.consulta


def test_sin_sector_ni_huella_no_se_inventa_una_busqueda():
    """Un enlace al buscador con la caja vacía es peor que no ofrecer nada."""
    assert busqueda_social.para_segmento(segmento.Huella(), "", "") == []


def test_las_busquedas_por_campana_respetan_el_orden_de_olas():
    campanas = [
        Campana(id="m", nombre="x", sector="Banks", nivel="mundo", prioridad=3,
                paises=["US"], idioma="en"),
        Campana(id="l", nombre="x", sector="Fintech", nivel="local", prioridad=1,
                paises=["UY"], idioma="es"),
        Campana(id="r", nombre="x", sector="Bancos", nivel="regional", prioridad=2,
                paises=["BR"], idioma="pt"),
    ]
    bloques = busqueda_social.por_campana(segmento.huella_de(_empresa()), campanas)
    assert [b["nivel"] for b in bloques] == ["local", "regional", "mundo"]
    # Y cada bloque busca en el idioma de SU ola.
    por_nivel = {b["nivel"]: b for b in bloques}
    decisores_br = [x for x in por_nivel["regional"]["busquedas"]
                    if x["etiqueta"] == "decisores"][0]
    assert "diretor" in decisores_br["consulta"]


def test_todas_las_urls_son_https_y_de_la_red_que_dicen():
    dominios = {"linkedin": "linkedin.com", "instagram": "instagram.com",
                "x": "x.com", "tiktok": "tiktok.com", "buscador": "duckduckgo.com"}
    for b in _busquedas():
        assert b.url.startswith("https://"), b.url
        assert dominios[b.red] in b.url, b.url
