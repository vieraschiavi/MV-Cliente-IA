"""
Fase 6 completa: correo en texto plano, correo HTML con banner y video, y los
dos formatos de LinkedIn — todo en el idioma del país del receptor.
"""
from __future__ import annotations

import re
from html import unescape

import pytest

from cliente_ia import pipeline
from cliente_ia.enlaces import Enlaces
from cliente_ia.redaccion import TOPE_NOTA_LINKEDIN


@pytest.fixture(scope="module")
def corrida():
    return pipeline.ejecutar(
        "mvkobranzaia.com", modo="demo", limite_prospectos=60, nombre="MV Kobra AI",
        enlaces={"sitio": "mvkobranzaia.com", "video_en_landing": True})


# ---------------------------------------------------------------------------
# Enlaces por idioma
# ---------------------------------------------------------------------------
def test_la_web_va_en_el_idioma_del_receptor():
    e = Enlaces.desde_dominio("mvkobranzaia.com")
    assert e.landing("es").startswith("https://mvkobranzaia.com/?")
    assert e.landing("pt").startswith("https://mvkobranzaia.com/pt/?")
    assert e.landing("en").startswith("https://mvkobranzaia.com/en/?")


def test_el_banner_va_en_el_idioma_del_receptor():
    e = Enlaces.desde_dominio("mvkobranzaia.com")
    for idioma in ("es", "pt", "en"):
        assert e.banner(idioma).endswith(f"banner_{idioma}.png")


def test_sin_video_configurado_no_se_promete_ninguno():
    """Lo importante: no ofrecer un video que no existe."""
    e = Enlaces.desde_dominio("mvkobranzaia.com")          # sin videos, sin landing
    assert e.video("es") == ""
    assert e.hay_video("en") is False


def test_video_propio_por_idioma_pisa_al_de_la_landing():
    e = Enlaces.desde_dominio("mvkobranzaia.com", video_en_landing=True,
                              videos={"en": "https://youtu.be/abc"})
    assert e.video("en") == "https://youtu.be/abc"          # el propio manda
    assert e.video("pt").startswith("https://mvkobranzaia.com/pt/")   # el resto, la landing


def test_los_utm_distinguen_canal_e_idioma():
    e = Enlaces.desde_dominio("mvkobranzaia.com")
    correo = e.landing("pt", "latam-bancos", "p0001", "email")
    linkedin = e.landing("pt", "latam-bancos", "p0001", "linkedin")
    assert "utm_source=email" in correo and "utm_source=linkedin" in linkedin
    assert "utm_term=pt" in correo
    assert "utm_campaign=latam-bancos" in correo
    assert "utm_content=p0001" in correo


def test_sin_sitio_no_se_inventan_enlaces():
    e = Enlaces()
    assert e.landing("es") == "" and e.banner("es") == "" and e.video("es") == ""


# ---------------------------------------------------------------------------
# Correo HTML
# ---------------------------------------------------------------------------
def test_el_html_lleva_banner_boton_y_video_del_idioma(corrida):
    for idioma in ("es", "pt", "en"):
        e = next(x for x in corrida.emails if x.idioma == idioma)
        # Dentro de un atributo HTML el "&" de la query va como "&amp;" — es lo
        # correcto, así que para comparar la URL hay que deshacer el escapado.
        html = unescape(e.cuerpo_html)
        assert f"banner_{idioma}.png" in html, f"[{idioma}] falta el banner de su idioma"
        assert e.landing_url in html, f"[{idioma}] falta el enlace a la web"
        assert e.video_url in html, f"[{idioma}] falta el enlace al video"
        assert html.startswith("<!DOCTYPE html>")
        # Outlook no soporta flexbox ni hojas embebidas: tiene que ser tablas
        # con estilos en línea.
        assert "<table" in html and "<style" not in html


def test_el_html_no_repite_las_urls_crudas(corrida):
    """
    Regresión: los enlaces en texto plano se colaban en los párrafos del HTML,
    donde el banner y el botón ya los llevan, y el correo mostraba la URL
    entera dos veces.
    """
    for e in corrida.emails:
        visible = re.sub(r"<[^>]+>", " ", e.cuerpo_html)
        assert "http" not in visible, f"URL cruda visible en el HTML de {e.id}"


def test_el_texto_plano_si_lleva_las_urls(corrida):
    for e in corrida.emails:
        assert e.video_url in e.cuerpo
        assert e.landing_url in e.cuerpo
        # Y van antes de la firma, no al final de todo.
        assert e.cuerpo.rstrip().endswith("MV Kobra AI")


def test_el_html_escapa_el_nombre_del_prospecto():
    """El nombre de la empresa entra al HTML: no puede inyectar markup."""
    from cliente_ia.modelos import Decisor, Empresa, Prospecto
    from cliente_ia.redaccion import redactar

    p = Prospecto(id="p1", nombre='Acme <script>alert(1)</script> S.A.',
                  dominio="acme.com.uy", sector="Bancos", pais="UY", empleados=100)
    d = Decisor(id="d1", prospecto_id="p1", nombre="Ana Pérez", cargo="Gerente",
                empresa=p.nombre, pais="UY", email="a@acme.com.uy", idioma="es")
    email = redactar(d, p, Empresa(dominio="x.com", nombre="X"), None,
                     enlaces=Enlaces.desde_dominio("x.com"))
    assert "<script>" not in email.cuerpo_html
    assert "&lt;script&gt;" in email.cuerpo_html


# ---------------------------------------------------------------------------
# LinkedIn
# ---------------------------------------------------------------------------
def test_hay_mensaje_y_nota_de_linkedin_para_cada_correo(corrida):
    for e in corrida.emails:
        assert e.linkedin.strip()
        assert e.linkedin_nota.strip()


def test_la_nota_de_invitacion_entra_en_el_limite(corrida):
    """LinkedIn corta la nota de invitación en 300 caracteres."""
    for e in corrida.emails:
        assert len(e.linkedin_nota) <= TOPE_NOTA_LINKEDIN, e.linkedin_nota


def test_la_nota_no_queda_cortada_a_la_mitad(corrida):
    """
    Regresión: recortar por cantidad de palabras dejaba frases colgadas como
    «prioriza a carteira por valor esperado de.» en portugués.
    """
    colgadas = (" de.", " da.", " do.", " y.", " e.", " of.", " the.", " por.", " com.")
    for e in corrida.emails:
        assert not e.linkedin_nota.endswith("…"), e.linkedin_nota
        for c in colgadas:
            assert c not in e.linkedin_nota, f"frase colgada en {e.id}: {e.linkedin_nota}"


def test_linkedin_usa_su_propio_utm(corrida):
    for e in corrida.emails:
        assert "utm_source=linkedin" in e.linkedin
        assert "utm_source=email" not in e.linkedin


def test_el_mensaje_de_linkedin_esta_en_el_idioma_del_receptor(corrida):
    marcas = {
        "es": "¿Charlamos 15 minutos",
        "pt": "Podemos conversar 15 minutos",
        "en": "Worth 15 minutes",
    }
    vistos = set()
    for e in corrida.emails:
        vistos.add(e.idioma)
        assert marcas[e.idioma] in e.linkedin, f"[{e.idioma}] {e.linkedin[-80:]}"
    assert vistos == set(marcas)


def test_el_video_se_ofrece_en_el_idioma_del_receptor(corrida):
    rutas = {"es": "/?", "pt": "/pt/", "en": "/en/"}
    nombres = {"es": "español", "pt": "português", "en": "English"}
    for e in corrida.emails:
        assert rutas[e.idioma] in e.video_url, f"[{e.idioma}] {e.video_url}"
        assert nombres[e.idioma] in e.cuerpo


def test_sin_video_los_mensajes_no_lo_mencionan():
    c = pipeline.ejecutar("mvkobranzaia.com", modo="demo", limite_prospectos=20,
                          nombre="MV Kobra AI",
                          enlaces={"sitio": "mvkobranzaia.com"})   # video_en_landing=False
    assert c.resumen()["con_video"] == 0
    for e in c.emails:
        assert e.video_url == ""
        assert "90 segundos" not in e.cuerpo and "90-second" not in e.cuerpo
        assert "Video de 90" not in e.cuerpo_html
        # …pero el enlace a la web y el banner siguen estando.
        assert e.landing_url and e.banner_url
        # El mensaje de LinkedIn lleva la web con SU propio utm_source, no el
        # del correo.
        assert e.linkedin.strip()
        assert e.landing_url.split("?")[0] in e.linkedin
        assert "utm_source=linkedin" in e.linkedin


def test_la_configuracion_de_enlaces_queda_guardada_en_la_corrida(corrida):
    assert corrida.enlaces["sitio"] == "https://mvkobranzaia.com"
    assert corrida.enlaces["video_en_landing"] is True


def test_el_export_lleva_linkedin_y_los_enlaces(corrida):
    import csv
    import io

    from cliente_ia import exportar
    filas = list(csv.DictReader(io.StringIO(exportar.a_csv(corrida))))
    assert {"linkedin", "linkedin_nota", "video_url", "landing_url"} <= set(filas[0])
    con_mensaje = [f for f in filas if f["asunto"]]
    assert con_mensaje and all(f["linkedin"] and f["video_url"] for f in con_mensaje)
